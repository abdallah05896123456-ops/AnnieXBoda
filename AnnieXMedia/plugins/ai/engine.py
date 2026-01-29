# plugins/ai/engine.py
# Authored By Certified Coders © 2026
# Local AI Engine (Ollama HTTP / Streaming / Stable State)

import os
import json
import asyncio
import logging
from typing import Dict, Optional, Callable

import aiohttp

logger = logging.getLogger("AnnieX_AI_Engine")
logging.basicConfig(level=logging.INFO)

# ------------------------------------------------------------------
# إعدادات Ollama
# ------------------------------------------------------------------

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
OLLAMA_CHAT_ENDPOINT = f"{OLLAMA_HOST}/api/chat"

OLLAMA_MODEL_DEFAULT = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")

# ------------------------------------------------------------------
# ذاكرة المستخدمين (محادثات)
# ------------------------------------------------------------------

USER_HISTORY: Dict[int, list] = {}

# ------------------------------------------------------------------
# حالة المحرك (مرتبطة بالهاندلرز)
# ------------------------------------------------------------------

class EngineState:
    def __init__(self):
        self.model: str = OLLAMA_MODEL_DEFAULT
        self.temperature: float = 0.7

ENGINE = EngineState()

# ------------------------------------------------------------------
# أدوات مساعدة
# ------------------------------------------------------------------

def _build_messages(
    user_id: int,
    prompt: str,
    system_prompt: str
) -> list:
    """
    يبني سجل الرسائل بالـ system + history + prompt الحالي
    """
    history = USER_HISTORY.get(user_id, [])

    messages = []

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


def _save_assistant_reply(user_id: int, prompt: str, reply: str):
    """
    يحفظ السؤال والرد في الذاكرة
    """
    history = USER_HISTORY.setdefault(user_id, [])

    history.append({
        "role": "user",
        "content": prompt
    })
    history.append({
        "role": "assistant",
        "content": reply
    })

    # تحديد حد أقصى للذاكرة
    if len(history) > 40:
        USER_HISTORY[user_id] = history[-40:]


# ------------------------------------------------------------------
# الدالة الرئيسية (Streaming)
# ------------------------------------------------------------------

async def ask_ollama_stream(
    user_id: int,
    prompt: str,
    system_prompt: str = "",
    model: Optional[str] = None,
    temperature: float = 0.7,
    on_update: Optional[Callable[[str], None]] = None,
) -> str:
    """
    استدعاء Ollama مع بث تدريجي
    """
    used_model = model or ENGINE.model

    payload = {
        "model": used_model,
        "messages": _build_messages(user_id, prompt, system_prompt),
        "stream": True,
        "options": {
            "temperature": temperature
        }
    }

    full_reply = ""

    timeout = aiohttp.ClientTimeout(total=None)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(OLLAMA_CHAT_ENDPOINT, json=payload) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(f"Ollama error {resp.status}: {text}")

            async for line in resp.content:
                if not line:
                    continue

                try:
                    data = json.loads(line.decode("utf-8"))
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

    _save_assistant_reply(user_id, prompt, full_reply)

    return full_reply


# ------------------------------------------------------------------
# أدوات تحكم (يستخدمها handlers)
# ------------------------------------------------------------------

def clear_user_memory(user_id: int):
    USER_HISTORY.pop(user_id, None)


def clear_all_memory():
    USER_HISTORY.clear()


def set_default_model(model_name: str):
    global OLLAMA_MODEL_DEFAULT
    OLLAMA_MODEL_DEFAULT = model_name
    ENGINE.model = model_name


def get_current_model() -> str:
    return ENGINE.model
