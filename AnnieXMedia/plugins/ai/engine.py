# plugins/ai/engine.py
# Unified Ollama AI Engine — Ultra Fast / Streaming / Stable (Improved)
# Authored By Certified Coders © 2026 (patched)
# Notes:
# - Robust URL handling (accepts host with or without http://)
# - Uses messages for /api/chat and prompt for /api/generate where appropriate
# - Strong streaming parser (handles JSON-per-line, SSE "data:" lines, partial chunks)
# - Automatic non-stream fallback and strict Arabic retry
# - Concurrency limiter, simple TTL cache, and history storage
# - Safe under load and tolerant to Ollama variants

import aiohttp
import asyncio
import json
import os
import time
import logging
import traceback
from typing import Optional, Callable, Any, Dict

# =========================
# Configuration
# =========================

_RAW_HOST = os.getenv("OLLAMA_HOST", "127.0.0.1:11434").rstrip("/")
# Normalize to base URL with scheme
if _RAW_HOST.startswith("http://") or _RAW_HOST.startswith("https://"):
    OLLAMA_BASE_URL = _RAW_HOST.rstrip("/")
else:
    OLLAMA_BASE_URL = f"http://{_RAW_HOST}"

OLLAMA_MODEL_DEFAULT = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")

OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "180"))
FIRST_CHUNK_TIMEOUT = float(os.getenv("FIRST_CHUNK_TIMEOUT", "3.0"))
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "2048"))

AI_CONCURRENCY = int(os.getenv("AI_CONCURRENCY", "6"))
MAX_HISTORY = int(os.getenv("AI_MAX_HISTORY", "8"))
CACHE_TTL = int(os.getenv("CACHE_TTL", "10"))

OLLAMA_TEMP = float(os.getenv("OLLAMA_TEMP", "0.18"))
OLLAMA_TOP_P = float(os.getenv("OLLAMA_TOP_P", "0.9"))
OLLAMA_MAX_TOKENS = int(os.getenv("OLLAMA_MAX_TOKENS", "1024"))

DEFAULT_SYSTEM_PROMPT = os.getenv(
    "OLLAMA_SYSTEM_PROMPT",
    "أجب بالعربية فقط وبشكل واضح ومباشر، من دون حشو أو خلط لغات."
)

# Endpoints to try (order matters)
DEFAULT_ENDPOINTS = [
    f"{OLLAMA_BASE_URL}/api/chat",
    f"{OLLAMA_BASE_URL}/api/generate",
]

# =========================
# Logging & State
# =========================

logger = logging.getLogger("AnnieX_AI_Engine")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

REQUEST_SEMAPHORE = asyncio.Semaphore(AI_CONCURRENCY)
USER_HISTORY: Dict[int, list] = {}

# =========================
# Utilities: Arabic check, cache
# =========================

import re
ARABIC_RE = re.compile(r"[\u0600-\u06FF]")

def looks_arabic(text: str, min_chars: int = 2) -> bool:
    return bool(text and len(ARABIC_RE.findall(text)) >= min_chars)

class SimpleCache:
    def __init__(self):
        self._data: Dict[str, tuple] = {}

    def get(self, key: str):
        item = self._data.get(key)
        if not item:
            return None
        exp, val = item
        if time.time() > exp:
            self._data.pop(key, None)
            return None
        return val

    def set(self, key: str, value: str, ttl: int = CACHE_TTL):
        self._data[key] = (time.time() + ttl, value)

CACHE = SimpleCache()

# =========================
# JSON/text extraction helper (robust)
# =========================

def extract_text_from_obj(obj: Any) -> str:
    """
    Try multiple common shapes returned by Ollama-like services.
    """
    try:
        if obj is None:
            return ""
        if isinstance(obj, str):
            return obj.strip()
        if isinstance(obj, dict):
            # common: {"message": {"role":"assistant","content":"..."}}
            msg = obj.get("message")
            if isinstance(msg, dict):
                c = msg.get("content")
                if isinstance(c, str) and c.strip():
                    return c.strip()
                # sometimes content is list of chunks
                if isinstance(c, list):
                    parts = []
                    for p in c:
                        if isinstance(p, str) and p.strip():
                            parts.append(p.strip())
                        elif isinstance(p, dict):
                            t = p.get("text") or p.get("content")
                            if isinstance(t, str) and t.strip():
                                parts.append(t.strip())
                    return " ".join(parts).strip()
            # fallback keys
            for k in ("response", "output", "text", "result"):
                if k in obj and isinstance(obj[k], str) and obj[k].strip():
                    return obj[k].strip()
            # choices style
            choices = obj.get("choices")
            if isinstance(choices, list) and choices:
                first = choices[0]
                if isinstance(first, dict):
                    t = first.get("text")
                    if isinstance(t, str) and t.strip():
                        return t.strip()
                    nested = first.get("message") or first.get("delta") or first.get("output")
                    if isinstance(nested, dict):
                        c = nested.get("content") or nested.get("text")
                        if isinstance(c, str) and c.strip():
                            return c.strip()
            # last resort: find first string anywhere
            def find_any(o):
                if isinstance(o, str) and o.strip():
                    return o.strip()
                if isinstance(o, dict):
                    for v in o.values():
                        s = find_any(v)
                        if s:
                            return s
                if isinstance(o, list):
                    for it in o:
                        s = find_any(it)
                        if s:
                            return s
                return None
            found = find_any(obj)
            return found or ""
    except Exception:
        logger.debug("extract_text_from_obj error", exc_info=True)
    return ""

# =========================
# Core: ask_ollama_stream
# =========================

async def ask_ollama_stream(
    user_id: int,
    prompt: str,
    on_update: Optional[Callable[[str], Any]] = None,
    system_prompt: Optional[str] = None,
    model: Optional[str] = None,
    endpoints: Optional[list] = None,
    stream: bool = True,
    timeout: Optional[int] = None,
) -> str:
    """
    Main interface for handlers:
        reply = await ask_ollama_stream(user_id, prompt, on_update=callback)
    Behavior:
    - Tries a list of endpoints (chat -> generate)
    - Parses streaming JSON-per-line and SSE 'data:' lines
    - Falls back to non-stream attempt if streaming returns nothing
    - Performs a strict Arabic retry if output doesn't look Arabic
    """
    if not prompt:
        return "لا يوجد نص للإجابة عليه."

    timeout = timeout or OLLAMA_TIMEOUT
    system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT
    model = model or OLLAMA_MODEL_DEFAULT
    endpoints = endpoints or DEFAULT_ENDPOINTS

    cache_key = f"{user_id}:{model}:{prompt}"
    cached = CACHE.get(cache_key)
    if cached:
        return cached

    # Build messages
    messages = [{"role": "system", "content": system_prompt}]
    history = USER_HISTORY.get(user_id, [])[-MAX_HISTORY:]
    for h in history:
        u = h.get("u"); a = h.get("a")
        if u: messages.append({"role": "user", "content": u})
        if a: messages.append({"role": "assistant", "content": a})
    messages.append({"role": "user", "content": prompt})

    # payload variants
    payload_messages = {
        "model": model,
        "messages": messages,
        "stream": stream,
        "options": {
            "temperature": OLLAMA_TEMP,
            "top_p": OLLAMA_TOP_P,
            "num_predict": OLLAMA_MAX_TOKENS,
        }
    }
    payload_prompt = {
        "model": model,
        "prompt": (system_prompt + "\n\n" if system_prompt else "") + prompt,
        "stream": stream,
        "options": payload_messages["options"],
    }

    async with REQUEST_SEMAPHORE:
        # Try endpoints in order with backoff between them
        for endpoint in endpoints:
            try:
                client_timeout = aiohttp.ClientTimeout(total=timeout)
                async with aiohttp.ClientSession(timeout=client_timeout) as session:
                    # pick payload type based on endpoint pattern
                    use_messages = endpoint.endswith("/api/chat") or endpoint.endswith("/api/create")
                    body = payload_messages if use_messages else payload_prompt

                    # POST
                    async with session.post(endpoint, json=body) as resp:
                        status = resp.status
                        if status >= 400:
                            # log and continue to next endpoint
                            try:
                                txt = await resp.text()
                            except Exception:
                                txt = f"HTTP {status}"
                            logger.warning("Ollama %s returned %s: %s", endpoint, status, txt[:200])
                            continue

                        # streaming handling
                        final_text = ""
                        buffer = ""
                        started = False
                        start_time = time.time()

                        if stream:
                            # some endpoints send newline-separated JSON objects or SSE-like "data: {...}"
                            async for chunk in resp.content.iter_chunked(CHUNK_SIZE):
                                if not chunk:
                                    continue
                                try:
                                    piece = chunk.decode("utf-8", errors="ignore")
                                except Exception:
                                    piece = str(chunk)
                                buffer += piece

                                # process complete lines
                                while True:
                                    if "\n" not in buffer:
                                        break
                                    line, buffer = buffer.split("\n", 1)
                                    line = line.strip()
                                    if not line:
                                        continue
                                    # SSE style
                                    if line.startswith("data:"):
                                        line = line[len("data:"):].strip()
                                    if line in ("[DONE]", ""):
                                        continue
                                    parsed = None
                                    chunk_text = ""
                                    # try json
                                    try:
                                        parsed = json.loads(line)
                                        chunk_text = extract_text_from_obj(parsed)
                                    except Exception:
                                        # not JSON — treat as raw text
                                        chunk_text = line

                                    if not chunk_text:
                                        continue

                                    # append smartly avoiding obvious duplication
                                    if final_text and chunk_text.startswith(final_text):
                                        add = chunk_text[len(final_text):]
                                    else:
                                        add = chunk_text if not final_text else (" " + chunk_text)

                                    if add:
                                        final_text = (final_text + add).strip()
                                        started = True
                                        if on_update:
                                            try:
                                                res = on_update(final_text)
                                                if asyncio.iscoroutine(res):
                                                    await res
                                            except Exception:
                                                logger.debug("on_update callback error", exc_info=True)

                                # timeout for first chunk to avoid hanging too long
                                if not started and (time.time() - start_time) > FIRST_CHUNK_TIMEOUT:
                                    # break out to fallback (non-stream) attempt for this endpoint
                                    break

                            # after stream loop, if we got something return it
                            final_text = final_text.strip()
                            if final_text:
                                # strict Arabic enforcement: if result is not Arabic, try non-stream strict retry
                                if not looks_arabic(final_text):
                                    try:
                                        strict_body = payload_messages if use_messages else payload_prompt
                                        # modify strict system if using messages
                                        if use_messages:
                                            strict_body = dict(strict_body)
                                            strict_msgs = list(strict_body["messages"])
                                            strict_msgs[0] = {"role": "system", "content": (system_prompt + " أجب بالعربية فقط.")}
                                            strict_body["messages"] = strict_msgs
                                        else:
                                            strict_body = dict(strict_body)
                                            strict_body["prompt"] = "أجب بالعربية فقط.\n\n" + strict_body.get("prompt", "")
                                        async with session.post(endpoint, json=strict_body) as r2:
                                            if r2.status == 200:
                                                try:
                                                    d2 = await r2.json(content_type=None)
                                                    strict_text = extract_text_from_obj(d2)
                                                    if strict_text and looks_arabic(strict_text):
                                                        final_text = strict_text.strip()
                                                except Exception:
                                                    txt2 = await r2.text()
                                                    if txt2 and looks_arabic(txt2):
                                                        final_text = txt2.strip()
                                    except Exception:
                                        logger.debug("strict retry failed", exc_info=True)

                                final_text = final_text or "لم يتم توليد رد صالح."
                                CACHE.set(cache_key, final_text)
                                USER_HISTORY.setdefault(user_id, []).append({"u": prompt, "a": final_text})
                                USER_HISTORY[user_id] = USER_HISTORY[user_id][-MAX_HISTORY:]
                                return final_text

                            # if stream produced nothing, try non-stream below for same endpoint
                            # fallthrough to non-stream attempt
                        # non-stream path (or fallback)
                        try:
                            # ensure non-stream body
                            non_stream_body = dict(payload_messages) if use_messages else dict(payload_prompt)
                            non_stream_body["stream"] = False
                            async with session.post(endpoint, json=non_stream_body) as resp2:
                                if resp2.status >= 400:
                                    txt = await resp2.text()
                                    logger.warning("Ollama non-stream %s returned %s: %s", endpoint, resp2.status, txt[:200])
                                    continue
                                # parse JSON or raw text
                                try:
                                    data = await resp2.json(content_type=None)
                                    out = extract_text_from_obj(data)
                                except Exception:
                                    out = (await resp2.text()).strip()
                                out = (out or "").strip()
                                if out:
                                    # strict Arabic enforcement
                                    if not looks_arabic(out):
                                        # try strict system once
                                        try:
                                            if use_messages:
                                                sbody = dict(non_stream_body)
                                                msgs = list(sbody["messages"])
                                                msgs[0] = {"role": "system", "content": system_prompt + " أجب بالعربية فقط."}
                                                sbody["messages"] = msgs
                                                async with session.post(endpoint, json=sbody) as r3:
                                                    d3 = await r3.json(content_type=None)
                                                    out2 = extract_text_from_obj(d3)
                                                    if out2 and looks_arabic(out2):
                                                        out = out2
                                            else:
                                                sbody = dict(non_stream_body)
                                                sbody["prompt"] = "أجب بالعربية فقط.\n\n" + sbody.get("prompt", "")
                                                async with session.post(endpoint, json=sbody) as r3:
                                                    d3 = await r3.json(content_type=None)
                                                    out2 = extract_text_from_obj(d3)
                                                    if out2 and looks_arabic(out2):
                                                        out = out2
                                        except Exception:
                                            logger.debug("strict retry (non-stream) failed", exc_info=True)
                                    out = out or "لم يتم توليد رد صالح."
                                    CACHE.set(cache_key, out)
                                    USER_HISTORY.setdefault(user_id, []).append({"u": prompt, "a": out})
                                    USER_HISTORY[user_id] = USER_HISTORY[user_id][-MAX_HISTORY:]
                                    return out
                                else:
                                    # nothing; try next endpoint
                                    continue
                        except Exception:
                            # fallback failed for this endpoint
                            logger.debug("non-stream attempt failed for endpoint %s", endpoint, exc_info=True)
                            continue

            except asyncio.TimeoutError:
                logger.warning("Timeout when contacting %s", endpoint)
                continue
            except aiohttp.ClientConnectorError as e:
                logger.warning("Connection error to %s: %s", endpoint, e)
                continue
            except Exception:
                logger.error("Unexpected error while contacting Ollama endpoint", exc_info=True)
                continue

    # all endpoints exhausted
    return "حصل خطأ في خدمة الذكاء الاصطناعي، حاول لاحقاً."
