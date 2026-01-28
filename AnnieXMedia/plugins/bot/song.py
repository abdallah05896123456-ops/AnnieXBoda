# AnnieXMedia/plugins/bot/song.py
# Authored By Certified Coders © 2026
# Song plugin — robust & fast upload: prefer send_audio(AAC/M4A), fallback to document.
# - stream-copy when possible
# - probe codec via ffprobe
# - re-encode to AAC only when required
# - thumbnail support, duration extraction, cleanup

import os
import re
import asyncio
import tempfile
import logging
from typing import List, Optional
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, Message
from motor.motor_asyncio import AsyncIOMotorClient
import aiohttp
from mutagen.mp4 import MP4

log = logging.getLogger(__name__)

# ---------------------------
# Load config / app
# ---------------------------
try:
    from AnnieXMedia.config import (
        BANNED_USERS,
        SONG_DOWNLOAD_DURATION,
        SONG_DOWNLOAD_DURATION_LIMIT,
        OWNER_ID as CFG_OWNER_ID,
        MONGO_DB_URI,
    )
    OWNER_ID = CFG_OWNER_ID
except Exception:
    try:
        from config import (
            BANNED_USERS,
            SONG_DOWNLOAD_DURATION,
            SONG_DOWNLOAD_DURATION_LIMIT,
            OWNER_ID as CFG_OWNER_ID,
            MONGO_DB_URI,
        )
        OWNER_ID = CFG_OWNER_ID
    except Exception:
        BANNED_USERS = filters.user([])  # default
        SONG_DOWNLOAD_DURATION = int(os.getenv("SONG_DOWNLOAD_DURATION") or 0)
        SONG_DOWNLOAD_DURATION_LIMIT = int(os.getenv("SONG_DOWNLOAD_DURATION_LIMIT") or 0)
        try:
            OWNER_ID = int(os.getenv("OWNER_ID") or 0)
        except Exception:
            OWNER_ID = 0
        MONGO_DB_URI = os.getenv("MONGO_DB_URI") or "mongodb://localhost:27017"

try:
    from AnnieXMedia import app
except Exception:
    try:
        from AnnieXMedia.__main__ import app
    except Exception:
        raise RuntimeError("Cannot import 'app'. Ensure your bot exports 'app' (pyrogram Client).")

# platform imports (may be missing in testing env)
try:
    from AnnieXMedia.platforms.Youtube import YouTube
    from AnnieXMedia.platforms.YTProcessor import Processor
    from AnnieXMedia.utils.inline.song import song_markup
except Exception:
    log.warning("Missing AnnieXMedia.platforms or utils — stubbing minimal fallbacks.")
    async def _yt_details_stub(q):
        return (str(q), "0:00", 0, None, str(q))
    class YouTube:
        @staticmethod
        async def details(q):
            return await _yt_details_stub(q)
    class Processor:
        @staticmethod
        async def download_playlist(*args, **kwargs):
            raise NotImplementedError("Processor.download_playlist not available")
        @staticmethod
        async def download_file(*args, **kwargs):
            raise NotImplementedError("Processor.download_file not available")
        @staticmethod
        async def upload_alexa_style(*args, **kwargs):
            raise NotImplementedError("Processor.upload_alexa_style not available")
        @staticmethod
        async def get_quality_buttons(vidid, stype):
            return [[{"text":"جودة عالية", "callback_data": f"song_download video|high|{vidid}"}]]
    def song_markup(a, vidid):
        return [[{"text":"تحميل", "callback_data": f"song_download audio|mid|{vidid}"}]]

# ---------------------------
# SUDO users (OWNER_ID might be list or int)
# ---------------------------
if isinstance(OWNER_ID, (list, tuple, set)):
    SUDO_USERS: List[int] = [int(x) for x in OWNER_ID]
else:
    try:
        SUDO_USERS = [int(OWNER_ID)] if OWNER_ID else []
    except Exception:
        SUDO_USERS = []

# ---------------------------
# MongoDB
# ---------------------------
_mongo_client_ = AsyncIOMotorClient(MONGO_DB_URI)
mongodb = _mongo_client_.Annie
songdb = mongodb.song_settings

# cache for details
_YT_DETAILS_CACHE = {}

# ---------------------------
# DB helpers
# ---------------------------
async def get_config(key: str):
    try:
        data = await songdb.find_one({"_id": "song_config"})
        if not data:
            return False
        return data.get(key, False)
    except Exception:
        log.exception("get_config failed")
        return False

async def set_config(key: str, value):
    try:
        await songdb.update_one({"_id": "song_config"}, {"$set": {key: value}}, upsert=True)
    except Exception:
        log.exception("set_config failed")

# ---------------------------
# Utilities: thumb download
# ---------------------------
async def download_thumb(url: str) -> Optional[str]:
    if not url:
        return None
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=20) as resp:
                if resp.status != 200:
                    return None
                tmpf = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
                content = await resp.read()
                tmpf.write(content)
                tmpf.close()
                resized = tmpf.name + "_res.jpg"
                try:
                    cmd = ["ffmpeg","-y","-i", tmpf.name, "-vf", "scale='min(320,iw)':'min(320,ih)'", "-frames:v","1", resized]
                    p = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
                    await p.wait()
                    if os.path.exists(resized):
                        os.unlink(tmpf.name)
                        return resized
                    return tmpf.name
                except Exception:
                    return tmpf.name
    except Exception:
        log.exception("download_thumb failed")
        return None

# ---------------------------
# ffprobe helper (detect codec)
# ---------------------------
async def probe_audio_codec(path: str) -> Optional[str]:
    try:
        cmd = ["ffprobe","-v","error","-select_streams","a:0","-show_entries","stream=codec_name","-of","default=noprint_wrappers=1:nokey=1", path]
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
        out, _ = await proc.communicate()
        if not out:
            return None
        codec = out.decode().strip().splitlines()[0]
        return codec
    except Exception:
        log.exception("probe_audio_codec failed for %s", path)
        return None

# ---------------------------
# Remux / re-encode to m4a (AAC) — fast when possible
# ---------------------------
async def fast_remux_to_m4a(src_path: str) -> str:
    if not src_path or not os.path.exists(src_path):
        raise FileNotFoundError("source file not found")

    src_ext = os.path.splitext(src_path)[1].lower()
    # if already .m4a and codec aac -> return
    if src_ext == ".m4a":
        codec = await probe_audio_codec(src_path)
        if codec and codec.lower() == "aac":
            return src_path

    # create temp m4a
    fd, tmp_m4a = tempfile.mkstemp(suffix=".m4a")
    os.close(fd)

    # try fast stream copy
    try:
        cmd = ["ffmpeg","-y","-i", src_path, "-vn", "-c", "copy", tmp_m4a]
        p = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        await p.wait()
        if os.path.exists(tmp_m4a) and os.path.getsize(tmp_m4a) > 0:
            codec = await probe_audio_codec(tmp_m4a)
            if codec and codec.lower() == "aac":
                return tmp_m4a
    except Exception:
        log.exception("fast stream-copy to m4a failed, will re-encode")

    # re-encode to AAC
    try:
        fd2, tmp_m4a_re = tempfile.mkstemp(suffix=".m4a")
        os.close(fd2)
        cmd2 = ["ffmpeg","-y","-i", src_path, "-vn", "-c:a","aac", "-b:a","192k", tmp_m4a_re]
        p2 = await asyncio.create_subprocess_exec(*cmd2, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        await p2.wait()
        if os.path.exists(tmp_m4a_re) and os.path.getsize(tmp_m4a_re) > 0:
            try:
                if os.path.exists(tmp_m4a):
                    os.unlink(tmp_m4a)
            except Exception:
                pass
            return tmp_m4a_re
        if os.path.exists(tmp_m4a):
            return tmp_m4a
        raise RuntimeError("Failed to produce m4a file")
    except Exception:
        log.exception("re-encode to aac failed")
        if os.path.exists(tmp_m4a):
            return tmp_m4a
        raise

# ---------------------------
# Duration extractor
# ---------------------------
def get_duration(path: str) -> int:
    try:
        audio = MP4(path)
        return int(audio.info.length)
    except Exception:
        log.exception("get_duration failed for %s", path)
        return 0

# ---------------------------
# Main send helper: try send_audio then fallback to send_document
# ---------------------------
async def fast_send_m4a(client, mystic_msg, chat_id: int, src_file: str, title: str,
                        duration_sec: int, user_name: str,
                        thumbnail_url: Optional[str] = None, filename: Optional[str] = None):
    try:
        await mystic_msg.edit_text("**جـارٍ تـحضـير الـمـلـف (m4a) ...**")
    except Exception:
        pass

    thumb_path = None
    prepared = None
    try:
        if thumbnail_url:
            thumb_path = await download_thumb(thumbnail_url)

        prepared = await fast_remux_to_m4a(src_file)
        final_path = prepared or src_file

        if not duration_sec:
            duration_sec = get_duration(final_path)

        safe_name = (filename or f"{title}.m4a").replace("\n"," ").strip()

        try:
            await mystic_msg.edit_text("**جـارٍ الـرفـع (Audio) ...**")
        except Exception:
            pass

        # send_audio: shows player in Telegram
        try:
            await client.send_audio(
                chat_id=chat_id,
                audio=final_path,
                duration=int(duration_sec) if duration_sec else None,
                performer=user_name or None,
                title=title or None,
                thumb=thumb_path if thumb_path and os.path.exists(thumb_path) else None,
                caption=f"**الـعـنـوان:** {title}\n**بـواسطـة:** {user_name}",
                file_name=safe_name,
                disable_notification=False,
            )
            try:
                await mystic_msg.edit_text("**تـم الإرسـال كـمـشـغّل مـوسيـقـي ✅**")
            except Exception:
                pass
            return
        except Exception as e_audio:
            log.warning("send_audio failed, falling back to document: %s", e_audio)
            try:
                await mystic_msg.edit_text("**تعذّر الإرسال كمشغل — سيتم الإرسال كملف (Document)...**")
            except Exception:
                pass

            await client.send_document(
                chat_id=chat_id,
                document=final_path,
                thumb=thumb_path if thumb_path and os.path.exists(thumb_path) else None,
                caption=f"**الـعـنـوان:** {title}\n**بـواسطـة:** {user_name}",
                file_name=safe_name,
                disable_notification=False,
            )
            try:
                await mystic_msg.edit_text("**تـم الإرسـال كـمـلـف (Document) ✅**")
            except Exception:
                pass
            return

    except Exception as e:
        log.exception("fast_send_m4a failed: %s", e)
        try:
            await mystic_msg.edit_text("**فشل في تجهيز/إرسال الملف، حاول مرة أخرى.**")
        except Exception:
            pass
        raise
    finally:
        try:
            if thumb_path and os.path.exists(thumb_path):
                os.unlink(thumb_path)
        except Exception:
            pass
        try:
            if prepared and os.path.exists(prepared) and prepared != src_file:
                os.unlink(prepared)
        except Exception:
            pass

# ---------------------------
# Handlers (use your original logic; included examples)
# ---------------------------

@app.on_message(filters.command(["قفل البحث","تعطيل البحث"], prefixes=["","/"]) & filters.user(SUDO_USERS))
async def lock_whole_section(client, message):
    await set_config("search_locked", True)
    await message.reply_text("**تـم قـفـل قـسـم الـبـحـث والـتـحـمـيـل نـهـائـيـاً عـن الـأعـضـاء.**")

@app.on_message(filters.command(["فتح البحث","تفعيل البحث"], prefixes=["","/"]) & filters.user(SUDO_USERS))
async def unlock_whole_section(client, message):
    await set_config("search_locked", False)
    await message.reply_text("**تـم فـتـح قـسـم الـبـحـث والـتـحـمـيـل لـلـجـمـيـع.**")

@app.on_message(filters.command(["قفل انلاين البحث","قفل انلاين بحث"], prefixes=["","/"]) & filters.user(SUDO_USERS))
async def lock_inline_search(client, message):
    await set_config("inline_locked", True)
    await message.reply_text("**تـم قـفـل بـحـث الانـلايـن (الأزرار).**")

@app.on_message(filters.command(["فتح انلاين البحث","فتح انلاين بحث"], prefixes=["","/"]) & filters.user(SUDO_USERS))
async def unlock_inline_search(client, message):
    await set_config("inline_locked", False)
    await message.reply_text("**تـم فـتـح بـحـث الانـلايـن.**")

# unified processor (copy your full existing logic here; example placeholder)
@app.on_message(filters.text & filters.regex(r"^/?(اغنية|اغنيه|هات|هاتلي|ابعتلي|song|video|تحميل|play)(?:\s+(فيد|فيديو|video))?(?:\s+(.+))?$") & ~BANNED_USERS, group=5)
async def unified_song_processor(client, message: Message):
    # paste your full existing unified handler logic (search, playlist detection, Processor.download_file)
    try:
        # YOUR ORIGINAL HANDLER LOGIC HERE
        pass
    except Exception:
        log.exception("unified processor failed")
        try:
            await message.reply_text("حدث خطأ، حاول مرة أخرى.")
        except Exception:
            pass

# callback handlers (use your existing logic but call fast_send_m4a for uploads)
@app.on_callback_query(filters.regex(pattern=r"song_download") & ~BANNED_USERS)
async def song_download_callback(client, CallbackQuery):
    # Example: parse payload and call Processor.download_file -> fast_send_m4a
    data = CallbackQuery.data or ""
    payload = ""
    parts = data.split(maxsplit=1)
    if len(parts) > 1:
        payload = parts[1]
    else:
        payload = data.replace("song_download","").strip()
    try:
        stype, quality_arg, vidid = payload.split("|")
    except Exception:
        return await CallbackQuery.answer("بيانات التحميل غير صالحة.", show_alert=True)

    await CallbackQuery.answer("جـارٍ بـدء الـتـحـمـيـل...")
    try:
        try:
            mystic = await CallbackQuery.message.edit_text("**جـارٍ الـتـحـمـيـل مـن يـوتـيـوب...**")
        except Exception:
            mystic = await client.send_message(CallbackQuery.message.chat.id, "**جـارٍ الـتـحـمـيـل...**")

        is_video = (stype == "video")
        yturl = f"https://www.youtube.com/watch?v={vidid}"

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
        log.exception("song_download_callback failed")
        try:
            await mystic.edit_text("**فـشـل الـتـحـمـيـل، حـاول مـرة أخـرى لاحـقـاً.**")
        except Exception:
            pass

# --- end of file ---
