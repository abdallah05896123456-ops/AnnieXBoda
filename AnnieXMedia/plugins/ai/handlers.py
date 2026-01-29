# plugins/ai/handlers.py
# Authored By Certified Coders © 2026
# High-Performance AI Handlers (Streaming / Anti-Timeout / Stable Output)

import re
import asyncio
import logging
from pyrogram import filters, enums
from pyrogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from AnnieXMedia import app
from config import OWNER_ID

from .engine import ask_ollama_stream, USER_HISTORY, CACHE
from .prompts import build_system_prompt

# ===============================
# Logging
# ===============================
logger = logging.getLogger("AnnieX_AI_Handlers")

# ===============================
# Globals
# ===============================
AI_STATUS = True
AI_MODE = "عام"
AI_MODEL = "qwen2.5:32b"

PERMANENT_USERS = set()

# ===============================
# SUDO
# ===============================
if isinstance(OWNER_ID, (list, tuple, set)):
    SUDO_USERS = set(OWNER_ID)
else:
    SUDO_USERS = {OWNER_ID}

SUDO_FILTER = filters.user(list(SUDO_USERS))

# ===============================
# Helpers
# ===============================
def is_sudo(uid: int) -> bool:
    return uid in SUDO_USERS


def extract_prompt(text: str) -> str:
    trigger = re.match(r"^(ذكاء|يا بوت|بوت|بقولك)(\s+|$)", text)
    if trigger:
        return text[trigger.end():].strip()
    return text.strip()


def should_trigger_ai(message: Message, bot_id: int) -> bool:
    uid = message.from_user.id

    if uid in PERMANENT_USERS:
        return True

    if message.reply_to_message:
        if (
            message.reply_to_message.from_user
            and message.reply_to_message.from_user.id == bot_id
        ):
            return True

    if re.match(r"^(ذكاء|يا بوت|بوت|بقولك)", message.text or ""):
        return True

    return False


def owner_only(cb: CallbackQuery) -> bool:
    if not is_sudo(cb.from_user.id):
        asyncio.create_task(
            cb.answer("للمالك فقط.", show_alert=True)
        )
        return False
    return True


# ===============================
# Keyboards
# ===============================
def main_ai_keyboard():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("أوامر المستخدمين", callback_data="ai_users"),
                InlineKeyboardButton("أوامر الأدمن", callback_data="ai_admin"),
            ],
            [
                InlineKeyboardButton("أوامر المالك", callback_data="ai_owner"),
            ],
            [
                InlineKeyboardButton("إغلاق", callback_data="ai_close"),
            ],
        ]
    )


def owner_keyboard():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("تشغيل / إيقاف", callback_data="ai_toggle"),
                InlineKeyboardButton("تبديل النمط", callback_data="ai_mode"),
            ],
            [
                InlineKeyboardButton("تبديل الموديل", callback_data="ai_model"),
                InlineKeyboardButton("إعادة تهيئة", callback_data="ai_reset"),
            ],
            [
                InlineKeyboardButton("تنظيف الذكاء", callback_data="ai_clean"),
            ],
            [
                InlineKeyboardButton("رجوع", callback_data="ai_back"),
            ],
        ]
    )


# ===============================
# AI Control Entry
# ===============================
@app.on_message(filters.regex(r"^(كيب الذكاء|كيب ذكاء|اوامر الذكاء)$"))
async def ai_keyboard_entry(_, m: Message):
    txt = (
        "لوحة أوامر الذكاء الاصطناعي\n\n"
        "اختر القسم المناسب."
    )
    await m.reply_text(txt, reply_markup=main_ai_keyboard())


# ===============================
# Callbacks (Navigation)
# ===============================
@app.on_callback_query(filters.regex("^ai_"))
async def ai_callbacks(_, cb: CallbackQuery):
    data = cb.data

    if data == "ai_close":
        await cb.message.delete()
        return

    if data == "ai_back":
        await cb.message.edit_text(
            "لوحة أوامر الذكاء الاصطناعي",
            reply_markup=main_ai_keyboard(),
        )
        return

    if data == "ai_users":
        await cb.message.edit_text(
            "أوامر المستخدمين:\n\n"
            "ذكاء دائم\n"
            "كفاية\n"
            "النداء: ذكاء / يا بوت",
            reply_markup=main_ai_keyboard(),
        )
        return

    if data == "ai_admin":
        await cb.message.edit_text(
            "أوامر الأدمن:\n\n"
            "لا يوجد تحكم مباشر.\n"
            "التحكم الكامل للمالك فقط.",
            reply_markup=main_ai_keyboard(),
        )
        return

    if data == "ai_owner":
        if not owner_only(cb):
            return
        await cb.message.edit_text(
            "لوحة تحكم المالك\n\n"
            f"الحالة: {'مفعل' if AI_STATUS else 'معطل'}\n"
            f"النمط: {AI_MODE}\n"
            f"الموديل: {AI_MODEL}",
            reply_markup=owner_keyboard(),
        )
        return

    # ===============================
    # Owner Actions
    # ===============================
    if not owner_only(cb):
        return

    global AI_STATUS, AI_MODE, AI_MODEL

    if data == "ai_toggle":
        AI_STATUS = not AI_STATUS
        await cb.answer("تم التغيير.")
    elif data == "ai_mode":
        AI_MODE = "تقني" if AI_MODE == "عام" else "عام"
        await cb.answer("تم تبديل النمط.")
    elif data == "ai_model":
        AI_MODEL = (
            "qwen2.5:7b"
            if AI_MODEL == "qwen2.5:32b"
            else "qwen2.5:32b"
        )
        await cb.answer("تم تبديل الموديل.")
    elif data == "ai_reset":
        USER_HISTORY.clear()
        await cb.answer("تمت إعادة التهيئة.")
    elif data == "ai_clean":
        USER_HISTORY.clear()
        CACHE._data.clear()
        PERMANENT_USERS.clear()
        await cb.answer("تم التنظيف الكامل.")

    await cb.message.edit_text(
        "لوحة تحكم المالك\n\n"
        f"الحالة: {'مفعل' if AI_STATUS else 'معطل'}\n"
        f"النمط: {AI_MODE}\n"
        f"الموديل: {AI_MODEL}",
        reply_markup=owner_keyboard(),
    )


# ===============================
# User Commands
# ===============================
@app.on_message(filters.regex(r"^(ذكاء دائم|افتح دائم)$"))
async def enable_permanent(_, m: Message):
    PERMANENT_USERS.add(m.from_user.id)
    await m.reply_text("تم تفعيل الوضع الدائم.")


@app.on_message(filters.regex(r"^(كفاية|خروج من الذكاء|انهاء)$"))
async def disable_permanent(_, m: Message):
    if m.from_user.id in PERMANENT_USERS:
        PERMANENT_USERS.remove(m.from_user.id)
        await m.reply_text("تم الخروج من الوضع الدائم.")
    else:
        await m.reply_text("أنت غير مفعل الوضع الدائم.")


# ===============================
# Main AI Handler
# ===============================
@app.on_message(filters.text & ~filters.bot, group=60)
async def ai_message_handler(client, m: Message):
    if not AI_STATUS and not is_sudo(m.from_user.id):
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
        return

    system_prompt = build_system_prompt(AI_MODE)

    try:
        await client.send_chat_action(m.chat.id, enums.ChatAction.TYPING)
    except Exception:
        pass

    wait = await m.reply_text("جاري التفكير...")

    last = ""

    async def on_update(t: str):
        nonlocal last
        if t.strip() == last.strip():
            return
        last = t
        try:
            await wait.edit(t[:1800])
        except Exception:
            pass

    try:
        reply = await ask_ollama_stream(
            user_id=m.from_user.id,
            prompt=prompt,
            on_update=on_update,
        )
        await wait.edit(reply)
    except Exception as e:
        logger.error(e)
        await wait.edit("حصل خطأ داخلي.")
