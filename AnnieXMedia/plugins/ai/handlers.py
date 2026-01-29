# plugins/ai/handlers.py
# Authored By Certified Coders © 2026
# High-Performance AI Handlers (Streaming / Anti-Timeout / Stable Output)

import re
import asyncio
import logging
from pyrogram import filters, enums
from pyrogram.types import Message, CallbackQuery

from AnnieXMedia import app
from config import OWNER_ID

from .engine import ask_ollama_stream
from .prompts import build_system_prompt

# ===============================
# Logging
# ===============================
logger = logging.getLogger("AnnieX_AI_Handlers")

# ===============================
# Globals
# ===============================
AI_STATUS = True
AI_MODE = "عام"   # عام | تقني
PERMANENT_USERS = set()

# ضبط SUDO
if isinstance(OWNER_ID, (list, tuple, set)):
    SUDO_USERS = set(OWNER_ID)
else:
    SUDO_USERS = {OWNER_ID}

SUDO_FILTER = filters.user(list(SUDO_USERS))

# ===============================
# Helpers
# ===============================
def is_sudo(user_id: int) -> bool:
    return user_id in SUDO_USERS


def extract_prompt(text: str) -> str:
    """
    يشيل كلمات النداء ويطلع الطلب الحقيقي
    """
    trigger = re.match(r"^(ذكاء|يا بوت|بوت|بقولك)(\s+|$)", text)
    if trigger:
        return text[trigger.end():].strip()
    return text.strip()


def should_trigger_ai(message: Message, bot_id: int) -> bool:
    """
    الذكاء يشتغل في الحالات دي فقط:
    - رد مباشر على البوت
    - مستخدم مفعل وضع دائم
    - رسالة تبدأ بكلمة نداء
    """
    uid = message.from_user.id

    if uid in PERMANENT_USERS:
        return True

    if message.reply_to_message:
        if message.reply_to_message.from_user and message.reply_to_message.from_user.id == bot_id:
            return True

    if re.match(r"^(ذكاء|يا بوت|بوت|بقولك)", message.text or ""):
        return True

    return False


# ===============================
# Developer Control Commands
# ===============================
@app.on_message(filters.regex(r"^(كيب الذكاء|كيب ذكاء|اوامر الذكاء)$") & SUDO_FILTER)
async def ai_control_panel(_, m: Message):
    status_txt = "مفعل" if AI_STATUS else "معطل"
    mode_txt = AI_MODE

    txt = (
        "لوحة تحكم الذكاء\n\n"
        f"الحالة: {status_txt}\n"
        f"النمط: {mode_txt}\n"
        f"وضع دائم: {len(PERMANENT_USERS)} مستخدم"
    )
    await m.reply_text(txt)


@app.on_message(filters.regex(r"^(تعطيل الذكاء|اقفل الذكاء)$") & SUDO_FILTER)
async def disable_ai(_, m: Message):
    global AI_STATUS
    AI_STATUS = False
    await m.reply_text("تم تعطيل الذكاء.")


@app.on_message(filters.regex(r"^(تشغيل الذكاء|افتح الذكاء)$") & SUDO_FILTER)
async def enable_ai(_, m: Message):
    global AI_STATUS
    AI_STATUS = True
    await m.reply_text("تم تشغيل الذكاء.")


@app.on_message(filters.regex(r"^(وضع تقني)$") & SUDO_FILTER)
async def switch_tech(_, m: Message):
    global AI_MODE
    AI_MODE = "تقني"
    await m.reply_text("تم التحويل للوضع التقني.")


@app.on_message(filters.regex(r"^(وضع عام)$") & SUDO_FILTER)
async def switch_general(_, m: Message):
    global AI_MODE
    AI_MODE = "عام"
    await m.reply_text("تم التحويل للوضع العام.")


# ===============================
# User Commands
# ===============================
@app.on_message(filters.regex(r"^(ذكاء دائم|افتح دائم)$"))
async def enable_permanent(_, m: Message):
    uid = m.from_user.id
    PERMANENT_USERS.add(uid)
    await m.reply_text("تم تفعيل الوضع الدائم لك.")


@app.on_message(filters.regex(r"^(كفاية|خروج من الذكاء|انهاء)$"))
async def disable_permanent(_, m: Message):
    uid = m.from_user.id
    if uid in PERMANENT_USERS:
        PERMANENT_USERS.remove(uid)
        await m.reply_text("تم الخروج من الوضع الدائم.")
    else:
        await m.reply_text("أنت مش في الوضع الدائم.")


# ===============================
# Main AI Handler (Streaming)
# ===============================
@app.on_message(filters.text & ~filters.bot, group=60)
async def ai_message_handler(client, m: Message):
    global AI_STATUS

    if not AI_STATUS and m.from_user.id not in SUDO_USERS:
        return

    if not m.text:
        return

    try:
        me = client.me or await client.get_me()
        bot_id = me.id
    except Exception:
        bot_id = None

    if not should_trigger_ai(m, bot_id):
        return

    prompt = extract_prompt(m.text)
    if not prompt:
        await m.reply_text("نعم؟")
        return

    system_prompt = build_system_prompt(AI_MODE)

    try:
        await client.send_chat_action(m.chat.id, enums.ChatAction.TYPING)
    except Exception:
        pass

    wait_msg = None
    try:
        wait_msg = await m.reply_text("جاري التفكير...")
    except Exception:
        pass

    last_sent = ""

    async def on_update(partial: str):
        nonlocal last_sent, wait_msg
        if not wait_msg:
            return

        if partial.strip() == last_sent.strip():
            return

        last_sent = partial

        preview = partial.strip()
        if len(preview) > 1800:
            preview = preview[:1800]

        try:
            await wait_msg.edit(preview)
        except Exception:
            pass

    try:
        reply = await ask_ollama_stream(
            user_id=m.from_user.id,
            prompt=prompt,
            on_update=on_update
        )

        if wait_msg:
            await wait_msg.edit(reply)
        else:
            await m.reply_text(reply)

    except asyncio.TimeoutError:
        await m.reply_text("الذكاء اتأخر شوية. حاول تاني.")
    except Exception as e:
        logger.error(f"AI handler error: {e}")
        await m.reply_text("حصل خطأ داخلي. حاول لاحقاً.")
