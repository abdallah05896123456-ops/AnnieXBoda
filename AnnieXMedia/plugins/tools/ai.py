# تم التطوير بواسطة الزملاء المبرمجين 2026
# محرك الذكاء الاصطناعي الفائق - نسخة Gemini 2.0 Flash النووية
# النظام: رد وتعديل فوري | لغة عربية فصحى | حفظ حالة دائم (Persistence)

import asyncio
import os
import time
import re
import json
import logging
from datetime import datetime
from collections import deque

import google.generativeai as genai
from pyrogram import filters, enums
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup

from AnnieXMedia import app
import config
from config import OWNER_ID, AI_HANDLER_GROUP

# --- إعدادات السجلات والتقارير ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AnnieX_AI_Core")

# --- تهيئة المحرك وربط المفتاح السري ---
# يتم سحب المفتاح من السكرتس GEMINI_API_KEY أو من ملف config.py
GEMINI_KEY = os.getenv("GEMINI_API_KEY") or getattr(config, "GEMINI_API_KEY", None)
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)
else:
    logger.error("خطأ فادح: لم يتم العثور على مفتاح GEMINI_API_KEY في السكرتس.")

# استخدام موديل Gemini 2.0 Flash الأحدث والأسرع عالمياً
model = genai.GenerativeModel('gemini-2.0-flash')

# --- متغيرات التحكم والذاكرة العميقة ---
SUDO_USERS = OWNER_ID if isinstance(OWNER_ID, list) else [OWNER_ID]
AI_STATUS = True
LIMIT_STATUS = True
DAILY_LIMIT = 150
AI_MODE = "عام" 

# ذاكرة المحادثات (حفظ سياق يصل لـ 50 رسالة لكل مستخدم)
user_contexts = {}
user_usage = {} # {uid: {"count": 0, "date": "YYYY-MM-DD"}}
PERMANENT_USERS = set() 
STATE_FILE = "ai_data/ai_master_state.json"

# --- وظائف إدارة البيانات وحفظ الحالة (Persistence) ---
def load_system_state():
    """استعادة إعدادات النظام وقائمة المستخدمين الدائمين من الملف"""
    global PERMANENT_USERS, DAILY_LIMIT, AI_STATUS, LIMIT_STATUS, AI_MODE
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)
            PERMANENT_USERS = set(state.get("PERMANENT_USERS", []))
            DAILY_LIMIT = state.get("DAILY_LIMIT", 150)
            AI_STATUS = state.get("AI_STATUS", True)
            LIMIT_STATUS = state.get("LIMIT_STATUS", True)
            AI_MODE = state.get("AI_MODE", "عام")
            logger.info("تمت استعادة حالة النظام بالكامل.")
        except Exception as e:
            logger.error(f"فشل استعادة الحالة: {e}")

def save_system_state():
    """حفظ إعدادات النظام الحالية في ملف JSON لضمان عدم ضياعها"""
    os.makedirs("ai_data", exist_ok=True)
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "PERMANENT_USERS": list(PERMANENT_USERS),
                "DAILY_LIMIT": DAILY_LIMIT,
                "AI_STATUS": AI_STATUS,
                "LIMIT_STATUS": LIMIT_STATUS,
                "AI_MODE": AI_MODE
            }, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logger.error(f"فشل حفظ حالة النظام: {e}")

load_system_state()

# --- محرك المعالجة والاستنتاج ---
async def generate_ai_response(u_id, prompt, img_path=None):
    """إرسال الطلب لمحرك Gemini ومعالجة الرد مع الحفاظ على السياق"""
    if u_id not in user_contexts:
        user_contexts[u_id] = model.start_chat(history=[])
    
    chat = user_contexts[u_id]
    
    # صياغة التعليمات البرمجية لنبرة الصوت (لغة فصحى راقية)
    system_instruction = (
        "أنت مساعد ذكي متمكن جداً، تتحدث اللغة العربية الفصحى بأسلوب مباشر وراقٍ. "
        "قدم إجابات مطولة، شاملة، ومنظمة جيداً. تجنب الاختصار المخل. "
        "لا تستخدم الرموز التعبيرية (Emojis) بتاتاً."
    )
    if AI_MODE == "تقني":
        system_instruction = "أنت كبير مهندسي برمجيات، اشرح الحلول التقنية بدقة هندسية عالية وبالفصحى."

    try:
        full_query = f"{system_instruction}\n\nالمستخدم يسأل: {prompt}"
        
        if img_path:
            from PIL import Image
            img = Image.open(img_path)
            # Gemini 2.0 Flash يعالج النصوص والصور بسرعة فائقة في طلب واحد
            response = await asyncio.to_thread(model.generate_content, [full_query, img])
        else:
            response = await asyncio.to_thread(chat.send_message, full_query)
            
        # تقليم السياق لـ 50 رسالة فقط لتوفير موارد السيرفر
        if len(chat.history) > 50:
            chat.history = chat.history[-50:]
            
        return response.text.strip()
    except Exception as e:
        logger.error(f"خطأ في استجابة Gemini: {e}")
        return None

# --- لوحة التحكم الإدارية (للمطورين فقط - بدون سلاش) ---

@app.on_message(filters.regex(r"^(قفل الذكاء|فتح الذكاء)$") & filters.user(SUDO_USERS))
async def admin_toggle_ai(_, m: Message):
    global AI_STATUS
    AI_STATUS = "فتح" in m.text
    save_system_state()
    await m.reply_text(f"تم تنفيذ أمر المطور: {'تشغيل' if AI_STATUS else 'إيقاف'} الذكاء الاصطناعي.")

@app.on_message(filters.regex(r"^(فتح الليمت|قفل الليمت)$") & filters.user(SUDO_USERS))
async def admin_toggle_limit(_, m: Message):
    global LIMIT_STATUS
    LIMIT_STATUS = "فتح" in m.text
    save_system_state()
    await m.reply_text(f"تم {'تفعيل' if LIMIT_STATUS else 'تعطيل'} نظام الحد اليومي للرسائل.")

@app.on_message(filters.regex(r"^وضع ليميت (\d+)$") & filters.user(SUDO_USERS))
async def admin_set_limit(_, m: Message):
    global DAILY_LIMIT
    DAILY_LIMIT = int(m.matches[0].group(1))
    save_system_state()
    await m.reply_text(f"تم تحديث سقف الاستخدام اليومي ليصبح {DAILY_LIMIT} رسالة.")

@app.on_message(filters.regex(r"^(فتح|قفل) الذكاء الدائم$") & filters.user(SUDO_USERS))
async def admin_permanent_user(_, m: Message):
    if not m.reply_to_message:
        return await m.reply_text("عليك الرد على رسالة الشخص المستهدف لتفعيل الذكاء الدائم له.")
    uid = m.reply_to_message.from_user.id
    if "فتح" in m.text:
        PERMANENT_USERS.add(uid)
    else:
        PERMANENT_USERS.discard(uid)
    save_system_state()
    await m.reply_text(f"تم تحديث صلاحيات المستخدم {uid}. الحالة الدائمة: {'مفعلة' if uid in PERMANENT_USERS else 'معطلة'}.")

@app.on_message(filters.regex(r"^تغيير المود (تقني|عام)$") & filters.user(SUDO_USERS))
async def admin_switch_mode(_, m: Message):
    global AI_MODE
    AI_MODE = m.matches[0].group(1)
    save_system_state()
    await m.reply_text(f"تم ضبط نبرة ردود المحرك على النمط الـ{AI_MODE}.")

@app.on_message(filters.regex(r"^(تنظيف الذاكرة|حالة الذكاء)$") & filters.user(SUDO_USERS))
async def admin_diagnostic(_, m: Message):
    if "تنظيف" in m.text:
        user_contexts.clear()
        user_usage.clear()
        await m.reply_text("تم تصفير سجلات الحوار وتفريغ ذاكرة الوصول العشوائي.")
    else:
        await m.reply_text(
            f"📊 تقرير النظام الحالي:\n"
            f"- الحالة العامة: {'نشط' if AI_STATUS else 'متوقف'}\n"
            f"- نمط الرد: {AI_MODE}\n"
            f"- الحد اليومي: {DAILY_LIMIT}\n"
            f"- المستخدمين الدائمين: {len(PERMANENT_USERS)}"
        )

# --- أوامر المستخدمين العادية ---

@app.on_message(filters.regex(r"^مسح محادثتي$") & ~filters.bot)
async def user_clear_context(_, m: Message):
    uid = m.from_user.id
    if uid in user_contexts:
        del user_contexts[uid]
        await m.reply_text("تم مسح سجل محادثتك معي بنجاح، يمكنك بدء حوار جديد الآن.")
    else:
        await m.reply_text("لا يوجد سجل محادثات نشط خاص بك حالياً.")

# --- المعالج المركزي (نظام الرد والتعديل الفوري) ---

@app.on_message((filters.text | filters.photo) & ~filters.bot, group=AI_HANDLER_GROUP)
async def central_ai_handler(bot, m: Message):
    if not AI_STATUS and m.from_user.id not in SUDO_USERS:
        return
    
    uid, raw_text = m.from_user.id, (m.text or m.caption or "")
    
    # فحص حالة المناداة أو الذكاء الدائم
    is_perm = uid in PERMANENT_USERS
    match = re.match(r"^(ذكاء|بقولك)(\s|$)", raw_text, re.IGNORECASE)
    
    if not is_perm and not match:
        return

    # استخلاص نص السؤال
    prompt = raw_text[match.end():].strip() if (match and not is_perm) else raw_text
    if not prompt and not m.photo:
        prompt = "أهلاً بك، أنا استمع إليك."

    # تدقيق ليميت الاستهلاك اليومي
    today = datetime.now().strftime("%Y-%m-%d")
    if uid not in user_usage or user_usage[uid].get("date") != today:
        user_usage[uid] = {"count": 0, "date": today}

    if LIMIT_STATUS and user_usage[uid]["count"] >= DAILY_LIMIT and uid not in SUDO_USERS:
        return await m.reply_text(f"نعتذر، لقد استنفدت حصتك اليومية المحددة بـ {DAILY_LIMIT} رسالة.")

    # معالجة الصور إن وجدت
    path = await m.download() if m.photo else None
    
    # 1. إرسال إشعار الانتظار الفوري كـ Reply
    status_msg = await m.reply_text("جـاري الـتـفكير ....", quote=True)
    await bot.send_chat_action(m.chat.id, enums.ChatAction.TYPING)
    
    # 2. بدء المعالجة عبر Gemini 2.0 Flash
    answer = await generate_ai_response(uid, prompt, path)
    if path: os.remove(path)
        
    # 3. التعديل النهائي لرسالة الانتظار بالرد الفصيح
    if answer:
        user_usage[uid]["count"] += 1
        await status_msg.edit(answer)
    else:
        await status_msg.edit("نعتذر، واجه محرك الذكاء صعوبة في الاستجابة حالياً، يرجى المحاولة لاحقاً.")

# --- وظيفة الحفظ الدوري التلقائي للحالة ---
async def auto_save_task():
    while True:
        await asyncio.sleep(600) # حفظ كل 10 دقائق لضمان الأمان
        save_system_state()

asyncio.get_event_loop().create_task(auto_save_task())
