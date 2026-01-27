# ai.py - AnnieXMedia AI Core (OpenAI GPT-4)
# تم التطوير بواسطة الزملاء المبرمجين 2026
# يركز على محرك الذكاء OpenAI مع صف انتظار، retry، حفظ سياق حتى 50 رسالة، وأوامر إدارية.

import os
import re
import time
import json
import asyncio
import logging
from typing import Dict, List, Optional
from pyrogram import filters, enums
from pyrogram.types import Message
from openai import AsyncOpenAI, OpenAIError

from AnnieXMedia import app
import config
from config import OWNER_ID, AI_HANDLER_GROUP

# إعداد السجل
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ai_core")

# إعدادات عامة
SUDO_USERS = OWNER_ID if isinstance(OWNER_ID, list) else [OWNER_ID]
AI_STATUS = True
LIMIT_STATUS = True
DAILY_LIMIT = 100
AI_MODE = "عام"  # أو "تقني"

# سياق وعدادات
context: Dict[int, List[Dict]] = {}
counter: Dict[int, List[float]] = {}
PERMANENT_USERS: Dict[int, bool] = {}

# ملف الحالة
DATA_DIR = os.path.join(os.path.dirname(__file__), "ai_data")
os.makedirs(DATA_DIR, exist_ok=True)
STATE_FILE = os.path.join(DATA_DIR, "state.json")

# إعداد OpenAI
OPENAI_KEY = getattr(config, "AI_API_KEY", None) or os.environ.get("OPENAI_API_KEY")
if not OPENAI_KEY:
    logger.error("OpenAI API key not configured. ضع AI_API_KEY في config أو OPENAI_API_KEY كمتغير بيئة.")
openai_client = AsyncOpenAI(api_key=OPENAI_KEY)

# موارد تشغيل الطابور
MAX_CONCURRENT = int(os.environ.get("AI_MAX_CONCURRENT", "4"))
_semaphore = asyncio.Semaphore(MAX_CONCURRENT)
pending_queue: asyncio.Queue = asyncio.Queue()

# إعدادات المحرك
MAX_CONTEXT_MESSAGES = 50  # حفظ حتى 50 رسالة
RETRY_MAX = 4
RETRY_TIMEOUT = 30
MODEL_NAME = os.environ.get("AI_MODEL", "gpt-4")  # يمكن تغييره إلى gpt-4o

# حفظ/تحميل الحالة
def save_state():
    try:
        state = {
            "PERMANENT_USERS": list(PERMANENT_USERS.keys()),
            "DAILY_LIMIT": DAILY_LIMIT,
            "AI_MODE": AI_MODE,
            "AI_STATUS": AI_STATUS,
            "LIMIT_STATUS": LIMIT_STATUS,
            "MAX_CONCURRENT": MAX_CONCURRENT
        }
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        logger.debug("State saved")
    except Exception as e:
        logger.exception("Failed to save state: %s", e)

def load_state():
    global PERMANENT_USERS, DAILY_LIMIT, AI_MODE, AI_STATUS, LIMIT_STATUS, MAX_CONCURRENT, _semaphore
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)
            PERMANENT_USERS = {int(k): True for k in state.get("PERMANENT_USERS", [])}
            DAILY_LIMIT = state.get("DAILY_LIMIT", DAILY_LIMIT)
            AI_MODE = state.get("AI_MODE", AI_MODE)
            AI_STATUS = state.get("AI_STATUS", AI_STATUS)
            LIMIT_STATUS = state.get("LIMIT_STATUS", LIMIT_STATUS)
            MAX_CONCURRENT = state.get("MAX_CONCURRENT", MAX_CONCURRENT)
            _semaphore = asyncio.Semaphore(MAX_CONCURRENT)
            logger.debug("State loaded")
    except Exception as e:
        logger.exception("Failed to load state: %s", e)

load_state()

# إدارة السياق
def append_context(user_id: int, role: str, content: str):
    lst = context.get(user_id, [])
    lst.append({"role": role, "content": content})
    if len(lst) > MAX_CONTEXT_MESSAGES:
        lst = lst[-MAX_CONTEXT_MESSAGES:]
    context[user_id] = lst

def build_system_prompt():
    if AI_MODE == "تقني":
        return "أنت خبير برمجيات محترف، قدم تحليلات هندسية دقيقة ومفصلة باللغة العربية الفصحى."
    return "أنت مساعد ذكي متمكن، قدم إجابات مفيدة وواضحة باللغة العربية الفصحى."

def build_messages_from_context(user_id: int, user_prompt: str) -> List[Dict]:
    msgs = [{"role": "system", "content": build_system_prompt()}]
    msgs += context.get(user_id, [])
    msgs.append({"role": "user", "content": user_prompt})
    return msgs

# استدعاء OpenAI مع retry و backoff
async def _call_openai_with_retries(messages: List[Dict], user_id: int, max_retries: int = RETRY_MAX, timeout: int = RETRY_TIMEOUT) -> Optional[str]:
    delay = 1.0
    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = await openai_client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                temperature=0.6,
                max_tokens=1500,
                timeout=timeout
            )
            if resp and getattr(resp, "choices", None):
                content = resp.choices[0].message.content.strip()
                return content
            last_err = "empty_response"
        except OpenAIError as e:
            last_err = str(e)
            logger.warning("OpenAIError attempt %s: %s", attempt, e)
        except asyncio.TimeoutError:
            last_err = "timeout"
            logger.warning("Timeout attempt %s", attempt)
        except Exception as e:
            last_err = str(e)
            logger.exception("Unexpected error on attempt %s: %s", attempt, e)
        await asyncio.sleep(delay)
        delay *= 2.0
    logger.error("All retries failed: %s", last_err)
    return None

# عامل الطابور
async def _worker_queue():
    while True:
        job = await pending_queue.get()
        message_obj, user_id, messages, status_msg = job
        try:
            async with _semaphore:
                result = await _call_openai_with_retries(messages, user_id)
                if result:
                    append_context(user_id, "user", messages[-1]["content"])
                    append_context(user_id, "assistant", result)
                    counter.setdefault(user_id, []).append(time.time())
                    try:
                        await status_msg.edit(result)
                    except Exception:
                        try:
                            await message_obj.reply_text(result)
                        except Exception:
                            logger.exception("Failed to reply to user %s", user_id)
                else:
                    try:
                        await status_msg.edit("نعتذر، المحرك لا يستجيب حالياً. يرجى إعادة المحاولة لاحقاً.")
                    except Exception:
                        pass
        except Exception as e:
            logger.exception("Worker failed: %s", e)
            try:
                await status_msg.edit("حدث خطأ غير متوقع أثناء المعالجة.")
            except Exception:
                pass
        finally:
            pending_queue.task_done()

# بدء العامل كخلفية
asyncio.get_event_loop().create_task(_worker_queue())

# أوامر الإدارة (مقتصرة على OWNER_ID فقط) - بدون سلاش
@app.on_message(filters.regex(r"^(قفل الذكاء|فتح الذكاء)$") & filters.user(SUDO_USERS))
async def cmd_toggle_ai(_, m: Message):
    global AI_STATUS
    AI_STATUS = "فتح" in m.text
    save_state()
    await m.reply_text("تم تنفيذ الطلب.")

@app.on_message(filters.regex(r"^(فتح الليمت|قفل الليمت)$") & filters.user(SUDO_USERS))
async def cmd_toggle_limit(_, m: Message):
    global LIMIT_STATUS
    LIMIT_STATUS = "فتح" in m.text
    save_state()
    await m.reply_text("تم تحديث حالة نظام الحد اليومي.")

@app.on_message(filters.regex(r"^وضع ليميت (\d+)$") & filters.user(SUDO_USERS))
async def cmd_set_limit(_, m: Message):
    global DAILY_LIMIT
    DAILY_LIMIT = int(m.matches[0].group(1))
    save_state()
    await m.reply_text(f"تم ضبط الحد اليومي إلى {DAILY_LIMIT} رسالة.")

@app.on_message(filters.regex(r"^فتح الذكاء الدائم (\d+)$") & filters.user(SUDO_USERS))
async def cmd_permanent_ai_enable_by_id(_, m: Message):
    target_id = int(m.matches[0].group(1))
    PERMANENT_USERS[target_id] = True
    save_state()
    await m.reply_text(f"تم تفعيل الذكاء الدائم للمستخدم {target_id}.")

@app.on_message(filters.regex(r"^قفل الذكاء الدائم (\d+)$") & filters.user(SUDO_USERS))
async def cmd_permanent_ai_disable_by_id(_, m: Message):
    target_id = int(m.matches[0].group(1))
    PERMANENT_USERS.pop(target_id, None)
    save_state()
    await m.reply_text(f"تم تعطيل الذكاء الدائم للمستخدم {target_id}.")

@app.on_message(filters.regex(r"^(فتح الذكاء الدائم|قفل الذكاء الدائم)$") & filters.user(SUDO_USERS))
async def cmd_permanent_ai_reply(_, m: Message):
    if not m.reply_to_message:
        return await m.reply_text("يرجى الرد على رسالة المستخدم المطلوب لتفعيل أو تعطيل الذكاء الدائم.")
    target_id = m.reply_to_message.from_user.id
    if "فتح" in m.text:
        PERMANENT_USERS[target_id] = True
        save_state()
        await m.reply_text(f"تم تفعيل الذكاء الدائم للمستخدم {target_id}.")
    else:
        PERMANENT_USERS.pop(target_id, None)
        save_state()
        await m.reply_text(f"تم تعطيل الذكاء الدائم للمستخدم {target_id}.")

@app.on_message(filters.regex(r"^تغيير المود (تقني|عام)$") & filters.user(SUDO_USERS))
async def cmd_change_mode(_, m: Message):
    global AI_MODE
    AI_MODE = m.matches[0].group(1)
    save_state()
    await m.reply_text(f"تم تغيير وضعية الذكاء إلى {AI_MODE}.")

@app.on_message(filters.regex(r"^تنظيف الذاكرة$") & filters.user(SUDO_USERS))
async def cmd_clear_memory(_, m: Message):
    context.clear()
    counter.clear()
    save_state()
    await m.reply_text("تم مسح الذاكرة وتصفير العدادات.")

@app.on_message(filters.regex(r"^استرجاع الحالة$") & filters.user(SUDO_USERS))
async def cmd_dump_state(_, m: Message):
    try:
        if os.path.exists(STATE_FILE):
            await m.reply_document(STATE_FILE, caption="ملف حالة النظام")
        else:
            await m.reply_text("لا توجد حالة محفوظة حالياً.")
    except Exception as e:
        await m.reply_text(f"فشل إرسال ملف الحالة: {e}")

@app.on_message(filters.regex(r"^تعيين التزامن (\d+)$") & filters.user(SUDO_USERS))
async def cmd_set_concurrency(_, m: Message):
    global MAX_CONCURRENT, _semaphore
    n = int(m.matches[0].group(1))
    if n < 1 or n > 64:
        return await m.reply_text("الرجاء اختيار قيمة بين 1 و64.")
    MAX_CONCURRENT = n
    _semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    save_state()
    await m.reply_text(f"تم ضبط التزامن إلى {MAX_CONCURRENT}.")

# معالج النداء الرئيسي - بدون سلاش: ارسل رسالة تبدأ بـ ذكاء أو بقولك
@app.on_message((filters.text | filters.caption) & ~filters.bot, group=AI_HANDLER_GROUP)
async def ai_handler(bot, m: Message):
    global counter
    uid = m.from_user.id
    text = (m.text or m.caption or "").strip()

    # إذا المستخدم مفعل له الذكاء الدائم فنعمل له الخدمة مباشرة
    if uid in PERMANENT_USERS:
        prompt = text or "استمر في الحديث"
    else:
        if not AI_STATUS and uid not in SUDO_USERS:
            return
        match = re.match(r"^(ذكاء|بقولك)(\s|$)", text, re.IGNORECASE)
        if not match:
            return
        prompt = text[match.end():].strip() or "استمر في الحديث"

    # التحقق من حدود الاستخدام اليومي
    now = time.time()
    counter.setdefault(uid, [])
    counter[uid] = [t for t in counter[uid] if now - t < 86400]
    if LIMIT_STATUS and uid not in SUDO_USERS and len(counter[uid]) >= DAILY_LIMIT:
        await m.reply_text(f"لقد استنفدت حصتك اليومية ({DAILY_LIMIT}).")
        return

    status_msg = await m.reply_text("جاري المعالجة، الرجاء الانتظار.", quote=True)
    messages = build_messages_from_context(uid, prompt)
    await pending_queue.put((m, uid, messages, status_msg))
    await status_msg.edit("تم وضع طلبك في قائمة الانتظار. سيتم الرد فور المعالجة.")

# أمر إعادة المحاولة من قبل المستخدم
@app.on_message(filters.regex(r"^(أعد المحاولة|retry)$") & ~filters.bot)
async def retry_command(_, m: Message):
    uid = m.from_user.id
    last_msgs = context.get(uid)
    if not last_msgs:
        await m.reply_text("لا توجد محادثة سابقة لإعادتها.")
        return
    last_user = None
    for msg in reversed(last_msgs):
        if msg.get("role") == "user":
            last_user = msg.get("content")
            break
    if not last_user:
        await m.reply_text("لا يوجد نص سابق لإعادة المحاولة.")
        return
    status = await m.reply_text("جارٍ إعادة المحاولة، الرجاء الانتظار.")
    messages = build_messages_from_context(uid, last_user)
    await pending_queue.put((m, uid, messages, status))
    await status.edit("تمت إضافة إعادة المحاولة إلى الطابور.")

# أمر حالة النظام للادمن
@app.on_message(filters.regex(r"^حالة الذكاء$") & filters.user(SUDO_USERS))
async def cmd_status(_, m: Message):
    await m.reply_text(
        f"AI_STATUS={AI_STATUS}\nLIMIT_STATUS={LIMIT_STATUS}\nDAILY_LIMIT={DAILY_LIMIT}\nAI_MODE={AI_MODE}\nPERMANENT_USERS={list(PERMANENT_USERS.keys())}\nQueue={pending_queue.qsize()}"
    )

# حفظ الحالة دوريًا
async def periodic_state_save():
    while True:
        await asyncio.sleep(300)
        try:
            save_state()
        except Exception as e:
            logger.exception("Failed periodic save: %s", e)

asyncio.get_event_loop().create_task(periodic_state_save())

# نهاية الملف
