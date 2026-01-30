# plugins/ai/engine.py
# Authored By Certified Coders © 2026
# Local AI Engine - Smart G4F (Auto-Healing & Robust)
# FULLY COMPATIBLE WITH handlers.py

import logging
import asyncio
import inspect
import time
from typing import Dict, Optional, Callable

# ✅ استدعاء العميل الأساسي
from g4f.client import AsyncClient

# ------------------------------------------------------------------
# Logger
# ------------------------------------------------------------------

logger = logging.getLogger("AnnieX_AI")
logging.basicConfig(level=logging.INFO)

# ------------------------------------------------------------------
# Models Mapping
# ------------------------------------------------------------------

LIGHT_MODEL = "gpt-3.5-turbo"
HEAVY_MODEL = "gpt-4"
DEFAULT_MODEL = LIGHT_MODEL

# ------------------------------------------------------------------
# Memory & Cache Management
# ------------------------------------------------------------------

USER_HISTORY: Dict[int, list] = {}
CACHE: Dict[str, str] = {}
MAX_HISTORY = 12       # عدد الرسائل المحفوظة لكل مستخدم
MAX_CACHE_SIZE = 500   # أقصى عدد ردود محفوظة في الكاش
MAX_USERS_IN_MEM = 100 # أقصى عدد مستخدمين في الذاكرة لتجنب استهلاك الرامات

# ------------------------------------------------------------------
# Engine State
# ------------------------------------------------------------------

class AIEngineState:
    def __init__(self):
        self.enabled: bool = True
        self.model: str = DEFAULT_MODEL
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
# Internal Helpers (Smart Logic)
# ------------------------------------------------------------------

def _clean_memory_if_needed():
    """تنظيف الذاكرة بذكاء إذا زاد الحمل"""
    if len(USER_HISTORY) > MAX_USERS_IN_MEM:
        # حذف أقدم 20 مستخدم لم يتفاعلوا مؤخراً
        keys_to_remove = list(USER_HISTORY.keys())[:20]
        for k in keys_to_remove:
            del USER_HISTORY[k]
    
    if len(CACHE) > MAX_CACHE_SIZE:
        CACHE.clear()

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
    _clean_memory_if_needed()
    history = USER_HISTORY.setdefault(user_id, [])
    history.append({"role": "user", "content": prompt})
    history.append({"role": "assistant", "content": reply})
    
    if len(history) > MAX_HISTORY:
        USER_HISTORY[user_id] = history[-MAX_HISTORY:]

# ------------------------------------------------------------------
# Core G4F Logic (The Smartest Implementation)
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
    دالة الذكاء الاصطناعي الأساسية
    """

    if not AI.enabled:
        return "الذكاء الاصطناعي متوقف حاليا."

    used_model = model or AI.model
    
    # 1. فحص الكاش للسرعة
    cache_key = f"{used_model}:{prompt}" 
    if cache_key in CACHE:
        return CACHE[cache_key]

    messages = _build_messages(user_id, prompt, system_prompt)
    
    # 2. تهيئة العميل (بدون تحديد مزود ليختار الأفضل تلقائياً)
    client = AsyncClient()

    full_reply = ""
    
    try:
        # 🔥 [الذكاء البرمجي هنا] 🔥
        # نقوم بإنشاء الطلب ولكن لا نستخدم await فوراً
        # لأن بعض النسخ تعيد Generator والبعض يعيد Coroutine
        response = client.chat.completions.create(
            model=used_model,
            messages=messages,
            stream=True 
        )

        # فحص نوع الاستجابة بذكاء
        # لو كانت دالة انتظار (Coroutine)، ننتظرها
        if inspect.iscoroutine(response):
            response = await response

        # الآن معنا الـ Stream، نلف عليه
        async for chunk in response:
            content = None
            
            # محاولة استخراج النص بأكثر من صيغة لضمان التوافق مع كل المزودات
            if hasattr(chunk.choices[0].delta, "content"):
                content = chunk.choices[0].delta.content
            elif hasattr(chunk, "content"):
                content = chunk.content
            
            if content:
                full_reply += content
                
                # تحديث الرسالة كل 20 حرف لتجنب حظر التليجرام (Flood Wait)
                if on_update and len(full_reply) % 20 == 0: 
                    try:
                        await on_update(full_reply)
                    except:
                        pass
        
        # التحديث النهائي للنص الكامل
        if on_update:
            await on_update(full_reply)

    except Exception as e:
        logger.error(f"G4F Smart Error: {e}")
        err_msg = str(e).lower()
        
        # ردود ذكية حسب نوع الخطأ
        if "404" in err_msg or "not found" in err_msg:
            return "الموديل ده عليه ضغط حالياً أو غير متاح، جرب تغير الوضع (سريع/ذكي)."
        elif "429" in err_msg or "rate limit" in err_msg:
            return "السيرفر مشغول جداً، جرب تاني كمان ثواني."
        else:
            return f"حصل خطأ بسيط في الاتصال، حاول مرة كمان. ({e})"

    if not full_reply:
        return "لم يصل رد من السيرفر، جرب مرة أخرى."

    # حفظ في الذاكرة والكاش
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
    "ask_ollama_stream", 
    "clear_user_memory",
    "clear_all_memory",
    "toggle_model",
    "set_light_model",
    "set_heavy_model",
    "get_model",
    "get_current_model",
]
