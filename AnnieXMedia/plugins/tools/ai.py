# Authored By Certified Coders 2026
# AnnieX AI - Supreme Logic Edition
# Technical Operations Only - No Emojis

import asyncio
import os
import time
import re
import json
import g4f.Provider as Providers
from pyrogram import filters, enums
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from g4f.client import AsyncClient

from AnnieXMedia import app
import config

# --- الإعدادات الفنية والتحكم في الموارد ---
SUDO_USERS = config.OWNER_ID if isinstance(config.OWNER_ID, list) else [config.OWNER_ID]
AI_STATUS = True
LIMIT_STATUS = True
DAILY_LIMIT = 100
AI_MODE = "technical" # انماط الاستجابة: تقني / عام
AI_GROUP = 30 

context = {}
counter = {}
client_ai = AsyncClient()

def get_provider(name):
    """الاستيراد الديناميكي للمزودين لضمان مرونة النظام"""
    return getattr(Providers, name, None)

async def process_ai_logic(u_id, prompt, img=None):
    if u_id not in context:
        context[u_id] = []
    
    # جلب المفتاح الرسمي من سكرت Fly.io
    api_key = os.getenv("GPT_4")
    
    # تحديد الهيكل التنظيمي للمزودين
    primary = get_provider("OpenaiChat") or get_provider("Openai")
    secondary = [get_provider("Liaobots"), get_provider("Blackbox"), get_provider("DuckDuckGo")]
    
    # تخصيص التعليمات البرمجية بناء على نمط الاستجابة
    if AI_MODE == "technical":
        instruction = (
            "انت مهندس برمجيات وخبير تقني في سورس AnnieXMedia. "
            "اجاباتك يجب ان تكون مطولة جدا، دقيقة، وشاملة لكل التفاصيل الهندسية. "
            "استخدم لغة عربية فصحى رسمية جادة ومباشرة."
        )
    else:
        instruction = "انت مساعد ذكي شامل. قدم اجابات مطولة ومفصلة في كافة المجالات بلغة عربية قوية."

    msgs = [{"role": "system", "content": instruction}] + \
           context[u_id] + [{"role": "user", "content": prompt}]
    
    image_data = open(img, "rb").read() if img else None
    
    # محاولة التنفيذ عبر الربط الرسمي اولا ثم البدلاء
    for p in [primary] + secondary:
        if not p: continue
        try:
            res = await client_ai.chat.completions.create(
                model="gpt-4o",
                messages=msgs,
                api_key=api_key if p == primary else None,
                provider=p,
                image=image_data,
                timeout=35
            )
            if res and res.choices:
                out = res.choices[0].message.content.strip()
                # حفظ السياق لتعميق الذاكرة (اخر 12 رسالة)
                context[u_id] = (context[u_id] + [{"role":"user","content":prompt}, {"role":"assistant","content":out}])[-12:]
                return out
        except:
            continue
    return None

# --- لوحة تحكم المطورين (أوامر الإدارة) ---

@app.on_message(filters.regex(r"^(قفل الذكاء|فتح الذكاء)$") & filters.user(SUDO_USERS))
async def toggle_ai_engine(_, m: Message):
    global AI_STATUS
    AI_STATUS = "فتح" in m.text
    await m.reply_text(f"تم تنفيذ امر {'تشغيل' if AI_STATUS else 'ايقاف'} محرك المعالجة بنجاح.")

@app.on_message(filters.regex(r"^(قفل الليمت|فتح الليمت)$") & filters.user(SUDO_USERS))
async def toggle_limit_logic(_, m: Message):
    global LIMIT_STATUS
    LIMIT_STATUS = "فتح" in m.text
    await m.reply_text(f"تم {'تفعيل' if LIMIT_STATUS else 'تعطيل'} نظام الرقابة على حدود الاستهلاك.")

@app.on_message(filters.regex(r"^وضع ليميت (\d+)$") & filters.user(SUDO_USERS))
async def update_limit_value(_, m: Message):
    global DAILY_LIMIT
    DAILY_LIMIT = int(m.matches[0].group(1))
    await m.reply_text(f"تم ضبط الحد الاقصى للاستهلاك اليومي عند {DAILY_LIMIT} رسالة.")

@app.on_message(filters.regex(r"^تغيير المود (تقني|عام)$") & filters.user(SUDO_USERS))
async def switch_ai_mode(_, m: Message):
    global AI_MODE
    AI_MODE = m.matches[0].group(1)
    await m.reply_text(f"تم تغيير نمط الاستجابة للمحرك الى النمط: {AI_MODE}.")

@app.on_message(filters.regex(r"^(تنظيف الذاكرة|فحص المحرك)$") & filters.user(SUDO_USERS))
async def diagnostics_handler(_, m: Message):
    if "تنظيف" in m.text:
        context.clear()
        counter.clear()
        await m.reply_text("تمت تصفية سجلات المعالجة وذاكرة السياق بالكامل.")
    else:
        api_check = "مفعل" if os.getenv("GPT_4") else "غير متوفر"
        active_p = len([p for p in [get_provider("OpenaiChat"), get_provider("Liaobots"), get_provider("Blackbox")] if p])
        await m.reply_text(f"تقرير حالة النظام:\n- الربط الرسمي: {api_check}\n- المزودين النشطين: {active_p}\n- النمط الحالي: {AI_MODE}\n- حد الاستهلاك: {DAILY_LIMIT}")

# --- معالج الرسائل الرئيسي ---

@app.on_message((filters.text | filters.photo) & ~filters.bot, group=AI_GROUP)
async def ai_master_handler(bot, m: Message):
    if not AI_STATUS and m.from_user.id not in SUDO_USERS: return
    
    uid, raw = m.from_user.id, (m.text or m.caption or "")
    match = re.match(r"^(ذكاء|ai|شات|بوت|bot|يا ذكاء)(\s|$)", raw, re.IGNORECASE)
    if not match: return

    # تدقيق حدود الاستخدام
    now = time.time()
    if uid not in counter: counter[uid] = []
    counter[uid] = [t for t in counter[uid] if now - t < 86400]
    
    if LIMIT_STATUS and len(counter[uid]) >= DAILY_LIMIT and uid not in SUDO_USERS:
        return await m.reply_text(f"لقد استنفدت حصتك اليومية المحددة بـ {DAILY_LIMIT} سؤال.")

    prompt = raw[match.end():].strip()
    if not prompt and not m.photo: return

    path = await m.download() if m.photo else None
    await bot.send_chat_action(m.chat.id, enums.ChatAction.TYPING)
    
    status_msg = await m.reply_text("يتم الآن معالجة الطلب برمجيا")
    start_t = time.time()
    
    ans = await process_ai_logic(uid, prompt, path)
    if path: os.remove(path)
        
    if ans:
        counter[uid].append(time.time())
        await status_msg.edit(f"{ans}\n\nزمن المعالجة: {round(time.time()-start_t, 1)} ثانية")
    else:
        await status_msg.edit("فشل المحرك في توليد استجابة منطقية حاليا.")
