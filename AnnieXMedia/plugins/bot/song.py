Authored By Certified Coders © 2026

System: Song Plugin | Playlist Support | MongoDB Fixed | Pyromod

Optimized for AnnieXMedia Bot Folder Structure

import asyncio import os import re import time import tempfile import shutil import traceback import logging from pyrogram import filters, enums from pyrogram.types import ( InlineKeyboardMarkup, Message, InputMediaAudio, InputMediaVideo ) from motor.motor_asyncio import AsyncIOMotorClient import aiohttp from mutagen.mp4 import MP4

استيراد الإعدادات وكائن البوت الرئيسي

from config import ( BANNED_USERS, SONG_DOWNLOAD_DURATION, SONG_DOWNLOAD_DURATION_LIMIT, OWNER_ID, MONGO_DB_URI ) from AnnieXMedia import app from AnnieXMedia.platforms.Youtube import YouTube from AnnieXMedia.platforms.YTProcessor import Processor from AnnieXMedia.utils.inline.song import song_markup

==========================================================

الإعـدادات الـتـقـنـيـة والاتـصـال بـالـقـاعـدة

==========================================================

معالجة OWNER_ID لضمان عمله سواء كان رقماً أو قائمة

SUDO_USERS = OWNER_ID if isinstance(OWNER_ID, list) else [OWNER_ID]

mongo_client = AsyncIOMotorClient(MONGO_DB_URI) mongodb = mongo_client.Annie songdb = mongodb.song_settings

بسيط جداً داخل الذاكرة لتقليل نداءات التفاصيل المتكررة

_YT_DETAILS_CACHE = {}

async def get_config(key): """جلب الإعدادات من قاعدة البيانات""" try: data = await songdb.find_one({"_id": "song_config"}) if not data: return False return data.get(key, False) except Exception: logging.exception("get_config failed") return False

async def set_config(key, value): """تحديث الإعدادات في قاعدة البيانات""" try: await songdb.update_one({"_id": "song_config"}, {"$set": {key: value}}, upsert=True) except Exception: logging.exception("set_config failed")

==========================================================

Utilities: تحميل الصورة، إعادة تغليف m4a بسرعة، استخراج المدة

==========================================================

async def download_thumb(url: str) -> str | None: """يحمل الصورة مؤقتًا ويُعيد مسار الملف، أو None.""" if not url: return None try: async with aiohttp.ClientSession() as session: async with session.get(url, timeout=20) as resp: if resp.status != 200: return None tmpf = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") content = await resp.read() tmpf.write(content) tmpf.close() # تصغير الصورة ليتوافق مع متطلبات Telegram (max 200KB/320x320 أفضل) resized = tmpf.name + "_res.jpg" # استخدام ffmpeg لخيار سريع وآمن (سيكون سريع ولا يعيد ترميز الصوت) try: cmd = [ "ffmpeg", "-y", "-i", tmpf.name, "-vf", "scale='min(320,iw)':'min(320,ih)'", "-frames:v", "1", resized ] proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL) await proc.wait() if os.path.exists(resized): os.unlink(tmpf.name) return resized return tmpf.name except Exception: return tmpf.name except Exception: logging.exception("download_thumb failed") return None

async def fast_remux_to_m4a(src_path: str) -> str: """لو الملف بالفعل m4a يرجعه، وإلا يعمل remux (copy codec) ويعيد المسار النهائي. يستخدم ffmpeg لكن مع stream copy لذا سريع جدًا. """ if not src_path or not os.path.exists(src_path): raise FileNotFoundError("source file not found")

ext = os.path.splitext(src_path)[1].lower()
if ext == ".m4a":
    return src_path

dst_fd, dst_path = tempfile.mkstemp(suffix=".m4a")
os.close(dst_fd)
try:
    cmd = [
        "ffmpeg", "-y",
        "-i", src_path,
        "-vn",  # no video
        "-c", "copy",
        dst_path
    ]
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
    await proc.wait()
    if os.path.exists(dst_path) and os.path.getsize(dst_path) > 0:
        return dst_path
    else:
        # fallback: do a safe re-encode to m4a (should be rare)
        cmd2 = [
            "ffmpeg", "-y",
            "-i", src_path,
            "-vn",
            "-c:a", "aac",
            "-b:a", "128k",
            dst_path
        ]
        proc2 = await asyncio.create_subprocess_exec(*cmd2, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        await proc2.wait()
        return dst_path
except Exception:
    logging.exception("fast_remux_to_m4a failed")
    if os.path.exists(dst_path):
        return dst_path
    raise

def get_duration(path: str) -> int: """استخراج المدة (بالثواني) باستخدام mutagen — سريع وخفيف.""" try: audio = MP4(path) return int(audio.info.length) except Exception: logging.exception("get_duration failed") return 0

async def fast_send_m4a(client, mystic_msg, chat_id: int, src_file: str, title: str, duration_sec: int, user_name: str, thumbnail_url: str | None = None, filename: str | None = None): """المُعالج الذي يقوم بـ: - اعادة تغليف لمصلح m4a بدون إعادة ترميز (سريع) - تحميل thumb وتصغيره - ارسال كـ document مع thumb (سريع وأسرع من send_audio في معظم الحالات) - تنظيف الملفات المؤقتة """ try: await mystic_msg.edit_text("جـارٍ تـحـضـيـر الـمـلـف (m4a) ...") except Exception: pass

thumb_path = None
tmp_remux = None
try:
    if thumbnail_url:
        thumb_path = await download_thumb(thumbnail_url)

    # remux to m4a (fast stream copy)
    tmp_remux = await fast_remux_to_m4a(src_file)
    final_path = tmp_remux or src_file

    # duration (verify)
    if not duration_sec:
        duration_sec = get_duration(final_path)

    # filename safe
    safe_name = (filename or f"{title}.m4a").replace('\n', ' ').strip()

    try:
        await mystic_msg.edit_text("**جـارٍ الـرفـع إلـى تـلـيـجـرام...**")
    except Exception:
        pass

    # send as document with thumb (fast)
    await client.send_document(
        chat_id=chat_id,
        document=final_path,
        thumb=thumb_path if thumb_path and os.path.exists(thumb_path) else None,
        caption=f"**الـعـنـوان:** {title}\n**بـواسطـة:** {user_name}",
        file_name=safe_name,
        disable_notification=False,
    )

    try:
        await mystic_msg.edit_text("**تـم الإرسـال بـنـجـاح ✅**")
    except Exception:
        pass

except Exception as e:
    logging.exception("fast_send_m4a failed")
    try:
        await mystic_msg.edit_text("**فـشـل فـي إرسـال الـمـلـف، حـاول مـرة أخـرى.**")
    except Exception:
        pass
    raise
finally:
    # تنظيف الملفات المؤقتة
    try:
        if thumb_path and os.path.exists(thumb_path):
            os.unlink(thumb_path)
    except Exception:
        pass
    try:
        # إذا أعدنا تغليف الملفات مؤقتًا - نحذفها إذا كانت ليست نفس الملف الأصلي
        if tmp_remux and os.path.exists(tmp_remux) and tmp_remux != src_file:
            os.unlink(tmp_remux)
    except Exception:
        pass

==========================================================

أوامـر الـتـحـكـم والـقـفـل (لـلـمـطـور فـقـط)

==========================================================

@app.on_message(filters.command(["قفل البحث", "تعطيل البحث"], prefixes=["", "/"]) & filters.user(SUDO_USERS)) async def lock_whole_section(client, message): await set_config("search_locked", True) await message.reply_text("تـم قـفـل قـسـم الـبـحـث والـتـحـمـيـل نـهـائـيـاً عـن الـأعـضـاء.")

@app.on_message(filters.command(["فتح البحث", "تفعيل البحث"], prefixes=["", "/"]) & filters.user(SUDO_USERS)) async def unlock_whole_section(client, message): await set_config("search_locked", False) await message.reply_text("تـم فـتـح قـسـم الـبـحـث والـتـحـمـيـل لـلـجـمـيـع.")

@app.on_message(filters.command(["قفل انلاين البحث", "قفل انلاين بحث"], prefixes=["", "/"]) & filters.user(SUDO_USERS)) async def lock_inline_search(client, message): await set_config("inline_locked", True) await message.reply_text("تـم قـفـل بـحـث الانـلايـن (الأزرار).")

@app.on_message(filters.command(["فتح انلاين البحث", "فتح انلاين بحث"], prefixes=["", "/"]) & filters.user(SUDO_USERS)) async def unlock_inline_search(client, message): await set_config("inline_locked", False) await message.reply_text("تـم فـتـح بـحـث الانـلايـن.")

==========================================================

الـمـعـالـج الـذكـي الـمـوحـد (Regex Engine) — قيديها على النص فقط

==========================================================

@app.on_message(filters.text & filters.regex(r"^/?(اغنية|اغنيه|هات|هاتلي|ابعتلي|song|video|تحميل|يوتيوب)(?:\s+(فيد|فيديو|video))?(?:\s+(.+))?$") & ~BANNED_USERS, group=5) async def unified_song_processor(client, message: Message):

# 1. فحص القفل العام
is_search_locked = await get_config("search_locked")
if is_search_locked and message.from_user.id not in SUDO_USERS:
    return await message.reply_text("**عـذراً، الـقـسـم مـغـلـق حـالـيـاً مـن قـبـل الـمـطـور.**")

match = re.match(r"^/?(اغنية|اغنيه|هات|هاتلي|ابعتلي|song|video|تحميل|ابعتلي)(?:\s+(فيد|فيديو|video))?(?:\s+(.+))?$", message.text)
if not match: return

command_trigger = match.group(1).lower()
video_trigger = match.group(2)
query = match.group(3)

is_video_request = command_trigger in ["video", "/video", "فيديو"] or video_trigger

# 2. نظام التفاعل الذكي (Pyromod Listen)
if not query:
    prompt = await message.reply_text("**ارسـل الان اسـم الـمـقـطـع أو رابـط الـقـائـمـة.**")
    try:
        response = await client.listen(chat_id=message.chat.id, user_id=message.from_user.id, timeout=20)
        if response and response.text:
            query = response.text
            await prompt.delete()
        else:
            return await prompt.edit_text("**تـم انـهـاء الانـتـظـار لـعـدم الـرد.**")
    except Exception:
        return await prompt.edit_text("**حـدث خـطـأ فـي نـظـام الـاسـتـمـاع.**")

mystic = await message.reply_text("**جـارٍ الـمـعـالـجـة والـبـحـث...**")

# 3. اكتشاف قوائم التشغيل (Playlists)
if "list=" in (query or "") and ("youtube.com" in (query or "") or "youtu.be" in (query or "")):
    try:
        await Processor.download_playlist(
            client=client,
            mystic_msg=mystic,
            playlist_url=query,
            is_video=is_video_request,
            user_name=message.from_user.first_name
        )
    except Exception as e:
        await mystic.edit_text(f"**حـدث خـطـأ فـي الـقـائـمـة:** {e}")
    return

# 4. معالجة الطلبات الفردية
try:
    # cache-aware details lookup
    if query in _YT_DETAILS_CACHE:
        title, duration_min, duration_sec, thumbnail, vidid = _YT_DETAILS_CACHE[query]
    else:
        title, duration_min, duration_sec, thumbnail, vidid = await YouTube.details(query)
        _YT_DETAILS_CACHE[query] = (title, duration_min, duration_sec, thumbnail, vidid)

    if duration_sec is None: duration_sec = 0

    if int(duration_sec) > 14400:
        return await mystic.edit_text("**عـذراً، الـمـقـطـع طـويـل جـداً (الـحـد الـأقـصـى 4 سـاعـات).**")

    is_inline_locked = await get_config("inline_locked")

    # التحميل المباشر (في حال قفل الأزرار)
    if is_inline_locked:
         await mystic.edit_text("**جـارٍ الـتـحـمـيـل الـفـوري...**")
         yturl = f"https://www.youtube.com/watch?v={vidid}"
         quality_arg = "high" if message.from_user.id in SUDO_USERS else "mid"

         file_path = await Processor.download_file(yturl, quality_arg, is_video_request, title, vidid=vidid, is_owner=(message.from_user.id in SUDO_USERS))
         await mystic.edit_text("**جـارٍ الـرفـع لـتـلـيـجـرام...**")

         if not is_video_request:
             # audio fast path (M4A with cover)
             try:
                 await fast_send_m4a(client, mystic, message.chat.id, file_path, title, duration_sec, message.from_user.first_name, thumbnail, filename=f"{title}.m4a")
             except Exception:
                 # fallback to existing uploader if anything fails
                 await Processor.upload_alexa_style(client, mystic, file_path, is_video_request, title, duration_sec, message.from_user.first_name, vidid=vidid)
         else:
             await Processor.upload_alexa_style(client, mystic, file_path, is_video_request, title, duration_sec, message.from_user.first_name, vidid=vidid)

    # عرض أزرار اختيار الجودة
    else:
        buttons = song_markup(None, vidid)
        await mystic.delete()
        await message.reply_photo(
            photo=thumbnail,
            caption=f"**الـعـنـوان:** {title}\n**الـمـدة:** {duration_min}\n\n**اخـتـر الـجـودة والـنـوع:**",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

except Exception as e:
    logging.exception("unified processor error")
    # نظام البحث الاحتياطي (Fallback Search)
    is_inline_locked = await get_config("inline_locked")
    if is_inline_locked or is_video_request:
        await mystic.edit_text("**جـارٍ الـبـحـث والـتـحـمـيـل...**")
        file_path = await Processor.download_file(query, "mid", is_video_request, query, is_owner=(message.from_user.id in SUDO_USERS))
        if file_path:
             await mystic.edit_text("**جـارٍ الـرفـع...**")
             if not is_video_request:
                 try:
                     await fast_send_m4a(client, mystic, message.chat.id, file_path, query, 0, message.from_user.first_name, None)
                 except Exception:
                     await Processor.upload_alexa_style(client, mystic, file_path, is_video_request, query, 0, message.from_user.first_name)
             else:
                 await Processor.upload_alexa_style(client, mystic, file_path, is_video_request, query, 0, message.from_user.first_name)
        else:
            await mystic.edit_text("**عـذراً، لـم يـتـم الـعـثـور عـلـى نـتـائـج.**")
    else:
         await mystic.edit_text("**عـذراً، لـم يـتـم الـعـثـور عـلـى نـتـائـج.**")

==========================================================

أوامـر الـتـحـمـيـل الـمـبـاشـر (يـوت)

==========================================================

@app.on_message(filters.command(["يوت"], prefixes=["", "/"]) & ~BANNED_USERS) async def yut_direct_audio(client, message: Message): if await get_config("search_locked") and message.from_user.id not in SUDO_USERS: return await message.reply_text("عـذراً، الـقـسـم مـغـلـق.")

if len(message.command) > 1 and message.command[1] in ["فيد", "فيديو", "video", "vid"]:
    return 

if len(message.command) < 2:
    return await message.reply_text("**يـرجـى كـتـابـة الـرابـط بـجـانـب الـأمـر.**")

query = message.text.split(None, 1)[1]
mystic = await message.reply_text("**جـارٍ الـتـحـمـيـل...**")

if "list=" in query:
     return await Processor.download_playlist(client, mystic, query, False, message.from_user.first_name)

try:
    # use cache if available
    if query in _YT_DETAILS_CACHE:
        title, _, duration_sec, thumbnail, vidid = _YT_DETAILS_CACHE[query]
    else:
        title, _, duration_sec, thumbnail, vidid = await YouTube.details(query)
        _YT_DETAILS_CACHE[query] = (title, _, duration_sec, thumbnail, vidid)
    yturl = f"https://www.youtube.com/watch?v={vidid}"
    quality_arg = "high" if message.from_user.id in SUDO_USERS else "mid"
    file_path = await Processor.download_file(yturl, quality_arg, False, title, vidid=vidid, is_owner=(message.from_user.id in SUDO_USERS))
    await mystic.edit_text("**جـارٍ الـرفـع...**")
    # fast audio path
    try:
        await fast_send_m4a(client, mystic, message.chat.id, file_path, title, duration_sec, message.from_user.first_name, thumbnail, filename=f"{title}.m4a")
    except Exception:
        await Processor.upload_alexa_style(client, mystic, file_path, False, title, duration_sec, message.from_user.first_name, vidid=vidid)
except Exception as e:
    await mystic.edit_text(f"**حـدث خـطـأ:** {e}")

@app.on_message(filters.command(["يوت فيد", "يوت فيديو"], prefixes=["", "/"]) & ~BANNED_USERS) async def yut_direct_video(client, message: Message): if await get_config("search_locked") and message.from_user.id not in SUDO_USERS: return await message.reply_text("عـذراً، الـقـسـم مـغـلـق.")

if len(message.command) < 3: 
    return await message.reply_text("**يـرجـى كـتـابـة الـرابـط بـجـانـب الـأمـر.**")

query = message.text.split(None, 2)[2]
mystic = await message.reply_text("**جـارٍ الـتـحـمـيـل...**")

if "list=" in query:
     return await Processor.download_playlist(client, mystic, query, True, message.from_user.first_name)

try:
    title, _, duration_sec, _, vidid = await YouTube.details(query)
    yturl = f"https://www.youtube.com/watch?v={vidid}"
    quality_arg = "high" if message.from_user.id in SUDO_USERS else "mid"
    file_path = await Processor.download_file(yturl, quality_arg, True, title, vidid=vidid, is_owner=(message.from_user.id in SUDO_USERS))
    await mystic.edit_text("**جـارٍ الـرفـع...**")
    await Processor.upload_alexa_style(client, mystic, file_path, True, title, duration_sec, message.from_user.first_name, vidid=vidid)
except Exception as e:
    await mystic.edit_text(f"**حـدث خـطـأ:** {e}")

==========================================================

مـعـالـجـات الـتـفـاعـل (Callback Queries)

==========================================================

@app.on_callback_query(filters.regex(pattern=r"song_download") & ~BANNED_USERS) async def song_download_callback(client, CallbackQuery): if await get_config("search_locked") and CallbackQuery.from_user.id not in SUDO_USERS: return await CallbackQuery.answer("قـسـم الـتـح_مـيـل مـغـلـق حـالـيـاً.", show_alert=True)

if await get_config("inline_locked") and CallbackQuery.from_user.id not in SUDO_USERS:
     return await CallbackQuery.answer("هـذه الـمـيـزة مـعـطـلـة مـؤقـتـاً.", show_alert=True)

stype, quality_arg, vidid = CallbackQuery.data.split(None, 1)[1].split("|")
await CallbackQuery.answer("جـارٍ بـدء الـتـحـمـيـل...")

try: mystic = await CallbackQuery.message.edit_text("**جـارٍ الـتـحـمـيـل مـن يـوتـيـوب...**")
except: mystic = await client.send_message(CallbackQuery.message.chat.id, "**جـارٍ الـتـحـمـيـل...**")

is_video = (stype == "video")
yturl = f"https://www.youtube.com/watch?v={vidid}"

try:
    # cache-aware
    if vidid in _YT_DETAILS_CACHE:
        title, _, duration_sec, thumbnail, _ = _YT_DETAILS_CACHE[vidid]
    else:
        title, _, duration_sec, thumbnail, _ = await YouTube.details(vidid)
        _YT_DETAILS_CACHE[vidid] = (title, _, duration_sec, thumbnail, vidid)
    file_path = await Processor.download_file(yturl, quality_arg, is_video, title, vidid=vidid, is_owner=(CallbackQuery.from_user.id in SUDO_USERS))
    await mystic.edit_text("**جـارٍ الـرفـع...**")
    if not is_video:
        try:
            await fast_send_m4a(client, mystic, CallbackQuery.message.chat.id, file_path, title, duration_sec, CallbackQuery.from_user.first_name, thumbnail, filename=f"{title}.m4a")
        except Exception:
            await Processor.upload_alexa_style(client, mystic, file_path, is_video, title, duration_sec, CallbackQuery.from_user.first_name, vidid=vidid)
    else:
        await Processor.upload_alexa_style(client, mystic, file_path, is_video, title, duration_sec, CallbackQuery.from_user.first_name, vidid=vidid)
except Exception:
    await mystic.edit_text("**فـشـل الـتـحـمـيـل، حـاول مـرة أخـرى لاحـقـاً.**")

@app.on_callback_query(filters.regex(pattern=r"song_helper") & ~BANNED_USERS) async def song_helper_callback(client, CallbackQuery): if await get_config("search_locked") and CallbackQuery.from_user.id not in SUDO_USERS: return await CallbackQuery.answer("الـقـسـم مـغـلـق.", show_alert=True)

stype, vidid = CallbackQuery.data.split(None, 1)[1].split("|")
await CallbackQuery.answer("جـارٍ جـلـب خـيـارات الـجـودة...")
buttons = await Processor.get_quality_buttons(vidid, stype)
await CallbackQuery.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))

@app.on_callback_query(filters.regex(pattern=r"song_back") & ~BANNED_USERS) async def song_back_callback(client, CallbackQuery): stype, vidid = CallbackQuery.data.split(None, 1)[1].split("|") buttons = song_markup(None, vidid) await CallbackQuery.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
