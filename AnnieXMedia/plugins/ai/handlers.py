# plugins/ai/handlers.py
# Authored By Certified Coders © 2026
# AI Handlers - Stable / Fast / Settings Enabled

import os
import re
import time
import logging
from typing import Optional, Set

from pyrogram import filters
from pyrogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from AnnieXMedia import app
from config import OWNER_ID

# استيراد دوال المحرك الجديد (g4f)
from .engine import (
    AI,
    ask_ollama_stream,
    clear_all_memory,
    clear_user_memory,
    set_light_model,
    set_heavy_model,
    toggle_model, # دالة التبديل الجديدة
    get_model,
)

from .prompts import build_system_prompt

logger = logging.getLogger("AnnieX_AI_Handlers")
logging.basicConfig(level=logging.INFO)

# -------------------------------------------------
# OWNER / SUDO
# -------------------------------------------------
if isinstance(OWNER_ID, (list, tuple, set)):
    SUDO_USERS = set(OWNER_ID)
else:
    SUDO_USERS = {OWNER_ID}

SUDO_FILTER = filters.user(list(SUDO_USERS))

# -------------------------------------------------
# AI STATE
# -------------------------------------------------
class AIState:
    def __init__(self):
        self.enabled: bool = True
        self.mode: str = "عام"
        self.permanent_users: Set[int] = set()
        self.speed: str = "light"  # light | heavy

AI_STATE = AIState()

# -------------------------------------------------
# Helpers
# -------------------------------------------------
def extract_prompt(text: str) -> str:
    trigger = re.match(r"^(ذكاء|يا بوت|بوت|بقولك)(\s+|$)", text or "", re.IGNORECASE)
    if trigger:
        return text[trigger.end():].strip()
    return (text or "").strip()


def should_trigger_ai(message: Message, bot_id: Optional[int]) -> bool:
    if not message.from_user:
        return False

    uid = message.from_user.id

    if uid in AI_STATE.permanent_users:
        return True

    if message.reply_to_message:
        if (
            message.reply_to_message.from_user
            and message.reply_to_message.from_user.id == bot_id
        ):
            return True

    return bool(re.match(r"^(ذكاء|يا بوت|بوت|بقولك)", message.text or "", re.IGNORECASE))


def owner_only_text() -> str:
    return "هذا الامر مخصص للمالك فقط."

# -------------------------------------------------
# Keyboards
# -------------------------------------------------
def build_control_keyboard() -> InlineKeyboardMarkup:
    # تحديد حالة السرعة للعرض في الزرار
    speed_icon = "⚡" if AI_STATE.speed == "light" else "🧠"
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("اوامر المستخدمين", callback_data="ai_users")],
            [
                InlineKeyboardButton("اوامر المالك", callback_data="ai_owner"),
                InlineKeyboardButton("الاعدادات", callback_data="ai_settings"),
            ],
            [
                InlineKeyboardButton("تشغيل / ايقاف", callback_data="ai_toggle"),
                InlineKeyboardButton("تنظيف الذاكرة", callback_data="ai_clean"),
            ],
            [
                InlineKeyboardButton(f"تبديل السرعة {speed_icon}", callback_data="ai_speed"),
                InlineKeyboardButton("اعادة تشغيل", callback_data="ai_restart"),
            ],
            [InlineKeyboardButton("اغلاق", callback_data="ai_close")],
        ]
    )


def build_settings_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("خفيف (سريع)", callback_data="ai_light"),
                InlineKeyboardButton("تقيل (ذكي)", callback_data="ai_heavy"),
            ],
            [InlineKeyboardButton("رجوع", callback_data="ai_back")],
        ]
    )

# -------------------------------------------------
# Control Panel
# -------------------------------------------------
@app.on_message(filters.regex(r"^(اوامر الذكاء|كيب ذكاء|كيب الذكاء)$") & SUDO_FILTER)
async def ai_control_panel(_, m: Message):
    text = (
        "**🤖 لوحة تحكم الذكاء الاصطناعي (G4F Engine)**\n\n"
        f"• **الحالة:** {'✅ مفعل' if AI_STATE.enabled else '❌ معطل'}\n"
        f"• **الموديل:** `{get_model()}`\n"
        f"• **الوضع:** {'⚡ سريع' if AI_STATE.speed == 'light' else '🧠 ذكي'}\n"
        f"• **المتصلين:** `{len(AI_STATE.permanent_users)}`\n"
    )
    await m.reply_text(text, reply_markup=build_control_keyboard())

# -------------------------------------------------
# Callbacks
# -------------------------------------------------
@app.on_callback_query(filters.regex("^ai_"))
async def ai_callbacks(_, q: CallbackQuery):
    data = q.data
    uid = q.from_user.id

    if data == "ai_users":
        await q.answer(
            "اوامر المستخدم:\n"
            "- ذكاء <سؤال>\n"
            "- ذكاء دائم\n"
            "- كفاية\n"
            "- مسح ذاكرتي",
            show_alert=True,
        )
        return

    if data == "ai_owner":
        if uid not in SUDO_USERS:
            await q.answer(owner_only_text(), show_alert=True)
            return
        await q.answer("لديك صلاحيات كاملة.", show_alert=True)
        return

    if data == "ai_settings":
        if uid not in SUDO_USERS:
            await q.answer(owner_only_text(), show_alert=True)
            return
        await q.message.edit_text(
            "اعدادات الذكاء الاصطناعي:",
            reply_markup=build_settings_keyboard(),
        )
        return

    # تبديل مباشر للسرعة
    if data == "ai_speed":
        if uid not in SUDO_USERS:
            await q.answer(owner_only_text(), show_alert=True)
            return
        
        new_model = toggle_model()
        if "gpt-4" in new_model:
            AI_STATE.speed = "heavy"
            msg = "تم التفعيل: الوضع الذكي (GPT-4)"
        else:
            AI_STATE.speed = "light"
            msg = "تم التفعيل: الوضع السريع (GPT-3.5)"
            
        await q.answer(msg, show_alert=True)
        # تحديث اللوحة
        text = (
            "**🤖 لوحة تحكم الذكاء الاصطناعي (G4F Engine)**\n\n"
            f"• **الحالة:** {'✅ مفعل' if AI_STATE.enabled else '❌ معطل'}\n"
            f"• **الموديل:** `{get_model()}`\n"
            f"• **الوضع:** {'⚡ سريع' if AI_STATE.speed == 'light' else '🧠 ذكي'}\n"
            f"• **المتصلين:** `{len(AI_STATE.permanent_users)}`\n"
        )
        try:
            await q.message.edit_text(text, reply_markup=build_control_keyboard())
        except:
            pass
        return

    if data == "ai_light":
        set_light_model()
        AI_STATE.speed = "light"
        await q.answer("تم تفعيل الوضع الخفيف السريع.", show_alert=True)
        return

    if data == "ai_heavy":
        set_heavy_model()
        AI_STATE.speed = "heavy"
        await q.answer("تم تفعيل الوضع التقيل الذكي.", show_alert=True)
        return

    if data == "ai_back":
        text = (
            "**🤖 لوحة تحكم الذكاء الاصطناعي (G4F Engine)**\n\n"
            f"• **الحالة:** {'✅ مفعل' if AI_STATE.enabled else '❌ معطل'}\n"
            f"• **الموديل:** `{get_model()}`\n"
            f"• **الوضع:** {'⚡ سريع' if AI_STATE.speed == 'light' else '🧠 ذكي'}\n"
            f"• **المتصلين:** `{len(AI_STATE.permanent_users)}`\n"
        )
        await q.message.edit_text(
            text,
            reply_markup=build_control_keyboard(),
        )
        return

    if data == "ai_toggle":
        if uid not in SUDO_USERS:
            await q.answer(owner_only_text(), show_alert=True)
            return
        AI_STATE.enabled = not AI_STATE.enabled
        AI.enabled = AI_STATE.enabled
        await q.answer("تم تحديث حالة الذكاء.", show_alert=True)
        # تحديث شكل الزر
        text = (
            "**🤖 لوحة تحكم الذكاء الاصطناعي (G4F Engine)**\n\n"
            f"• **الحالة:** {'✅ مفعل' if AI_STATE.enabled else '❌ معطل'}\n"
            f"• **الموديل:** `{get_model()}`\n"
            f"• **الوضع:** {'⚡ سريع' if AI_STATE.speed == 'light' else '🧠 ذكي'}\n"
            f"• **المتصلين:** `{len(AI_STATE.permanent_users)}`\n"
        )
        try:
            await q.message.edit_text(text, reply_markup=build_control_keyboard())
        except:
            pass
        return

    if data == "ai_clean":
        if uid not in SUDO_USERS:
            await q.answer(owner_only_text(), show_alert=True)
            return
        clear_all_memory()
        AI_STATE.permanent_users.clear()
        await q.answer("تم تنظيف الذاكرة.", show_alert=True)
        return

    if data == "ai_restart":
        if uid not in SUDO_USERS:
            await q.answer(owner_only_text(), show_alert=True)
            return
        os._exit(0)

    if data == "ai_close":
        await q.message.delete()

# -------------------------------------------------
# User Commands
# -------------------------------------------------
@app.on_message(filters.regex(r"^(ذكاء دائم)$") & ~filters.bot)
async def enable_permanent(_, m: Message):
    AI_STATE.permanent_users.add(m.from_user.id)
    await m.reply_text("تم تفعيل وضع الذكاء الدائم.")

@app.on_message(filters.regex(r"^(كفاية|خروج)$") & ~filters.bot)
async def disable_permanent(_, m: Message):
    AI_STATE.permanent_users.discard(m.from_user.id)
    await m.reply_text("تم ايقاف الذكاء الدائم.")

@app.on_message(filters.regex(r"^(مسح ذاكرتي)$") & ~filters.bot)
async def clear_user(_, m: Message):
    clear_user_memory(m.from_user.id)
    await m.reply_text("تم مسح ذاكرتك.")

# -------------------------------------------------
# Main AI Handler (FAST + SAFE)
# -------------------------------------------------
@app.on_message(filters.text & ~filters.bot, group=60)
async def ai_handler(client, m: Message):
    if not AI_STATE.enabled and m.from_user.id not in SUDO_USERS:
        return

    try:
        bot_id = (client.me or await client.get_me()).id
    except Exception:
        bot_id = None

    if not should_trigger_ai(m, bot_id):
        return

    prompt = extract_prompt(m.text)
    if not prompt:
        return

    system_prompt = build_system_prompt(AI_STATE.mode)

    wait_msg = await m.reply_text("جاري التفكير ...")

    last_edit = 0

    async def on_update(text: str):
        nonlocal last_edit
        now = time.time()
        if now - last_edit < 1.2:
            return
        last_edit = now
        try:
            await wait_msg.edit(text[:1800])
        except Exception:
            pass

    reply = await ask_ollama_stream(
        user_id=m.from_user.id,
        prompt=prompt,
        system_prompt=system_prompt,
        on_update=on_update,
    )

    await wait_msg.edit(reply)
