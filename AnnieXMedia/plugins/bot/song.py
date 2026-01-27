# Authored By Certified Coders © 2026
# System: Song Plugin V9 | Corrected Commands | Clean Text
# Optimized for AnnieXMedia Bot Folder Structure

import asyncio
import re
from pyrogram import filters, enums
from pyrogram.types import (
    InlineKeyboardMarkup, 
    InlineKeyboardButton, 
    Message, 
    CallbackQuery
)
from motor.motor_asyncio import AsyncIOMotorClient

from config import (
    BANNED_USERS, 
    OWNER_ID, 
    MONGO_DB_URI
)
from AnnieXMedia import app
from AnnieXMedia.platforms.Youtube import YouTube 
from AnnieXMedia.platforms.YTProcessor import Processor 
from AnnieXMedia.utils.inline.song import song_markup

# ==========================================================
# إعـدادات الـنـظـام والـذاكـرة الـمـؤقـتـة
# ==========================================================

SUDO_USERS = OWNER_ID if isinstance(OWNER_ID, list) else [OWNER_ID]

_mongo_client_ = AsyncIOMotorClient(MONGO_DB_URI)
songdb = _mongo_client_.Annie.song_settings

_CONF_CACHE = {"search_locked": None}
SEARCH_CACHE = {}

async def get_config(key):
    if _CONF_CACHE.get(key) is not None:
        return _CONF_CACHE[key]
    try:
        data = await songdb.find_one({"_id": "song_config"})
        if not data: return False
        val = data.get(key, False)
        _CONF_CACHE[key] = val
        return val
    except:
        return False

async def set_config(key, value):
    try:
        await songdb.update_one({"_id": "song_config"}, {"$set": {key: value}}, upsert=True)
        _CONF_CACHE[key] = value
    except:
        pass

# ==========================================================
# لـوحـة تـحـكـم الـمـسـؤول
# ==========================================================

@app.on_message(filters.regex(r"^(اوامـر الاغاني|اوامـر الـمـالـك|اوامـر الـبـحـث)$") & filters.user(SUDO_USERS))
async def songs_admin_panel(client, message):
    text = (
        "**لـوحـة تـحـكـم نـظـام الـأغـانـي (V9):**\n\n"
        "**أوامـر الـقـفـل والـفـتـح:**\n"
        "• `قفل البحث` : تـعـطـيـل الـبـحـث لـلـجـمـيـع.\n"
        "• `فتح البحث` : تـفـعـيـل الـبـحـث لـلـجـمـيـع.\n\n"
        "**أوامـر الـبـحـث:**\n"
        "• `كيب اغاني [الاسم]` : بـحـث مـتـطـور.\n"
        "• `كيب صوت [الاسم]` : بـحـث مـتـطـور.\n"
        "• `يوت [الرابط]` : تـحـمـيـل صـوت.\n"
        "• `يوت فيديو [الرابط]` : تـحـمـيـل فـيـديـو.\n"
    )
    await message.reply_text(text)

@app.on_message(filters.command(["قفل البحث"], prefixes=["", "/"]) & filters.user(SUDO_USERS))
async def lock_search(c, m):
    await set_config("search_locked", True)
    await m.reply_text("تـم قـفـل الـبـحـث والـتـحـمـيـل.")

@app.on_message(filters.command(["فتح البحث"], prefixes=["", "/"]) & filters.user(SUDO_USERS))
async def unlock_search(c, m):
    await set_config("search_locked", False)
    await m.reply_text("تـم فـتـح الـبـحـث والـتـحـمـيـل.")

# ==========================================================
# مـحـرك الـبـحـث والـتـصـفـح
# ==========================================================

@app.on_message(filters.regex(r"^/?(كيب اغاني|كيب صوت|بحث|song|music|دور|هات|هاتلي|ابعتلي|تحميل|نزل|تنزيل)(?:\s+(.+))?$") & ~BANNED_USERS, group=6)
async def smart_search_engine(client, message: Message):
    
    if await get_config("search_locked") and message.from_user.id not in SUDO_USERS:
        return await message.reply_text("عـذراً، الـقـسـم مـغـلـق لـلـصـيـانـة.")

    match = re.match(r"^/?(كيب اغاني|كيب صوت|بحث|song|music|دور|هات|هاتلي|ابعتلي|تحميل|نزل|تنزيل)(?:\s+(.+))?$", message.text)
    if not match: return
    query = match.group(2)

    # مـيـزة الانـتـظـار (Listener)
    if not query:
        ask = await message.reply_text("ارسـل الان اسـم الـأغـنـيـة او الـرابـط...")
        try:
            response = await client.listen(chat_id=message.chat.id, user_id=message.from_user.id, timeout=20)
            if response and response.text:
                query = response.text
                await ask.delete()
            else:
                return await ask.edit_text("تـم الـغـاء الـطـلـب لـعـدم الـرد.")
        except Exception:
            return await ask.edit_text("انـتـهـى وقـت الانـتـظـار.")

    msg = await message.reply_text("جـارٍ الـبـحـث...")
    try:
        results = await YouTube.search(query, limit=10)
        
        if not results:
            return await msg.edit_text("لـم يـتـم الـعـثـور عـلـى نـتـائـج.")
        
        uid = message.from_user.id
        SEARCH_CACHE[uid] = results
        
        await show_search_result(client, msg, uid, 0)

    except Exception as e:
        await msg.edit_text(f"حـدث خـطـأ: {e}")

async def show_search_result(client, message, user_id, index):
    results = SEARCH_CACHE.get(user_id)
    if not results or index >= len(results):
        return await message.edit_text("انـتـهـت جـلـسـة الـبـحـث.")

    res = results[index]
    vidid = res["vidid"]
    title = res["title"]
    duration = res["duration"]
    thumb = res["thumb"]
    
    # تـصـمـيـم الـأزرار (نـظـيـف بـدون إيـمـوجـي)
    buttons = [
        [
            InlineKeyboardButton("فـيـديـو", callback_data=f"dl_v_{vidid}"),
            InlineKeyboardButton("صــوت", callback_data=f"dl_a_{vidid}")
        ]
    ]
    
    # صـف الـتـنـقـل والـإغـلاق
    nav_row = []
    
    if index < len(results) - 1:
        nav_row.append(InlineKeyboardButton("الـتـالـي", callback_data=f"nav_{index+1}"))
    else:
        nav_row.append(InlineKeyboardButton("•", callback_data="ignore"))

    nav_row.append(InlineKeyboardButton("إغـلاق", callback_data="close_search"))

    if index > 0:
        nav_row.append(InlineKeyboardButton("الـسـابـق", callback_data=f"nav_{index-1}"))
    else:
        nav_row.append(InlineKeyboardButton("•", callback_data="ignore"))
    
    buttons.append(nav_row)
    
    text = (
        f"**الـنـتـائـج:** [{index+1}/{len(results)}]\n"
        f"**الـعـنـوان:** [{title[:60]}](https://t.me/{client.me.username})\n"
        f"**الـمـدة:** {duration}\n\n"
        "اخـتـر طـريـقـة الـتـحـمـيـل:"
    )
    
    try:
        await message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), disable_web_page_preview=False)
    except:
        await message.delete()
        await client.send_photo(
            message.chat.id,
            photo=thumb,
            caption=text,
            reply_markup=InlineKeyboardMarkup(buttons)
        )

# ==========================================================
# مـعـالـجـة الـأزرار (Callback)
# ==========================================================

@app.on_callback_query(filters.regex(r"^(nav_|dl_|close_)") & ~BANNED_USERS)
async def search_callbacks(client, q: CallbackQuery):
    data = q.data
    uid = q.from_user.id
    
    if data == "close_search":
        if uid in SEARCH_CACHE: del SEARCH_CACHE[uid]
        await q.message.delete()
        return

    if data.startswith("nav_"):
        if uid not in SEARCH_CACHE:
            return await q.answer("انـتـهـت الـجـلـسـة، ابـحـث مـجـدداً.", show_alert=True)
        new_index = int(data.split("_")[1])
        await show_search_result(client, q.message, uid, new_index)
        await q.answer()
        return

    if data.startswith("dl_"):
        if await get_config("search_locked") and uid not in SUDO_USERS:
            return await q.answer("الـتـحـمـيـل مـغـلـق لـلـصـيـانـة.", show_alert=True)

        type_code, vidid = data.split("_")[1], data.split("_")[2]
        is_video = (type_code == "v")
        
        await q.answer("جـارٍ بـدء الـتـحـمـيـل...", show_alert=False)
        if uid in SEARCH_CACHE: del SEARCH_CACHE[uid]
        
        try: await q.message.edit_text("جـارٍ الـتـحـمـيـل...")
        except: pass
        
        try:
            yturl = f"https://www.youtube.com/watch?v={vidid}"
            quality = "high" if uid in SUDO_USERS else "mid"
            title, _, duration_sec, _, _ = await YouTube.details(vidid)
            
            file_path = await Processor.download_file(
                yturl, quality, is_video, title, 
                vidid=vidid, is_owner=(uid in SUDO_USERS)
            )
            
            await q.message.edit_text("جـارٍ الـرفـع...")
            await client.send_chat_action(
                q.message.chat.id, 
                enums.ChatAction.UPLOAD_VIDEO if is_video else enums.ChatAction.UPLOAD_AUDIO
            )
            
            await Processor.upload_alexa_style(
                client, q.message, file_path, is_video, 
                title, duration_sec, q.from_user.first_name, vidid=vidid
            )
            
        except Exception as e:
            await q.message.edit_text(f"فـشـل الـتـحـمـيـل: {e}")

# ==========================================================
# الـتـحـمـيـل الـمـبـاشـر بـالـرابـط
# ==========================================================

@app.on_message(filters.command(["يوت", "يوت فيديو"], prefixes=["", "/"]) & ~BANNED_USERS)
async def direct_link_download(client, message):
    if await get_config("search_locked") and message.from_user.id not in SUDO_USERS:
        return await message.reply_text("عـذراً، الـقـسـم مـغـلـق لـلـصـيـانـة.")

    if len(message.command) < 2:
        return await message.reply_text("يـرجـى وضـع الـرابـط بـجـانـب الـأمـر.")

    is_video = "فيديو" in message.command[0]
    url = message.text.split(None, 1)[1]
    
    msg = await message.reply_text("جـارٍ الـمـعـالـجـة...")
    
    try:
        title, _, duration_sec, _, vidid = await YouTube.details(url)
        yturl = f"https://www.youtube.com/watch?v={vidid}"
        quality = "high" if message.from_user.id in SUDO_USERS else "mid"
        
        file_path = await Processor.download_file(yturl, quality, is_video, title, vidid=vidid, is_owner=(message.from_user.id in SUDO_USERS))
        
        await msg.edit_text("جـارٍ الـرفـع...")
        await Processor.upload_alexa_style(client, msg, file_path, is_video, title, duration_sec, message.from_user.first_name, vidid=vidid)
        
    except Exception as e:
        await msg.edit_text(f"حـدث خـطـأ: {e}")
