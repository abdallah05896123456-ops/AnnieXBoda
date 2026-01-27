# plugins/ai.py
# AnnieXMedia - AI core
# يعتمد على OpenAI الرسمي عبر متغيرات البيئة (OPENAI_API_KEY, OWNER_ID)
# أوامر بدون سلاش، لغة عربية فصحى، حفظ سياق حتى 50 رسالة، ذاكـرة دائمة لكل user_id.

import os
import re
import time
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
from config import AI_HANDLER_GROUP

# -------------------- سجل التشغيل --------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ai_core")

# -------------------- قراءة السكرتس من البيئة --------------------
# يفضّل ضبط هذه المتغيرات باستخدام fly secrets أو طريقة آمنة
OPENAI_KEY = os.getenv("OPENAI_API_KEY") or getattr(config, "AI_API_KEY", None)
OWNER = os.getenv("OWNER_ID") or getattr(config, "OWNER_ID", None)
if isinstance(OWNER, str) and OWNER.isdigit():
    OWNER_ID = int(OWNER)
elif isinstance(OWNER, int):
    OWNER_ID = OWNER
else:
    OWNER_ID = None

if OWNER_ID is None:
    logger.error("OWNER_ID غير مهيأ. ضع OWNER_ID كمتغير بيئة أو في config.py")
if not OPENAI_KEY:
    logger.warning("OPENAI_API_KEY غير مهيأ. يمكن تفعيل المفتاح لاحقاً بأمر إداري.")

# عميل OpenAI قابل للتحديث عند تعيين مفتاح جديد أثناء التشغيل
openai_client: Optional[AsyncOpenAI] = AsyncOpenAI(api_key=OPENAI_KEY) if OPENAI_KEY else None

# -------------------- إعدادات السلوك --------------------
MODEL_NAME = os.getenv("AI_MODEL", "gpt-4")  # يمكن تغييره عبر متغير بيئة
MAX_CONTEXT = 50
DAILY_LIMIT_DEFAULT = 150
MAX_CONCURRENT = int(os.getenv("AI_MAX_CONCURRENT", "4"))

# -------------------- بيانات الذاكرة --------------------
contexts: Dict[int, deque] = defaultdict(lambda: deque(maxlen=MAX_CONTEXT))
daily_counts: Dict[int, int] = defaultdict(int)
daily_date: Dict[int, date] = defaultdict(lambda: date.today())
permanent_users: Dict[int, bool] = {}  # user_id -> True
user_mode: Dict[int, str] = defaultdict(lambda: "عام")  # "عام" أو "تقني"

AI_STATUS = True
LIMIT_STATUS = False
DAILY_LIMIT = int(os.getenv("DAILY_LIMIT", DAILY_LIMIT_DEFAULT))

# حالة وحفظ بسيط على القرص (مخزن القناع فقط، لا يخزن المفتاح الكامل)
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
            "user_mode_defaults": {},  # احتياطي
            "openai_masked": mask_key(OPENAI_KEY)
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
    except Exception:
        logger.exception("فشل تحميل الحالة")


load_state()

# -------------------- موارد التزامن و الطابور --------------------
_semaphore = asyncio.Semaphore(MAX_CONCURRENT)
pending_queue: asyncio.Queue = asyncio.Queue()


async def call_openai_with_retries(messages: List[Dict], max_retries: int = 4, timeout: int = 30) -> Optional[str]:
    global openai_client
    if not openai_client:
        logger.error("عميل OpenAI غير مهيأ")
        return None

    delay = 1.0
    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = await openai_client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                temperature=0.4,
                max_tokens=1500,
                timeout=timeout
            )
            if resp and getattr(resp, "choices", None):
                return resp.choices[0].message.content.strip()
            last_err = "empty"
        except OpenAIError as e:
            last_err = str(e)
            logger.warning("OpenAIError attempt %s: %s", attempt, e)
            # كشف خطأ مفتاح غير صالح يفصل المحاولات
            if "invalid_api_key" in str(e) or "Incorrect API key" in str(e):
                logger.error("مفتاح OpenAI غير صالح (ستتوقف المحاولات).")
                break
        except asyncio.TimeoutError:
            last_err = "timeout"
            logger.warning("Timeout attempt %s", attempt)
        except Exception as e:
            last_err = str(e)
            logger.exception("خطأ غير متوقع attempt %s: %s", attempt, e)
        await asyncio.sleep(delay)
        delay *= 2.0
    logger.error("فشلت كل المحاولات: %s", last_err)
    return None


async def worker():
    while True:
        job = await pending_queue.get()
        msg_obj, user_id, messages, status_msg = job
        try:
            async with _semaphore:
                result = await call_openai_with_retries(messages)
                if result:
                    # حفظ السياق
                    contexts[user_id].append({"role": "user", "content": messages[-1]["content"]})
                    contexts[user_id].append({"role": "assistant", "content": result})
                    # عداد يومي
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
            logger.exception("عامل الطابور تعرّض إلى خطأ")
            try:
                await status_msg.edit_text("حدث خطأ غير متوقع أثناء المعالجة.")
            except:
                pass
        finally:
            pending_queue.task_done()


asyncio.get_event_loop().create_task(worker())

# -------------------- مساعدة بناء الرسائل --------------------
def build_system_prompt(uid: int) -> str:
    mode = user_mode.get(uid, "عام")
    if mode == "تقني":
        return "أنت مساعد تقني، اشرح بمصطلحات هندسية دقيقة وبالفصحى."
    return "أنت مساعد ذكي، أجب بإيجاز ووضوح وبالفصحى."

def build_messages(uid: int, user_text: str) -> List[Dict]:
    msgs = [{"role": "system", "content": build_system_prompt(uid)}]
    msgs.extend(list(contexts[uid]))
    msgs.append({"role": "user", "content": user_text})
    return msgs

# -------------------- فحوص يومية للعداد --------------------
def reset_daily_if_needed(uid: int):
    if daily_date.get(uid) != date.today():
        daily_date[uid] = date.today()
        daily_counts[uid] = 0

# -------------------- مساعدة: مالك أم لا --------------------
def is_owner(uid: int) -> bool:
    return OWNER_ID is not None and uid == OWNER_ID

# -------------------- عملية الطلب الذكي --------------------
async def queue_user_request(msg_obj: Message, uid: int, prompt: str):
    messages = build_messages(uid, prompt)
    status = await msg_obj.reply_text("جاري المعالجة، الرجاء الانتظار.")
    await pending_queue.put((msg_obj, uid, messages, status))
    await status.edit_text("تم وضع طلبك في قائمة الانتظار. سيتم الرد فور المعالجة.")

# -------------------- أوامر الإدارة والنظام (بدون سلاش) --------------------

# تفعيل/تعطيل الذكاء
@app.on_message(filters.regex(r"^(قفل الذكاء|فتح الذكاء)$") & filters.user(lambda _, __, m: is_owner(m.from_user.id)))
async def toggle_ai(_, m: Message):
    global AI_STATUS
    AI_STATUS = "فتح" in m.text
    save_state()
    await m.reply_text("تم تنفيذ الطلب.")

# تفعيل/تعطيل الليمت
@app.on_message(filters.regex(r"^(فتح الليمت|قفل الليمت)$") & filters.user(lambda _, __, m: is_owner(m.from_user.id)))
async def toggle_limit(_, m: Message):
    global LIMIT_STATUS
    LIMIT_STATUS = "فتح" in m.text
    save_state()
    await m.reply_text("تم تحديث حالة الحد اليومي.")

# وضع ليميت رقم
@app.on_message(filters.regex(r"^وضع ليميت (\d+)$") & filters.user(lambda _, __, m: is_owner(m.from_user.id)))
async def set_limit(_, m: Message):
    global DAILY_LIMIT
    DAILY_LIMIT = int(m.matches[0].group(1))
    save_state()
    await m.reply_text(f"تم ضبط الحد اليومي إلى {DAILY_LIMIT} رسالة.")

# تفعيل الذكاء الدائم عن طريق الرد (مالك)
@app.on_message(filters.regex(r"^(فتح الذكاء الدائم|قفل الذكاء الدائم)$") & filters.user(lambda _, __, m: is_owner(m.from_user.id)))
async def permanent_reply(_, m: Message):
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

# تفعيل/تعطيل الذكاء الدائم عبر معرف رقمياً (مالك)
@app.on_message(filters.regex(r"^فتح الذكاء الدائم (\d+)$") & filters.user(lambda _, __, m: is_owner(m.from_user.id)))
async def permanent_enable_id(_, m: Message):
    target = int(m.matches[0].group(1))
    permanent_users[target] = True
    save_state()
    await m.reply_text(f"تم تفعيل الذكاء الدائم للمستخدم {target}.")

@app.on_message(filters.regex(r"^قفل الذكاء الدائم (\d+)$") & filters.user(lambda _, __, m: is_owner(m.from_user.id)))
async def permanent_disable_id(_, m: Message):
    target = int(m.matches[0].group(1))
    permanent_users.pop(target, None)
    save_state()
    await m.reply_text(f"تم إيقاف الذكاء الدائم للمستخدم {target}.")

# تغيير المود (مالك)
@app.on_message(filters.regex(r"^تغيير المود (تقني|عام)$") & filters.user(lambda _, __, m: is_owner(m.from_user.id)))
async def change_mode_owner(_, m: Message):
    # يغيّر المود العام العامي (لا وهو ممكن أن نطبقه افتراضياً)
    mode = m.matches[0].group(1)
    # يمكن استخدامه لضبط سلوك افتراضي؛ هنا نطبّق فقط على مرسال المالك
    user_mode[m.from_user.id] = mode
    save_state()
    await m.reply_text(f"تم تغيير الوضع إلى {mode}.")

# تنظيف الذاكرة (مالك)
@app.on_message(filters.regex(r"^تنظيف الذاكرة$") & filters.user(lambda _, __, m: is_owner(m.from_user.id)))
async def clear_memory(_, m: Message):
    contexts.clear()
    daily_counts.clear()
    save_state()
    await m.reply_text("تم مسح الذاكرة وتصفير العدادات.")

# تعيين التزامن (مالك)
@app.on_message(filters.regex(r"^تعيين التزامن (\d+)$") & filters.user(lambda _, __, m: is_owner(m.from_user.id)))
async def set_concurrency(_, m: Message):
    global _semaphore
    n = int(m.matches[0].group(1))
    if n < 1 or n > 64:
        return await m.reply_text("الرجاء اختيار قيمة بين 1 و64.")
    _semaphore = asyncio.Semaphore(n)
    save_state()
    await m.reply_text(f"تم ضبط التزامن إلى {n}.")

# تعيين مفتاح OpenAI أثناء التشغيل (مالك) — يفعّل المفتاح في الذاكرة فوراً (لا يحفظ المفتاح كاملًا على القرص)
@app.on_message(filters.regex(r"^تعيين مفتاح AI\s+(.+)$") & filters.user(lambda _, __, m: is_owner(m.from_user.id)))
async def set_openai_key(_, m: Message):
    global OPENAI_KEY, openai_client, AI_STATUS
    key = m.matches[0].group(1).strip()
    if not key:
        return await m.reply_text("الرجاء تزويد مفتاح صالح.")
    # نختبر المفتاح سريعاً
    try:
        candidate = AsyncOpenAI(api_key=key)
        # اختبار بسيط
        test_msgs = [{"role": "system", "content": "test"}, {"role": "user", "content": "hi"}]
        resp = await candidate.chat.completions.create(model=MODEL_NAME, messages=test_msgs, max_tokens=1, timeout=10)
        if resp and getattr(resp, "choices", None):
            openai_client = candidate
            OPENAI_KEY = key
            AI_STATUS = True
            save_state()
            await m.reply_text("تم تفعيل المفتاح بنجاح. يُنصح بتعيينه كـ secret في بيئة الاستضافة للحفظ الدائم.")
            return
    except Exception as e:
        logger.exception("فشل التحقق من المفتاح أثناء التعيين: %s", e)
    AI_STATUS = False
    await m.reply_text("فشل التحقق من المفتاح. الرجاء التحقق من المفتاح والمحاولة مجدداً.")

# أمر حالة النظام (مالك)
@app.on_message(filters.regex(r"^حالة الذكاء$") & filters.user(lambda _, __, m: is_owner(m.from_user.id)))
async def status_cmd(_, m: Message):
    await m.reply_text(
        f"AI_STATUS={AI_STATUS}\nLIMIT_STATUS={LIMIT_STATUS}\nDAILY_LIMIT={DAILY_LIMIT}\nQueue={pending_queue.qsize()}\nOpenAI_key={mask_key(OPENAI_KEY)}"
    )

# أمر إعادة المحاولة للمستخدم
@app.on_message(filters.regex(r"^(أعد المحاولة|retry)$") & ~filters.bot)
async def retry_cmd(_, m: Message):
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

# -------------------- المعالج الرئيسي للنداء (ذكاء / بقولك) بدون سلاش --------------------
@app.on_message((filters.text | filters.caption) & ~filters.bot, group=AI_HANDLER_GROUP)
async def main_handler(_, m: Message):
    global AI_STATUS, LIMIT_STATUS, DAILY_LIMIT
    uid = m.from_user.id
    text = (m.text or m.caption or "").strip()
    if not text:
        return

    # إذا المستخدم مفعل له الذكاء الدائم، نخدم طلبه مهما كان النص
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

    # التحقق من العداد اليومي
    reset_daily_if_needed(uid)
    if LIMIT_STATUS and not is_owner(uid):
        if daily_counts.get(uid, 0) >= DAILY_LIMIT:
            return await m.reply_text("لقد استنفدت حصتك اليومية.")
        # لا نزيد العداد هنا، بل بعد نجاح الرد ضمن العامل worker لضمان عدم الحجز الخاطئ
    # وضع الطلب في الطابور
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

# النهاية
