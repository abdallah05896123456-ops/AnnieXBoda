# plugins/ai/engine.py
# Authored By Certified Coders © 2026
# Local AI Engine - Switched to G4F (Fast Cloud)
# FULLY COMPATIBLE WITH handlers.py

import logging
import asyncio
from typing import Dict, Optional, Callable

# استدعاء مكتبة G4F والعميل غير المتزامن
from g4f.client import AsyncClient
from g4f.Provider import RetryProvider, Bing, FreeGpt, Liaobots, DarkAI, Blackbox

# ------------------------------------------------------------------
# Logger
# ------------------------------------------------------------------

logger = logging.getLogger("AnnieX_AI")
logging.basicConfig(level=logging.INFO)

# ------------------------------------------------------------------
# Models Mapping (Light vs Heavy)
# ------------------------------------------------------------------

# Light = GPT-3.5 or Mini (Fastest)
LIGHT_MODEL = "gpt-3.5-turbo"

# Heavy = GPT-4 (Smartest)
HEAVY_MODEL = "gpt-4"

DEFAULT_MODEL = LIGHT_MODEL

# ------------------------------------------------------------------
# Memory & Cache
# ------------------------------------------------------------------

USER_HISTORY: Dict[int, list] = {}
CACHE: Dict[str, str] = {}
MAX_HISTORY = 12  # تقليل السياق قليلاً لضمان استجابة المزودات المجانية

# ------------------------------------------------------------------
# Engine State
# ------------------------------------------------------------------

class AIEngineState:
    def __init__(self):
        self.enabled: bool = True
        self.model: str = DEFAULT_MODEL
        # g4f providers often ignore temperature, but kept for compatibility
        self.temperature: float = 0.7 

    @property
    def status(self) -> bool:
        return self.enabled

    def reset(self):
        self.enabled = True
        self.model = DEFAULT_MODEL


AI = AIEngineState()
ENGINE = AI

# ------------------------------------------------------------------
# Internal Helpers
# ------------------------------------------------------------------

def _build_messages(user_id: int, prompt: str, system_prompt: str) -> list:
    messages = []
    
    # System Prompt
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    # User History
    history = USER_HISTORY.get(user_id, [])
    messages.extend(history)

    # Current Message
    messages.append({"role": "user", "content": prompt})
    return messages


def _save_history(user_id: int, prompt: str, reply: str):
    history = USER_HISTORY.setdefault(user_id, [])
    history.append({"role": "user", "content": prompt})
    history.append({"role": "assistant", "content": reply})
    
    if len(history) > MAX_HISTORY:
        USER_HISTORY[user_id] = history[-MAX_HISTORY:]

# ------------------------------------------------------------------
# Core G4F Logic (Replaces Ollama)
# ------------------------------------------------------------------

async def ask_ollama_stream(
    user_id: int,
    prompt: str,
    system_prompt: str = "",
    model: Optional[str] = None,
    temperature: Optional[float] = None, 
    on_update: Optional[Callable[[str], None]] = None,
) -> str:
    """
    Function name kept as 'ask_ollama_stream' for compatibility 
    with existing handlers.py, but logic is pure G4F.
    """

    if not AI.enabled:
        return "الذكاء الاصطناعي متوقف حاليا."

    used_model = model or AI.model
    
    # Check Cache (Simple caching)
    cache_key = f"{used_model}:{prompt}" 
    if cache_key in CACHE:
        return CACHE[cache_key]

    messages = _build_messages(user_id, prompt, system_prompt)
    
    # Initialize G4F Client with RetryProvider for stability
    # This automatically tries multiple providers if one fails
    client = AsyncClient(
        provider=RetryProvider([Bing, Blackbox, FreeGpt, Liaobots, DarkAI], shuffle=False)
    )

    full_reply = ""
    
    try:
        # Request from G4F
        response = await client.chat.completions.create(
            model=used_model,
            messages=messages,
            stream=True 
        )

        async for chunk in response:
            if chunk.choices[0].delta.content:
                delta = chunk.choices[0].delta.content
                full_reply += delta
                
                # Update Message (Streaming effect)
                # We update every few chars to avoid flooding Telegram API
                if on_update and len(full_reply) % 15 == 0: 
                    try:
                        await on_update(full_reply)
                    except:
                        pass
        
        # Final update to ensure complete text is shown
        if on_update:
            await on_update(full_reply)

    except Exception as e:
        logger.error(f"G4F Error: {e}")
        return f"عذراً، الخوادم مشغولة حالياً، حاول مرة أخرى. ({e})"

    if not full_reply:
        return "لم أستطع الحصول على رد، حاول مرة أخرى."

    # Save logic
    _save_history(user_id, prompt, full_reply)
    CACHE[cache_key] = full_reply
    
    return full_reply

# ------------------------------------------------------------------
# Controls (Standard - Fully Compatible)
# ------------------------------------------------------------------

def clear_user_memory(user_id: int):
    USER_HISTORY.pop(user_id, None)

def clear_all_memory():
    USER_HISTORY.clear()
    CACHE.clear()

def enable_ai():
    AI.enabled = True

def disable_ai():
    AI.enabled = False

def set_light_model():
    AI.model = LIGHT_MODEL

def set_heavy_model():
    AI.model = HEAVY_MODEL

def toggle_model() -> str:
    AI.model = HEAVY_MODEL if AI.model == LIGHT_MODEL else LIGHT_MODEL
    return AI.model

def get_model() -> str:
    return AI.model

def get_current_model() -> str:
    return AI.model

# ------------------------------------------------------------------
# Exports
# ------------------------------------------------------------------

__all__ = [
    "AI",
    "ENGINE",
    "ask_ollama_stream", # Kept name for compatibility
    "clear_user_memory",
    "clear_all_memory",
    "toggle_model",
    "set_light_model",
    "set_heavy_model",
    "get_model",
    "get_current_model",
]
