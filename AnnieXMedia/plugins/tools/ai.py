# plugins/ai.py
# AnnieXMedia - Gemini-backed AI core
# جميع الأوامر بالعربية الفصحى بدون سلاش. سياق حتى 50 رسالة. رسالة انتظار: "جـاري الـتـفكير ...."
# يعتمد على واجهة HTTP لـ Gemini (أو أي مزود جنيريتيف) عبر متغيرات البيئة.

import os
import re
import json
import asyncio
import logging
from typing import Dict, List, Optional
from collections import deque, defaultdict
from datetime import date
import aiohttp

from pyrogram import filters
from pyrogram.types import Message
from AnnieXMedia import app
import config

# ---------- سجل التشغيل ----------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ai_gemini")

# ---------- إعدادات بيئية ----------
GEMINI_API_URL = os.getenv("GEMINI_API_URL")  # واجهة الـ generate endpoint
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or getattr(config, "GEMINI_API_KEY", None)
OWNER_ENV = os.getenv("OWNER_ID") or getattr(config, "OWNER_ID", None)
try:
    OWNER_ID = int(OWNER_ENV) if OWNER_ENV is not None else None
except Exception:
    OWNER_ID = None

if OWNER_ID is None:
    logger.warning("OWNER_ID غير مهيأ؛ تأكد من تعيين SECRET OWNER_ID في بيئة النشر.")

if not GEMINI_API_URL:
    logger.warning("GEMINI_API_URL غير مهيأ. ضع URL الواجهة في ENV: GEMINI_API_URL")
if not GEMINI_API_KEY:
    logger.warning("GEMINI_API_KEY غير مهيأ. يمكن تعيينه لاحقًا بأمر المالك.")

# ---------- ضبط السلوك ----------
MAX_CONTEXT = int(os.getenv("AI_MAX_CONTEXT", "50"))
MAX_CONCURRENT = int(os.getenv("AI_MAX_CONCURRENT", "4"))
DAILY_LIMIT_DEFAULT = int(os.getenv("DAILY_LIMIT", "150"))
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")  # يمكن تغييره عبر env

# ---------- ذاكرة وسجل ----------
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

# ---------- طابور ومعالج ----------
_semaphore = asyncio.Semaphore(MAX_CONCURRENT)
pending_queue: asyncio.Queue = asyncio.Queue()

# ---------- حفظ/تحميل الحالة ----------
def save_state():
    try:
        s = {
            "permanent_users": list(permanent_users.keys()),
            "daily_limit": DAILY_LIMIT,
            "ai_status": AI_STATUS,
            "limit_status": LIMIT_STATUS,
            "model": MODEL_NAME,
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

# ---------- مساعد بناء الطلب لمزود Gemini ----------
def build_system_prompt(uid: int) -> str:
    # نوجه النموذج ليكون فصيحاً، حساساً لنبرة المستخدم، ويطابق المزاج
    default = (
        "أنت مساعد ذكي فصيح باللغة العربية. اكتشف مزاج المستخدم من نص سؤاله "
        "(حزين، فرحان، غاضب، محايد) واطرح الإجابة بنبرة مطابقة وباحترام وتعاطف "
        "عند الحاجة. كن موجزًا مفيدًا وواضحًا، ولا تستخدم رموزًا تعبيرية."
    )
    if user_mode.get(uid) == "تقني":
        return (
            "أنت خبير تقني محترف، اشرح الحلول الهندسية بدقة وبالفصحى. إذا اشتمل سؤال المستخدم "
            "على عاطفة، اذكرها بإيجاز ثم انتقل للتحليل التقني."
        )
    return default

def build_messages(uid: int, user_text: str) -> List[Dict]:
    msgs = [{"role": "system", "content": build_system_prompt(uid)}]
    msgs.extend(list(contexts[uid]))
    msgs.append({"role": "user", "content": user_text})
    return msgs

# ---------- استدعاء HTTP إلى Gemini (مرن) ----------
async def call_gemini_api(messages: List[Dict], model: Optional[str] = None, timeout: int = 30) -> Optional[str]:
    """
    يتوقع JSON خروج بصيغة مرنة. تحتاج أن تُعرّف GEMINI_API_URL لتشير إلى نقطة توليد صحيحة.
    """
    url = GEMINI_API_URL
    key = GEMINI_API_KEY
    if not url or not key:
        logger.error("Gemini URL أو KEY غير موجودين.")
        return None

    payload = {
        # بنية مبسطة: مزودك قد يطلب شي مختلف، اضبط حسب واجهتك
        "model": model or MODEL_NAME,
        "messages": messages,
        "temperature": 0.4,
        "max_output_tokens": 1024
    }

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json"
    }

    # محاولات مع backoff قصير
    delay = 1.0
    for attempt in range(1, 4):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers, timeout=timeout) as resp:
                    text = await resp.text()
                    status = resp.status
                    if status >= 200 and status < 300:
                        # نحاول تفكيك أشكال مختلفة من الاستجابة
                        try:
                            j = await resp.json()
                        except Exception:
                            j = None
                        # محتمل حقول: candidates[0].content, outputText, text, content
                        if j:
                            # Android-style generative responses
                            if "candidates" in j and isinstance(j["candidates"], list) and j["candidates"]:
                                c = j["candidates"][0]
                                if isinstance(c, dict):
                                    # قد تحتوي على 'content' أو 'message' أو 'output'
                                    if "content" in c:
                                        return c["content"].get("text") if isinstance(c["content"], dict) and "text" in c["content"] else c["content"]
                                    if "message" in c and isinstance(c["message"], dict):
                                        return c["message"].get("content") or c["message"].get("text")
                                    if "output" in c:
                                        return c["output"]
                            # بعض واجهات تعيد 'outputText'
                            if "outputText" in j:
                                return j["outputText"]
                            if "text" in j:
                                return j["text"]
                            # generic
                            # search for first string in json
                            def find_first_str(obj):
                                if isinstance(obj, str):
                                    return obj
                                if isinstance(obj, dict):
                                    for v in obj.values():
                                        r = find_first_str(v)
                                        if r:
                                            return r
                                if isinstance(obj, list):
                                    for i in obj:
                                        r = find_first_str(i)
                                        if r:
                                            return r
                                return None
                            r = find_first_str(j)
                            return r
                        else:
                            # fallback: نص خام
                            return text.strip()
                    else:
                        logger.warning("Gemini API returned status %s: %s", status, text[:300])
                        # لو 401 أو 403 افصل فورًا
                        if status in (401, 403):
                            return None
        except asyncio.TimeoutError:
            logger.warning("Timeout calling Gemini attempt %s", attempt)
        except Exception as e:
            logger.exception("Error calling Gemini attempt %s: %s", attempt, e)
        await asyncio.sleep(delay)
        delay *= 2.0
    return None

# ---------- عامل الطابور ----------
async def worker():
    while True:
        job = await pending_queue.get()
        msg_obj, user_id, messages, status_msg = job
        try:
            async with _semaphore:
                result = await call_gemini_api(messages)
                if result:
                    # حفظ السياق بعد نجاح الرد
                    contexts[user_id].append({"role": "user", "content": messages[-1]["content"]})
                    contexts[user_id].append({"role": "assistant", "content": result})
                    # تحديث العداد اليومي
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

# ---------- أوامر إدارة (بدون سلاش) ----------
def is_owner(uid: int) -> bool:
    return OWNER_ID is not None and uid == OWNER_ID

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

@app.on_message(filters.regex(r"^تعيين مفتاح GEMINI\s+(.+)$"))
async def cmd_set_gemini_key(_, m: Message):
    global GEMINI_API_KEY, GEMINI_API_URL, openai_client
    uid = m.from_user.id
    if not is_owner(uid):
        return await m.reply_text("ليس لديك صلاحية تنفيذ هذا الأمر.")
    key = m.matches[0].group(1).strip()
    if not key:
        return await m.reply_text("الرجاء تزويد مفتاح صالح.")
    GEMINI_API_KEY = key
    # نصيحة: خزنه كـ secret في المضيف
    save_state()
    await m.reply_text("تم تفعيل المفتاح موقتا في الذاكرة. ينصح بتخزينه في الـ secrets للمضيف.")

@app.on_message(filters.regex(r"^حالة الذكاء$"))
async def cmd_status(_, m: Message):
    uid = m.from_user.id
    if not is_owner(uid):
        return await m.reply_text("ليس لديك صلاحية تنفيذ هذا الأمر.")
    await m.reply_text(
        f"AI_STATUS={AI_STATUS}\nLIMIT_STATUS={LIMIT_STATUS}\nDAILY_LIMIT={DAILY_LIMIT}\nQueue={pending_queue.qsize()}\nModel={MODEL_NAME}\nGEMINI_URL={GEMINI_API_URL or '<not set>'}"
    )

# ---------- أمر إعادة المحاولة ----------
@app.on_message(filters.regex(r"^(أعد المحاولة|retry)$"))
async def cmd_retry(_, m: Message):
    uid = m.from_user.id
    last_user = None
    for item in reversed(contexts.get(uid, [])):
        if item.get("role") == "user":
            last_user = item.get("content")
            break
    if not last_user:
        return await m.reply_text("لا توجد محادثة سابقة لإعادتها.")
    await queue_user_request(m, uid, last_user)
    await m.reply_text("تمت إضافة إعادة المحاولة إلى الطابور.")

# ---------- وضع الطلب في الطابور مع رسالة انتظار "جـاري الـتـفكير ...." ----------
async def queue_user_request(msg_obj: Message, uid: int, prompt: str):
    messages = build_messages(uid, prompt)
    # رسالة انتظار مباشرة كما طلبت
    status = await msg_obj.reply_text("جـاري الـتـفكير ....", quote=True)
    await pending_queue.put((msg_obj, uid, messages, status))

# ---------- المعالج الرئيسي (ذكاء / بقولك) بدون سلاش ----------
@app.on_message((filters.text | filters.caption) & ~filters.bot, group=1)
async def main_handler(_, m: Message):
    global AI_STATUS, LIMIT_STATUS, DAILY_LIMIT
    uid = m.from_user.id
    text = (m.text or m.caption or "").strip()
    if not text:
        return

    # إذا المستخدم مفعل له الذكاء الدائم، نخدمه
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

    # حد يومي
    if daily_date.get(uid) != date.today():
        daily_date[uid] = date.today()
        daily_counts[uid] = 0

    if LIMIT_STATUS and not is_owner(uid):
        if daily_counts.get(uid, 0) >= DAILY_LIMIT:
            return await m.reply_text("لقد استنفدت حصتك اليومية.")
    await queue_user_request(m, uid, prompt)

# ---------- حفظ دوري ----------
async def periodic_save():
    while True:
        await asyncio.sleep(300)
        try:
            save_state()
        except Exception:
            logger.exception("فشل الحفظ الدوري")

asyncio.get_event_loop().create_task(periodic_save())
