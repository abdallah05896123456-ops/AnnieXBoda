# file: song.py
# Plugin: Song handling for AnnieXMedia (uses AnnieXMedia.platforms.Youtube.YouTube)
# Expects Processor.download_file -> (path_or_url, direct_flag)

import asyncio
import os
import re
import time
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, Message
from motor.motor_asyncio import AsyncIOMotorClient

from config import (
    BANNED_USERS,
    OWNER_ID,
    MONGO_DB_URI,
)
from AnnieXMedia import app
from AnnieXMedia.platforms.Youtube import YouTube
from AnnieXMedia.platforms.YTProcessor import Processor
from AnnieXMedia.utils.inline.song import song_markup

SUDO_USERS = OWNER_ID if isinstance(OWNER_ID, list) else [OWNER_ID]

_mongo_client_ = AsyncIOMotorClient(MONGO_DB_URI)
mongodb = _mongo_client_.Annie
songdb = mongodb.song_settings

async def get_config(key):
    try:
        data = await songdb.find_one({"_id": "song_config"})
        if not data:
            return False
        return data.get(key, False)
    except Exception:
        return False

async def set_config(key, value):
    try:
        await songdb.update_one({"_id": "song_config"}, {"$set": {key: value}}, upsert=True)
    except Exception:
        pass

def _normalize_download_result(res):
    """
    Normalize Processor.download_file returns to (path_or_url, direct_bool)
    """
    if res is None:
        return None, False
    if isinstance(res, tuple) or isinstance(res, list):
        if len(res) >= 2:
            return res[0], bool(res[1])
        if len(res) == 1:
            return res[0], False
        return None, False
    if isinstance(res, str):
        return res, False
    return None, False

# ---------------- Command handlers (same as before, using normalized returns) ----------------

@app.on_message(filters.command(["قفل البحث", "تعطيل البحث"], prefixes=["", "/"]) & filters.user(SUDO_USERS))
async def lock_whole_section(client, message):
    await set_config("search_locked", True)
    await message.reply_text("**تم قفل قسم البحث والتحميل نهائياً.**")

@app.on_message(filters.command(["فتح البحث", "تفعيل البحث"], prefixes=["", "/"]) & filters.user(SUDO_USERS))
async def unlock_whole_section(client, message):
    await set_config("search_locked", False)
    await message.reply_text("**تم فتح قسم البحث والتحميل.**")

@app.on_message(filters.command(["قفل انلاين البحث", "قفل انلاين بحث"], prefixes=["", "/"]) & filters.user(SUDO_USERS))
async def lock_inline_search(client, message):
    await set_config("inline_locked", True)
    await message.reply_text("**تم قفل بحث الانلاين.**")

@app.on_message(filters.command(["فتح انلاين البحث", "فتح انلاين بحث"], prefixes=["", "/"]) & filters.user(SUDO_USERS))
async def unlock_inline_search(client, message):
    await set_config("inline_locked", False)
    await message.reply_text("**تم فتح بحث الانلاين.**")

@app.on_message(filters.regex(r"^/?(اغنية|اغنيه|هات|هاتلي|ابعتلي|song|video|تحميل|يوتيوب)(?:\s+(فيد|فيديو|video))?(?:\s+(.+))?$") & ~BANNED_USERS, group=5)
async def unified_song_processor(client, message: Message):
    is_search_locked = await get_config("search_locked")
    if is_search_locked and message.from_user.id not in SUDO_USERS:
        return await message.reply_text("**عذراً، القسم مغلق.**")

    match = re.match(r"^/?(اغنية|اغنيه|هات|هاتلي|ابعتلي|song|video|تحميل|يوتيوب)(?:\s+(فيد|فيديو|video))?(?:\s+(.+))?$", message.text or "")
    if not match:
        return

    command_trigger = match.group(1).lower()
    video_trigger = match.group(2)
    query = match.group(3)

    is_video_request = command_trigger in ["video", "/video", "فيديو"] or bool(video_trigger)

    if not query:
        prompt = await message.reply_text("**ارسل اسم المقطع او رابط اليوتيوب الآن...**")
        try:
            response = await client.listen(chat_id=message.chat.id, user_id=message.from_user.id, timeout=20)
            if response and (response.text or response.reply_to_message):
                query = response.text or (response.reply_to_message.text if response.reply_to_message else None)
                await prompt.delete()
            else:
                return await prompt.edit_text("**انتهى وقت الانتظار.**")
        except Exception:
            return await prompt.edit_text("**حصل خطأ في الاستماع.**")

    mystic = await message.reply_text("**جاري البحث...**")

    # playlist detection
    if "list=" in str(query) and ("youtube.com" in query or "youtu.be" in query):
        try:
            await Processor.download_playlist(
                client=client,
                mystic_msg=mystic,
                playlist_url=query,
                is_video=is_video_request,
                user_name=message.from_user.first_name
            )
        except Exception as e:
            await mystic.edit_text(f"**خطأ في القائمة:** {e}")
        return

    # single item
    try:
        title, duration_min, duration_sec, thumbnail, vidid = await YouTube.details(query)
        if duration_sec is None:
            duration_sec = 0

        if int(duration_sec) > 14400:
            return await mystic.edit_text("**المقطع طويل جداً (حد أقصى 4 ساعات).**")

        is_inline_locked = await get_config("inline_locked")

        if is_inline_locked:
            await mystic.edit_text("**جاري التحميل الفوري...**")
            yturl = f"https://www.youtube.com/watch?v={vidid}"
            quality_arg = "high" if message.from_user.id in SUDO_USERS else "mid"
            res = await Processor.download_file(yturl, quality_arg, is_video_request, title, vidid=vidid, is_owner=(message.from_user.id in SUDO_USERS))
            file_path, direct = _normalize_download_result(res)
            if not file_path:
                return await mystic.edit_text("**فشل التحميل.**")
            await mystic.edit_text("**جاري الرفع إلى تليجرام...**")
            await Processor.upload_alexa_style(client, mystic, file_path, is_video_request, title, duration_sec, message.from_user.first_name, vidid=vidid)
        else:
            buttons = song_markup(None, vidid)
            await mystic.delete()
            await message.reply_photo(
                photo=thumbnail,
                caption=f"**العنوان:** {title}\n**المدة:** {duration_min}\n\n**اختر الجودة:**",
                reply_markup=InlineKeyboardMarkup(buttons)
            )
    except Exception:
        is_inline_locked = await get_config("inline_locked")
        if is_inline_locked or is_video_request:
            await mystic.edit_text("**جاري البحث والتحميل...**")
            res = await Processor.download_file(query, "mid", is_video_request, query, is_owner=(message.from_user.id in SUDO_USERS))
            file_path, direct = _normalize_download_result(res)
            if file_path:
                await mystic.edit_text("**جاري الرفع...**")
                await Processor.upload_alexa_style(client, mystic, file_path, is_video_request, query, 0, message.from_user.first_name)
            else:
                await mystic.edit_text("**لم يتم العثور على نتائج.**")
        else:
            await mystic.edit_text("**لم يتم العثور على نتائج.**")

@app.on_message(filters.command(["يوت"], prefixes=["", "/"]) & ~BANNED_USERS)
async def yut_direct_audio(client, message: Message):
    if await get_config("search_locked") and message.from_user.id not in SUDO_USERS:
        return await message.reply_text("**القسم مغلق.**")
    if len(message.command) < 2:
        return await message.reply_text("**اكتب رابط اليوتيوب بجانب الأمر.**")
    query = message.text.split(None, 1)[1]
    mystic = await message.reply_text("**جاري التحميل...**")
    if "list=" in query:
        return await Processor.download_playlist(client, mystic, query, False, message.from_user.first_name)
    try:
        title, _, duration_sec, _, vidid = await YouTube.details(query)
        yturl = f"https://www.youtube.com/watch?v={vidid}"
        quality_arg = "high" if message.from_user.id in SUDO_USERS else "mid"
        res = await Processor.download_file(yturl, quality_arg, False, title, vidid=vidid, is_owner=(message.from_user.id in SUDO_USERS))
        file_path, direct = _normalize_download_result(res)
        if not file_path:
            return await mystic.edit_text("**فشل التحميل.**")
        await mystic.edit_text("**جاري الرفع...**")
        await Processor.upload_alexa_style(client, mystic, file_path, False, title, duration_sec, message.from_user.first_name, vidid=vidid)
    except Exception as e:
        await mystic.edit_text(f"**حدث خطأ:** {e}")

@app.on_message(filters.command(["يوت فيد", "يوت فيديو"], prefixes=["", "/"]) & ~BANNED_USERS)
async def yut_direct_video(client, message: Message):
    if await get_config("search_locked") and message.from_user.id not in SUDO_USERS:
        return await message.reply_text("**القسم مغلق.**")
    if len(message.command) < 3:
        return await message.reply_text("**اكتب رابط الفيديو بعد الأمر.**")
    query = message.text.split(None, 2)[2]
    mystic = await message.reply_text("**جاري التحميل...**")
    if "list=" in query:
        return await Processor.download_playlist(client, mystic, query, True, message.from_user.first_name)
    try:
        title, _, duration_sec, _, vidid = await YouTube.details(query)
        yturl = f"https://www.youtube.com/watch?v={vidid}"
        quality_arg = "high" if message.from_user.id in SUDO_USERS else "mid"
        res = await Processor.download_file(yturl, quality_arg, True, title, vidid=vidid, is_owner=(message.from_user.id in SUDO_USERS))
        file_path, direct = _normalize_download_result(res)
        if not file_path:
            return await mystic.edit_text("**فشل التحميل.**")
        await mystic.edit_text("**جاري الرفع...**")
        await Processor.upload_alexa_style(client, mystic, file_path, True, title, duration_sec, message.from_user.first_name, vidid=vidid)
    except Exception as e:
        await mystic.edit_text(f"**حدث خطأ:** {e}")

@app.on_callback_query(filters.regex(pattern=r"song_download") & ~BANNED_USERS)
async def song_download_callback(client, query):
    if await get_config("search_locked") and query.from_user.id not in SUDO_USERS:
        return await query.answer("القسم مغلق.", show_alert=True)
    if await get_config("inline_locked") and query.from_user.id not in SUDO_USERS:
        return await query.answer("الميزة معطلة مؤقتاً.", show_alert=True)

    data = query.data
    try:
        payload = data.split(None, 1)[1] if " " in data else data.replace("song_download", "").lstrip("_ ").lstrip()
        parts = payload.split("|")
        if len(parts) < 3:
            raise ValueError("invalid")
        stype, quality_arg, vidid = parts[0], parts[1], parts[2]
    except Exception:
        return await query.answer("خطأ في البيانات.", show_alert=True)

    await query.answer("جاري بدء التحميل...")
    try:
        try:
            mystic = await query.message.edit_text("**جارٍ التحميل من يوتيوب...**")
        except Exception:
            mystic = await client.send_message(query.message.chat.id, "**جارٍ التحميل...**")
        is_video = (stype == "video")
        yturl = f"https://www.youtube.com/watch?v={vidid}"
        title, _, duration_sec, _, _ = await YouTube.details(vidid)
        res = await Processor.download_file(yturl, quality_arg, is_video, title, vidid=vidid, is_owner=(query.from_user.id in SUDO_USERS))
        file_path, direct = _normalize_download_result(res)
        if not file_path:
            return await mystic.edit_text("**فشل التحميل، حاول مرة أخرى.**")
        await mystic.edit_text("**جاري الرفع...**")
        await Processor.upload_alexa_style(client, mystic, file_path, is_video, title, duration_sec, query.from_user.first_name, vidid=vidid)
    except Exception:
        await mystic.edit_text("**فشل التحميل، حاول لاحقاً.**")

@app.on_callback_query(filters.regex(pattern=r"song_helper") & ~BANNED_USERS)
async def song_helper_callback(client, query):
    if await get_config("search_locked") and query.from_user.id not in SUDO_USERS:
        return await query.answer("القسم مغلق.", show_alert=True)
    try:
        payload = query.data.split(None, 1)[1] if " " in query.data else query.data.replace("song_helper", "").lstrip("_ ").lstrip()
        stype, vidid = payload.split("|")
    except Exception:
        return await query.answer("خطأ في البيانات.", show_alert=True)
    await query.answer("جلب خيارات الجودة...")
    buttons = await Processor.get_quality_buttons(vidid, stype)
    await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))

@app.on_callback_query(filters.regex(pattern=r"song_back") & ~BANNED_USERS)
async def song_back_callback(client, query):
    try:
        payload = query.data.split(None, 1)[1] if " " in query.data else query.data.replace("song_back", "").lstrip("_ ").lstrip()
        stype, vidid = payload.split("|")
    except Exception:
        return await query.answer("خطأ في البيانات.", show_alert=True)
    buttons = song_markup(None, vidid)
    await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
