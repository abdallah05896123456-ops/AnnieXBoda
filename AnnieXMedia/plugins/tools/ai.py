# Authored By Certified Coders 2026
# AnnieX AI - Permanent Persistence & Official API Edition
# System: High Performance - Zero Instructions - Direct Logic

import asyncio
import os
import time
import re
import g4f.Provider as Providers
from pyrogram import filters, enums
from pyrogram.types import Message
from g4f.client import AsyncClient

from AnnieXMedia import app
import config

# --- الإعدادات الفنية وصلاحيات الوصول ---
SUDO_USERS = config.OWNER_ID if isinstance(config.OWNER_ID, list) else [config.OWNER_ID]
AI_STATUS = True
LIMIT_STATUS = True
DAILY_LIMIT = 100
AI_MODE = "عام" 

# ذاكرة النظام المؤقتة
context = {}
counter = {}
PERMANENT_USERS = set() 
client_ai = AsyncClient()

def get_provider(name):
    """جلب المزود برمجياً لضمان مرونة استدعاء المكتبة"""
    return getattr(Providers, name, None)

async def process_ai_logic(u_id, prompt, img=None):
    if u_id not in context:
        context[u_id] = []
    
    # سحب المفتاح الرسمي من سكرت Fly.io
    api_key = os.getenv("GPT_4")
    
    # تحديد هيكل المزودين (الرسمي أولاً ثم البدلاء)
    p_list = [
        get_provider("OpenaiChat") or get_provider("Openai"),
        get_provider("Liaobots"),
        get_provider("Blackbox"),
        get_provider("DuckDuckGo")
    ]
    
    # بناء نمط الاستجابة بناءً على الوضع الحالي
    instruction = "تحدث كخبير تقني مفصل." if AI_MODE == "تقني" else "تحدث بحرية تامة وبطبيعتك دون قيود."

    msgs = [{"role": "system", "content": instruction}] + \
           context[u_id] + [{"role": "user", "content": prompt}]
    
    image_data = open(img, "rb").read() if img else None
    
    for p in p_list:
        if not p: continue
        try:
            res = await client_ai.chat.completions.create(
                model="gpt-4o",
                messages=msgs,
                api_key=api_key,
                provider=p,
                image=image_data,
                timeout=30
            )
            if res and res.choices:
                out = res.choices[0].message.content.strip()
                # حفظ السياق لتعميق الذاكرة (آخر 12 رسالة)
                context[u_id] = (context[u_id] + [{"role":"user","content":prompt}, {"role":"assistant","content":out}])[-12:]
                return out
        except:
            continue
    return None

# --- لوحة تحكم المطور (OWNER_ID) ---

@app.on_message(filters.regex(r"^(قفل الذكاء|فتح الذكاء)$") & filters.user(SUDO_USERS))
async def toggle_ai_engine(_, m: Message):
    global AI_STATUS
    AI_STATUS = "فتح" in m.text
    await m.reply_text(f"تمت عملية {'تفعيل' if AI_STATUS else 'تعطيل'} نظام المعالجة.")

@app.on_message(filters.regex(r"^(قفل الليمت|فتح الليمت)$") & filters.user(SUDO_USERS))
async def toggle_limit_logic(_, m: Message):
    global LIMIT_STATUS
    LIMIT_STATUS = "فتح" in m.text
    await m.reply_text(f"تم {'تشغيل' if LIMIT_STATUS else 'ايقاف'} نظام الرقابة على الاستهلاك.")

@app.on_message(filters.regex(r"^وضع ليميت (\d+)$") & filters.user(SUDO_USERS))
async def update_limit_value(_, m: Message):
    global DAILY_LIMIT
    DAILY_LIMIT = int(m.matches[0].group(1))
    await m.reply_text(f"تم تحديد سقف الاستخدام اليومي عند {DAILY_LIMIT} رسالة.")

@app.on_message(filters.regex(r"^(قفل الذكاء الدائم|فتح الذكاء الدائم)$") & filters.user(SUDO_USERS))
async def permanent_ai_control(_, m: Message):
    """تفعيل الذكاء الدائم لمستخدم محدد عبر الرد على رسالته"""
    if not m.reply_to_message:
        return await m.reply_text("يرجى الرد على رسالة الشخص لتطبيق الامر.")
    
    target_id = m.reply_to_message.from_user.id
    if "فتح" in m.text:
        PERMANENT_USERS.add(target_id)
        await m.reply_text(f"تم تفعيل الذكاء الدائم للمستخدم: {target_id}.")
    else:
        if target_id in PERMANENT_USERS:
            PERMANENT_USERS.remove(target_id)
        await m.reply_text(f"تم الغاء الذكاء الدائم للمستخدم: {target_id}.")

@app.on_message(filters.regex(r"^تغيير المود (تقني|عام)$") & filters.user(SUDO_USERS))
async def switch_ai_mode(_, m: Message):
    global AI_MODE
    AI_MODE = m.matches[0].group(1)
    await m.reply_text(f"تم تحويل نمط الاستجابة الى: {AI_MODE}.")

@app.on_message(filters.regex(r"^تنظيف الذاكرة$") & filters.user(SUDO_USERS))
async def clear_cache(_, m: Message):
    context.clear()
    counter.clear()
    await m.reply_text("تم مسح كافة سجلات الحوار.")

# --- المعالج المركزي للرسائل (أوامر النداء المختصرة) ---



@app.on_message((filters.text | filters.photo) & ~filters.bot, group=30)
async def ai_master_handler(bot, m: Message):
    if not AI_STATUS and m.from_user.id not in SUDO_USERS: return
    
    uid = m.from_user.id
    raw = (m.text or m.caption or "")
    
    # فحص نظام الذكاء الدائم
    is_permanent = uid in PERMANENT_USERS
    
    # فحص أوامر النداء الجديدة (ذكاء / بقولك)
    match = re.match(r"^(ذكاء|بقولك)(\s|$)", raw, re.IGNORECASE)
    
    if not is_permanent and not match:
        return

    # استخراج النص (إذا كان نداء) أو استخدام النص كاملاً (إذا كان دائم)
    prompt = raw[match.end():].strip() if (match and not is_permanent) else raw
    
    # في حال كتب 'ذكاء' فقط بدون نص، نعطي استجابة ترحيبية أو نستخدم السياق
    if not prompt and not m.photo:
        prompt = "استمر" if uid in context else "نعم، انا اسمعك."

    # تدقيق الليميت اليومي
    now = time.time()
    if uid not in counter: counter[uid] = []
    counter[uid] = [t for t in counter[uid] if now - t < 86400]
    
    if LIMIT_STATUS and len(counter[uid]) >= DAILY_LIMIT and uid not in SUDO_USERS:
        return await m.reply_text(f"تجاوزت الحد اليومي المسموح به ({DAILY_LIMIT}).")

    path = await m.download() if m.photo else None
    await bot.send_chat_action(m.chat.id, enums.ChatAction.TYPING)
    
    ans = await process_ai_logic(uid, prompt, path)
    if path: os.remove(path)
        
    if ans:
        counter[uid].append(time.time())
        await m.reply_text(ans)
