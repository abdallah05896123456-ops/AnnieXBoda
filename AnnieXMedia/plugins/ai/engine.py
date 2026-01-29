# plugins/ai/engine.py
# Unified Ollama AI Engine — Ultra Fast / Streaming / Stable
# Authored By Certified Coders © 2026

import aiohttp
import asyncio
import json
import os
import time
import re
import logging
import traceback
from typing import Optional, Callable, Any, Dict

# =========================
# Environment Configuration
# =========================
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:32b")

OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "180"))
FIRST_CHUNK_TIMEOUT = float(os.getenv("OLLAMA_FIRST_CHUNK_TIMEOUT", "2.0"))
CHUNK_SIZE = int(os.getenv("OLLAMA_CHUNK_SIZE", "2048"))

AI_CONCURRENCY = int(os.getenv("AI_CONCURRENCY", "6"))
MAX_HISTORY = int(os.getenv("AI_MAX_HISTORY", "8"))
CACHE_TTL = int(os.getenv("AI_CACHE_TTL", "10"))

OLLAMA_TEMP = float(os.getenv("OLLAMA_TEMP", "0.18"))
OLLAMA_TOP_P = float(os.getenv("OLLAMA_TOP_P", "0.9"))
OLLAMA_MAX_TOKENS = int(os.getenv("OLLAMA_MAX_TOKENS", "1024"))

DEFAULT_SYSTEM_PROMPT = os.getenv(
    "OLLAMA_SYSTEM_PROMPT",
    "أجب بالعربية الفصحى فقط، بدقة وذكاء ومن دون إطالة غير ضرورية."
)

# =========================
# Logging
# =========================
logger = logging.getLogger("AnnieX_AI_Engine")
logging.basicConfig(level=logging.INFO)

# =========================
# Runtime State
# =========================
REQUEST_SEMAPHORE = asyncio.Semaphore(AI_CONCURRENCY)
USER_HISTORY: Dict[int, list] = {}

# =========================
# Arabic Detection
# =========================
ARABIC_RE = re.compile(r"[\u0600-\u06FF]")

def looks_arabic(text: str, min_chars: int = 2) -> bool:
    return bool(text and len(ARABIC_RE.findall(text)) >= min_chars)

# =========================
# TTL Cache
# =========================
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
# Text Extractor (Robust)
# =========================
def extract_text(obj: Any) -> str:
    try:
        if obj is None:
            return ""
        if isinstance(obj, str):
            return obj.strip()
        if isinstance(obj, dict):
            if "message" in obj and isinstance(obj["message"], dict):
                c = obj["message"].get("content")
                if isinstance(c, str):
                    return c.strip()
            for k in ("response", "text", "output", "result"):
                if k in obj and isinstance(obj[k], str):
                    return obj[k].strip()
            if "choices" in obj and isinstance(obj["choices"], list):
                for ch in obj["choices"]:
                    if isinstance(ch, dict):
                        t = ch.get("text")
                        if isinstance(t, str):
                            return t.strip()
        return ""
    except Exception:
        return ""

# =========================
# Core Engine (Streaming)
# =========================
async def ask_ollama_stream(
    user_id: int,
    prompt: str,
    on_update: Optional[Callable[[str], Any]] = None,
    system_prompt: Optional[str] = None,
    stream: bool = True,
    timeout: Optional[int] = None,
) -> str:
    """
    الدالة الوحيدة المعتمدة من handlers.py
    """

    if not prompt:
        return "❌ لا يوجد نص للإجابة عليه."

    timeout = timeout or OLLAMA_TIMEOUT
    system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT

    cache_key = f"{user_id}:{prompt}"
    cached = CACHE.get(cache_key)
    if cached:
        return cached

    # ===== Build Messages =====
    messages = [{"role": "system", "content": system_prompt}]

    history = USER_HISTORY.get(user_id, [])[-MAX_HISTORY:]
    for h in history:
        messages.append({"role": "user", "content": h["u"]})
        messages.append({"role": "assistant", "content": h["a"]})

    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": stream,
        "options": {
            "temperature": OLLAMA_TEMP,
            "top_p": OLLAMA_TOP_P,
            "num_predict": OLLAMA_MAX_TOKENS,
        },
    }

    endpoints = [
        f"{OLLAMA_HOST}/api/chat",
        f"{OLLAMA_HOST}/api/generate",
    ]

    async with REQUEST_SEMAPHORE:
        for endpoint in endpoints:
            try:
                client_timeout = aiohttp.ClientTimeout(total=timeout)
                async with aiohttp.ClientSession(timeout=client_timeout) as session:
                    async with session.post(endpoint, json=payload) as resp:
                        if resp.status != 200:
                            continue

                        final_text = ""
                        started = False
                        start_time = time.time()
                        buffer = ""

                        async for chunk in resp.content.iter_chunked(CHUNK_SIZE):
                            decoded = chunk.decode(errors="ignore")
                            buffer += decoded

                            lines = buffer.splitlines()
                            buffer = lines.pop() if not buffer.endswith("\n") else ""

                            for line in lines:
                                if not line.strip():
                                    continue
                                if line.startswith("data:"):
                                    line = line[5:].strip()

                                try:
                                    parsed = json.loads(line)
                                    part = extract_text(parsed)
                                except Exception:
                                    part = line

                                if not part:
                                    continue

                                if part.startswith(final_text):
                                    part = part[len(final_text):]

                                final_text += part
                                started = True

                                if on_update:
                                    try:
                                        r = on_update(final_text)
                                        if asyncio.iscoroutine(r):
                                            await r
                                    except Exception:
                                        pass

                            if not started and time.time() - start_time > FIRST_CHUNK_TIMEOUT:
                                break

                        final_text = final_text.strip()

                        # Arabic enforcement retry (non-stream)
                        if not looks_arabic(final_text):
                            retry_payload = {
                                "model": OLLAMA_MODEL,
                                "messages": [
                                    {
                                        "role": "system",
                                        "content": system_prompt + "\nأجب بالعربية فقط."
                                    },
                                    {"role": "user", "content": prompt},
                                ],
                                "stream": False,
                            }
                            async with session.post(endpoint, json=retry_payload) as r2:
                                data = await r2.json(content_type=None)
                                final_text = extract_text(data)

                        final_text = final_text or "لم يتم توليد رد صالح."

                        CACHE.set(cache_key, final_text)
                        USER_HISTORY.setdefault(user_id, []).append(
                            {"u": prompt, "a": final_text}
                        )
                        USER_HISTORY[user_id] = USER_HISTORY[user_id][-MAX_HISTORY:]

                        return final_text

            except asyncio.TimeoutError:
                continue
            except Exception:
                logger.error(traceback.format_exc())
                continue

    return "❌ حصل خطأ داخلي في خدمة الذكاء الاصطناعي."
