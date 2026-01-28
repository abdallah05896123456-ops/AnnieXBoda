# تم التطوير بواسطة الزملاء المبرمجين 2026
# محرك الذكاء الاصطناعي الفائق - Gemini (google-genai async)
# النظام: رد وتعديل فوري | لغة عربية فصحى | حفظ حالة دائم (Persistence)
# يحافظ على نفس أوامر الملف الأصلي ونصوص الردود بالعربية

import asyncio
import os
import re
import json
import time
import logging
from datetime import datetime
from collections import deque, defaultdict
from typing import Optional

from pyrogram import filters, enums
from pyrogram.types import Message

from AnnieXMedia import app
import config
from config import OWNER_ID, AI_HANDLER_GROUP

# official new SDK (async)
from google.genai import Client, types

# -------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AnnieX_AI_Core")

# -------------------------
# Read API key (ENV preferred, fallback to config)
GEMINI_KEY = os.getenv("GEMINI_API_KEY") or getattr(config, "GEMINI_API_KEY", None)
if not GEMINI_KEY:
    logger.error("GEMINI_API_KEY غير موجود — سيتم تعطيل AI حتى توفر المفتاح.")
    aio_client = None
else:
    try:
        aio_client = Client(api_key=GEMINI_KEY).aio
    except Exception as e:
        aio_client = None
        logger.exception("فشل إنشاء عميل google-genai الآسنك: %s", e)

# Default model (kept name as requested; you can change via config)
MODEL_ID = getattr(config, "GEMINI_MODEL_ID", "gemini-2.0-flash")

# -------------------------
# Runtime settings & persistence
SUDO_USERS = OWNER_ID if isinstance(OWNER_ID, list) else [OWNER_ID]
AI_STATUS = True
LIMIT_STATUS = True
DAILY_LIMIT = getattr(config, "AI_DAILY_LIMIT", 150)
AI_MODE = "عام"

user_contexts = {}        # uid -> deque([('user', text), ('assistant', text), ...], maxlen=50)
user_usage = {}           # uid -> {"count": int, "date": "YYYY-MM-DD"}
PERMANENT_USERS = set()
STATE_FILE = "ai_data/ai_master_state.json"

# in-memory lightweight rate-limits and cooldowns
_user_min_interval = defaultdict(float)   # uid -> last request timestamp
_global_last_call = 0.0
_global_cooldown = 1.0    # seconds, adaptive (increased on RESOURCE_EXHAUSTED)
MIN_USER_INTERVAL = 0.5   # seconds between user's consecutive AI calls to avoid abuse
DEFAULT_COOLDOWN_ON_QUOTA = 30  # if we detect quota, start with this

# -------------------------
def load_system_state():
    global PERMANENT_USERS, DAILY_LIMIT, AI_STATUS, LIMIT_STATUS, AI_MODE
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                s = json.load(f)
            PERMANENT_USERS = set(s.get("PERMANENT_USERS", []))
            DAILY_LIMIT = s.get("DAILY_LIMIT", DAILY_LIMIT)
            AI_STATUS = s.get("AI_STATUS", AI_STATUS)
            LIMIT_STATUS = s.get("LIMIT_STATUS", LIMIT_STATUS)
            AI_MODE = s.get("AI_MODE", AI_MODE)
            logger.info("تمت استعادة حالة النظام من الملف.")
        except Exception as e:
            logger.exception("فشل استعادة الحالة: %s", e)

def save_system_state():
    try:
        os.makedirs(os.path.dirname(STATE_FILE) or ".", exist_ok=True)
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "PERMANENT_USERS": list(PERMANENT_USERS),
                "DAILY_LIMIT": DAILY_LIMIT,
                "AI_STATUS": AI_STATUS,
                "LIMIT_STATUS": LIMIT_STATUS,
                "AI_MODE": AI_MODE
            }, f, ensure_ascii=False, indent=2)
    except Exception:
        logger.exception("فشل حفظ حالة النظام")

load_system_state()

# -------------------------
SYSTEM_GENERAL = (
    "أنت مساعد ذكي متمكن جداً، تتحدث اللغة العربية الفصحى بأسلوب مباشر وراقٍ. "
    "قدم إجابات مطولة، شاملة، ومنظمة جيداً. تجنب الاختصار المخل. "
    "لا تستخدم الرموز التعبيرية (Emojis) بتاتاً."
)
SYSTEM_TECH = "أنت كبير مهندسي برمجيات، اشرح الحلول التقنية بدقة هندسية عالية وبالفصحى."

# -------------------------
def _parse_retry_seconds_from_exc(exc_str: str) -> Optional[int]:
    """
    محاولة استخراج قيمة retryDelay مثل '42s' من النص.
    """
    try:
        m = re.search(r"retryDelay(?:'|\":\\s*)'?(?P<t>\\d+)(?:s)?", exc_str, re.IGNORECASE)
        if m:
            return int(m.group("t"))
    except Exception:
        pass
    # fall back: search any '(\d+)s' pattern near 'retry'
    try:
        m2 = re.search(r"retryDelay.*?(\\d+)s", exc_str, re.IGNORECASE)
        if m2:
            return int(m2.group(1))
    except Exception:
        pass
    # last resort: find first number followed by 's'
    m3 = re.search(r"(\\d+)s", exc_str)
    if m3:
        try:
            return int(m3.group(1))
        except Exception:
            return None
    return None

# -------------------------
async def generate_ai_response(u_id: int, prompt: str, img_path: Optional[str] = None) -> Optional[str]:
    """
    إرسال الطلب لمولد Gemini عبر google-genai async client.
    يتضمن:
    - حماية ضد السبام (global + per-user interval)
    - تعامل ذكي مع RESOURCE_EXHAUSTED (429) واستخراج retryDelay
    - حفظ السياق (deque بحد 50)
    - إرجاع نص الرد أو None
    """
    global _global_last_call, _global_cooldown

    if aio_client is None:
        logger.error("عميل GenAI غير مهيأ (GEMINI_API_KEY مفقود أو خطأ في الإنشاء).")
        return None

    now = time.time()

    # per-user micro-rate-limit to avoid accidental spam
    last_user = _user_min_interval.get(u_id, 0.0)
    if now - last_user < MIN_USER_INTERVAL:
        # quick polite message so user doesn't wait forever
        return "⏳ رجاءً انتظر لحظة ثم حاول مرة أخرى."

    _user_min_interval[u_id] = now

    # global cooldown (adaptive)
    if now - _global_last_call < _global_cooldown:
        wait_time = int(_global_cooldown - (now - _global_last_call))
        return f"⏳ تم الوصول لمعدل الاستعلامات. الرجاء الانتظار {wait_time} ثانية وإعادة المحاولة."

    # prepare conversation context
    if u_id not in user_contexts:
        user_contexts[u_id] = deque(maxlen=50)
    history = user_contexts[u_id]

    # add user message to history
    history.append(('user', prompt))

    # build conversation text to send (simple deterministic formatting)
    convo_parts = []
    for role, text in history:
        label = "المستخدم" if role == 'user' else "المساعد"
        convo_parts.append(f"{label}: {text}")
    convo_text = "\n\n".join(convo_parts)

    system_instruction = SYSTEM_TECH if AI_MODE == "تقني" else SYSTEM_GENERAL
    full_query = f"{system_instruction}\n\n{convo_text}\n\nالمطلوب: "
    if img_path:
        full_query += "\n(ملاحظة: تم إرفاق صورة مع الطلب — فسّرها أو دوّن ملاحظات عنها إذا لزم.)"

    # mark the last call time immediately to avoid races
    _global_last_call = now

    try:
        response = await aio_client.models.generate_content(
            model=MODEL_ID,
            contents=full_query,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.3,
                max_output_tokens=1024,
            ),
        )
        text = getattr(response, "text", None)
        if not text:
            parts = getattr(response, "parts", None) or []
            collected = []
            for p in parts:
                t = getattr(p, "text", None)
                if t:
                    collected.append(t)
            text = "\n".join(collected).strip() if collected else None

        if not text:
            logger.error("لم يصل نص من مولد Gemini (رد فارغ).")
            return None

        # append assistant reply to history
        history.append(('assistant', text))

        return text.strip()

    except Exception as exc:
        exc_str = str(exc)
        logger.error("خطأ في استجابة Gemini: %s", exc_str)

        # detect quota / 429 / RESOURCE_EXHAUSTED
        if "RESOURCE_EXHAUSTED" in exc_str or "429" in exc_str or "quota" in exc_str.lower():
            retry_sec = _parse_retry_seconds_from_exc(exc_str) or DEFAULT_COOLDOWN_ON_QUOTA
            # set adaptive global cooldown so next calls wait
            _global_cooldown = max(_global_cooldown, retry_sec, DEFAULT_COOLDOWN_ON_QUOTA)
            logger.warning("Detected quota exhaustion. Setting global cooldown to %s seconds.", _global_cooldown)
            return f"🚫 تم تجاوز حصة الاستخدام لمولد الذكاء الاصطناعي. الرجاء المحاولة بعد {retry_sec} ثانية."
        # other errors -> return None so handler shows generic error message
        return None

# -------------------------
# Admin commands (same triggers and texts as original)
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

# -------------------------
@app.on_message(filters.regex(r"^مسح محادثتي$") & ~filters.bot)
async def user_clear_context(_, m: Message):
    uid = m.from_user.id
    if uid in user_contexts:
        del user_contexts[uid]
        await m.reply_text("تم مسح سجل محادثتك معي بنجاح، يمكنك بدء حوار جديد الآن.")
    else:
        await m.reply_text("لا يوجد سجل محادثات نشط خاص بك حالياً.")

# -------------------------
@app.on_message((filters.text | filters.photo) & ~filters.bot, group=AI_HANDLER_GROUP)
async def central_ai_handler(bot, m: Message):
    if not AI_STATUS and m.from_user.id not in SUDO_USERS:
        return

    uid = m.from_user.id
    raw_text = (m.text or m.caption or "").strip()

    is_perm = uid in PERMANENT_USERS
    match = re.match(r"^(ذكاء|بقولك)(\s|$)", raw_text, re.IGNORECASE)

    if not is_perm and not match:
        return

    # extract prompt
    prompt = raw_text[match.end():].strip() if (match and not is_perm) else raw_text
    if not prompt and not m.photo:
        prompt = "أهلاً بك، أنا استمع إليك."

    # daily usage reset bookkeeping
    today = datetime.now().strftime("%Y-%m-%d")
    if uid not in user_usage or user_usage[uid].get("date") != today:
        user_usage[uid] = {"count": 0, "date": today}

    if LIMIT_STATUS and user_usage[uid]["count"] >= DAILY_LIMIT and uid not in SUDO_USERS:
        return await m.reply_text(f"نعتذر، لقد استنفدت حصتك اليومية المحددة بـ {DAILY_LIMIT} رسالة.")

    # download image if any (temporary)
    img_path = None
    if m.photo:
        try:
            img_path = await m.download()
        except Exception:
            img_path = None

    # immediate waiting message
    try:
        status_msg = await m.reply_text("جـاري الـتـفكير ....", quote=True)
    except Exception:
        status_msg = await m.reply_text("جـاري الـتـفكير ....")

    await bot.send_chat_action(m.chat.id, enums.ChatAction.TYPING)

    # call generator
    answer = await generate_ai_response(uid, prompt, img_path)

    # cleanup image
    if img_path:
        try:
            os.remove(img_path)
        except Exception:
            pass

    if answer is None:
        # generic error (no specific message)
        try:
            await status_msg.edit("نعتذر، واجه محرك الذكاء صعوبة في الاستجابة حالياً، يرجى المحاولة لاحقاً.")
        except Exception:
            await m.reply_text("نعتذر، واجه محرك الذكاء صعوبة في الاستجابة حالياً، يرجى المحاولة لاحقاً.")
        return

    # if answer contains immediate cooldown message string we return it directly
    try:
        # increment usage only for real generated answers (not cooldown strings)
        if not answer.startswith("⏳") and not answer.startswith("🚫"):
            user_usage[uid]["count"] += 1
            await status_msg.edit(answer)
        else:
            # return the message as-is (cooldown / quota info)
            await status_msg.edit(answer)
    except Exception:
        try:
            await m.reply_text(answer)
        except Exception:
            pass

# -------------------------
# autosave persistence loop
async def _autosave_loop():
    while True:
        try:
            save_system_state()
        except Exception:
            logger.exception("Autosave failed")
        await asyncio.sleep(600)

# schedule autosave safely
try:
    asyncio.get_event_loop().create_task(_autosave_loop())
except RuntimeError:
    # if no running loop at import time, schedule to start later
    def _schedule_autosave_later():
        try:
            loop = asyncio.get_event_loop()
            loop.create_task(_autosave_loop())
        except Exception:
            pass
    try:
        asyncio.get_event_loop_policy().get_event_loop().call_soon_threadsafe(_schedule_autosave_later)
    except Exception:
        # fallback: ignore, it will start when app loop is active
        pass

# -------------------------
# End of ai.py
