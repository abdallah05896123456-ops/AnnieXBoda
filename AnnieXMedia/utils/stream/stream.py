import os
import asyncio
import logging
from random import randint
from typing import Union, Dict, List, Optional

from pyrogram import Client
from pyrogram.types import InlineKeyboardMarkup, Message
from pyrogram.errors import FloodWait

import config
from AnnieXMedia import Carbon, YouTube, app
from AnnieXMedia.core.call import StreamController
from AnnieXMedia.misc import db
from AnnieXMedia.utils.database import (
    add_active_video_chat,
    is_active_chat,
    add_active_chat,
)
from AnnieXMedia.utils.exceptions import AssistantErr
from AnnieXMedia.utils.inline import aq_markup, close_markup, stream_markup
from AnnieXMedia.utils.pastebin import ANNIEBIN
from AnnieXMedia.utils.stream.queue import put_queue, put_queue_index
from AnnieXMedia.utils.thumbnails import get_thumb
from AnnieXMedia.utils.errors import capture_internal_err

# إعداد السجلات (Logging)
logger = logging.getLogger(__name__)

async def safe_delete(message: Message):
    """حذف الرسالة بأمان."""
    try:
        await message.delete()
    except Exception:
        pass

async def safe_join_call(chat_id, original_chat_id, file_path, video_status, thumbnail):
    """الانضمام للمكالمة مع حماية من الأخطاء."""
    logger.info(f"Joining call in chat {chat_id}, Video: {video_status}")
    if not file_path:
        raise AssistantErr("❌ لم يتم العثور على رابط صالح للتشغيل.")
    try:
        await StreamController.join_call(
            chat_id,
            original_chat_id,
            file_path,
            video=video_status,
            image=thumbnail,
        )
    except Exception as e:
        logger.error(f"Failed to join call: {e}")
        if "NoneType" in str(e) or "incorrect type" in str(e):
            raise AssistantErr("⚠️ خطأ داخلي: فشل استخراج الرابط.")
        raise e

async def get_thumb_safe(vidid):
    """دالة مساعدة لجلب الصورة مع تجاوز الأخطاء."""
    try:
        return await get_thumb(vidid) or config.STREAM_IMG_URL
    except Exception:
        return config.STREAM_IMG_URL

@capture_internal_err
async def stream(
    _: Union[Client, Dict[str, str]], # تم تعديل النوع ليقبل قاموس اللغة
    mystic: Message,
    user_id: int,
    result: Union[dict, List, str],
    chat_id: int,
    user_name: str,
    original_chat_id: int,
    video: bool = None,
    streamtype: str = None,
    spotify: bool = None,
    forceplay: bool = None,
) -> None:
    """
    الدالة الرئيسية للتحكم في البث.
    """
    if not result:
        return

    # توحيد حالة الفيديو
    status = True if video else None
    forceplay = bool(forceplay)

    # إيقاف البث الإجباري
    if forceplay:
        await StreamController.force_stop_stream(chat_id)

    # =====================================
    # 1. PLAYLIST MODE
    # =====================================
    if streamtype == "playlist":
        msg = f"{_['play_19']}\n\n"
        count = 0 
        processed = 0 # عداد منفصل للمعالجة الفعلية
        
        # التأكد من تهيئة القائمة في قاعدة البيانات
        if not db.get(chat_id):
            db[chat_id] = []

        for search in result:
            if processed >= config.PLAYLIST_FETCH_LIMIT:
                break
            try:
                # استخراج البيانات كـ Tuple
                title, duration_min, duration_sec, thumbnail, vidid = await YouTube.details(
                    search, False if spotify else True
                )
            except Exception as e:
                continue

            if str(duration_min) == "None":
                continue
            if duration_sec and duration_sec > config.DURATION_LIMIT:
                continue

            # إضافة للقائمة إذا كان الشات نشطاً
            if await is_active_chat(chat_id):
                await put_queue(
                    chat_id,
                    original_chat_id,
                    f"vid_{vidid}",
                    title,
                    duration_min,
                    user_name,
                    vidid,
                    user_id,
                    "video" if video else "audio",
                )
                # حماية db.get
                queue_len = len(db.get(chat_id, []))
                position = queue_len - 1
                processed += 1
                count += 1
                msg += f"{count}. {title[:70]}\n"
                msg += f"{_['play_20']} {position}\n\n"
            else:
                if not forceplay:
                    db[chat_id] = []
                
                file_path = None
                direct = False
                
                # المحاولة الأولى: رابط مباشر
                try:
                    file_path, direct = await YouTube.download(vidid, mystic, video=status, videoid=True)
                except Exception:
                    pass
                
                # المحاولة الثانية: تحميل
                if not file_path:
                    try:
                        file_path, direct = await YouTube.download(vidid, mystic, video=status, videoid=False)
                    except Exception:
                        pass
                
                if not file_path:
                    continue

                try:
                    await safe_join_call(
                        chat_id,
                        original_chat_id,
                        file_path,
                        status,
                        thumbnail,
                    )
                except Exception:
                    continue

                await put_queue(
                    chat_id,
                    original_chat_id,
                    file_path if direct else f"vid_{vidid}",
                    title,
                    duration_min,
                    user_name,
                    vidid,
                    user_id,
                    "video" if video else "audio",
                    forceplay=forceplay,
                )
                
                img = await get_thumb_safe(vidid)
                button = stream_markup(_, chat_id)
                await safe_delete(mystic)

                caption_text = "🧚 " + _["stream_1"].format(
                    f"https://t.me/{app.username}?start=info_{vidid}",
                    title[:23],
                    duration_min,
                    user_name,
                )
                try:
                    run = await app.send_photo(
                        original_chat_id,
                        photo=img,
                        caption=caption_text,
                        reply_markup=InlineKeyboardMarkup(button),
                    )
                    if db.get(chat_id):
                        db[chat_id][0]["mystic"] = run
                        db[chat_id][0]["markup"] = "stream"
                except FloodWait as e:
                    await asyncio.sleep(e.value)
                    run = await app.send_photo(
                        original_chat_id,
                        photo=img,
                        caption=caption_text,
                        reply_markup=InlineKeyboardMarkup(button),
                    )
                    if db.get(chat_id):
                        db[chat_id][0]["mystic"] = run
                        db[chat_id][0]["markup"] = "stream"

        if count == 0:
            return
            
        link = await ANNIEBIN(msg)
        lines = msg.count("\n")
        car = os.linesep.join(msg.split(os.linesep)[:17]) if lines >= 17 else msg
        try:
            carbon = await Carbon.generate(car, randint(100, 10000000))
            playlist_photo = carbon
        except Exception:
            playlist_photo = config.PLAYLIST_IMG_URL
            
        upl = close_markup(_)
        final_position = len(db.get(chat_id, [])) - 1
        
        return await app.send_photo(
            original_chat_id,
            photo=playlist_photo,
            caption="🧚 " + _["play_21"].format(final_position, link),
            reply_markup=upl,
        )

    # =====================================
    # 2. YOUTUBE MODE
    # =====================================
    elif streamtype == "youtube":
        link = result.get("link")
        vidid = result.get("vidid")
        title = (result.get("title", "Unknown Track")).title()
        duration_min = result.get("duration_min", "00:00")
        thumbnail = result.get("thumb")

        file_path = None
        direct = False

        try:
            file_path, direct = await YouTube.download(
                vidid, mystic, videoid=True, video=status
            )
        except Exception:
            pass

        if not file_path:
            try:
                try:
                    await mystic.edit_text("🔄 جاري محاولة التحميل بطريقة بديلة...")
                except Exception:
                    pass
                file_path, direct = await YouTube.download(
                    vidid, mystic, videoid=False, video=status
                )
            except Exception:
                pass

        if not file_path:
            file_path = link 
            direct = True 

        if await is_active_chat(chat_id):
            await put_queue(
                chat_id,
                original_chat_id,
                f"vid_{vidid}",
                title,
                duration_min,
                user_name,
                vidid,
                user_id,
                "video" if video else "audio",
            )
            
            img = await get_thumb_safe(vidid)
            position = len(db.get(chat_id, [])) - 1
            button = aq_markup(_, chat_id)
            await safe_delete(mystic)
            
            await app.send_photo(
                chat_id=original_chat_id,
                photo=img,
                caption="🧚 " + _["queue_4"].format(position, title[:27], duration_min, user_name),
                reply_markup=InlineKeyboardMarkup(button),
            )
        else:
            if not forceplay:
                db[chat_id] = []
            
            try:
                await safe_join_call(
                    chat_id,
                    original_chat_id,
                    file_path,
                    status,
                    thumbnail,
                )
            except AssistantErr as e:
                await safe_delete(mystic)
                return await app.send_message(original_chat_id, f"⚠️ {e}")
            except Exception:
                await safe_delete(mystic)
                return await app.send_message(
                    original_chat_id, 
                    f"⚠️ تعذر تشغيل الفيديو.\nيوتيوب يرفض الاتصال أو الصيغة غير مدعومة حالياً."
                )

            await put_queue(
                chat_id,
                original_chat_id,
                file_path if direct else f"vid_{vidid}",
                title,
                duration_min,
                user_name,
                vidid,
                user_id,
                "video" if video else "audio",
                forceplay=forceplay,
            )
            
            img = await get_thumb_safe(vidid)
            button = stream_markup(_, chat_id)
            await safe_delete(mystic)
            
            caption_text = "🧚 " + _["stream_1"].format(
                f"https://t.me/{app.username}?start=info_{vidid}",
                title[:23],
                duration_min,
                user_name,
            )
            try:
                run = await app.send_photo(
                    original_chat_id,
                    photo=img,
                    caption=caption_text,
                    reply_markup=InlineKeyboardMarkup(button),
                )
                if db.get(chat_id):
                    db[chat_id][0]["mystic"] = run
                    db[chat_id][0]["markup"] = "stream"
            except FloodWait as e:
                await asyncio.sleep(e.value)
                run = await app.send_photo(
                    original_chat_id,
                    photo=img,
                    caption=caption_text,
                    reply_markup=InlineKeyboardMarkup(button),
                )
                if db.get(chat_id):
                    db[chat_id][0]["mystic"] = run
                    db[chat_id][0]["markup"] = "stream"

    # =====================================
    # 3. SOUNDCLOUD MODE
    # =====================================
    elif streamtype == "soundcloud":
        file_path = result.get("filepath")
        title = result.get("title", "SoundCloud Track")
        duration_min = result.get("duration_min", "00:00")
        
        if not file_path:
            raise AssistantErr(_["play_14"])

        if await is_active_chat(chat_id):
            await put_queue(
                chat_id,
                original_chat_id,
                file_path,
                title,
                duration_min,
                user_name,
                streamtype,
                user_id,
                "audio",
            )
            position = len(db.get(chat_id, [])) - 1
            button = aq_markup(_, chat_id)
            await app.send_message(
                chat_id=original_chat_id,
                text="🧚 " + _["queue_4"].format(position, title[:27], duration_min, user_name),
                reply_markup=InlineKeyboardMarkup(button),
            )
        else:
            if not forceplay:
                db[chat_id] = []
            
            try:
                await safe_join_call(chat_id, original_chat_id, file_path, False, None)
            except Exception:
                await safe_delete(mystic)
                return await app.send_message(original_chat_id, "⚠️ فشل تشغيل الساوند كلاود.")

            await put_queue(
                chat_id,
                original_chat_id,
                file_path,
                title,
                duration_min,
                user_name,
                streamtype,
                user_id,
                "audio",
                forceplay=forceplay,
            )
            button = stream_markup(_, chat_id)
            await safe_delete(mystic)
            run = await app.send_photo(
                original_chat_id,
                photo=config.SOUNCLOUD_IMG_URL,
                caption="🧚 " + _["stream_1"].format(
                    config.SUPPORT_CHAT, title[:23], duration_min, user_name
                ),
                reply_markup=InlineKeyboardMarkup(button),
            )
            if db.get(chat_id):
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "tg"

    # =====================================
    # 4. TELEGRAM FILES MODE
    # =====================================
    elif streamtype == "telegram":
        file_path = result.get("path")
        link = result.get("link")
        title = (result.get("title", "Telegram File")).title()
        duration_min = result.get("dur", result.get("duration_min", "00:00"))
        
        if not file_path:
            raise AssistantErr(_["play_14"])

        if await is_active_chat(chat_id):
            await put_queue(
                chat_id,
                original_chat_id,
                file_path,
                title,
                duration_min,
                user_name,
                streamtype,
                user_id,
                "video" if video else "audio",
            )
            position = len(db.get(chat_id, [])) - 1
            button = aq_markup(_, chat_id)
            await app.send_message(
                chat_id=original_chat_id,
                text="🧚 " + _["queue_4"].format(position, title[:27], duration_min, user_name),
                reply_markup=InlineKeyboardMarkup(button),
            )
        else:
            if not forceplay:
                db[chat_id] = []
            
            try:
                await safe_join_call(chat_id, original_chat_id, file_path, status, None)
            except:
                return await app.send_message(original_chat_id, "⚠️ الملف غير صالح.")

            await put_queue(
                chat_id,
                original_chat_id,
                file_path,
                title,
                duration_min,
                user_name,
                streamtype,
                user_id,
                "video" if video else "audio",
                forceplay=forceplay,
            )
            if video:
                await add_active_video_chat(chat_id)
            button = stream_markup(_, chat_id)
            await safe_delete(mystic)
            run = await app.send_photo(
                original_chat_id,
                photo=config.TELEGRAM_VIDEO_URL if video else config.TELEGRAM_AUDIO_URL,
                caption="🧚 " + _["stream_1"].format(link, title[:23], duration_min, user_name),
                reply_markup=InlineKeyboardMarkup(button),
            )
            if db.get(chat_id):
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "tg"

    # =====================================
    # 5. LIVE STREAM MODE
    # =====================================
    elif streamtype == "live":
        link = result.get("link")
        vidid = result.get("vidid")
        title = (result.get("title", "Live Stream")).title()
        thumbnail = result.get("thumb")
        duration_min = "Live Track"

        if await is_active_chat(chat_id):
            await put_queue(
                chat_id,
                original_chat_id,
                f"live_{vidid}",
                title,
                duration_min,
                user_name,
                vidid,
                user_id,
                "video" if video else "audio",
            )
            position = len(db.get(chat_id, [])) - 1
            button = aq_markup(_, chat_id)
            await app.send_message(
                chat_id=original_chat_id,
                text="🧚 " + _["queue_4"].format(position, title[:27], duration_min, user_name),
                reply_markup=InlineKeyboardMarkup(button),
            )
        else:
            if not forceplay:
                db[chat_id] = []
            
            file_path = None
            try:
                is_live, direct_link = await YouTube.video(link)
                if is_live and direct_link:
                    file_path = direct_link
                else:
                    file_path = link
            except Exception:
                file_path = link

            try:
                await safe_join_call(
                    chat_id,
                    original_chat_id,
                    file_path,
                    status,
                    thumbnail or None,
                )
            except Exception as e:
                await safe_delete(mystic)
                return await app.send_message(original_chat_id, f"⚠️ فشل تشغيل البث المباشر: {e}")

            await put_queue(
                chat_id,
                original_chat_id,
                f"live_{vidid}",
                title,
                duration_min,
                user_name,
                vidid,
                user_id,
                "video" if video else "audio",
                forceplay=forceplay,
            )
            
            img = await get_thumb_safe(vidid)
            button = stream_markup(_, chat_id)
            await safe_delete(mystic)
            run = await app.send_photo(
                original_chat_id,
                photo=img,
                caption="🧚 " + _["stream_1"].format(
                    f"https://t.me/{app.username}?start=info_{vidid}",
                    title[:23],
                    duration_min,
                    user_name,
                ),
                reply_markup=InlineKeyboardMarkup(button),
            )
            if db.get(chat_id):
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "tg"

    # =====================================
    # 6. INDEX / M3U8 MODE
    # =====================================
    elif streamtype == "index":
        link = result
        title = "رابط خارجي أو M3u8"
        duration_min = "00:00"

        if await is_active_chat(chat_id):
            await put_queue_index(
                chat_id,
                original_chat_id,
                "index_url",
                title,
                duration_min,
                user_name,
                link,
                "video" if video else "audio",
            )
            position = len(db.get(chat_id, [])) - 1
            button = aq_markup(_, chat_id)
            try:
                await mystic.edit_text(
                    text="🧚 " + _["queue_4"].format(position, title[:27], duration_min, user_name),
                    reply_markup=InlineKeyboardMarkup(button),
                )
            except Exception:
                pass
        else:
            if not forceplay:
                db[chat_id] = []
            
            try:
                await safe_join_call(
                    chat_id,
                    original_chat_id,
                    link,
                    status,
                    None
                )
            except:
                return await app.send_message(original_chat_id, "⚠️ الرابط الخارجي لا يعمل.")

            await put_queue_index(
                chat_id,
                original_chat_id,
                "index_url",
                title,
                duration_min,
                user_name,
                link,
                "video" if video else "audio",
                forceplay=forceplay,
            )
            button = stream_markup(_, chat_id)
            await safe_delete(mystic)
            run = await app.send_photo(
                original_chat_id,
                photo=config.STREAM_IMG_URL,
                caption="🧚 " + _["stream_2"].format(user_name),
                reply_markup=InlineKeyboardMarkup(button),
            )
            if db.get(chat_id):
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "tg"
