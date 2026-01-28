# Authored By Certified Coders © 2026 (patched)
# System: Local AI (Debug Mode) | Full Error Tracing
# الـمـحـرك: Ollama (Qwen 2.5 32B) - نـظـام كـشـف الـأخـطـاء الـدقـيـق
# ملاحظة: ملف مستقل تماماً — لا علاقة له بالأذان أو دخول المساعد.

import asyncio
import aiohttp
import json
import os
import logging
import traceback
import re
from typing import Any, Dict, List, Optional

from pyrogram import filters, enums
from pyrogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)

from AnnieXMedia import app
from config import OWNER_ID

# -------------------------
# إعدادات النظام (قابلة للتعديل عبر متغيرات البيئة)
# -------------------------
OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", "http://127.0.0.1:11434/api/chat")
DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:32b")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AnnieX_AI")

# SUDO_USERS يجب أن يكون قائمة قابلة للتمرير إلى filters.user
if isinstance(OWNER_ID, (list, tuple, set)):
    SUDO_USERS = list(OWNER_ID)
else:
    SUDO_USERS = [OWNER_ID]

AI_STATUS: bool = True
AI_MODE: str = "عـام"  # "تـقـنـي" أو "عـام"
MAX_HISTORY: int = 8
user_history: Dict[int, List[Dict[str, str]]] = {}
PERMANENT_USERS: set = set()

STATE_DIR = "ai_data"
STATE_FILE = os.path.join(STATE_DIR, "ollama_settings.json")
os.makedirs(STATE_DIR, exist_ok=True)

# -------------------------
# دوال الحفظ والاستعادة
# -------------------------
def load_state() -> None:
    global PERMANENT_USERS, AI_STATUS, AI_MODE
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            PERMANENT_USERS = set(data.get("PERMANENT_USERS", []))
            AI_STATUS = bool(data.get("AI_STATUS", AI_STATUS))
            AI_MODE = data.get("AI_MODE", AI_MODE)
            logger.info("AI state loaded.")
    except Exception as e:
        logger.warning(f"Failed to load AI state: {e}")

def save_state() -> None:
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "PERMANENT_USERS": list(PERMANENT_USERS),
                "AI_STATUS": AI_STATUS,
                "AI_MODE": AI_MODE
            }, f, ensure_ascii=False, indent=2)
        logger.info("AI state saved.")
    except Exception as e:
        logger.warning(f"Failed to save AI state: {e}")

load_state()

# -------------------------
# دوال مساعدة لاستخراج نص من استجابة Ollama
# -------------------------
def extract_text_from_ollama_json(data: Any) -> str:
    """
    يحاول استخراج نص من صيغ JSON مختلفة قد تُعيدها خدمة Ollama.
    """
    try:
        if isinstance(data, dict):
            # شكل شائع: {"message": {"content": "..."}}
            if "message" in data and isinstance(data["message"], dict):
                cont = data["message"].get("content")
                if isinstance(cont, str) and cont.strip():
                    return cont.strip()
                if isinstance(cont, list):
                    parts = []
                    for p in cont:
                        if isinstance(p, dict):
                            # some formats may use {"text": "..."}
                            txt = p.get("text") or p.get("content")
                            if isinstance(txt, str):
                                parts.append(txt)
                        elif isinstance(p, str):
                            parts.append(p)
                    return " ".join(parts).strip()

            # أحوال بديلة
            for key in ("response", "output", "text"):
                if key in data and isinstance(data[key], str) and data[key].strip():
                    return data[key].strip()

            # choices -> [{ "message": {"content": ...} }]
            if "choices" in data and isinstance(data["choices"], list) and data["choices"]:
                first = data["choices"][0]
                if isinstance(first, dict):
                    # try nested message.content
                    msg = first.get("message") or first.get("delta") or first.get("output")
                    if isinstance(msg, dict):
                        cont = msg.get("content") or msg.get("text")
                        if isinstance(cont, str) and cont.strip():
                            return cont.strip()
                    txt = first.get("text")
                    if isinstance(txt, str) and txt.strip():
                        return txt.strip()

            # محاولة العثور على أول سترينغ في البنية كـ fallback
            def find_str(obj):
                if isinstance(obj, str) and obj.strip():
                    return obj.strip()
                if isinstance(obj, dict):
                    for v in obj.values():
                        s = find_str(v)
                        if s:
                            return s
                if isinstance(obj, list):
                    for item in obj:
                        s = find_str(item)
                        if s:
                            return s
                return None

            found = find_str(data)
            return found or ""
        if isinstance(data, str):
            return data.strip()
    except Exception as e:
        logger.debug(f"extract_text_from_ollama_json error: {e}")
    return ""

# -------------------------
# استدعاء محرك Ollama (شبكي) مع تحمّل أخطاء قوي
# -------------------------
async def ask_ollama(user_id: int, prompt: str) -> str:
    """
    يرسل الطلب إلى Ollama ويحاول استخراج الرد مع معالجة الأخطاء.
    """
    # system message حسب الوضع
    if AI_MODE == "تـقـنـي":
        sys_content = (
            "You are a Genius Senior Developer and a Hacker. "
            "You write complex, flawless, production-ready code. "
            "You speak Egyptian Arabic comfortably."
        )
    else:
        sys_content = (
            "You are a smart, witty Egyptian companion. "
            "You speak pure Egyptian slang (Masri). "
            "You understand deep sarcasm and street vibes."
        )

    messages = [{"role": "system", "content": sys_content}]
    history = user_history.get(user_id, [])
    for item in history:
        try:
            u = item.get("u", "")
            a = item.get("a", "")
            if u:
                messages.append({"role": "user", "content": u})
            if a:
                messages.append({"role": "assistant", "content": a})
        except:
            continue
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": DEFAULT_MODEL,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": 0.7,
            "num_ctx": 2048
        }
    }

    timeout = aiohttp.ClientTimeout(total=300)  # 5 دقائق
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(OLLAMA_API_URL, json=payload) as resp:
                data = None
                text_body = None
                try:
                    data = await resp.json(content_type=None)
                except Exception:
                    try:
                        text_body = await resp.text()
                    except Exception:
                        text_body = ""

                if resp.status == 200:
                    # نبدأ بمحاولة استخراج نص من الـ JSON
                    if data is not None:
                        extracted = extract_text_from_ollama_json(data)
                        if extracted:
                            # تحديث الذاكرة
                            hist = user_history.get(user_id, [])
                            hist.append({"u": prompt, "a": extracted})
                            if len(hist) > MAX_HISTORY:
                                hist = hist[-MAX_HISTORY:]
                            user_history[user_id] = hist
                            return extracted
                    # fallback لنص خام إن وجد
                    if text_body:
                        reply = text_body.strip()
                        if reply:
                            hist = user_history.get(user_id, [])
                            hist.append({"u": prompt, "a": reply})
                            if len(hist) > MAX_HISTORY:
                                hist = hist[-MAX_HISTORY:]
                            user_history[user_id] = hist
                            return reply
                    return "⚠️ الموديل رد ولكن لم يتم استخراج رد صالح."
                else:
                    body_snippet = (text_body or json.dumps(data or {}, ensure_ascii=False))[:800]
                    return f"❌ HTTP {resp.status} من خدمة الذكاء.\n{body_snippet}"
    except aiohttp.ClientConnectorError as e:
        logger.debug(f"Ollama connection error: {e}")
        return "🔌 خطأ اتصال: لا يمكن الوصول إلى خدمة Ollama (127.0.0.1:11434). تأكد من تشغيل الخدمة."
    except asyncio.TimeoutError:
        return "⏰ مهلة الاتصال انتهت (300s). الخدمة بطيئة أو غير متاحة."
    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f"ask_ollama unexpected: {e}\n{tb}")
        truncated = tb[:500].replace("\n", " ")
        return f"💀 خطأ داخلي في الذكاء:\n`{str(e)}`\n{truncated}"

# -------------------------
# لوحة تحكم المطور (Debug Panel)
# -------------------------
@app.on_message(filters.regex(r"^(كيب الذكاء|كيب ذكاء|اوامر الذكاء)$") & filters.user(SUDO_USERS))
async def ai_control_panel(_, m: Message):
    try:
        st_txt = "مـفـعـل" if AI_STATUS else "مـعـطـل"
        mode_txt = "تـقـنـي" if AI_MODE == "تـقـنـي" else "عـام"
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"الـحـالـة: {st_txt}", callback_data="toggle_ai_status"),
                InlineKeyboardButton(f"الـنـمـط: {mode_txt}", callback_data="toggle_ai_mode")
            ],
            [
                InlineKeyboardButton("تـنـظـيـف الـذاكـرة", callback_data="clean_ai_ram"),
                InlineKeyboardButton("إغـلاق", callback_data="close_ai_panel")
            ]
        ])
        text = (
            f"🤖 Debug Panel (Qwen 32B)\n"
            f"• Model: `{DEFAULT_MODEL}`\n"
            f"• Users in Memory: {len(user_history)}\n"
            f"• Permanent users: {len(PERMANENT_USERS)}"
        )
        await m.reply_text(text, reply_markup=keyboard)
    except Exception as e:
        logger.error(f"ai_control_panel error: {e}")

@app.on_callback_query(filters.regex(r"^(toggle_ai_|clean_ai_|close_ai_)"))
async def ai_panel_callback(_, q: CallbackQuery):
    global AI_STATUS, AI_MODE
    try:
        if q.from_user.id not in SUDO_USERS:
            return await q.answer("للمطور فقط.", show_alert=True)

        data = q.data or ""
        if data == "close_ai_panel":
            try:
                await q.message.delete()
            except:
                pass
            return

        if data == "toggle_ai_status":
            AI_STATUS = not AI_STATUS
            save_state()
            await q.answer(f"AI_STATUS -> {'ON' if AI_STATUS else 'OFF'}", show_alert=False)
        elif data == "toggle_ai_mode":
            AI_MODE = "تـقـنـي" if AI_MODE == "عـام" else "عـام"
            save_state()
            await q.answer(f"AI_MODE -> {AI_MODE}", show_alert=False)
        elif data == "clean_ai_ram":
            user_history.clear()
            await q.answer("تم تنظيف الذاكرة.", show_alert=True)

        # تحديث الأزرار
        st_txt = "مـفـعـل" if AI_STATUS else "مـعـطـل"
        mode_txt = "تـقـنـي" if AI_MODE == "تـقـنـي" else "عـام"
        new_kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"الـحـالـة: {st_txt}", callback_data="toggle_ai_status"),
                InlineKeyboardButton(f"الـنـمـط: {mode_txt}", callback_data="toggle_ai_mode")
            ],
            [
                InlineKeyboardButton("تـنـظـيـف الـذاكـرة", callback_data="clean_ai_ram"),
                InlineKeyboardButton("إغـلاق", callback_data="close_ai_panel")
            ]
        ])
        try:
            await q.message.edit_reply_markup(reply_markup=new_kb)
        except Exception:
            pass
    except Exception as e:
        logger.error(f"ai_panel_callback error: {e}")

# -------------------------
# أوامر المستخدمين لإدارة الحالة
# -------------------------
@app.on_message(filters.regex(r"^(ذكاء كفاية|خروج من الذكاء|انهاء|كفاية)$") & ~filters.bot)
async def user_exit_ai(_, m: Message):
    try:
        uid = m.from_user.id
        if uid in PERMANENT_USERS:
            PERMANENT_USERS.discard(uid)
            save_state()
            await m.reply_text("👋 تم الخروج من الوضع الدائم.")
        else:
            await m.reply_text("أنت لست في الوضع الدائم.")
    except Exception as e:
        logger.error(f"user_exit_ai error: {e}")

@app.on_message(filters.regex(r"^(مسح ذاكرتي|نسيان|تصفير)$") & ~filters.bot)
async def user_clear_history(_, m: Message):
    try:
        uid = m.from_user.id
        if uid in user_history:
            del user_history[uid]
            await m.reply_text("🗑️ تم مسح الذاكرة الخاصة بك.")
        else:
            await m.reply_text("لا يوجد شيء مسجّل لديك.")
    except Exception as e:
        logger.error(f"user_clear_history error: {e}")

# -------------------------
# المعالج الرئيسي للذكاء
# -------------------------
@app.on_message((filters.text) & ~filters.bot, group=60)
async def main_ai_handler(client, m: Message):
    global user_history
    try:
        if not AI_STATUS and m.from_user.id not in SUDO_USERS:
            return

        uid = m.from_user.id
        text = (m.text or "").strip()
        if not text:
            return

        # الحصول على id البوت بطريقة آمنة
        try:
            bot_me = client.me or await client.get_me()
            bot_id = getattr(bot_me, "id", None)
        except Exception:
            bot_id = None

        is_perm = uid in PERMANENT_USERS
        is_reply = bool(m.reply_to_message and getattr(m.reply_to_message.from_user, "id", None) == bot_id)
        match_trigger = re.match(r"^(ذكاء|بقولك|يا بوت|بوت)(\s|$)", text, re.IGNORECASE)

        if not (is_perm or is_reply or match_trigger):
            return

        if match_trigger and not is_perm:
            prompt = text[match_trigger.end():].strip()
        else:
            prompt = text

        if not prompt:
            await m.reply_text("نعم؟")
            return

        # أمر سري للمطور لتفعيل الوضع الدائم
        if match_trigger and uid in SUDO_USERS and "افتح دائم" in prompt:
            PERMANENT_USERS.add(uid)
            save_state()
            await m.reply_text("✅ تم تفعيل الوضع الدائم لك.")
            return

        try:
            await client.send_chat_action(m.chat.id, enums.ChatAction.TYPING)
        except:
            pass

        wait_msg = None
        try:
            wait_msg = await m.reply_text("⏳ جارٍ التفكير...", quote=True)
        except:
            wait_msg = None

        reply = await ask_ollama(uid, prompt)

        try:
            if wait_msg:
                await wait_msg.edit(reply)
            else:
                await m.reply_text(reply)
        except Exception:
            try:
                await m.reply_text(reply)
            except Exception as e:
                logger.error(f"Failed to send AI reply: {e}")

    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f"main_ai_handler unexpected: {e}\n{tb}")
        try:
            await m.reply_text("🚨 حدث خطأ داخل المساعد. حاول لاحقاً.")
        except:
            pass
