# Authored By Certified Coders © 2026 (streaming + performance)
# System: Local AI (Debug Mode) | Streaming + Low-latency improvements
# المحرك: Ollama (Qwen 2.5 32B)

import asyncio
import aiohttp
import json
import os
import logging
import traceback
import re
import time
from typing import Any, Dict, List, Optional, Callable

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
# إعدادات النظام (قابلة للتعديل عبر المتغيرات البيئية)
# -------------------------
OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", "http://127.0.0.1:11434/api/chat")
DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:32b")
# timeout شامل (ثواني) للاتصال النهائي
DEFAULT_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "30"))
# المهلة لانتظار الشظية الأولى (ثواني) — لتقليل "الغياب"
FIRST_CHUNK_TIMEOUT = float(os.getenv("OLLAMA_FIRST_CHUNK_TIMEOUT", "2.5"))
# حجم buffer للقراءة
CHUNK_SIZE = int(os.getenv("OLLAMA_CHUNK_SIZE", "2048"))
# حد التاريخ في الذاكرة
MAX_HISTORY = int(os.getenv("AI_MAX_HISTORY", "8"))
# كاش قصيرة (ثواني)
CACHE_TTL = int(os.getenv("AI_CACHE_TTL", "8"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AnnieX_AI_Stream")

# إعداد SUDO_USERS
if isinstance(OWNER_ID, (list, tuple, set)):
    SUDO_USERS = list(OWNER_ID)
else:
    SUDO_USERS = [OWNER_ID]

AI_STATUS: bool = True
AI_MODE: str = "عـام"
user_history: Dict[int, List[Dict[str, str]]] = {}
PERMANENT_USERS: set = set()

STATE_DIR = "ai_data"
STATE_FILE = os.path.join(STATE_DIR, "ollama_settings.json")
os.makedirs(STATE_DIR, exist_ok=True)

# بسيط ليميت للتزامن (لتفادي طلبات متفجرة للموديل)
REQUEST_SEMAPHORE = asyncio.Semaphore(int(os.getenv("AI_CONCURRENCY", "6")))

# -------------------------
# حفظ واسترجاع حالة
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
# استخراج نص من JSON (متعدد الأشكال)
# -------------------------
def extract_text_from_ollama_json(data: Any) -> str:
    try:
        if isinstance(data, dict):
            if "message" in data and isinstance(data["message"], dict):
                cont = data["message"].get("content")
                if isinstance(cont, str) and cont.strip():
                    return cont.strip()
                if isinstance(cont, list):
                    parts = []
                    for p in cont:
                        if isinstance(p, dict):
                            txt = p.get("text") or p.get("content")
                            if isinstance(txt, str):
                                parts.append(txt)
                        elif isinstance(p, str):
                            parts.append(p)
                    return " ".join(parts).strip()
            for key in ("response", "output", "text"):
                if key in data and isinstance(data[key], str) and data[key].strip():
                    return data[key].strip()
            if "choices" in data and isinstance(data["choices"], list) and data["choices"]:
                first = data["choices"][0]
                if isinstance(first, dict):
                    msg = first.get("message") or first.get("delta") or first.get("output")
                    if isinstance(msg, dict):
                        cont = msg.get("content") or msg.get("text")
                        if isinstance(cont, str) and cont.strip():
                            return cont.strip()
                    txt = first.get("text")
                    if isinstance(txt, str) and txt.strip():
                        return txt.strip()
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
# فحص العربية
# -------------------------
ARABIC_RE = re.compile(r'[\u0600-\u06FF]')
def looks_arabic_enough(text: str, min_chars: int = 2) -> bool:
    if not text:
        return False
    return len(ARABIC_RE.findall(text)) >= min_chars

# -------------------------
# كاش قصيرة للردود الشائعة
# -------------------------
class SimpleCache:
    def __init__(self):
        self._data = {}  # key -> (expiry_ts, value)
    def get(self, key):
        item = self._data.get(key)
        if not item: return None
        expiry, val = item
        if time.time() > expiry:
            del self._data[key]
            return None
        return val
    def set(self, key, val, ttl=CACHE_TTL):
        self._data[key] = (time.time() + ttl, val)

CACHE = SimpleCache()

# -------------------------
# دالة streaming إلى Ollama
# on_update: coroutine that receives partial text updates (string)
# returns final text (string)
# -------------------------
async def ask_ollama_stream(
    user_id: int,
    prompt: str,
    on_update: Optional[Callable[[str], Any]] = None
) -> str:
    """
    يرسل الطلب إلى Ollama مع تهيئة للـ stream. يدعم:
    - ردود جزئية فورية (on_update callback)
    - إعادة محاولة صارمة لو الرد الأول غير عربي
    - كاش قصير للطلبات المتكررة
    """
    cache_key = f"{user_id}:{prompt}"
    cached = CACHE.get(cache_key)
    if cached:
        return cached

    # system message
    if AI_MODE == "تـقـنـي":
        sys_content = (
            "You are a Genius Senior Developer and a Hacker. "
            "You write complex, flawless, production-ready code. "
            "You speak Egyptian Arabic comfortably. "
            "Answer in Arabic (Egyptian dialect OK) unless user asks otherwise."
        )
    else:
        sys_content = (
            "You are a smart, witty Egyptian companion. "
            "You speak pure Egyptian slang (Masri) when appropriate. "
            "You must answer in Arabic only unless the user explicitly requests another language."
        )

    messages = [{"role": "system", "content": sys_content}]
    history = user_history.get(user_id, [])[-MAX_HISTORY:]
    for item in history:
        u = item.get("u", "")
        a = item.get("a", "")
        if u: messages.append({"role": "user", "content": u})
        if a: messages.append({"role": "assistant", "content": a})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": DEFAULT_MODEL,
        "messages": messages,
        "stream": True,
        "options": {
            "temperature": float(os.getenv("OLLAMA_TEMP", "0.15")),
            "top_p": 0.9,
            "max_tokens": int(os.getenv("OLLAMA_MAX_TOKENS", "1024"))
        }
    }

    headers = {"Content-Type": "application/json"}
    configured_timeout = int(os.getenv("OLLAMA_TIMEOUT", str(DEFAULT_TIMEOUT)))

    # concurrency limiter
    async with REQUEST_SEMAPHORE:
        try:
            timeout = aiohttp.ClientTimeout(total=configured_timeout)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                # POST with streaming
                async with session.post(OLLAMA_API_URL, json=payload, headers=headers) as resp:
                    if resp.status != 200:
                        # try to get text body
                        try:
                            tb = await resp.text()
                        except:
                            tb = ""
                        return f"❌ HTTP {resp.status} من خدمة الذكاء.\n{tb[:800]}"

                    # stream reading
                    buf = ""
                    final_text = ""
                    first_chunk_received = False
                    start_time = time.time()
                    # create task to read chunks
                    async for chunk in resp.content.iter_chunked(CHUNK_SIZE):
                        if not chunk:
                            continue
                        try:
                            decoded = chunk.decode(errors="ignore")
                        except:
                            decoded = str(chunk)
                        buf += decoded

                        # try split by newline — common streaming format: json per line
                        lines = buf.splitlines()
                        # keep last partial in buf
                        if not buf.endswith("\n"):
                            buf = lines.pop()  # last part
                        else:
                            buf = ""

                        updated = False
                        for line in lines:
                            line = line.strip()
                            if not line:
                                continue
                            # many streaming APIs send plain text or JSON chunks
                            # try JSON
                            parsed = None
                            if (line.startswith("{") and line.endswith("}")) or (line.startswith("[") and line.endswith("]")):
                                try:
                                    parsed = json.loads(line)
                                except:
                                    parsed = None
                            # fallback: sometimes plain text comes
                            candidate = ""
                            if parsed is not None:
                                candidate = extract_text_from_ollama_json(parsed) or ""
                            else:
                                candidate = line

                            if not candidate:
                                continue

                            # append to final_text
                            # avoid duplicate appends: append only new suffix
                            if not final_text or not candidate.endswith(final_text):
                                # Simple append heuristic:
                                if final_text and candidate.startswith(final_text):
                                    new_part = candidate[len(final_text):]
                                else:
                                    new_part = candidate
                                final_text += new_part
                                updated = True

                        # call on_update when we have something new (first chunk or subsequent)
                        if updated:
                            first_chunk_received = True
                            if on_update:
                                try:
                                    await on_update(final_text)
                                except Exception:
                                    # don't fail on callback error
                                    logger.debug("on_update callback error", exc_info=True)

                        # quick-break: if we've been streaming for long, continue reading; loop will finish when connection closes
                    # end stream loop

                    # if nothing from stream (some servers don't stream), try fallback to full json body
                    if not final_text:
                        try:
                            data = await resp.json(content_type=None)
                            final_text = extract_text_from_ollama_json(data) or ""
                        except Exception:
                            try:
                                final_text = (await resp.text() or "").strip()
                            except:
                                final_text = ""

                    final_text = final_text.strip() or "⚠️ الموديل رد ولكن لم يتم استخراج رد صالح."
                    # Arabic check and one strict retry if needed
                    if not looks_arabic_enough(final_text, min_chars=2):
                        # strict retry (non-stream) with explicit Arabic system
                        strict_sys = sys_content + " ملاحظة: أجب الآن **بالعربية فقط**، بدون أي كلمات بلغات أخرى."
                        s_payload = {
                            "model": DEFAULT_MODEL,
                            "messages": [{"role": "system", "content": strict_sys}, {"role": "user", "content": prompt}],
                            "stream": False,
                            "options": {"temperature": 0.1, "max_tokens": payload["options"]["max_tokens"]}
                        }
                        try:
                            async with session.post(OLLAMA_API_URL, json=s_payload, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as r2:
                                if r2.status == 200:
                                    try:
                                        d2 = await r2.json(content_type=None)
                                        final2 = extract_text_from_ollama_json(d2) or ""
                                    except:
                                        final2 = (await r2.text()) or ""
                                    final2 = final2.strip()
                                    if final2 and looks_arabic_enough(final2, min_chars=2):
                                        final_text = final2
                        except Exception as e:
                            logger.debug(f"Strict retry failed: {e}")

                    # store in cache and history
                    CACHE.set(cache_key, final_text)
                    hist = user_history.get(user_id, [])
                    hist.append({"u": prompt, "a": final_text})
                    if len(hist) > MAX_HISTORY:
                        hist = hist[-MAX_HISTORY:]
                    user_history[user_id] = hist
                    return final_text

        except aiohttp.ClientConnectorError as e:
            logger.debug(f"Ollama connection error: {e}")
            return "🔌 خطأ اتصال: لا يمكن الوصول إلى خدمة Ollama (127.0.0.1:11434). تأكد من تشغيل الخدمة."
        except asyncio.TimeoutError:
            return f"⏰ مهلة الاتصال انتهت ({configured_timeout}s). الخدمة بطيئة أو غير متاحة."
        except Exception as e:
            tb = traceback.format_exc()
            logger.error(f"ask_ollama_stream unexpected: {e}\n{tb}")
            truncated = tb[:500].replace("\n", " ")
            return f"💀 خطأ داخلي في الذكاء:\n`{str(e)}`\n{truncated}"

# -------------------------
# لوحة تحكم المطور (نفس نصوصك)
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
# أوامر المستخدمين لإدارة الحالة (نفس نصوصك)
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
# المعالج الرئيسي — يستخدم streaming callback لتحسين سرعة الإحساس
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

        # تفعيل الوضع الدائم للمطور (سري)
        if match_trigger and uid in SUDO_USERS and "افتح دائم" in prompt:
            PERMANENT_USERS.add(uid)
            save_state()
            await m.reply_text("✅ تم تفعيل الوضع الدائم لك.")
            return

        # إرسال حالة "يكتب" للمستخدم
        try:
            await client.send_chat_action(m.chat.id, enums.ChatAction.TYPING)
        except:
            pass

        wait_msg = None
        try:
            wait_msg = await m.reply_text("⏳ جارٍ التفكير...", quote=True)
        except:
            wait_msg = None

        # on_update callback يُرسل أجزاء الرد إلى wait_msg (إن وُجد)
        async def on_update_partial(partial_text: str):
            nonlocal wait_msg
            # نرسل فقط لو في تغيير حقيقي أو طول كافي
            if not wait_msg:
                return
            try:
                # محدودية الطول: نرسل أول 1024 حرف لتفادي مشكلات تحرير طويلة جداً
                preview = partial_text.strip()
                if len(preview) > 1500:
                    preview = preview[:1500] + "..."
                await wait_msg.edit(preview)
            except Exception:
                # لا نرمي الخطأ لو التحرير فشل
                pass

        # استدعاء المحرك مع الاستريم
        reply = await ask_ollama_stream(uid, prompt, on_update=on_update_partial)

        # أخيراً: تعديل/ارسال الرسالة بالرد النهائي
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
