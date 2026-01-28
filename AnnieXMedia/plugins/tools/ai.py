# تم التطوير بواسطة الزملاء المبرمجين 2026
# محرك الذكاء الاصطناعي الفائق - نسخة Gemini 2.0 Flash النووية
# النظام: رد وتعديل فوري | لغة عربية فصحى | حفظ حالة دائم (Persistence)

import asyncio
import os
import re
import json
import logging
from datetime import datetime
from collections import deque
from typing import Optional

# استخدم SDK الجديد الرسمي (آسنك)
from google.genai import Client, types

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
if not GEMINI_KEY:
    logger.error("خطأ فادح: لم يتم العثور على مفتاح GEMINI_API_KEY في السكرتس. AI سيتم تعطيله مؤقتاً.")
    aio_client = None
else:
    try:
        aio_client = Client(api_key=GEMINI_KEY).aio
    except Exception as e:
        aio_client = None
        logger.exception("فشل إنشاء عميل google-genai الآسنك: %s", e)

# نحتفظ باسم الموديل كما طلبت (gemini-2.0-flash)
MODEL_ID = getattr(config, "GEMINI_MODEL_ID", "gemini-2.0-flash")

# --- متغيرات التحكم والذاكرة العميقة ---
SUDO_USERS = OWNER_ID if isinstance(OWNER_ID, list) else [OWNER_ID]
AI_STATUS = True
LIMIT_STATUS = True
DAILY_LIMIT = 150
AI_MODE = "عام"

# ذاكرة المحادثات: لكل مستخدم deque بطول أقصى 50 عنصر (role, text)
user_contexts = {}            # uid -> deque([('user', text), ('assistant', text), ...], maxlen=50)
user_usage = {}               # {uid: {"count": 0, "date": "YYYY-MM-DD"}}
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
            DAILY_LIMIT = state.get("DAILY_LIMIT", DAILY_LIMIT)
            AI_STATUS = state.get("AI_STATUS", AI_STATUS)
            LIMIT_STATUS = state.get("LIMIT_STATUS", LIMIT_STATUS)
            AI_MODE = state.get("AI_MODE", AI_MODE)
            logger.info("تمت استعادة حالة النظام بالكامل.")
        except Exception as e:
            logger.error(f"فشل استعادة الحالة: {e}")

def save_system_state():
    """حفظ إعدادات النظام الحالية في ملف JSON لضمان عدم ضياعها"""
    try:
        os.makedirs(os.path.dirname(STATE_FILE) or ".", exist_ok=True)
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
async def generate_ai_response(u_id: int, prompt: str, img_path: Optional[str] = None) -> Optional[str]:
    """
    إرسال الطلب لمحرك Gemini (google-genai async) ومعالجة الرد مع الحفاظ على السياق.
    نحافظ على سجل محادثة لكل مستخدم (حتى 50 إدخال).
    """
    if aio_client is None:
        logger.error("لا يوجد عميل GenAI مهيأ. تأكد من وجود GEMINI_API_KEY.")
        return None

    # تأكد من وجود سجل deque للمستخدم
    if u_id not in user_contexts:
        user_contexts[u_id] = deque(maxlen=50)

    history = user_contexts[u_id]

    # صياغة الـ system instruction كما طلبت
    system_instruction = (
        "أنت مساعد ذكي متمكن جداً، تتحدث اللغة العربية الفصحى بأسلوب مباشر وراقٍ. "
        "قدم إجابات مطولة، شاملة، ومنظمة جيداً. تجنب الاختصار المخل. "
        "لا تستخدم الرموز التعبيرية (Emojis) بتاتاً."
    )
    if AI_MODE == "تقني":
        system_instruction = "أنت كبير مهندسي برمجيات، اشرح الحلول التقنية بدقة هندسية عالية وبالفصحى."

    try:
        # أضف رسالة المستخدم إلى السجل
        history.append(('user', prompt))

        # بناء نص محادثة مبسط من السجل
        convo_parts = []
        for role, txt in history:
            if role == 'user':
                convo_parts.append(f"المستخدم: {txt}")
            else:
                convo_parts.append(f"المساعد: {txt}")
        convo_text = "\n\n".join(convo_parts)

        full_query = f"{system_instruction}\n\n{convo_text}\n\nالمطلوب: "

        # في حال وجود صورة، نضيف ملاحظة (تم تجنب رفع الصورة نفسها هنا)
        if img_path:
            full_query += "\n(ملاحظة: تم إرفاق صورة مع الطلب — فسّرها أو دوّن ملاحظات عنها إذا لزم.)"

        # استدعاء GenAI الآسنك
        response = await aio_client.models.generate_content(
            model=MODEL_ID,
            contents=full_query,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.3,
                max_output_tokens=1024,
            ),
        )

        # الحصول على النص من الـ response
        text = getattr(response, "text", None)
        if not text:
            # إذا لم يكن هناك text، نجمع الأجزاء إن وُجدت
            parts = getattr(response, "parts", None) or []
            collected = []
            for p in parts:
                t = getattr(p, "text", None)
                if t:
                    collected.append(t)
            text = "\n".join(collected).strip() if collected else None

        if not text:
            logger.error("لم يصل نص من مولد Gemini.")
            return None

        # أضف رد المساعد إلى السجل
        history.append(('assistant', text))

        # deque يضمن بحد ذاته ألا يزيد الطول عن 50
        return text.strip()

    except Exception as e:
        logger.error(f"خطأ في استجابة Gemini: {e}")
        return None

# --- لوحة التحكم الإدارية (للمطورين فقط - بدون سلاش) ---
# (الأوامر والنصوص كما في الملف الأصلي بالضبط)

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
    try:
        DAILY_LIMIT = int(re.search(r"(\d+)", m.text).group(1))
        save_system_state()
        await m.reply_text(f"تم تحديث سقف الاستخدام اليومي ليصبح {DAILY_LIMIT} رسالة.")
    except Exception:
        await m.reply_text("خطأ في قراءة القيمة. استخدم: وضع ليميت 150")

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
    g = re.search(r"(تقني|عام)", m.text)
    if g:
        AI_MODE = g.group(1)
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

    uid = m.from_user.id
    raw_text = (m.text or m.caption or "")

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
    path = None
    if m.photo:
        try:
            path = await m.download()
        except Exception:
            path = None

    # 1. إرسال إشعار الانتظار الفوري كـ Reply
    try:
        status_msg = await m.reply_text("جـاري الـتـفكير ....", quote=True)
    except Exception:
        status_msg = await m.reply_text("جـاري الـتـفكير ....")
    await bot.send_chat_action(m.chat.id, enums.ChatAction.TYPING)

    # 2. بدء المعالجة عبر Gemini
    answer = await generate_ai_response(uid, prompt, path)
    # تنظيف ملف الصورة لو تم تحميله
    if path:
        try:
            os.remove(path)
        except Exception:
            pass

    # 3. التعديل النهائي لرسالة الانتظار بالرد الفصيح
    if answer:
        user_usage[uid]["count"] += 1
        try:
            await status_msg.edit(answer)
        except Exception:
            await m.reply_text(answer)
    else:
        try:
            await status_msg.edit("نعتذر، واجه محرك الذكاء صعوبة في الاستجابة حالياً، يرجى المحاولة لاحقاً.")
        except Exception:
            await m.reply_text("نعتذر، واجه محرك الذكاء صعوبة في الاستجابة حالياً، يرجى المحاولة لاحقاً.")

# --- وظيفة الحفظ الدوري التلقائي للحالة ---
async def auto_save_task():
    while True:
        await asyncio.sleep(600) # حفظ كل 10 دقائق لضمان الأمان
        save_system_state()

# schedule autosave task
try:
    asyncio.get_event_loop().create_task(auto_save_task())
except RuntimeError:
    # إذا لم تكن هناك حلقة حدث عند وقت الاستيراد، حاول جدولة لاحقاً
    def _defer():
        loop = asyncio.get_event_loop()
        loop.create_task(auto_save_task())
    try:
        asyncio.get_event_loop_policy().get_event_loop().call_soon_threadsafe(_defer)
    except Exception:
        # كحل أخير تجاهل، سيتم البدء عند تشغيل التطبيق
        pass
