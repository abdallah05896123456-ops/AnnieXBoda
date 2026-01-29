# plugins/ai/handlers.py
# Authored By Certified Coders © 2026
# High-Performance AI Handlers (Streaming / Control Keyboard / Stable Output)
# هذا الملف يحل مشكلة global ويضيف لوحة أوامر تفاعلية مع صلاحيات (مالك / أدمن / مستخدم)

import os
import re
import asyncio
import logging
from typing import Optional, Callable, Any, Set

from pyrogram import filters, enums
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from AnnieXMedia import app
from config import OWNER_ID

# استيراد محرك الذكاء (الدالة الرئيسية للاستدعاء)
from .engine import ask_ollama_stream  # واجهة الاستدعاء للبث
from . import engine as ai_engine    # للوصول إلى USER_HISTORY و CACHE إن وُجدت
from .prompts import build_system_prompt

logger = logging.getLogger("AnnieX_AI_Handlers")
logging.basicConfig(level=logging.INFO)

# -------------------------
# حالة النظام (بدون استخدام global مباشرة)
# -------------------------
class AIState:
    def __init__(self):
        self.status: bool = True                # تشغيل / إيقاف الذكاء
        self.mode: str = "عام"                  # "عام" أو "تقني"
        self.model: str = getattr(ai_engine, "OLLAMA_MODEL_DEFAULT", os.getenv("OLLAMA_MODEL", "qwen2.5:7b"))
        self.permanent_users: Set[int] = set()  # مستخدمين في وضع دائم

AI = AIState()

# -------------------------
# SUDO / OWNER configuration
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
    """
    يشيل كلمات النداء ويطلع الطلب الحقيقي
    """
    trigger = re.match(r"^(ذكاء|يا بوت|بوت|بقولك)(\s+|$)", text or "", re.IGNORECASE)
    if trigger:
        return text[trigger.end():].strip()
    return (text or "").strip()

def should_trigger_ai(message: Message, bot_id: Optional[int]) -> bool:
    """
    الذكاء يشتغل في الحالات:
    - رد مباشر على البوت
    - مستخدم مفعل وضع دائم
    - رسالة تبدأ بكلمة نداء
    """
    if not message.from_user:
        return False
    uid = message.from_user.id

    if uid in AI.permanent_users:
        return True

    if message.reply_to_message:
        if message.reply_to_message.from_user and getattr(message.reply_to_message.from_user, "id", None) == bot_id:
            return True

    if re.match(r"^(ذكاء|يا بوت|بوت|بقولك)", message.text or "", re.IGNORECASE):
        return True

    return False

def owner_only_text() -> str:
    return "هذا الزر مخصص للمالك فقط."

# -------------------------
# Keyboard / Panel builder
# -------------------------
def build_control_keyboard() -> InlineKeyboardMarkup:
    """
    يبني لوحة أوامر:
    - صف للمستخدمين العاديين (زر عرض الأوامر العامة)
    - صف للمالك (زر إجراء تحكم رئيسي)
    - صف للأدمن (زر عرض أوامر الأدمن)
    - صف أزرار تشغيل/إيقاف، تنظيف، تبديل موديل، رسترة، إغلاق اللوحة
    """
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("أوامر المجموعة", callback_data="ai_kb_group")],
            [InlineKeyboardButton("أوامر المالك", callback_data="ai_kb_owner"),
             InlineKeyboardButton("أوامر الأدمن", callback_data="ai_kb_admin")],
            [
                InlineKeyboardButton("تشغيل/إيقاف الذكاء", callback_data="ai_toggle"),
                InlineKeyboardButton("تنظيف الذاكرة", callback_data="ai_clean")
            ],
            [
                InlineKeyboardButton("تبديل الموديل", callback_data="ai_models"),
                InlineKeyboardButton("إعادة تشغيل الذكاء", callback_data="ai_restart")
            ],
            [InlineKeyboardButton("إغلاق اللوحة", callback_data="ai_close_kb")]
        ]
    )
    return kb

def build_models_keyboard() -> InlineKeyboardMarkup:
    # قائمة موديلات افتراضية يمكنك تعديلها حسب ما هو متاح عندك
    models = [
        "qwen2.5:7b",
        "qwen2.5:32b",
        "qwen2.5:14b",
        "local-lite"
    ]
    rows = [[InlineKeyboardButton(m, callback_data=f"ai_switch_model:{m}")] for m in models]
    rows.append([InlineKeyboardButton("عودة", callback_data="ai_kb_back")])
    return InlineKeyboardMarkup(rows)

# -------------------------
# Developer Control Panel (عرض اللوحة)
# -------------------------
@app.on_message(filters.regex(r"^(كيب الذكاء|كيب ذكاء|اوامر الذكاء)$") & SUDO_FILTER)
async def ai_control_panel(_, m: Message):
    status_txt = "مفعل" if AI.status else "معطل"
    mode_txt = AI.mode
    model_txt = AI.model

    txt = (
        "لوحة تحكم الذكاء\n\n"
        f"الحالة: {status_txt}\n"
        f"النمط: {mode_txt}\n"
        f"الموديل الحالي: {model_txt}\n"
        f"عدد المستخدمين في الوضع الدائم: {len(AI.permanent_users)}\n\n"
        "اختر زر من اللوحة لمعرفة الأوامر أو للتحكم."
    )

    try:
        await m.reply_text(txt, reply_markup=build_control_keyboard())
    except Exception as e:
        logger.error("Failed to send control panel: %s", e)
        try:
            await m.reply_text(txt)
        except:
            pass

# -------------------------
# Callback query handler (جميع أزرار اللوحة)
# -------------------------
@app.on_callback_query(filters.regex(r"^ai_"))
async def ai_panel_callback(_, q: CallbackQuery):
    data = q.data or ""
    user_id = q.from_user.id

    # ---------- المجموعة (عرض أوامر عامة)
    if data == "ai_kb_group":
        group_txt = (
            "أوامر للمستخدمين:\n"
            "- اكتب 'ذكاء <سؤال>' أو راسل البوت مباشرة للرد.\n"
            "- ارسل 'ذكاء دائم' لتفعيل الوضع الدائم لك.\n"
            "- ارسل 'كفاية' أو 'خروج من الذكاء' للخروج من الوضع الدائم.\n"
            "- ارسل 'مسح ذاكرتي' لمسح الذاكرة الخاصة بك."
        )
        await q.answer(group_txt, show_alert=True)
        return

    # ---------- أوامر المالك (مطلوب صلاحية)
    if data == "ai_kb_owner":
        if user_id not in SUDO_USERS:
            await q.answer(owner_only_text(), show_alert=True)
            return
        owner_txt = (
            "أوامر المالك:\n"
            "- تشغيل/إيقاف الذكاء (زر في اللوحة).\n"
            "- تبديل الموديل.\n"
            "- تنظيف الذاكرة العالمية.\n"
            "- إعادة تشغيل خدمة الذكاء.\n"
            "- إغلاق اللوحة."
        )
        await q.answer(owner_txt, show_alert=True)
        return

    # ---------- أوامر الأدمن (معاينة)
    if data == "ai_kb_admin":
        admin_txt = (
            "أوامر الأدمن:\n"
            "- عرض أوامر المجموعة للأعضاء.\n"
            "- لا توجد صلاحيات إدارية إضافية في هذه اللوحة حالياً."
        )
        await q.answer(admin_txt, show_alert=True)
        return

    # ---------- تبديل تشغيل/ايقاف الذكاء
    if data == "ai_toggle":
        if user_id not in SUDO_USERS:
            await q.answer(owner_only_text(), show_alert=True)
            return
        AI.status = not AI.status
        await q.answer(f"الحالة الآن: {'مفعل' if AI.status else 'معطل'}", show_alert=True)
        # حدث رسالة اللوحة إن أمكن
        try:
            await q.message.edit_text(
                "لوحة تحكم الذكاء\n\n"
                f"الحالة: {'مفعل' if AI.status else 'معطل'}\n"
                f"النمط: {AI.mode}\n"
                f"الموديل الحالي: {AI.model}\n\n"
                "اختر زر من اللوحة.", reply_markup=build_control_keyboard()
            )
        except:
            pass
        return

    # ---------- تنظيف الذاكرة
    if data == "ai_clean":
        if user_id not in SUDO_USERS:
            await q.answer(owner_only_text(), show_alert=True)
            return
        # مسح الذاكرة في الموديل إن وُجد
        cleaned = []
        try:
            if hasattr(ai_engine, "USER_HISTORY"):
                ai_engine.USER_HISTORY.clear()
                cleaned.append("USER_HISTORY")
        except Exception:
            logger.exception("Failed to clear USER_HISTORY")
        try:
            if hasattr(ai_engine, "CACHE"):
                try:
                    # بعض نسخ تستخدم كائن cache مختلف
                    ai_engine.CACHE._data.clear()
                except Exception:
                    # fallback
                    ai_engine.CACHE = None
                cleaned.append("CACHE")
        except Exception:
            logger.exception("Failed to clear CACHE")
        # تنظيف في الكلاس المحلي أيضاً
        AI.permanent_users.clear()
        result_txt = "تم تنظيف الذاكرة."
        await q.answer(result_txt, show_alert=True)
        return

    # ---------- فتح قائمة الموديلات
    if data == "ai_models":
        if user_id not in SUDO_USERS:
            await q.answer(owner_only_text(), show_alert=True)
            return
        try:
            await q.message.edit_text("اختر موديل للتبديل:", reply_markup=build_models_keyboard())
        except Exception:
            await q.answer("خطأ في عرض قائمة الموديلات.", show_alert=True)
        return

    # ---------- تبديل موديل محدد
    if data.startswith("ai_switch_model:"):
        if user_id not in SUDO_USERS:
            await q.answer(owner_only_text(), show_alert=True)
            return
        _, model_name = data.split(":", 1)
        model_name = model_name.strip()
        # قم بتبديل الموديل في الحالة وفي المحرك إن كان موجوداً
        AI.model = model_name
        try:
            # إذا محرك ai_engine يدعم تعديل الموديل الافتراضي
            if hasattr(ai_engine, "OLLAMA_MODEL_DEFAULT"):
                ai_engine.OLLAMA_MODEL_DEFAULT = model_name
            if hasattr(ai_engine, "OLLAMA_MODEL"):
                ai_engine.OLLAMA_MODEL = model_name
        except Exception:
            logger.exception("Failed to set engine model variable")
        await q.answer(f"تم تبديل الموديل إلى: {model_name}", show_alert=True)
        try:
            await q.message.edit_text(
                "لوحة تحكم الذكاء\n\n"
                f"الحالة: {'مفعل' if AI.status else 'معطل'}\n"
                f"النمط: {AI.mode}\n"
                f"الموديل الحالي: {AI.model}\n\n"
                "اختر زر من اللوحة.", reply_markup=build_control_keyboard()
            )
        except:
            pass
        return

    # ---------- اعادة اللوحة الرئيسية
    if data == "ai_kb_back":
        try:
            await q.message.edit_text(
                "لوحة تحكم الذكاء\n\n"
                f"الحالة: {'مفعل' if AI.status else 'معطل'}\n"
                f"النمط: {AI.mode}\n"
                f"الموديل الحالي: {AI.model}\n\n"
                "اختر زر من اللوحة.", reply_markup=build_control_keyboard()
            )
        except:
            pass
        return

    # ---------- اعادة تشغيل الذكاء (مالك فقط)
    if data == "ai_restart":
        if user_id not in SUDO_USERS:
            await q.answer(owner_only_text(), show_alert=True)
            return
        await q.answer("جارٍ إعادة تشغيل خدمة الذكاء.", show_alert=True)
        # تنفيذ عملية إعادة التشغيل بطريقة بسيطة: حاول إنهاء العملية ليعاد تشغيلها من النظام (إذا أدارته)
        try:
            # إن أردت تنفيذ أوامر إضافية هنا يمكنك استدعاء سكربت خارجي
            os._exit(0)
        except Exception:
            pass
        return

    # ---------- اغلاق اللوحة
    if data == "ai_close_kb":
        # مسموح للجميع بغلق الرسالة نفسها
        try:
            await q.message.delete()
        except:
            try:
                await q.answer("تم إغلاق اللوحة.", show_alert=True)
            except:
                pass
        return

    # فشل افتراضي
    await q.answer("إجراء غير معروف.", show_alert=True)

# -------------------------
# Simple commands (نفس نصوصك مع تحسين)
# -------------------------
@app.on_message(filters.regex(r"^(تعطيل الذكاء|اقفل الذكاء)$") & SUDO_FILTER)
async def disable_ai_cmd(_, m: Message):
    AI.status = False
    await m.reply_text("تم تعطيل الذكاء.")

@app.on_message(filters.regex(r"^(تشغيل الذكاء|افتح الذكاء)$") & SUDO_FILTER)
async def enable_ai_cmd(_, m: Message):
    AI.status = True
    await m.reply_text("تم تشغيل الذكاء.")

@app.on_message(filters.regex(r"^(وضع تقني)$") & SUDO_FILTER)
async def switch_tech_cmd(_, m: Message):
    AI.mode = "تقني"
    await m.reply_text("تم التحويل للوضع التقني.")

@app.on_message(filters.regex(r"^(وضع عام)$") & SUDO_FILTER)
async def switch_general_cmd(_, m: Message):
    AI.mode = "عام"
    await m.reply_text("تم التحويل للوضع العام.")

# -------------------------
# User commands (وضع دائم ومسح ذاكرة شخصية)
# -------------------------
@app.on_message(filters.regex(r"^(ذكاء دائم|افتح دائم)$") & ~filters.bot)
async def enable_permanent(_, m: Message):
    uid = m.from_user.id
    AI.permanent_users.add(uid)
    await m.reply_text("تم تفعيل الوضع الدائم لك.")

@app.on_message(filters.regex(r"^(كفاية|خروج من الذكاء|انهاء)$") & ~filters.bot)
async def disable_permanent(_, m: Message):
    uid = m.from_user.id
    if uid in AI.permanent_users:
        AI.permanent_users.discard(uid)
        await m.reply_text("تم الخروج من الوضع الدائم.")
    else:
        await m.reply_text("أنت لست في الوضع الدائم.")

@app.on_message(filters.regex(r"^(مسح ذاكرتي|نسيان|تصفير)$") & ~filters.bot)
async def user_clear_history(_, m: Message):
    uid = m.from_user.id
    try:
        if hasattr(ai_engine, "USER_HISTORY"):
            ai_engine.USER_HISTORY.pop(uid, None)
        await m.reply_text("تم مسح الذاكرة الخاصة بك.")
    except Exception:
        await m.reply_text("لم أتمكن من مسح الذاكرة الآن.")

# -------------------------
# Main AI Handler (Streaming)
# -------------------------
@app.on_message(filters.text & ~filters.bot, group=60)
async def ai_message_handler(client, m: Message):
    # منع الرد لو الذكاء متوقف إلا للمالك
    if not AI.status and m.from_user.id not in SUDO_USERS:
        return

    if not m.text:
        return

    try:
        me = client.me or await client.get_me()
        bot_id = getattr(me, "id", None)
    except Exception:
        bot_id = None

    if not should_trigger_ai(m, bot_id):
        return

    prompt = extract_prompt(m.text)
    if not prompt:
        await m.reply_text("نعم؟")
        return

    # بناء system prompt من ملف prompts.py
    system_prompt = build_system_prompt(AI.mode)

    # مؤشر كتابة
    try:
        await client.send_chat_action(m.chat.id, enums.ChatAction.TYPING)
    except:
        pass

    wait_msg = None
    try:
        wait_msg = await m.reply_text("جار التفكير...")
    except:
        wait_msg = None

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
        except:
            pass

    try:
        # استدعاء محرك الذكاء مع الموديل من الحالة
        reply = await ask_ollama_stream(
            user_id=m.from_user.id,
            prompt=prompt,
            on_update=on_update,
            system_prompt=system_prompt,
            model=AI.model,
            stream=True,
            timeout=None
        )

        if wait_msg:
            try:
                await wait_msg.edit(reply)
            except:
                await m.reply_text(reply)
        else:
            await m.reply_text(reply)

    except asyncio.TimeoutError:
        await m.reply_text("الذكاء تأخر في الرد. حاول مجدداً.")
    except Exception as e:
        logger.exception("AI handler error: %s", e)
        try:
            await m.reply_text("حصل خطأ داخلي. حاول لاحقاً.")
        except:
            pass
