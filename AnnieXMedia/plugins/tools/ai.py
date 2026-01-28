# Authored By Certified Coders © 2026
# System: Local AI (Debug Mode) | Full Error Tracing
# الـمـحـرك: Ollama (Qwen 2.5 32B) - نـظـام كـشـف الـأخـطـاء الـدقـيـق

import asyncio
import aiohttp
import json
import os
import logging
import traceback
from pyrogram import filters, enums
from pyrogram.types import (
    Message, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton, 
    CallbackQuery
)
from AnnieXMedia import app
from config import OWNER_ID

# -------------------------
# إعـدادات الـنـظـام
# -------------------------
# استخدام 127.0.0.1 بدلاً من localhost لتجنب مشاكل الشبكة
OLLAMA_API_URL = "http://127.0.0.1:11434/api/chat"
DEFAULT_MODEL = "qwen2.5:32b"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AnnieX_Debug_AI")

SUDO_USERS = OWNER_ID if isinstance(OWNER_ID, list) else [OWNER_ID]
AI_STATUS = True
AI_MODE = "عـام"
MAX_HISTORY = 8
user_history = {}
PERMANENT_USERS = set()
STATE_FILE = "ai_data/ollama_settings.json"

# -------------------------
# دوال الـحـفـظ والـاسـتـعـادة
# -------------------------
def load_state():
    global PERMANENT_USERS, AI_STATUS, AI_MODE
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            PERMANENT_USERS = set(data.get("PERMANENT_USERS", []))
            AI_STATUS = data.get("AI_STATUS", True)
            AI_MODE = data.get("AI_MODE", "عـام")
    except: pass

def save_state():
    try:
        os.makedirs("ai_data", exist_ok=True)
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "PERMANENT_USERS": list(PERMANENT_USERS),
                "AI_STATUS": AI_STATUS,
                "AI_MODE": AI_MODE
            }, f, ensure_ascii=False, indent=2)
    except: pass

load_state()

# -------------------------
# مـحـرك الـذكـاء (Ollama Smart Chat)
# -------------------------
async def ask_ollama(user_id, prompt):
    # إعداد الشخصية
    sys_content = "You are a helpful assistant."
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

    # بناء سياق المحادثة
    messages = [{"role": "system", "content": sys_content}]
    
    # إضافة التاريخ السابق
    current_history = user_history.get(user_id, [])
    for item in current_history:
        messages.append({"role": "user", "content": item['u']})
        messages.append({"role": "assistant", "content": item['a']})
    
    # إضافة السؤال الحالي
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": DEFAULT_MODEL,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": 0.7, 
            "num_ctx": 2048, 
            "num_thread": 10
        }
    }

    # 🔥 هنا كود كشف الأخطاء الدقيق 🔥
    try:
        async with aiohttp.ClientSession() as session:
            # زيادة التايم أوت لـ 300 ثانية (5 دقائق)
            async with session.post(OLLAMA_API_URL, json=payload, timeout=300) as resp:
                
                # 1. لو السيرفر رد بـ 200 (كله تمام)
                if resp.status == 200:
                    res = await resp.json()
                    reply = res.get("message", {}).get("content", "").strip()
                    
                    if not reply:
                        return "⚠️ الموديل رد، بس الرسالة فاضية!"
                    
                    # تحديث الذاكرة
                    current_history.append({"u": prompt, "a": reply})
                    if len(current_history) > MAX_HISTORY:
                        current_history.pop(0)
                    user_history[user_id] = current_history
                    
                    return reply
                
                # 2. لو السيرفر رد بحاجة غير 200 (مشكلة في الطلب)
                else:
                    error_text = await resp.text()
                    return f"❌ HTTP Error {resp.status}:\n`{error_text}`"

    except aiohttp.ClientConnectorError as e:
        # 3. مشكلة اتصال (السيرفر مش شغال أو العنوان غلط)
        return f"🔌 Connection Error:\n`Cannot connect to 127.0.0.1:11434`\n\nDetailed: `{str(e)}`"

    except asyncio.TimeoutError:
        # 4. الموديل خد وقت طويل
        return "⏰ Timeout Error:\nالموديل استغرق أكثر من 300 ثانية في التفكير (السيرفر بطيء)."

    except Exception as e:
        # 5. أي خطأ تاني (بايثون ضرب)
        return f"💀 Critical Error:\n`{str(e)}`\n\nTraceback:\n`{traceback.format_exc()[:500]}`"

# -------------------------
# لـوحـة الـتـحـكـم
# -------------------------

@app.on_message(filters.regex(r"^(كيب الذكاء|كيب ذكاء|اوامر الذكاء)$") & filters.user(SUDO_USERS))
async def ai_control_panel(_, m):
    """Debug Panel"""
    
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
    
    await m.reply_text(
        f"**🤖 Debug Panel (Qwen 32B)**\n"
        f"• Model: `{DEFAULT_MODEL}`\n"
        f"• Users in Memory: {len(user_history)}", 
        reply_markup=keyboard
    )

@app.on_callback_query(filters.regex(r"^(toggle_ai_|clean_ai_|close_ai_)"))
async def ai_panel_callback(_, q: CallbackQuery):
    global AI_STATUS, AI_MODE
    
    if q.from_user.id not in SUDO_USERS:
        return await q.answer("للمطور فقط.", show_alert=True)

    data = q.data
    if data == "close_ai_panel":
        return await q.message.delete()

    if data == "toggle_ai_status":
        AI_STATUS = not AI_STATUS
        save_state()
    elif data == "toggle_ai_mode":
        AI_MODE = "تـقـنـي" if AI_MODE == "عـام" else "عـام"
        save_state()
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
    except: pass

# -------------------------
# أوامـر الـمـسـتـخـدمـيـن
# -------------------------

@app.on_message(filters.regex(r"^(ذكاء كفاية|خروج من الذكاء|انهاء|كفاية)$") & ~filters.bot)
async def user_exit_ai(_, m):
    uid = m.from_user.id
    if uid in PERMANENT_USERS:
        PERMANENT_USERS.discard(uid)
        save_state()
        await m.reply_text("👋 تـم الـخـروج.")
    else:
        await m.reply_text("أنـت لـسـت فـي الـوضـع الـدائـم.")

@app.on_message(filters.regex(r"^(مسح ذاكرتي|نسيان|تصفير)$") & ~filters.bot)
async def user_clear_history(_, m):
    uid = m.from_user.id
    if uid in user_history:
        del user_history[uid]
        await m.reply_text("🗑️ تـم مـسـح الـذاكـرة.")
    else:
        await m.reply_text("لـا يـوجـد شـيء مـسـجـل.")

# -------------------------
# الـمـعـالـج الـرئـيـسـي
# -------------------------

@app.on_message((filters.text) & ~filters.bot, group=60)
async def main_ai_handler(client, m: Message):
    if not AI_STATUS and m.from_user.id not in SUDO_USERS:
        return

    uid = m.from_user.id
    text = m.text.strip()
    
    # الشروط
    is_perm = uid in PERMANENT_USERS
    is_reply = m.reply_to_message and m.reply_to_message.from_user.id == client.me.id
    match_trigger = re.match(r"^(ذكاء|بقولك|يا بوت|بوت)(\s|$)", text, re.IGNORECASE)

    if not (is_perm or is_reply or match_trigger):
        return

    # استخراج النص
    if match_trigger and not is_perm:
        prompt = text[match_trigger.end():].strip()
    else:
        prompt = text

    if not prompt:
        await m.reply_text("نعم؟")
        return

    # أمر سري للمطور
    if match_trigger and uid in SUDO_USERS and "افتح دائم" in prompt:
        PERMANENT_USERS.add(uid)
        save_state()
        await m.reply_text("✅ تـم تـفـعـيـل الـوضـع الـدائـم.")
        return

    # مؤشر الكتابة
    await client.send_chat_action(m.chat.id, enums.ChatAction.TYPING)
    
    try:
        # رسالة انتظار
        wait_msg = await m.reply_text("⏳ ...", quote=True)
        
        # استدعاء المحرك
        response = await ask_ollama(uid, prompt)
        
        # تعديل الرد
        await wait_msg.edit(response)
        
    except Exception as e:
        # حتى لو دالة ask_ollama فشلت، هنطبع الخطأ هنا برضه
        try:
            await wait_msg.edit(f"🚨 Handler Error:\n`{str(e)}`")
        except:
            pass
