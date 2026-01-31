# plugins/ai/engine.py
# Authored By Certified Coders (c) 2026
# Local AI Engine - Enterprise Edition (Persona Fixed)
# Fixes: "I am OpenAI" response, API Key Errors, Throttling

import logging
import asyncio
import time
import random
from typing import Dict, Optional, Callable

# استدعاء العميل والمزودات المحترمة فقط
from g4f.client import AsyncClient
from g4f.Provider import (
    Blackbox,      # العمدة (بيقبل الشخصيات وسريع)
    PollinationsAI, # ممتاز جدا في تقمص الأدوار
    DarkAI,         # بديل قوي
    ChatGptEs,      # بيدعم GPT-4 مجانا
)

# ------------------------------------------------------------------
# Logger
# ------------------------------------------------------------------

logger = logging.getLogger("AnnieX_AI")
logging.basicConfig(level=logging.INFO)

# ------------------------------------------------------------------
# Constants & Config
# ------------------------------------------------------------------

# تم حذف DuckDuckGo لانه هو اللي كان بيبوظ الردود
# الاعتماد الكلي على Blackbox و Pollinations لانهم بيسمعوا الكلام

FAST_PROVIDERS = [Blackbox, PollinationsAI]  # للوضع السريع
SMART_PROVIDERS = [Blackbox, DarkAI, ChatGptEs] # للوضع التقيل

LIGHT_MODEL = "gpt-3.5-turbo" 
HEAVY_MODEL = "gpt-4-turbo"   
DEFAULT_MODEL = HEAVY_MODEL   # خلينا الديفولت التقيل عشان الجودة

# اعدادات الذاكرة
USER_HISTORY: Dict[int, list] = {}
CACHE: Dict[str, str] = {}
MAX_HISTORY = 10       
MAX_CACHE_SIZE = 500   
MAX_USERS_IN_MEM = 50 

# ------------------------------------------------------------------
# Engine State
# ------------------------------------------------------------------

class AIEngineState:
    def __init__(self):
        self.enabled: bool = True
        self.model: str = DEFAULT_MODEL
        self.temperature: float = 0.7 

    def reset(self):
        self.enabled = True
        self.model = DEFAULT_MODEL

AI = AIEngineState()
ENGINE = AI

# ------------------------------------------------------------------
# Internal Helpers
# ------------------------------------------------------------------

def _clean_memory_if_needed():
    if len(USER_HISTORY) > MAX_USERS_IN_MEM:
        keys = list(USER_HISTORY.keys())[:15]
        for k in keys: del USER_HISTORY[k]
    if len(CACHE) > MAX_CACHE_SIZE:
        CACHE.clear()

def _build_messages(user_id: int, prompt: str, system_prompt: str) -> list:
    messages = []
    
    # اجبار المزود على احترام الشخصية
    # بعض المزودات بتحتاج الـ System Prompt يكون في الاول
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    
    # تنظيف الذاكرة القديمة جدا
    history = USER_HISTORY.get(user_id, [])
    recent_history = history[-6:] 
    
    messages.extend(recent_history)
    messages.append({"role": "user", "content": prompt})
    return messages

def _save_history(user_id: int, prompt: str, reply: str):
    _clean_memory_if_needed()
    history = USER_HISTORY.setdefault(user_id, [])
    history.append({"role": "user", "content": prompt})
    history.append({"role": "assistant", "content": reply})
    if len(history) > MAX_HISTORY:
        USER_HISTORY[user_id] = history[-MAX_HISTORY:]

# ------------------------------------------------------------------
# Core Logic (Smart Throttling + Persona Fix)
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
    دالة ذكية تتفادى الردود الالية وتستخدم موديلات قوية فقط
    """
    if not AI.enabled:
        return "الذكاء الاصطناعي متوقف للصيانة."

    used_model = model or AI.model
    
    # 1. فحص الكاش
    cache_key = f"{used_model}:{prompt}" 
    if cache_key in CACHE:
        return CACHE[cache_key]

    # 2. تحديد المزود (Provider)
    # هنا التعديل: استخدمنا Blackbox و Pollinations في الحالتين
    # لانهم الافضل في تقمص الشخصيات
    current_provider = None
    if used_model == LIGHT_MODEL:
        current_provider = random.choice(FAST_PROVIDERS)
    else:
        current_provider = random.choice(SMART_PROVIDERS)

    # بناء الرسائل
    messages = _build_messages(user_id, prompt, system_prompt)
    
    # اعداد العميل
    client = AsyncClient(provider=current_provider)

    full_reply = ""
    last_update_time = 0
    last_sent_text = ""

    # محاولة الاتصال مع نظام اعادة المحاولة (Retry)
    for attempt in range(2): 
        try:
            if attempt > 0:
                # لو فشل، جرب Blackbox لانه الجوكر
                client = AsyncClient(provider=Blackbox) 
            
            response = await client.chat.completions.create(
                model=used_model,
                messages=messages,
                stream=True
            )
            
            async for chunk in response:
                content = ""
                if hasattr(chunk.choices[0].delta, "content"):
                    content = chunk.choices[0].delta.content
                elif hasattr(chunk, "content"):
                    content = chunk.content
                
                if content:
                    full_reply += content
                    
                    # Smart Throttling System
                    # نفس نظام الحماية من التعليق اللي عجبك
                    current_time = time.time()
                    if on_update and (current_time - last_update_time > 1.5) and (full_reply != last_sent_text):
                        try:
                            await on_update(full_reply)
                            last_update_time = current_time
                            last_sent_text = full_reply 
                        except Exception as e:
                            # تجاهل اخطاء التعديل لمنع التعليق
                            if "MESSAGE_NOT_MODIFIED" in str(e):
                                pass
                            else:
                                pass # تجاهل صامت

            # لو الرد جه وكان مش فاضي ومش الرد الالي الغبي
            if full_reply and "I am an AI" not in full_reply:
                break 
            elif attempt == 0:
                # لو رد الرد الالي، نعتبره فشل ونحاول تاني بمزود مختلف
                full_reply = "" 
                continue

        except Exception as e:
            logger.error(f"Attempt {attempt+1} failed: {e}")
            if attempt == 1: 
                return "حدث خطأ في الاتصال بالسيرفرات، حاول مرة اخرى."
            await asyncio.sleep(1)

    if not full_reply:
        return "السيرفر لم يرسل اي رد مفيد."

    # التحديث النهائي
    if on_update and full_reply != last_sent_text:
        try:
            await on_update(full_reply)
        except:
            pass

    # حفظ النتائج
    _save_history(user_id, prompt, full_reply)
    CACHE[cache_key] = full_reply
    
    return full_reply

# ------------------------------------------------------------------
# Controls
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

def get_current_model() -> str:
    return AI.model

# ------------------------------------------------------------------
# Exports
# ------------------------------------------------------------------

__all__ = [
    "AI",
    "ENGINE",
    "ask_ollama_stream", 
    "clear_user_memory",
    "clear_all_memory",
    "toggle_model",
    "set_light_model",
    "set_heavy_model",
    "get_current_model",
]
