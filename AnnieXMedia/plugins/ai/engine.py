# plugins/ai/engine.py
# Authored By Certified Coders © 2026
# Local AI Engine - Ollama HTTP Streaming
# FULLY COMPATIBLE WITH handlers.py
# MODELS: llama3.1:8b / llama3.1:70b

import os
import json
import logging
from typing import Dict, Optional, Callable

import aiohttp

# ------------------------------------------------------------------
# Logger
# ------------------------------------------------------------------

logger = logging.getLogger("AnnieX_AI")
logging.basicConfig(level=logging.INFO)

# ------------------------------------------------------------------
# Ollama Configuration
# ------------------------------------------------------------------

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
OLLAMA_CHAT_ENDPOINT = f"{OLLAMA_HOST}/api/chat"

# 🔥 MODELS (LLAMA 3.1)
LIGHT_MODEL = os.getenv("OLLAMA_LIGHT_MODEL", "llama3.1:8b")
HEAVY_MODEL = os.getenv("OLLAMA_HEAVY_MODEL", "llama3.1:70b")

DEFAULT_MODEL = LIGHT_MODEL

# ------------------------------------------------------------------
# Memory & Cache (REQUIRED BY HANDLERS)
# ------------------------------------------------------------------

USER_HISTORY: Dict[int, list] = {}
CACHE: Dict[str, str] = {}

MAX_HISTORY = 40

# ------------------------------------------------------------------
# Engine State
# ------------------------------------------------------------------

class AIEngineState:
    def __init__(self):
        self.enabled: bool = True
        self.model: str = DEFAULT_MODEL
        self.temperature: float = 0.7

    # 👇 REQUIRED BY handlers.py
    @property
    def status(self) -> bool:
        return self.enabled

    def reset(self):
        self.enabled = True
        self.model = DEFAULT_MODEL
        self.temperature = 0.7


AI = AIEngineState()

# 👇 REQUIRED BY handlers.py
ENGINE = AI

# ------------------------------------------------------------------
# Internal Helpers
# ------------------------------------------------------------------

def _build_messages(user_id: int, prompt: str, system_prompt: str) -> list:
    messages = []

    if system_prompt:
        messages.append({
            "role": "system",
            "content": system_prompt
        })

    history = USER_HISTORY.get(user_id, [])
    messages.extend(history)

    messages.append({
        "role": "user",
        "content": prompt
        })

    return messages


def _save_history(user_id: int, prompt: str, reply: str):
    history = USER_HISTORY.setdefault(user_id, [])

    history.append({"role": "user", "content": prompt})
    history.append({"role": "assistant", "content": reply})

    if len(history) > MAX_HISTORY:
        USER_HISTORY[user_id] = history[-MAX_HISTORY:]


# ------------------------------------------------------------------
# Core Ollama Streaming
# ------------------------------------------------------------------

async def ask_ollama_stream(
    user_id: int,
    prompt: str,
    system_prompt: str = "",
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    on_update: Optional[Callable[[str], None]] = None,
) -> str:

    if not AI.enabled:
        return "الذكاء الاصطناعي متوقف حاليا."

    used_model = model or AI.model
    used_temp = temperature if temperature is not None else AI.temperature

    cache_key = f"{user_id}:{used_model}:{prompt}"
    if cache_key in CACHE:
        return CACHE[cache_key]

    payload = {
        "model": used_model,
        "stream": True,
        "messages": _build_messages(user_id, prompt, system_prompt),
        "options": {
            "temperature": used_temp
        }
    }

    full_reply = ""
    timeout = aiohttp.ClientTimeout(total=None)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(OLLAMA_CHAT_ENDPOINT, json=payload) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(f"Ollama Error {resp.status}: {text}")

            async for raw in resp.content:
                if not raw:
                    continue

                try:
                    data = json.loads(raw.decode("utf-8"))
                except Exception:
                    continue

                if data.get("done"):
                    break

                delta = data.get("message", {}).get("content")
                if not delta:
                    continue

                full_reply += delta

                if on_update:
                    try:
                        await on_update(full_reply)
                    except Exception:
                        pass

    _save_history(user_id, prompt, full_reply)
    CACHE[cache_key] = full_reply
    return full_reply


# ------------------------------------------------------------------
# Memory Control
# ------------------------------------------------------------------

def clear_user_memory(user_id: int):
    USER_HISTORY.pop(user_id, None)


def clear_all_memory():
    USER_HISTORY.clear()
    CACHE.clear()


# ------------------------------------------------------------------
# Engine Control
# ------------------------------------------------------------------

def enable_ai():
    AI.enabled = True


def disable_ai():
    AI.enabled = False


def reset_engine():
    clear_all_memory()
    AI.reset()


# ------------------------------------------------------------------
# Model Control
# ------------------------------------------------------------------

def set_light_model():
    AI.model = LIGHT_MODEL


def set_heavy_model():
    AI.model = HEAVY_MODEL


def toggle_model() -> str:
    AI.model = HEAVY_MODEL if AI.model == LIGHT_MODEL else LIGHT_MODEL
    return AI.model


def get_model() -> str:
    return AI.model


# 👇 REQUIRED BY handlers.py
def get_current_model() -> str:
    return AI.model


# ------------------------------------------------------------------
# Exports
# ------------------------------------------------------------------

__all__ = [
    "AI",
    "ENGINE",
    "ask_ollama_stream",
    "USER_HISTORY",
    "CACHE",
    "enable_ai",
    "disable_ai",
    "reset_engine",
    "clear_user_memory",
    "clear_all_memory",
    "toggle_model",
    "set_light_model",
    "set_heavy_model",
    "get_model",
    "get_current_model",
]
