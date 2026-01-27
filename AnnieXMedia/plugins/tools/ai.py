# plugins/ai.py
# AnnieXMedia - AI core rebuilt (model fallback + owner commands fixed)
# باللغة العربية الفصحى، أوامر بدون سلاش، سياق حتى 50 رسالة، صف/retry/semaphore.

import os
import re
import json
import asyncio
import logging
from typing import Dict, List, Optional
from collections import deque, defaultdict
from datetime import date
from pyrogram import filters
from pyrogram.types import Message
from openai import AsyncOpenAI, OpenAIError

from AnnieXMedia import app
import config

# -------------------- إعداد السجل --------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ai_core")

# -------------------- تحميل السكرتس من البيئة --------------------
OPENAI_KEY = os.getenv("OPENAI_API_KEY") or getattr(config, "AI_API_KEY", None)
OWNER_ENV = os.getenv("OWNER_ID") or getattr(config, "OWNER_ID", None)
try:
    OWNER_ID = int(OWNER_ENV) if OWNER_ENV is not None else None
except Exception:
    OWNER_ID = None

if OWNER_ID is None:
    logger.error("OWNER_ID غير مهيأ. ضع OWNER_ID في متغيرات البيئة أو في config.py")

# -------------------- نماذج مرشحة - يمكن تغييره عبر AI_MODEL_CANDIDATES env --------------------
candidates_env = os.getenv("AI_MODEL_CANDIDATES", "")
if candidates_env:
    MODEL_CANDIDATES = [m.strip() for m in candidates_env.split(",") if m.strip()]
else:
    # ترتيب الأولوية: حاول gpt-4 ثم بدائل حديثة
    MODEL_CANDIDATES = ["gpt-4", "gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"]

ACTIVE_MODEL: Optional[str] = None

# -------------------- إعداد OpenAI client (يُعاد تهيئته عند تعيين مفتاح جديد) --------------------
openai_client: Optional[AsyncOpenAI] = AsyncOpenAI(api_key=OPENAI_KEY) if OPENAI_KEY else None

# -------------------- ضبط السلوك --------------------
MAX_CONTEXT = int(os.getenv("AI_MAX_CONTEXT", "50"))
DAILY_LIMIT_DEFAULT = int(os.getenv("DAILY_LIMIT", "150"))
MAX_CONCURRENT = int(os.getenv("AI_MAX_CONCURRENT", "4"))

MAX_RETRIES = 4
RETRY_TIMEOUT = 30

# -------------------- الذاكرة والحالة --------------------
contexts: Dict[int, deque] = defaultdict(lambda: deque(maxlen=MAX_CONTEXT))
daily_counts: Dict[int, int] = defaultdict(int)
daily_date: Dict[int, date] = defaultdict(lambda: date.today())
permanent_users: Dict[int, bool] = {}  # user_id -> True
user_mode: Dict[int, str] = defaultdict(lambda: "عام")  # "عام" أو "تقني"

AI_STATUS = True
LIMIT_STATUS = False
DAILY_LIMIT = DAILY_LIMIT_DEFAULT

DATA_DIR = os.path.join(os.path.dirname(__file__), "ai_data")
os.makedirs(DATA_DIR, exist_ok=True)
STATE_FILE = os.path.join(DATA_DIR, "state.json")


def mask_key(k: Optional[str]) -> str:
    if not k:
        return "<not set>"
    k = k.strip()
    if len(k) <= 10:
        return k[0:2] + "..." + k[-2:]
    return k[:6] + "..." + k[-4:]


def save_state():
    try:
        s = {
            "permanent_users": list(permanent_users.keys()),
            "daily_limit": DAILY_LIMIT,
            "ai_status": AI_STATUS,
            "limit_status": LIMIT_STATUS,
            "active_model": ACTIVE_MODEL,
            "openai_masked": mask_key(OPENAI_KEY),
        }
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(s, f, ensure_ascii=False, indent=2)
    except Exception:
        logger.exception("فشل حفظ الحالة")


def load_state():
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                s = json.load(f)
            for uid in s.get("permanent_users", []):
                try:
                    permanent_users[int(uid)] = True
                except:
                    pass
            # لا نستعيد المفتاح الكامل من الملف لأسباب أمنية
    except Exception:
        logger.exception("فشل تحميل الحالة")


load_state()

# -------------------- طابور ومعالج --------------------
_semaphore = asyncio.Semaphore(MAX_CONCURRENT)
pending_queue: asyncio.Queue = asyncio.Queue()


async def call_openai_model(messages: List[dict], model: str, timeout: int = RETRY_TIMEOUT):
    """
    استدعاء واحد لنموذج محدد (لا يتضمن retries).
    """
    global openai_client
    if not openai_client:
        raise RuntimeError("OpenAI client not configured")
    return await openai_client.chat.completions.create(model=model, messages=messages, timeout=timeout)


async def call_openai_with_fallback(messages: List[dict]) -> Optional[str]:
    """
    تجربة النماذج في MODEL_CANDIDATES حتى نجد نموذجاً يعمل.
    يحتفظ بـ ACTIVE_MODEL لاستخدامه لاحقًا.
    """
    global ACTIVE_MODEL
    last_err = None
    # إذا تم اختيار نموذج سابقاً، جربه أولاً
    tried = []
    if ACTIVE_MODEL:
        tried.append(ACTIVE_MODEL)
    for m in MODEL_CANDIDATES:
        if m in tried:
            continue
        tried.append(m)

    # أضف أي نموذج مرشح مذكور مسبقًا
    for model in tried:
        try:
            resp = await call_openai_model(messages, model)
            if resp and getattr(resp, "choices", None):
                ACTIVE_MODEL = model
                logger.info(f"تم تفعيل النموذج: {ACTIVE_MODEL}")
                return resp.choices[0].message.content.strip()
        except Exception as e:
            last_err = e
            logger.warning("فشل النموذج %s: %s", model, str(e))
            # استمر إلى النموذج التالي
            continue

    logger.error("فشلت كل النماذج: %s", str(last_err))
    return None


async def _call_with_retries(messages: List[dict], max_retries: int = MAX_RETRIES) -> Optional[str]:
    """
    واجهة retry عامة: تحاول call_openai_with_fallback مع backoff بسيط.
    """
    delay = 1.0
    for attempt in range(1, max_retries + 1):
        try:
            result = await call_openai_with_fallback(messages)
            if result is not None:
                return result
        except Exception as e:
            logger.exception("خطأ أثناء المحاولة %s: %s", attempt, e)
        await asyncio.sleep(delay)
        delay *= 2.0
    return None


async def worker():
    while True:
        job = await pending_queue.get()
        msg_obj, user_id, messages, status_msg = job
        try:
            async with _semaphore:
                result = await _call_with_retries(messages)
                if result is not None:
                    contexts[user_id].append({"role": "user", "content": messages[-1]["content"]})
                    contexts[user_id].append({"role": "assistant", "content": result})
                    # عدّاد يومي يُزاد بعد نجاح الرد
                    daily_counts[user_id] += 1
                    try:
                        await status_msg.edit_text(result)
                    except Exception:
                        try:
                            await msg_obj.reply_text(result)
                        except Exception:
                            logger.exception("فشل إرسال الرد للمستخدم %s", user_id)
                else:
                    try:
                        await status_msg.edit_text("نعتذر، المحرك لا يستجيب حالياً. يرجى إعادة المحاولة لاحقاً.")
                    except Exception:
                        pass
        except Exception:
            logger.exception("عامل الطابور حدث له خطأ")
            try:
                await status_msg.edit_text("حدث خطأ غير متوقع أثناء المعالجة.")
            except:
                pass
        finally:
            pending_queue.task_done()


asyncio.get_event_loop().create_task(worker())

# -------------------- اختيار النموذج عند التشغيل --------------------
async def probe_models_and_notify():
    """
    تحاول تفعيل أول نموذج يعمل من MODEL_CANDIDATES عند بدء التشغيل،
    وتعلم المالك إذا فشل التحقق.
    """
    global openai_client, ACTIVE_MODEL
    if not openai_client:
        logger.warning("لم يتم تهيئة عميل OpenAI بعد.")
        return

    test_msgs = [{"role": "system", "content": "test"}, {"role": "user", "content": "ping"}]
    ok = False
    for model in MODEL_CANDIDATES:
        try:
            resp = await call_openai_model(test_msgs, model, timeout=8)
            if resp and getattr(resp, "choices", None):
                ACTIVE_MODEL = model
                logger.info("النموذج المفعّل عند الإقلاع: %s", ACTIVE_MODEL)
                ok = True
                break
        except Exception as e:
            logger.warning("فشل اختبار النموذج %s: %s", model, e)
            continue

    if not ok:
        # إخطار المالك إن وُجد
        if OWNER_ID is not None:
            async def notify_owner():
                await asyncio.sleep(2)
                try:
                    await app.send_message(OWNER_ID,
                                           "تنبيه: تعذر تفعيل أي نموذج OpenAI من القائمة. يرجى التحقق من المفتاح وصلاحيات الحساب أو تعيين مفتاح جديد عبر الأمر: تعيين مفتاح AI <key>")
                except Exception:
                    logger.exception("فشل إشعار المالك")
            asyncio.get_event_loop().create_task(notify_owner())


# شغّل probe فور تحميل الموديول (لو المفتاح موجود)
if openai_client:
    asyncio.get_event_loop().create_task(probe_models_and_notify())

# -------------------- بناء الرسائل والسياق --------------------
def build_system_prompt(uid: int) -> str:
    mode = user_mode.get(uid, "عام")
    if mode == "تقني":
        return "أنت مساعد تقني، اشرح بمصطلحات هندسية دقيقة وبالفصحى."
    return "أنت مساعد ذكي، أجب بإيجاز ووضوح وبالفصحى."

def build_messages(uid: int, user_text: str) -> List[dict]:
    msgs = [{"role": "system", "content": build_system_prompt(uid)}]
    msgs.extend(list(contexts[uid]))
    msgs.append({"role": "user", "content": user_text})
    return msgs

def reset_daily_if_needed(uid: int):
    if daily_date.get(uid) != date.today():
        daily_date[uid] = date.today()
        daily_counts[uid] = 0

def is_owner(uid: int) -> bool:
    return OWNER_ID is not None and uid == OWNER_ID

async def queue_user_request(msg_obj: Message, uid: int, prompt: str):
    messages = build_messages(uid, prompt)
    status = await msg_obj.reply_text("جاري المعالجة، الرجاء الانتظار.")
    await pending_queue.put((msg_obj, uid, messages, status))
    await status.edit_text("تم وضع طلبك في قائمة الانتظار. سيتم الرد فور المعالجة.")

# -------------------- أوامر إدارية مصححة (فحص الصلاحية داخل المعالج) --------------------

@app.on_message(filters.regex(r"^(قفل الذكاء|فتح الذكاء)$"))
async def cmd_toggle_ai(_, m: Message):
    global AI_STATUS
    uid = m.from_user.id
    if not is_owner(uid):
        return await m.reply_text("ليس لديك صلاحية تنفيذ هذا الأمر.")
    AI_STATUS = "فتح" in m.text
    save_state()
    await m.reply_text("تم تنفيذ الطلب.")

@app.on_message(filters.regex(r"^(فتح الليمت|قفل الليمت)$"))
async def cmd_toggle_limit(_, m: Message):
    global LIMIT_STATUS
    uid = m.from_user.id
    if not is_owner(uid):
        return await m.reply_text("ليس لديك صلاحية تنفيذ هذا الأمر.")
    LIMIT_STATUS = "فتح" in m.text
    save_state()
    await m.reply_text("تم تحديث حالة الحد اليومي.")

@app.on_message(filters.regex(r"^وضع ليميت (\d+)$"))
async def cmd_set_limit(_, m: Message):
    global DAILY_LIMIT
    uid = m.from_user.id
    if not is_owner(uid):
        return await m.reply_text("ليس لديك صلاحية تنفيذ هذا الأمر.")
    DAILY_LIMIT = int(m.matches[0].group(1))
    save_state()
    await m.reply_text(f"تم ضبط الحد اليومي إلى {DAILY_LIMIT} رسالة.")

@app.on_message(filters.regex(r"^فتح الذكاء الدائم (\d+)$"))
async def cmd_permanent_enable_id(_, m: Message):
    uid = m.from_user.id
    if not is_owner(uid):
        return await m.reply_text("ليس لديك صلاحية تنفيذ هذا الأمر.")
    target = int(m.matches[0].group(1))
    permanent_users[target] = True
    save_state()
    await m.reply_text(f"تم تفعيل الذكاء الدائم للمستخدم {target}.")

@app.on_message(filters.regex(r"^قفل الذكاء الدائم (\d+)$"))
async def cmd_permanent_disable_id(_, m: Message):
    uid = m.from_user.id
    if not is_owner(uid):
        return await m.reply_text("ليس لديك صلاحية تنفيذ هذا الأمر.")
    target = int(m.matches[0].group(1))
    permanent_users.pop(target, None)
    save_state()
    await m.reply_text(f"تم إيقاف الذكاء الدائم للمستخدم {target}.")

@app.on_message(filters.regex(r"^(فتح الذكاء الدائم|قفل الذكاء الدائم)$"))
async def cmd_permanent_reply(_, m: Message):
    uid = m.from_user.id
    if not is_owner(uid):
        return await m.reply_text("ليس لديك صلاحية تنفيذ هذا الأمر.")
    if not m.reply_to_message:
        return await m.reply_text("يرجى الرد على رسالة المستخدم المطلوب.")
    target = m.reply_to_message.from_user.id
    if "فتح" in m.text:
        permanent_users[target] = True
        save_state()
        await m.reply_text(f"تم تفعيل الذكاء الدائم للمستخدم {target}.")
    else:
        permanent_users.pop(target, None)
        save_state()
        await m.reply_text(f"تم إيقاف الذكاء الدائم للمستخدم {target}.")

@app.on_message(filters.regex(r"^تغيير المود (تقني|عام)$"))
async def cmd_change_mode(_, m: Message):
    uid = m.from_user.id
    if not is_owner(uid):
        return await m.reply_text("ليس لديك صلاحية تنفيذ هذا الأمر.")
    mode = m.matches[0].group(1)
    user_mode[uid] = mode
    save_state()
    await m.reply_text(f"تم تغيير وضع المالك إلى {mode}.")

@app.on_message(filters.regex(r"^تنظيف الذاكرة$"))
async def cmd_clear_memory(_, m: Message):
    uid = m.from_user.id
    if not is_owner(uid):
        return await m.reply_text("ليس لديك صلاحية تنفيذ هذا الأمر.")
    contexts.clear()
    daily_counts.clear()
    save_state()
    await m.reply_text("تم مسح الذاكرة وتصفير العدادات.")

@app.on_message(filters.regex(r"^تعيين مفتاح AI\s+(.+)$"))
async def cmd_set_openai_key(_, m: Message):
    global OPENAI_KEY, openai_client, ACTIVE_MODEL, AI_STATUS
    uid = m.from_user.id
    if not is_owner(uid):
        return await m.reply_text("ليس لديك صلاحية تنفيذ هذا الأمر.")
    key = m.matches[0].group(1).strip()
    if not key:
        return await m.reply_text("الرجاء تزويد مفتاح صالح.")
    # جرب المفتاح سريعًا
    try:
        candidate = AsyncOpenAI(api_key=key)
        test_msgs = [{"role": "system", "content": "test"}, {"role": "user", "content": "ping"}]
        ok = False
        for model in MODEL_CANDIDATES:
            try:
                resp = await candidate.chat.completions.create(model=model, messages=test_msgs, max_tokens=1, timeout=8)
                if resp and getattr(resp, "choices", None):
                    # قبول المفتاح والنموذج
                    openai_client = candidate
                    OPENAI_KEY = key
                    ACTIVE_MODEL = model
                    AI_STATUS = True
                    save_state()
                    await m.reply_text(f"تم تفعيل المفتاح والنموذج: {model}. يُنصح بتخزين المفتاح كسِكِرت في مضيفك.")
                    ok = True
                    break
            except Exception:
                continue
        if not ok:
            AI_STATUS = False
            await m.reply_text("فشل التحقق من المفتاح مع النماذج المرشحة. الرجاء التحقق أو استخدام مفتاح آخر.")
    except Exception as e:
        logger.exception("خطأ أثناء تعيين المفتاح: %s", e)
        AI_STATUS = False
        await m.reply_text("حدث خطأ أثناء محاولة تفعيل المفتاح.")

@app.on_message(filters.regex(r"^حالة الذكاء$"))
async def cmd_status(_, m: Message):
    uid = m.from_user.id
    if not is_owner(uid):
        return await m.reply_text("ليس لديك صلاحية تنفيذ هذا الأمر.")
    await m.reply_text(
        f"AI_STATUS={AI_STATUS}\nLIMIT_STATUS={LIMIT_STATUS}\nDAILY_LIMIT={DAILY_LIMIT}\nQueue={pending_queue.qsize()}\nActiveModel={ACTIVE_MODEL}\nOpenAI_key={mask_key(OPENAI_KEY)}"
    )

@app.on_message(filters.regex(r"^(أعد المحاولة|retry)$"))
async def cmd_retry(_, m: Message):
    uid = m.from_user.id
    # جلب آخر طلب user من السياق
    last_user = None
    for item in reversed(contexts.get(uid, [])):
        if item.get("role") == "user":
            last_user = item.get("content")
            break
    if not last_user:
        return await m.reply_text("لا توجد محادثة سابقة لإعادتها.")
    await queue_user_request(m, uid, last_user)
    await m.reply_text("تمت إضافة إعادة المحاولة إلى الطابور.")

# -------------------- معالج النداء الرئيسي (ذكاء / بقولك) بدون سلاش --------------------
@app.on_message((filters.text | filters.caption) & ~filters.bot, group=1)
async def main_handler(_, m: Message):
    global AI_STATUS, LIMIT_STATUS, DAILY_LIMIT
    uid = m.from_user.id
    text = (m.text or m.caption or "").strip()
    if not text:
        return

    # المستخدم مفعل له الذكاء الدائم
    if uid in permanent_users:
        prompt = text
    else:
        if not AI_STATUS and not is_owner(uid):
            return
        match = re.match(r"^(ذكاء|بقولك)(\s|$)", text, re.IGNORECASE)
        if not match:
            return
        prompt = text[match.end():].strip()
        if not prompt:
            return

    # التحقق من العد اليومي وإعادة التصفير إذا لزم
    reset_daily_if_needed(uid)
    if LIMIT_STATUS and not is_owner(uid):
        if daily_counts.get(uid, 0) >= DAILY_LIMIT:
            return await m.reply_text("لقد استنفدت حصتك اليومية.")
    # ضع الطلب في الطابور
    await queue_user_request(m, uid, prompt)

# -------------------- حفظ حالة دوري --------------------
async def periodic_save():
    while True:
        await asyncio.sleep(300)
        try:
            save_state()
        except Exception:
            logger.exception("فشل الحفظ الدوري")

asyncio.get_event_loop().create_task(periodic_save())

# نهاية الملف
