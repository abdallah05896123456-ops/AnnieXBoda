# Authored By Certified Coders © 2026
# System: Local AI (Ollama Qwen 2.5 Edition) | Clean Interface
# الـمـحـرك: Ollama (Qwen 2.5 32B) - أذكى موديل 20 جيجا للكود

import asyncio
import aiohttp
import json
import time
import re
import os
import logging
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
OLLAMA_API_URL = "http://localhost:11434/api/chat"
DEFAULT_MODEL = "qwen2.5:32b"  # 🔥 تـم الـتـحـديـث لـمـوديل الـكـود الـعـبـقـري

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AnnieX_Qwen_AI")

SUDO_USERS = OWNER_ID if isinstance(OWNER_ID, list) else [OWNER_ID]

# مـتـغـيـرات الـحـالـة
AI_STATUS = True
AI_MODE = "عـام"
MAX_HISTORY = 8  # تقليل الذاكرة قليلاً لتوفير الرام للموديل الكبير

# الـذاكـرة (RAM)
user_history = {}     
PERMANENT_USERS = set()
STATE_FILE = "ai_data/ollama_settings.json"

# -------------------------
# دوال الـحـفـظ والـاسـتـعـادة
# -------------------------
def load_state():
    global PERMANENT_USERS, AI_STATUS, AI_MODE
    if os.path.exists(STATE_FILE):
        try:
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
    # 1. تـجـهـيـز الـشـخـصـيـة (Qwen 2.5 Prompt)
    if AI_MODE == "تـقـنـي":
        sys_content = (
            "You are a Genius Senior Developer and a Hacker from 2026. "
            "You write complex, flawless, production-ready code. "
            "You speak Egyptian Arabic comfortably. "
            "You are confident, slightly arrogant but helpful."
        )
    else:
        sys_content = (
            "You are a smart, witty Egyptian companion. "
            "You speak pure Egyptian slang (Masri). "
            "You understand deep sarcasm and street vibes. "
            "You are not a robot; you have a strong personality."
        )

    # 2. بـنـاء مـصـفـوفـة الـرسـائـل
    messages = [{"role": "system", "content": sys_content}]
    
    # إضـافـة الـسـجـل
    history = user_history.get(user_id, [])
    for item in history:
        messages.append({"role": "user", "content": item['u']})
        messages.append({"role": "assistant", "content": item['a']})
    
    # الـسـؤال الـحـالـي
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": DEFAULT_MODEL,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": 0.7, 
            "num_ctx": 2048,  # حجم الذاكرة المناسب لـ 20 جيجا على CPU
            "num_thread": 4   # تحديد الأنوية لمنع التهنيج
        }
    }

    try:
        # زيادة وقت الانتظار لأن الموديل الـ 20 جيجا بياخد وقت أطول في التفكير
        async with aiohttp.ClientSession() as session:
            async with session.post(OLLAMA_API_URL, json=payload, timeout=180) as resp:
                if resp.status == 200:
                    res = await resp.json()
                    reply = res.get("message", {}).get("content", "").strip()
                    
                    if not reply:
                        return "عـذراً، لـم أسـتـطـع تـكـويـن رد مـنـاسـب."

                    # تـحـديـث الـذاكـرة
                    history.append({"u": prompt, "a": reply})
                    if len(history) > MAX_HISTORY:
                        history.pop(0)
                    user_history[user_id] = history
                    
                    return reply
                else:
                    return f"خـطـأ فـي الـخـادم: {resp.status}"
    except Exception as e:
        logger.error(f"Ollama Connection Error: {e}")
        return "الـخـادم الـمـحـلـي غـيـر مـتـصـل أو الـمـوديـل يـتـم تـحـمـيـلـه."

# -------------------------
# لـوحـة الـتـحـكـم (بـدون إيـمـوجـي)
# -------------------------

@app.on_message(filters.regex(r"^(كيب الذكاء|كيب ذكاء|اوامر الذكاء)$") & filters.user(SUDO_USERS))
async def ai_control_panel(_, m):
    """لـوحـة تـحـكـم نـظـيـفـة"""
    
    st_txt = "مـفـعـل" if AI_STATUS else "مـعـطـل"
    mode_txt = "تـقـنـي" if AI_MODE == "تـقـنـي" else "عـام"
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"الـحـالـة: {st_txt}", callback_data="toggle_ai_status"),
            InlineKeyboardButton(f"الـنـمـط: {mode_txt}", callback_data="toggle_ai_mode")
        ],
        [
            InlineKeyboardButton("تـنـظـيـف الـذاكـرة", callback_data="clean_ai_ram"),
            InlineKeyboardButton("الـمـتـصـلـيـن", callback_data="ai_users_count")
        ],
        [
            InlineKeyboardButton("إغـلاق", callback_data="close_ai_panel")
        ]
    ])
    
    await m.reply_text(
        f"**لـوحـة تـحـكـم Qwen 2.5 AI**\n\n"
        f"• **الـمـوديـل:** `{DEFAULT_MODEL}`\n"
        f"• **الـذاكـرة:** {len(user_history)} مـحـادثـة نـشـطـة\n",
        reply_markup=keyboard
    )

@app.on_callback_query(filters.regex(r"^(toggle_ai_|clean_ai_|ai_users_|close_ai_)"))
async def ai_panel_callback(_, q: CallbackQuery):
    global AI_STATUS, AI_MODE
    data = q.data
    user_id = q.from_user.id
    
    if user_id not in SUDO_USERS:
        return await q.answer("لـلـمـطـور فـقـط.", show_alert=True)

    if data == "close_ai_panel":
        return await q.message.delete()

    if data == "toggle_ai_status":
        AI_STATUS = not AI_STATUS
        save_state()
        new_st = "مـفـعـل" if AI_STATUS else "مـعـطـل"
        await q.answer(f"الـحـالـة: {new_st}")
        
    elif data == "toggle_ai_mode":
        AI_MODE = "تـقـنـي" if AI_MODE == "عـام" else "عـام"
        save_state()
        await q.answer(f"الـنـمـط: {AI_MODE}")

    elif data == "clean_ai_ram":
        user_history.clear()
        await q.answer("تـم تـصـفـيـر الـرام.", show_alert=True)

    elif data == "ai_users_count":
        count = len(PERMANENT_USERS)
        await q.answer(f"الـمـسـتـخـدمـيـن الـدائـمـيـن: {count}", show_alert=True)
        return

    st_txt = "مـفـعـل" if AI_STATUS else "مـعـطـل"
    mode_txt = "تـقـنـي" if AI_MODE == "تـقـنـي" else "عـام"
    
    new_kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"الـحـالـة: {st_txt}", callback_data="toggle_ai_status"),
            InlineKeyboardButton(f"الـنـمـط: {mode_txt}", callback_data="toggle_ai_mode")
        ],
        [
            InlineKeyboardButton("تـنـظـيـف الـذاكـرة", callback_data="clean_ai_ram"),
            InlineKeyboardButton("الـمـتـصـلـيـن", callback_data="ai_users_count")
        ],
        [
            InlineKeyboardButton("إغـلاق", callback_data="close_ai_panel")
        ]
    ])
    await q.message.edit_reply_markup(reply_markup=new_kb)

# -------------------------
# أوامـر الـمـسـتـخـدمـيـن
# -------------------------

@app.on_message(filters.regex(r"^(ذكاء كفاية|خروج من الذكاء|انهاء|كفاية)$") & ~filters.bot)
async def user_exit_ai(_, m):
    uid = m.from_user.id
    if uid in PERMANENT_USERS:
        PERMANENT_USERS.discard(uid)
        save_state()
        await m.reply_text("تـم الـخـروج.")
    else:
        await m.reply_text("أنـت لـسـت فـي الـوضـع الـدائـم.")

@app.on_message(filters.regex(r"^(مسح ذاكرتي|نسيان|تصفير)$") & ~filters.bot)
async def user_clear_history(_, m):
    uid = m.from_user.id
    if uid in user_history:
        del user_history[uid]
        await m.reply_text("تـم مـسـح ذاكـرتـي عـنـك.")
    else:
        await m.reply_text("لـا يـوجـد شـيء مـسـجـل.")

# -------------------------
# الـمـعـالـج
# -------------------------

@app.on_message((filters.text) & ~filters.bot, group=60)
async def main_ai_handler(client, m: Message):
    if not AI_STATUS and m.from_user.id not in SUDO_USERS:
        return

    uid = m.from_user.id
    text = m.text.strip()
    
    # الـشـروط
    is_perm = uid in PERMANENT_USERS
    is_reply = m.reply_to_message and m.reply_to_message.from_user.id == client.me.id
    match_trigger = re.match(r"^(ذكاء|بقولك|يا بوت|بوت)(\s|$)", text, re.IGNORECASE)

    if not (is_perm or is_reply or match_trigger):
        return

    # اسـتـخـراج الـنـص
    if match_trigger and not is_perm:
        prompt = text[match_trigger.end():].strip()
    else:
        prompt = text

    if not prompt:
        await m.reply_text("أيـوه يـا غـالـي.. سـامـعـك، قـول؟")
        return

    # أمـر سـري لـلـمـطـور
    if match_trigger and uid in SUDO_USERS and "افتح دائم" in prompt:
        PERMANENT_USERS.add(uid)
        save_state()
        await m.reply_text("تـم تـفـعـيـل الـوضـع الـدائـم.")
        return

    # مـؤشـر الـكـتـابـة
    await client.send_chat_action(m.chat.id, enums.ChatAction.TYPING)
    
    try:
        # رسـالـة انـتـظـار
        wait_msg = await m.reply_text("...", quote=True)
        
        response = await ask_ollama(uid, prompt)
        
        # تـعـديـل الـرد
        await wait_msg.edit(response)
        
    except Exception as e:
        logger.error(f"AI Error: {e}")
        try: await wait_msg.edit("حـدث خـطـأ.")
        except: pass
