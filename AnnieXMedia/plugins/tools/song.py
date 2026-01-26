# تم التطوير بواسطة Certified Coders 2026
# الربط الوظيفي: YouTube + YTProcessor (Cookie Rotation)
# Zero Errors Edition

import asyncio
import os
from pyrogram import filters
from pyrogram.types import (
    InlineKeyboardMarkup, 
    Message, 
    InputMediaAudio, 
    InputMediaVideo
)

from config import BANNED_USERS, SONG_DOWNLOAD_DURATION, SONG_DOWNLOAD_DURATION_LIMIT
from AnnieXMedia import app
from AnnieXMedia.platforms.Youtube import YouTube 
from AnnieXMedia.platforms.YTProcessor import Processor 
from AnnieXMedia.utils.inline.song import song_markup

COMMANDS = ["اغنية", "اغنيه", "هات", "ابعتلي"]

@app.on_message(filters.command(COMMANDS, prefixes=["", "/"]) & ~BANNED_USERS)
async def song_processor(client, message: Message):
    """البحث مع حماية ضد أخطاء الـ Listener"""
    
    if len(message.command) < 2:
        # التحقق من وجود خاصية listen لتجنب الانهيار
        if not hasattr(client, "listen"):
            return await message.reply_text("⬇️ يـرجى كـتـابـة اسـم الـمـقـطـع بـعـد الأمـر.\nمـثـال: /اغنية سورة البقرة")
            
        try:
            prompt = await message.reply_text("ارسـل الان اسـم الـمـقـطـع")
            response = await client.listen(
                chat_id=message.chat.id,
                filters=filters.user(message.from_user.id),
                timeout=10
            )
            if response:
                query = response.text
                await prompt.delete()
            else:
                return await prompt.edit_text("تـم انـهـاء الـطـلـب لـعـدم وجـود رد .")
        except asyncio.TimeoutError:
            return await message.reply_text("تـم انـهـاء الـطـلـب لـعـدم وجـود طـلـب .")
        except Exception:
            # إخفاء أي خطأ تقني وتوجيه المستخدم للطريقة الصحيحة
            return await message.reply_text("⚠️ حـدث خـطأ، يـرجى كـتـابة الاسم بـعد الأمر مـباشـرة.")
    else:
        query = message.text.split(None, 1)[1]
    
    mystic = await message.reply_text("جـاري الـبـحـث...")
    
    try:
        title, duration_min, duration_sec, thumbnail, vidid = await YouTube.details(query)
        
        if int(duration_sec) > SONG_DOWNLOAD_DURATION_LIMIT:
            return await mystic.edit_text(f"الـمـقـطـع يـتـجـاوز الـحـد الـمـسـمـوح {SONG_DOWNLOAD_DURATION} دقـيـقـة")
        
        buttons = song_markup(None, vidid)
        await mystic.delete()
        await message.reply_photo(
            photo=thumbnail, 
            caption=f"الـعـنـوان: {title}\nالـمـدة: {duration_min}\n\nاخـتـر الـجـودة والـنـوع الـمـطـلوب:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except Exception:
        await mystic.edit_text("لـم يـتـم الـعـثـور عـلـى نـتـائج")

@app.on_message(filters.command(["يوت"], prefixes=["", "/"]) & ~BANNED_USERS)
async def yut_direct_processor(client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("يـرجى كـتـابـة اسـم الـمـقـطـع أو الـرابـط")
    
    query = message.text.split(None, 1)[1]
    mystic = await message.reply_text("جـاري الـتـحـمـيـل...")
    try:
        title, _, duration_sec, _, vidid = await YouTube.details(query)
        yturl = f"https://www.youtube.com/watch?v={vidid}"
        file_path = await Processor.download_file(yturl, "bestaudio", False, title)
        await mystic.edit_text("جـاري الـرفـع...")
        await Processor.send_smart_file(
            client, message.chat.id, file_path, False, 
            title, duration_sec, None, message.from_user.first_name
        )
        await mystic.delete()
    except Exception as e:
        await mystic.edit_text(f"حـدث خـطـأ: {e}")

@app.on_callback_query(filters.regex(pattern=r"song_download") & ~BANNED_USERS)
async def song_download_callback(client, CallbackQuery):
    stype, format_id, vidid = CallbackQuery.data.split(None, 1)[1].split("|")
    await CallbackQuery.answer("جـاري تـحـضـيـر الـمـلـف...")
    mystic = await CallbackQuery.edit_message_text("جـاري الـتـحـمـيـل...")
    is_video = (stype == "video")
    yturl = f"https://www.youtube.com/watch?v={vidid}"
    
    try:
        title, _, duration_sec, _, _ = await YouTube.details(vidid)
        file_path = await Processor.download_file(yturl, format_id, is_video, title)
        thumb = await CallbackQuery.message.download() if CallbackQuery.message.photo else None
        await mystic.edit_text("جـاري الـرفـع...")
        
        if is_video:
            media = InputMediaVideo(
                media=file_path, thumb=thumb,
                caption=f"الـعـنـوان: {title}\nطـلـب: {CallbackQuery.from_user.first_name}",
                duration=duration_sec, supports_streaming=True
            )
        else:
            media = InputMediaAudio(
                media=file_path, thumb=thumb,
                caption=f"الـعـنـوان: {title}\nطـلـب: {CallbackQuery.from_user.first_name}",
                duration=duration_sec, title=title, performer=CallbackQuery.from_user.first_name
            )
        try:
            await CallbackQuery.edit_message_media(media=media)
            if os.path.exists(file_path): os.remove(file_path)
        except Exception:
            await Processor.send_smart_file(
                client, CallbackQuery.message.chat.id, file_path, 
                is_video, title, duration_sec, thumb, CallbackQuery.from_user.first_name
            )
        await mystic.delete()
    except Exception as e:
        await mystic.edit_text(f"فـشـل الإرسـال: {e}")

@app.on_callback_query(filters.regex(pattern=r"song_helper") & ~BANNED_USERS)
async def song_helper_callback(client, CallbackQuery):
    stype, vidid = CallbackQuery.data.split(None, 1)[1].split("|")
    await CallbackQuery.answer("جـاري جـلـب الـجـودات...")
    buttons = await Processor.get_quality_buttons(vidid, stype)
    await CallbackQuery.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))

@app.on_callback_query(filters.regex(pattern=r"song_back") & ~BANNED_USERS)
async def song_back_callback(client, CallbackQuery):
    stype, vidid = CallbackQuery.data.split(None, 1)[1].split("|")
    buttons = song_markup(None, vidid)
    await CallbackQuery.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
