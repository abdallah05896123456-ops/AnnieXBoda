# plugins/ai/client.py
# Authored By Certified Coders © 2026
# AI Engine Core – Ollama Streaming (High Performance)

import asyncio
import aiohttp
import json
import os
import time
import re
import logging
import traceback
from typing import Any, Dict, Optional, Callable

# =====================
# Environment Settings
# =====================
OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", "http://127.0.0.1:11434/api/chat")
DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:32b")

DEFAULT_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "30"))
FIRST_CHUNK_TIMEOUT = float(os.getenv("OLLAMA_FIRST_CHUNK_TIMEOUT", "2.5"))
CHUNK_SIZE = int(os.getenv("OLLAMA_CHUNK_SIZE", "2048"))

MAX_HISTORY = int(os.getenv("AI_MAX_HISTORY", "8"))
CACHE_TTL = int(os.getenv("AI_CACHE_TTL", "8"))
AI_CONCURRENCY = int(os.getenv("AI_CONCURRENCY", "6"))

# =====================
# Logging
# =====================
logger = logging.getLogger("AnnieX_AI_Client")
logging.basicConfig(level=logging.INFO)

# =====================
# Runtime State
# =====================
REQUEST_SEMAPHORE = asyncio.Semaphore(AI_CONCURRENCY)
user_history: Dict[int, list] = {}

# =====================
# Arabic Detection
# =====================
ARABIC_RE = re.compile(r"[\u0600-\u06FF]")

def looks_arabic(text: str, min_chars: int = 2) -> bool:
    if not text:
        return False
    return len(ARABIC_RE.findall(text)) >= min_chars

# =====================
# Simple TTL Cache
# =====================
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

# =====================
# Ollama JSON Extractor
# =====================
def extract_text(data: Any) -> str:
    try:
        if isinstance(data, dict):
            if "message" in data:
                content = data["message"].get("content")
                if isinstance(content, str):
                    return content.strip()
            for k in ("response", "text", "output"):
                if k in data and isinstance(data[k], str):
                    return data[k].strip()
        if isinstance(data, str):
            return data.strip()
    except Exception:
        pass
    return ""

# =====================
# Core Streaming Engine
# =====================
async def ask_ollama(
    user_id: int,
    prompt: str,
    system_prompt: str,
    on_update: Optional[Callable[[str], None]] = None
) -> str:

    cache_key = f"{user_id}:{prompt}"
    cached = CACHE.get(cache_key)
    if cached:
        return cached

    messages = [{"role": "system", "content": system_prompt}]

    history = user_history.get(user_id, [])[-MAX_HISTORY:]
    for h in history:
        messages.append({"role": "user", "content": h["u"]})
        messages.append({"role": "assistant", "content": h["a"]})

    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": DEFAULT_MODEL,
        "messages": messages,
        "stream": True,
        "options": {
            "temperature": 0.15,
            "top_p": 0.9,
            "num_predict": 512
        }
    }

    async with REQUEST_SEMAPHORE:
        try:
            timeout = aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(OLLAMA_API_URL, json=payload) as resp:
                    if resp.status != 200:
                        return f"❌ Ollama HTTP {resp.status}"

                    buffer = ""
                    final_text = ""
                    started = False
                    start_time = time.time()

                    async for chunk in resp.content.iter_chunked(CHUNK_SIZE):
                        decoded = chunk.decode(errors="ignore")
                        buffer += decoded

                        lines = buffer.splitlines()
                        buffer = lines.pop() if not buffer.endswith("\n") else ""

                        for line in lines:
                            if not line.strip():
                                continue
                            try:
                                parsed = json.loads(line)
                                part = extract_text(parsed)
                            except Exception:
                                part = line

                            if not part:
                                continue

                            final_text += part
                            if on_update:
                                await on_update(final_text)

                            if not started:
                                started = True

                        if not started and time.time() - start_time > FIRST_CHUNK_TIMEOUT:
                            break

                    final_text = final_text.strip()

                    # Strict Arabic Retry
                    if not looks_arabic(final_text):
                        retry_payload = {
                            "model": DEFAULT_MODEL,
                            "messages": [
                                {
                                    "role": "system",
                                    "content": system_prompt + "\nأجب بالعربية فقط دون أي لغة أخرى."
                                },
                                {"role": "user", "content": prompt}
                            ],
                            "stream": False,
                            "options": {"temperature": 0.1}
                        }
                        async with session.post(OLLAMA_API_URL, json=retry_payload) as r2:
                            data = await r2.json(content_type=None)
                            final_text = extract_text(data)

                    final_text = final_text or "لم يتم توليد رد صالح."

                    CACHE.set(cache_key, final_text)
                    user_history.setdefault(user_id, []).append(
                        {"u": prompt, "a": final_text}
                    )

                    if len(user_history[user_id]) > MAX_HISTORY:
                        user_history[user_id] = user_history[user_id][-MAX_HISTORY:]

                    return final_text

        except asyncio.TimeoutError:
            return "الذكاء اتأخر في الرد."
        except Exception as e:
            logger.error(traceback.format_exc())
            return f"خطأ داخلي: {str(e)}"
