# Authored By Certified Coders © 2026
# System: Song Plugin V13 | Master Control Keyboard | Default Quality Settings
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

# ==========================================================
# إعـدادات الـنـظـام والـكـاش
# ==========================================================

SUDO_USERS = OWNER_ID if isinstance(OWNER_ID, list) else [OWNER_ID]
_mongo_client_ = AsyncIOMotorClient(MONGO_DB_URI)
songdb = _mongo_client_.Annie.song_settings

_CONF_CACHE = {
    "search_locked": None, 
    "inline_locked": None,
    "def_audio": None, # الجودة الافتراضية للصوت
    "def_video": None  # الجودة الافتراضية للفيديو
}
SEARCH_CACHE = {}

async def get_config(key, default=False):
    if _CONF_CACHE.get(key) is not None: return _CONF_CACHE[key]
    try:
        data = await songdb.find_one({"_id": "song_config"})
        if not data: return default
        val = data.get(key, default)
        _CONF_CACHE[key] = val
        return val
    except: return default

async def set_config(key, value):
    try:
        await songdb.update_one({"_id": "song_config"}, {"$set": {key: value}}, upsert=True)
        _CONF_CACHE[key] = value
    except: pass

# ==========================================================
# 🎖 لـوحـة الـمـالـك الـشـامـلـة (كـيـب الاغـانـي)
# ==========================================================

@app.on_message(filters.regex(r"^كيب الاغاني$") & filters.user(SUDO_USERS))
async def owner_master_keyboard(client, message):
    await show_owner_keyboard(client, message)

async def show_owner_keyboard(client, message, is_callback=False):
    s_lock = await get_config("search_locked")
    i_lock = await get_config("inline_locked")
    d_audio = await get_config("def_audio", "mid") # الافتراضي متوسط
    d_video = await get_config("def_video", "mid") # الافتراضي متوسط
    
    t_s = "مـغـلـق" if s_lock else "مـفـتـوح"
    t_i = "مـعـطـلـة" if i_lock else "مـفـعـلـة"
    q_a = "عـالـيـة (320)" if d_audio == "high" else "مـتـوسـطـة (128)"
    q_v = "عـالـيـة (HD)" if d_video == "high" else "مـتـوسـطـة (480)"
    
    text = (
        "**لـوحـة تـحـكـم الـمـطـور الـشـامـلـة**\n\n"
        f"**الـبـحـث والـتـحـمـيـل :** {t_s}\n"
        f"**أزرار الـجـودات :** {t_i}\n\n"
        f"**جـودة الـصـوت الـتـلـقـائـيـة :** {q_a}\n"
        f"**جـودة الـفـيـديـو الـت_لـقـائـيـة :** {q_v}\n"
    )
    
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"الـبـحـث : {t_s}", callback_data="tgl_search"),
            InlineKeyboardButton(f"الـأزرار : {t_i}", callback_data="tgl_inline")
        ],
        [
            InlineKeyboardButton(f"صـوت : {d_audio.upper()}", callback_data="tgl_qaudio"),
            InlineKeyboardButton(f"فـيـديـو : {d_video.upper()}", callback_data="tgl_qvideo")
        ],
        [InlineKeyboardButton("• إغـلاق •", callback_data="close_search")]
    ])
    
    if is_callback: await message.edit_text(text, reply_markup=kb)
    else: await message.reply_text(text, reply_markup=kb)

# ==========================================================
# 👥 مـحـرك الـبـحـث والـتـحـمـيـل الـهـجـيـن
# ==========================================================

@app.on_message(filters.regex(r"^/?(كيب اغاني|كيب صوت|اغنية|اغنيه|هات|ابعتلي|بحث|نزل|تنزيل|video|فيديو)(?:\s+(.+))?$") & ~BANNED_USERS, group=6)
async def smart_search_engine(client, message: Message):
    if await get_config("search_locked") and message.from_user.id not in SUDO_USERS:
        return await message.reply_text("عـذراً، الـقـسـم مـغـلـق حـالـيـاً.")

    match = re.match(r"^/?(كيب اغاني|كيب صوت|اغنية|اغنيه|هات|ابعتلي|بحث|نزل|تنزيل|video|فيديو)(?:\s+(.+))?$", message.text)
    if not match: return
    query = match.group(2)

    if not query:
        ask = await message.reply_text("ارسـل الان اسـم الـأغـنـيـة او الـرابـط...")
        try:
            response = await client.listen(chat_id=message.chat.id, user_id=message.from_user.id, timeout=20)
            if response and response.text:
                query = response.text
                await ask.delete()
            else: return await ask.edit_text("تـم الـغـاء الـطـلـب.")
        except: return await ask.edit_text("انـتـهـى الـوقـت.")

    msg = await message.reply_text("جـارٍ الـبـحـث...")

    # التحميل المباشر (عند قفل الأزرار)
    if await get_config("inline_locked") and message.from_user.id not in SUDO_USERS:
        try:
            results = await YouTube.search(query, limit=1)
            if not results: return await msg.edit_text("لـم يـتـم الـعـثـور عـلـى نـتـائـج.")
            res = results[0]
            await msg.edit_text("جـارٍ الـتـحـمـيـل الـفـوري...")
            
            # استخدام الجودة الافتراضية التي حددها المطور
            def_q = await get_config("def_audio", "mid")
            file_path = await Processor.download_file(f"https://www.youtube.com/watch?v={res['vidid']}", def_q, False, res['title'], vidid=res['vidid'])
            await Processor.upload_alexa_style(client, msg, file_path, False, res['title'], 0, message.from_user.first_name, vidid=res['vidid'])
            return
        except: return await msg.edit_text("فـشـل الـتـحـمـيـل.")

    try:
        results = await YouTube.search(query, limit=10)
        if not results: return await msg.edit_text("لـم يـتـم الـعـثـور عـلـى نـتـائـج.")
        uid = message.from_user.id
        SEARCH_CACHE[uid] = results
        await show_search_result(client, msg, uid, 0, mode="fast")
    except Exception as e: await msg.edit_text(f"حـدث خـطـأ: {e}")

async def show_search_result(client, message, user_id, index, mode="fast"):
    results = SEARCH_CACHE.get(user_id)
    if not results or index >= len(results): return await message.edit_text("انـتـهـت الـجـلـسـة.")
    res = results[index]
    vidid, title, duration, thumb = res["vidid"], res["title"], res["duration"], res["thumb"]
    
    buttons = []
    if mode == "fast":
        buttons.append([
            InlineKeyboardButton("فـيـديـو", callback_data=f"dl_v_{vidid}"),
            InlineKeyboardButton("صــوت", callback_data=f"dl_a_{vidid}")
        ])
        buttons.append([InlineKeyboardButton("خـيـارات الـجـودة", callback_data=f"sw_qual_{index}")])
        nav_row = [
            InlineKeyboardButton("الـتـالـي", callback_data=f"nav_{index+1}") if index < len(results)-1 else InlineKeyboardButton("•", callback_data="ignore"),
            InlineKeyboardButton("إغـلاق", callback_data="close_search"),
            InlineKeyboardButton("الـسـابـق", callback_data=f"nav_{index-1}") if index > 0 else InlineKeyboardButton("•", callback_data="ignore")
        ]
        buttons.append(nav_row)
    else:
        buttons.append([
            InlineKeyboardButton("صـوت (320)", callback_data=f"qdl_a_high_{vidid}"),
            InlineKeyboardButton("صـوت (128)", callback_data=f"qdl_a_mid_{vidid}")
        ])
        buttons.append([
            InlineKeyboardButton("فـيـديـو (HD)", callback_data=f"qdl_v_high_{vidid}"),
            InlineKeyboardButton("فـيـديـو (480)", callback_data=f"qdl_v_mid_{vidid}")
        ])
        buttons.append([InlineKeyboardButton("الـتـحـمـيـل الـسـريـع", callback_data=f"sw_fast_{index}")])
        buttons.append([InlineKeyboardButton("• إغـلاق •", callback_data="close_search")])

    text = f"**الـنـتـائـج:** [{index+1}/{len(results)}]\n**الـعـنـوان:** [{title[:60]}](https://t.me/{client.me.username})\n**الـمـدة:** {duration}\n\nاخـتـر طـريـقـة الـتـحـمـيـل:"
    try: await message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), disable_web_page_preview=False)
    except:
        await message.delete()
        await client.send_photo(message.chat.id, photo=thumb, caption=text, reply_markup=InlineKeyboardMarkup(buttons))

# ==========================================================
# 🎮 مـعـالـج الـتـفـاعـل الـشـامـل (Callbacks)
# ==========================================================

@app.on_callback_query(filters.regex(r"^(nav_|dl_|qdl_|sw_|close_|tgl_|song_)") & ~BANNED_USERS)
async def song_callbacks_handler(client, q: CallbackQuery):
    data, uid = q.data, q.from_user.id

    if data == "close_search":
        if uid in SEARCH_CACHE: del SEARCH_CACHE[uid]
        return await q.message.delete()

    # --- تحكم المالك وتغيير الجودات ---
    if data.startswith("tgl_"):
        if uid not in SUDO_USERS: return await q.answer("لـلـمـطـور فـقـط.", show_alert=True)
        
        if "search" in data: key = "search_locked"
        elif "inline" in data: key = "inline_locked"
        elif "qaudio" in data: key = "def_audio"
        elif "qvideo" in data: key = "def_video"
        
        # التبديل بين القيم
        if key in ["search_locked", "inline_locked"]:
            current = await get_config(key)
            await set_config(key, not current)
        else:
            current = await get_config(key, "mid")
            await set_config(key, "high" if current == "mid" else "mid")
            
        await show_owner_keyboard(client, q.message, is_callback=True)
        return await q.answer("تـم الـتـحـديـث.")

    # --- التنقل والتبديل ---
    if data.startswith("sw_"):
        mode, index = data.split("_")[1], int(data.split("_")[2])
        await show_search_result(client, q.message, uid, index, mode="quality" if mode == "qual" else "fast")
    
    if data.startswith("nav_"):
        await show_search_result(client, q.message, uid, int(data.split("_")[1]), mode="fast")

    # --- معالجة التحميل ---
    if data.startswith(("dl_", "qdl_", "song_")):
        if await get_config("search_locked") and uid not in SUDO_USERS:
            return await q.answer("الـقـسـم مـغـلـق.", show_alert=True)

        if data.startswith("dl_"):
            st_c = data.split("_")[1]
            vidid = data.split("_")[2]
            # قراءة الجودة الافتراضية من القاعدة
            if st_c == "v":
                stype, is_v, quality = "video", True, await get_config("def_video", "mid")
            else:
                stype, is_v, quality = "audio", False, await get_config("def_audio", "mid")
                
            # استثناء المالك: دائماً جودة عالية في التحميل السريع
            if uid in SUDO_USERS: quality = "high"

        elif data.startswith("qdl_"):
            parts = data.split("_")
            stype, is_v, quality, vidid = ("video" if parts[1] == "v" else "audio"), (parts[1] == "v"), parts[2], parts[3]
        
        else: # song_download
            parts = data.split(None, 1)[1].split("|")
            stype, is_v, quality, vidid = parts[0], (parts[0] == "video"), parts[1], parts[2]

        await q.answer("جـارٍ الـتـحـمـيـل...")
        try: mystic = await q.message.edit_text("جـارٍ الـتـحـمـيـل...")
        except: mystic = await client.send_message(q.message.chat.id, "جـارٍ الـتـحـمـيـل...")

        try:
            title, _, dur_sec, _, _ = await YouTube.details(vidid)
            file_path = await Processor.download_file(f"https://www.youtube.com/watch?v={vidid}", quality, is_v, title, vidid=vidid, is_owner=(uid in SUDO_USERS))
            await Processor.upload_alexa_style(client, mystic, file_path, is_v, title, dur_sec, q.from_user.first_name, vidid=vidid)
        except: await mystic.edit_text("فـشـل الـتـحـمـيـل.")

# ==========================================================
# 📥 الـتـحـمـيـل الـمـبـاشـر (يـوت)
# ==========================================================

@app.on_message(filters.command(["يوت", "يوت فيديو"], prefixes=["", "/"]) & ~BANNED_USERS)
async def direct_yut(client, message):
    if await get_config("search_locked") and message.from_user.id not in SUDO_USERS:
        return await message.reply_text("مـغـلـق.")
    if len(message.command) < 2: return await message.reply_text("ضـع الـرابـط.")
    
    is_v = "فيديو" in message.command[0]
    q = message.text.split(None, 1)[1]
    m = await message.reply_text("جـارٍ الـتـحـمـيـل...")
    try:
        title, _, dur, _, vidid = await YouTube.details(q)
        # استخدام الجودة المختارة من الكيبورد
        key = "def_video" if is_v else "def_audio"
        qual = await get_config(key, "mid")
        if message.from_user.id in SUDO_USERS: qual = "high"
        
        path = await Processor.download_file(f"https://www.youtube.com/watch?v={vidid}", qual, is_v, title, vidid=vidid, is_owner=(message.from_user.id in SUDO_USERS))
        await Processor.upload_alexa_style(client, m, path, is_v, title, dur, message.from_user.first_name, vidid=vidid)
    except: await m.edit_text("خـطـأ.")
