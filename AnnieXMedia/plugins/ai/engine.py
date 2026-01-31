# plugins/ai/engine.py
# Authored By Certified Coders (c) 2026
# Local AI Engine - Enterprise Edition (Async Fix + Crash Proof)
# Fixes: async_generator error, ImportError, and Throttling

import logging
import asyncio
import time
import random
import inspect 
from typing import Dict, Optional, Callable

# استدعاء العميل
from g4f.client import AsyncClient
# استدعاء المزودات كحزمة كاملة
import g4f.Provider

# ------------------------------------------------------------------
# Logger
# ------------------------------------------------------------------

logger = logging.getLogger("AnnieX_AI")
logging.basicConfig(level=logging.INFO)

# ------------------------------------------------------------------
# Dynamic Provider Loader
# ------------------------------------------------------------------

def get_provider_by_name(name_list):
    """
    فحص وتحميل المزودات المتاحة فقط لتجنب انهيار البوت
    """
    available = []
    for name in name_list:
        if hasattr(g4f.Provider, name):
            available.append(getattr(g4f.Provider, name))
    return available

# قوائم المزودات المحسنة
# تم استبدال Blackbox بـ BlackboxPro لتوافق التحديثات
FAST_NAMES = ["PollinationsAI", "DeepInfra", "HuggingChat", "DuckDuckGo"]
SMART_NAMES = ["BlackboxPro", "Blackbox", "PollinationsAI"]

FAST_PROVIDERS = get_provider_by_name(FAST_NAMES)
SMART_PROVIDERS = get_provider_by_name(SMART_NAMES)

# منطق التبديل التلقائي في حال عدم توفر مزودات
if not FAST_PROVIDERS and SMART_PROVIDERS:
    FAST_PROVIDERS = SMART_PROVIDERS
if not SMART_PROVIDERS and FAST_PROVIDERS:
    SMART_PROVIDERS = FAST_PROVIDERS

LIGHT_MODEL = "gpt-3.5-turbo" 
HEAVY_MODEL = "gpt-4"   
DEFAULT_MODEL = HEAVY_MODEL

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
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    
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
# Core Logic (Fixed for async_generator)
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
        return "الذكاء الاصطناعي متوقف للصيانة."

    used_model = model or AI.model
    
    # 1. فحص الكاش
    cache_key = f"{used_model}:{prompt}" 
    if cache_key in CACHE:
        return CACHE[cache_key]

    # 2. تحديد المزود
    target_list = FAST_PROVIDERS if used_model == LIGHT_MODEL else SMART_PROVIDERS
    current_provider = random.choice(target_list) if target_list else None
    
    # 3. بناء الرسائل
    messages = _build_messages(user_id, prompt, system_prompt)
    
    # 4. اعداد العميل
    if current_provider:
        client = AsyncClient(provider=current_provider)
    else:
        client = AsyncClient()

    full_reply = ""
    last_update_time = 0
    last_sent_text = ""

    # 5. محاولة الاتصال
    for attempt in range(2): 
        try:
            if attempt > 0:
                # في المحاولة الثانية نستخدم الوضع التلقائي
                client = AsyncClient()
            
            # انشاء الطلب (بدون await مبدئيا)
            response_obj = client.chat.completions.create(
                model=used_model,
                messages=messages,
                stream=True
            )
            
            # --- الاصلاح الجذري لمشكلة async_generator ---
            # نفحص ما اذا كانت النتيجة تحتاج لانتظار (Coroutine) ام انها جاهزة (Generator)
            if inspect.iscoroutine(response_obj):
                response = await response_obj
            else:
                response = response_obj
            
            # الان يمكننا الدوران بامان
            async for chunk in response:
                content = ""
                # محاولات استخراج النص بصيغ مختلفة
                if hasattr(chunk.choices[0].delta, "content"):
                    content = chunk.choices[0].delta.content
                elif hasattr(chunk, "content"):
                    content = chunk.content
                
                if content:
                    full_reply += content
                    
                    # استدعاء دالة التحديث
                    # نترك التحكم في التوقيت (FloodWait) للهاندلر الخارجي
                    # ولكن نقوم بفحص بسيط لتخفيف الحمل
                    if on_update and full_reply != last_sent_text:
                        try:
                            await on_update(full_reply)
                            last_sent_text = full_reply 
                        except Exception:
                            # تجاهل اي خطا اثناء التحديث لضمان استمرار التوليد
                            pass 

            # التحقق من صحة الرد
            if full_reply and "I am an AI" not in full_reply:
                break 
            elif attempt == 0:
                full_reply = "" 
                continue

        except Exception as e:
            logger.error(f"Attempt {attempt+1} failed: {e}")
            if attempt == 1: 
                return "نواجه مشكلة تقنية في الاتصال بالخادم، حاول لاحقا."
            await asyncio.sleep(1)

    if not full_reply:
        return "لم يتم استلام اي رد."

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
