# Authored By Certified Coders © 2026
# System: Local AI (Ollama) | Full Control Panel | No Emoji
# الـمـحـرك: Ollama (Mistral) مـحـلـيـاً عـلـى الـسـيـرفـر
# الـمـيـزات: لـوحـة تـحـكـم كـامـلـة لـلـمـالـك (كـيـب الـذكـاء) + ذاكـرة قـويـة

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
from config import OWNER_ID, BANNED_USERS

# -------------------------
# إعـدادات الـنـظـام
# -------------------------
OLLAMA_API_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "mistral"  # تأكد أن الموديل محمل

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AnnieX_Ollama_AI")

SUDO_USERS = OWNER_ID if isinstance(OWNER_ID, list) else [OWNER_ID]

# مـتـغـيـرات الـحـالـة
AI_STATUS = True
AI_MODE = "عـام"  # عـام / تـقـنـي
MAX_HISTORY = 10  # عـدد الـرسـائـل الـتـي يـتـذكـرهـا الـبـوت

# الـذاكـرة (RAM)
user_history = {}     # تـخـزيـن سـيـاق الـحـديـث
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
# مـحـرك الـذكـاء (Ollama)
# -------------------------
async def ask_ollama(user_id, prompt):
    """إرسـال الـطـلـب إلـى الـسـيـرفـر الـمـحـلـي"""
    
    # تـحـديـد الـشـخـصـيـة
    system_msg = "You are a helpful AI assistant speaking Arabic. Be concise."
    if AI_MODE == "تـقـنـي":
        system_msg = "You are an expert programmer. Explain code and logic in Arabic."

    # بـنـاء الـسـيـاق مـن الـذاكـرة
    context_list = user_history.get(user_id, [])
    full_prompt = f"{system_msg}\n"
    for item in context_list:
        full_prompt += f"User: {item['u']}\nAI: {item['a']}\n"
    full_prompt += f"User: {prompt}\nAI:"

    payload = {
        "model": DEFAULT_MODEL,
        "prompt": full_prompt,
        "stream": False,
        "options": {"temperature": 0.7, "num_ctx": 2048}
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(OLLAMA_API_URL, json=payload, timeout=40) as resp:
                if resp.status == 200:
                    res = await resp.json()
                    reply = res.get("response", "").strip()
                    
                    # تـحـديـث الـذاكـرة
                    context_list.append({"u": prompt, "a": reply})
                    if len(context_list) > MAX_HISTORY:
                        context_list.pop(0)
                    user_history[user_id] = context_list
                    
                    return reply
                else:
                    return "عـذراً، هـنـاك خـطـأ فـي مـعـالـجـة الـطـلـب."
    except:
        return "عـذراً، الـخـادم الـمـحـلـي لـلـذكـاء غـيـر مـتـصـل."

# -------------------------
# لـوحـة الـتـحـكـم (كـيـب الـذكـاء)
# -------------------------

@app.on_message(filters.regex(r"^(كيب الذكاء|كيب ذكاء|اوامر الذكاء)$") & filters.user(SUDO_USERS))
async def ai_control_panel(_, m):
    """عـرض لـوحـة الـتـحـكـم الـشـامـلـة لـلـمـالـك"""
    
    st_txt = "مـفـعـل" if AI_STATUS else "مـعـطـل"
    mode_txt = AI_MODE
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"الـحـالـة: {st_txt}", callback_data="toggle_ai_status"),
            InlineKeyboardButton(f"الـنـمـط: {mode_txt}", callback_data="toggle_ai_mode")
        ],
        [
            InlineKeyboardButton("تـنـظـيـف الـذاكـرة الـعـامـة", callback_data="clean_ai_ram"),
            InlineKeyboardButton("عـدد الـمـسـتـخـدمـيـن", callback_data="ai_users_count")
        ],
        [
            InlineKeyboardButton("إغـلاق الـلـوحـة", callback_data="close_ai_panel")
        ]
    ])
    
    text = (
        "**لـوحـة تـحـكـم نـظـام الـذكـاء الـاصـطـنـاعـي:**\n\n"
        "مـن هـنـا يـمـكـنـك الـتـحـكـم فـي كـافـة إعـدادات الـمـحـرك الـمـحـلـي.\n"
        "اخـتـر الـإجـراء الـمـطـلـوب:"
    )
    await m.reply_text(text, reply_markup=keyboard)

# --- مـعـالـجـة أزرار الـكـيـب ---
@app.on_callback_query(filters.regex(r"^(toggle_ai_|clean_ai_|ai_users_|close_ai_)"))
async def ai_panel_callback(_, q: CallbackQuery):
    global AI_STATUS, AI_MODE
    data = q.data
    user_id = q.from_user.id
    
    if user_id not in SUDO_USERS:
        return await q.answer("هـذا الـأمـر لـلـمـالـك فـقـط.", show_alert=True)

    if data == "close_ai_panel":
        return await q.message.delete()

    if data == "toggle_ai_status":
        AI_STATUS = not AI_STATUS
        save_state()
        new_st = "مـفـعـل" if AI_STATUS else "مـعـطـل"
        await q.answer(f"تـم تـغـيـيـر الـحـالـة إلـى: {new_st}")
        
    elif data == "toggle_ai_mode":
        AI_MODE = "تـقـنـي" if AI_MODE == "عـام" else "عـام"
        save_state()
        await q.answer(f"تـم تـغـيـيـر نـمـط الـرد إلـى: {AI_MODE}")

    elif data == "clean_ai_ram":
        user_history.clear()
        await q.answer("تـم تـنـظـيـف ذاكـرة الـمـحـادثـات لـلـجـمـيـع.", show_alert=True)

    elif data == "ai_users_count":
        count = len(PERMANENT_USERS)
        await q.answer(f"عـدد الـمـسـتـخـدمـيـن فـي الـوضـع الـدائـم: {count}", show_alert=True)
        return # لا داعي لتحديث اللوحة

    # تـحـديـث شـكـل الـلـوحـة بـعـد الـتـغـيـيـر
    st_txt = "مـفـعـل" if AI_STATUS else "مـعـطـل"
    mode_txt = AI_MODE
    new_kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"الـحـالـة: {st_txt}", callback_data="toggle_ai_status"),
            InlineKeyboardButton(f"الـنـمـط: {mode_txt}", callback_data="toggle_ai_mode")
        ],
        [
            InlineKeyboardButton("تـنـظـيـف الـذاكـرة الـعـامـة", callback_data="clean_ai_ram"),
            InlineKeyboardButton("عـدد الـمـسـتـخـدمـيـن", callback_data="ai_users_count")
        ],
        [
            InlineKeyboardButton("إغـلاق الـلـوحـة", callback_data="close_ai_panel")
        ]
    ])
    await q.message.edit_reply_markup(reply_markup=new_kb)

# -------------------------
# أوامـر الـمـسـتـخـدمـيـن (الـخـروج والـمـسـح)
# -------------------------

@app.on_message(filters.regex(r"^(ذكاء كفاية|خروج من الذكاء|انهاء|كفاية)$") & ~filters.bot)
async def user_exit_ai(_, m):
    """الـخـروج مـن وضـع الـشـات الـدائـم"""
    uid = m.from_user.id
    if uid in PERMANENT_USERS:
        PERMANENT_USERS.discard(uid)
        save_state()
        await m.reply_text("تـم الـخـروج مـن وضـع الـذكـاء الـدائـم بـنـجـاح.")
    else:
        await m.reply_text("أنـت لـسـت فـي وضـع الـمـحـادثـة الـدائـمـة بـالـفـعـل.")

@app.on_message(filters.regex(r"^(مسح ذاكرتي|نسيان|تصفير)$") & ~filters.bot)
async def user_clear_history(_, m):
    """مـسـح سـجـل الـمـحـادثـة الـخـاص بـالـعـضـو"""
    uid = m.from_user.id
    if uid in user_history:
        del user_history[uid]
        await m.reply_text("تـم مـسـح سـجـل مـحـادثـتـك مـعـي، يـمـكـنـك الـبـدء مـن جـديـد.")
    else:
        await m.reply_text("لـا يـوجـد لـك سـجـل مـحـادثـات نـشـط حـالـيـاً.")

# -------------------------
# الـمـعـالـج الـرئـيـسـي (الـمـخ)
# -------------------------

@app.on_message((filters.text) & ~filters.bot, group=60)
async def main_ai_handler(client, m: Message):
    # 1. الـتـحـقـق مـن حـالـة الـنـظـام
    if not AI_STATUS and m.from_user.id not in SUDO_USERS:
        return

    uid = m.from_user.id
    text = m.text.strip()
    
    # 2. هـل الـمـسـتـخـدم يـتـحـدث مـع الـبـوت؟
    is_perm = uid in PERMANENT_USERS
    is_reply = m.reply_to_message and m.reply_to_message.from_user.id == client.me.id
    match_trigger = re.match(r"^(ذكاء|بقولك|يا بوت|بوت)(\s|$)", text, re.IGNORECASE)

    # شـرط الـد خـول: وضـع دائـم OR رد عـلـى الـبـوت OR كـلـمـة مـفـتـاحـيـة
    if not (is_perm or is_reply or match_trigger):
        return

    # 3. تـجـهـيـز الـسـؤال
    if match_trigger and not is_perm:
        prompt = text[match_trigger.end():].strip()
    else:
        prompt = text

    if not prompt:
        await m.reply_text("نـعـم يـا صـديـقـي، أنـا أسـتـمـع إلـيـك.. تـفـضـل؟")
        return

    # 4. تـفـعـيـل الـوضـع الـدائـم لـلـمـالـك (اخـتـيـاري)
    if match_trigger and uid in SUDO_USERS and "افتح دائم" in prompt:
        PERMANENT_USERS.add(uid)
        save_state()
        await m.reply_text("تـم تـفـعـيـل الـوضـع الـدائـم لـك يـا مـطـور.")
        return

    # 5. إرسـال مـؤشـر الـكـتـابـة
    await client.send_chat_action(m.chat.id, enums.ChatAction.TYPING)
    
    # 6. الـحـصـول عـلـى الـرد
    try:
        wait_msg = await m.reply_text("جـارٍ الـتـحـلـيـل والـرد...", quote=True)
        response = await ask_ollama(uid, prompt)
        await wait_msg.edit(response)
    except Exception as e:
        logger.error(f"AI Error: {e}")
        try: await wait_msg.edit("عـذراً، حـدث خـطـأ أثـنـاء الـمـعـالـجـة.")
        except: pass
