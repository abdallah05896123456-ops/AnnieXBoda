# plugins/ai/handlers.py
# Authored By Certified Coders © 2026
# High-Performance AI Handlers (Streaming / Control Keyboard / Stable Output)

import os
import re
import logging
from typing import Optional

from pyrogram import filters
from pyrogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from AnnieXMedia import app
from config import OWNER_ID

from .engine import ask_ollama_stream, AI, USER_HISTORY, CACHE
from .prompts import build_system_prompt

logger = logging.getLogger("AnnieX_AI_Handlers")
logging.basicConfig(level=logging.INFO)

# -------------------------
# OWNER / SUDO
# -------------------------
if isinstance(OWNER_ID, (list, tuple, set)):
    SUDO_USERS = list(OWNER_ID)
else:
    SUDO_USERS = [OWNER_ID]

SUDO_FILTER = filters.user(SUDO_USERS)

# -------------------------
# Helpers
# -------------------------
def extract_prompt(text: str) -> str:
    trigger = re.match(r"^(ذكاء|يا بوت|بوت|بقولك)(\s+|$)", text or "", re.IGNORECASE)
    if trigger:
        return text[trigger.end():].strip()
    return (text or "").strip()

def should_trigger_ai(message: Message, bot_id: Optional[int]) -> bool:
    if not message.from_user:
        return False

    uid = message.from_user.id

    if uid in AI.permanent_users:
        return True

    if message.reply_to_message:
        if (
            message.reply_to_message.from_user
            and message.reply_to_message.from_user.id == bot_id
        ):
            return True

    return bool(re.match(r"^(ذكاء|يا بوت|بوت|بقولك)", message.text or "", re.IGNORECASE))

def owner_only_text() -> str:
    return "هذا الزر مخصص للمالك فقط."

# -------------------------
# Keyboards
# -------------------------
def build_control_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("اوامر المستخدمين", callback_data="ai_kb_group")],
            [
                InlineKeyboardButton("اوامر المالك", callback_data="ai_kb_owner"),
                InlineKeyboardButton("اوامر الادمن", callback_data="ai_kb_admin"),
            ],
            [
                InlineKeyboardButton("تشغيل / ايقاف", callback_data="ai_toggle"),
                InlineKeyboardButton("تنظيف الذاكرة", callback_data="ai_clean"),
            ],
            [
                InlineKeyboardButton("تبديل الموديل", callback_data="ai_models"),
                InlineKeyboardButton("اعادة تشغيل الذكاء", callback_data="ai_restart"),
            ],
            [InlineKeyboardButton("اغلاق الكيبورد", callback_data="ai_close_kb")],
        ]
    )

def build_models_keyboard() -> InlineKeyboardMarkup:
    models = ["qwen2.5:7b", "qwen2.5:14b", "qwen2.5:32b"]
    rows = [[InlineKeyboardButton(m, callback_data=f"ai_switch:{m}")] for m in models]
    rows.append([InlineKeyboardButton("رجوع", callback_data="ai_back")])
    return InlineKeyboardMarkup(rows)

# -------------------------
# Control Panel Command
# -------------------------
@app.on_message(filters.regex(r"^(كيب الذكاء|كيب ذكاء|اوامر الذكاء)$") & SUDO_FILTER)
async def ai_control_panel(_, m: Message):
    text = (
        "لوحة تحكم الذكاء\n\n"
        f"الحالة: {'مفعل' if AI.status else 'معطل'}\n"
        f"النمط: {AI.mode}\n"
        f"الموديل الحالي: {AI.model}\n"
        f"عدد المستخدمين الدائمين: {len(AI.permanent_users)}\n"
    )
    await m.reply_text(text, reply_markup=build_control_keyboard())

# -------------------------
# Callbacks
# -------------------------
@app.on_callback_query(filters.regex("^ai_"))
async def ai_callbacks(_, q: CallbackQuery):
    data = q.data
    uid = q.from_user.id

    if data == "ai_kb_group":
        await q.answer(
            "اوامر المستخدمين:\n"
            "- ذكاء <سؤال>\n"
            "- ذكاء دائم\n"
            "- كفاية\n"
            "- مسح ذاكرتي",
            show_alert=True,
        )
        return

    if data == "ai_kb_owner":
        if uid not in SUDO_USERS:
            await q.answer(owner_only_text(), show_alert=True)
            return
        await q.answer("هذه الاوامر مخصصة للمالك.", show_alert=True)
        return

    if data == "ai_kb_admin":
        await q.answer("لا توجد اوامر اضافية للادمن حاليا.", show_alert=True)
        return

    if data == "ai_toggle":
        if uid not in SUDO_USERS:
            await q.answer(owner_only_text(), show_alert=True)
            return
        AI.status = not AI.status
        await q.answer(
            f"تم {'تشغيل' if AI.status else 'ايقاف'} الذكاء الاصطناعي",
            show_alert=True,
        )
        return

    if data == "ai_clean":
        if uid not in SUDO_USERS:
            await q.answer(owner_only_text(), show_alert=True)
            return
        USER_HISTORY.clear()
        CACHE.clear()
        AI.permanent_users.clear()
        await q.answer("تم تنظيف الذاكرة بالكامل.", show_alert=True)
        return

    if data == "ai_models":
        if uid not in SUDO_USERS:
            await q.answer(owner_only_text(), show_alert=True)
            return
        await q.message.edit_text(
            "اختر الموديل:", reply_markup=build_models_keyboard()
        )
        return

    if data.startswith("ai_switch:"):
        if uid not in SUDO_USERS:
            await q.answer(owner_only_text(), show_alert=True)
            return
        AI.model = data.split(":", 1)[1]
        await q.answer(f"تم التبديل الى الموديل {AI.model}", show_alert=True)
        return

    if data == "ai_restart":
        if uid not in SUDO_USERS:
            await q.answer(owner_only_text(), show_alert=True)
            return
        await q.answer("اعادة تشغيل النظام...", show_alert=True)
        os._exit(0)

    if data == "ai_close_kb":
        await q.message.delete()

# -------------------------
# User Commands
# -------------------------
@app.on_message(filters.regex(r"^(ذكاء دائم)$") & ~filters.bot)
async def enable_permanent(_, m: Message):
    AI.permanent_users.add(m.from_user.id)
    await m.reply_text("تم تفعيل وضع الذكاء الدائم.")

@app.on_message(filters.regex(r"^(كفاية|خروج)$") & ~filters.bot)
async def disable_permanent(_, m: Message):
    AI.permanent_users.discard(m.from_user.id)
    await m.reply_text("تم ايقاف الذكاء الدائم.")

@app.on_message(filters.regex(r"^(مسح ذاكرتي)$") & ~filters.bot)
async def clear_user(_, m: Message):
    USER_HISTORY.pop(m.from_user.id, None)
    await m.reply_text("تم مسح ذاكرتك.")

# -------------------------
# Main AI Handler
# -------------------------
@app.on_message(filters.text & ~filters.bot, group=60)
async def ai_handler(client, m: Message):
    if not AI.status and m.from_user.id not in SUDO_USERS:
        return

    try:
        me = client.me or await client.get_me()
        bot_id = me.id
    except Exception:
        bot_id = None

    if not should_trigger_ai(m, bot_id):
        return

    prompt = extract_prompt(m.text)
    system_prompt = build_system_prompt(AI.mode)

    wait_msg = await m.reply_text("جاري التفكير...")

    async def on_update(text: str):
        try:
            await wait_msg.edit(text[:1800])
        except:
            pass

    reply = await ask_ollama_stream(
        user_id=m.from_user.id,
        prompt=prompt,
        system_prompt=system_prompt,
        model=AI.model,
        on_update=on_update,
    )

    await wait_msg.edit(reply)
