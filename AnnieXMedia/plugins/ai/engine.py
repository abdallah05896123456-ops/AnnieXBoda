# Authored By Certified Coders © 2026
# Local AI Engine (Ollama HTTP / Streaming / Stable State)

import os
import json
import asyncio
import logging
from typing import Dict, Optional, Callable, List

import aiohttp

logger = logging.getLogger("AnnieX_AI_Engine")
logging.basicConfig(level=logging.INFO)

# ------------------------------------------------------------------
# إعدادات Ollama
# ------------------------------------------------------------------

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
OLLAMA_CHAT_ENDPOINT = f"{OLLAMA_HOST}/api/chat"

OLLAMA_MODEL_DEFAULT = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "0"))  # 0 = بدون حد

# ------------------------------------------------------------------
# ذاكرة المستخدمين
# ------------------------------------------------------------------

USER_HISTORY: Dict[int, List[Dict[str, str]]] = {}

MAX_HISTORY_MESSAGES = int(os.getenv("AI_MAX_HISTORY", "40"))

# ------------------------------------------------------------------
# حالة الذكاء (State)
# ------------------------------------------------------------------

class AIState:
    def __init__(self):
        self.enabled: bool = True
        self.model: str = OLLAMA_MODEL_DEFAULT
        self.temperature: float = float(os.getenv("AI_TEMPERATURE", "0.7"))

AI = AIState()

# ------------------------------------------------------------------
# أدوات داخلية
# ------------------------------------------------------------------

def _build_messages(
    user_id: int,
    prompt: str,
    system_prompt: str
) -> List[Dict[str, str]]:
    history = USER_HISTORY.get(user_id, [])

    messages: List[Dict[str, str]] = []

    if system_prompt:
        messages.append({
            "role": "system",
            "content": system_prompt
        })

    messages.extend(history)

    messages.append({
        "role": "user",
        "content": prompt
    })

    return messages


def _save_history(user_id: int, prompt: str, reply: str) -> None:
    history = USER_HISTORY.setdefault(user_id, [])

    history.append({
        "role": "user",
        "content": prompt
    })
    history.append({
        "role": "assistant",
        "content": reply
    })

    if len(history) > MAX_HISTORY_MESSAGES:
        USER_HISTORY[user_id] = history[-MAX_HISTORY_MESSAGES:]


# ------------------------------------------------------------------
# الدالة الرئيسية (Streaming)
# ------------------------------------------------------------------

async def ask_ollama_stream(
    user_id: int,
    prompt: str,
    system_prompt: str = "",
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    on_update: Optional[Callable[[str], asyncio.Future]] = None,
) -> str:
    """
    استدعاء Ollama ببث تدريجي (Streaming)
    """

    if not AI.enabled:
        return "الذكاء الاصطناعي متوقف حالياً."

    used_model = model or AI.model
    used_temp = temperature if temperature is not None else AI.temperature

    payload = {
        "model": used_model,
        "stream": True,
        "messages": _build_messages(user_id, prompt, system_prompt),
        "options": {
            "temperature": used_temp
        }
    }

    full_reply = ""

    timeout = aiohttp.ClientTimeout(total=None if OLLAMA_TIMEOUT == 0 else OLLAMA_TIMEOUT)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(OLLAMA_CHAT_ENDPOINT, json=payload) as resp:
            if resp.status != 200:
                body = await resp.text()
                raise RuntimeError(f"Ollama HTTP {resp.status}: {body}")

            async for raw in resp.content:
                if not raw:
                    continue

                try:
                    data = json.loads(raw.decode("utf-8"))
                except Exception:
                    continue

                if data.get("done") is True:
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

    return full_reply.strip()

# ------------------------------------------------------------------
# أدوات تحكم (تُستخدم من handlers)
# ------------------------------------------------------------------

def enable_ai():
    AI.enabled = True


def disable_ai():
    AI.enabled = False


def toggle_ai() -> bool:
    AI.enabled = not AI.enabled
    return AI.enabled


def clear_user_memory(user_id: int):
    USER_HISTORY.pop(user_id, None)


def clear_all_memory():
    USER_HISTORY.clear()


def set_model(model_name: str):
    AI.model = model_name


def get_model() -> str:
    return AI.model


def set_temperature(value: float):
    AI.temperature = float(value)


def get_status() -> bool:
    return AI.enabled
