# Authored By Certified Coders © 2025
import os
import asyncio
from random import randint
from typing import Union

from pyrogram.types import InlineKeyboardMarkup
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

# --- دالة الحذف الآمن ---
async def safe_delete(message):
    try:
        await message.delete()
    except:
        pass

# --- الدالة الذكية للتشغيل (Smart Play Wrapper) ---
# هذه الدالة تحاول التشغيل المباشر، وإذا فشلت، تقوم بالتحميل تلقائياً
async def smart_play(chat_id, original_chat_id, file_path, video_status, thumbnail, link, vidid, mystic):
    try:
        # المحاولة 1: تشغيل الرابط المباشر (الأسرع)
        await StreamController.join_call(
            chat_id,
            original_chat_id,
            file_path,
            video=video_status,
            image=thumbnail,
        )
        return file_path, False  # False تعني أنه لم يتم التحميل محلياً (رابط مباشر)
    except Exception as e:
        # إذا فشل التشغيل المباشر، ننتقل للخطة البديلة
        if "NoVideoSourceFound" in str(e) or "Format" in str(e):
            try:
                # المحاولة 2: تحميل الملف محلياً (الأضمن)
                if mystic:
                    try:
                        await mystic.edit_text("⚠️ فشل الرابط المباشر.. جاري التحميل السريع 📥...")
                    except:
                        pass
                
                # إجبار التحميل
                new_file_path, _ = await YouTube.download(
                    vidid if vidid else link, 
                    mystic, 
                    videoid=False, # نجبره يحمل كملف
                    video=video_status
                )
                
                if new_file_path:
                    await StreamController.join_call(
                        chat_id,
                        original_chat_id,
                        new_file_path,
                        video=video_status,
                        image=thumbnail,
                    )
                    return new_file_path, True # True تعني أنه تم التحميل محلياً
            except Exception as final_err:
                raise AssistantErr(f"فشل التشغيل بكل الطرق: {final_err}")
        else:
            raise e
    return file_path, False

@capture_internal_err
async def stream(
    _,
    mystic,
    user_id,
    result,
    chat_id,
    user_name,
    original_chat_id,
    video: Union[bool, str] = None,
    streamtype: Union[bool, str] = None,
    spotify: Union[bool, str] = None,
    forceplay: Union[bool, str] = None,
) -> None:
    if not result:
        return

    status = True if video else None
    forceplay = bool(forceplay)

    if forceplay:
        await StreamController.force_stop_stream(chat_id)

    # =====================================
    # 1. PLAYLIST MODE
    # =====================================
    if streamtype == "playlist":
        msg = f"{_['play_19']}\n\n"
        count = 0
        position = 0

        for search in result:
            if int(count) == config.PLAYLIST_FETCH_LIMIT:
                continue
            try:
                title, duration_min, duration_sec, thumbnail, vidid = await YouTube.details(
                    search, False if spotify else True
                )
            except Exception:
                continue

            if str(duration_min) == "None":
                continue
            if duration_sec and duration_sec > config.DURATION_LIMIT:
                continue

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
                position = len(db.get(chat_id)) - 1
                count += 1
                msg += f"{count}. {title[:70]}\n"
                msg += f"{_['play_20']} {position}\n\n"
            else:
                if not forceplay:
                    db[chat_id] = []
                
                # نحاول نجيب رابط مباشر الأول
                try:
                    file_path, direct = await YouTube.download(
                        vidid, mystic, video=status, videoid=True
                    )
                except:
                    continue

                # استخدام التشغيل الذكي
                try:
                    final_path, is_downloaded = await smart_play(
                        chat_id, original_chat_id, file_path, status, thumbnail, None, vidid, mystic
                    )
                except:
                    continue

                await put_queue(
                    chat_id,
                    original_chat_id,
                    final_path if is_downloaded else f"vid_{vidid}",
                    title,
                    duration_min,
                    user_name,
                    vidid,
                    user_id,
                    "video" if video else "audio",
                    forceplay=forceplay,
                )
                
                try:
                    img = await get_thumb(vidid)
                except:
                    img = config.STREAM_IMG_URL

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
        final_position = len(db.get(chat_id) or []) - 1
        
        return await app.send_photo(
            original_chat_id,
            photo=playlist_photo,
            caption="🧚 " + _["play_21"].format(final_position, link),
            reply_markup=upl,
        )

    # =====================================
    # 2. YOUTUBE MODE (SMART HANDLING)
    # =====================================
    elif streamtype == "youtube":
        link = result.get("link")
        vidid = result.get("vidid")
        title = (result.get("title", "Unknown Track")).title()
        duration_min = result.get("duration_min", "00:00")
        thumbnail = result.get("thumb")

        try:
            # نجرب نجيب رابط مباشر (videoid=True) للسرعة
            file_path, direct = await YouTube.download(
                vidid, mystic, videoid=True, video=status
            )
        except Exception:
             # لو فشل الاستخراج، نعتبره فشل ونجرب نحمل
            file_path = vidid # مجرد تمرير
            direct = False

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
            
            try:
                img = await get_thumb(vidid)
            except:
                img = config.STREAM_IMG_URL

            position = len(db.get(chat_id)) - 1
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
            
            # 🔥 هنا السحر: التشغيل الذكي (مباشر أو تحميل)
            try:
                final_path, is_downloaded = await smart_play(
                    chat_id, original_chat_id, file_path, status, thumbnail, link, vidid, mystic
                )
            except AssistantErr as e:
                await safe_delete(mystic)
                return await app.send_message(original_chat_id, f"⚠️ {e}")
            except Exception as e:
                 await safe_delete(mystic)
                 return await app.send_message(original_chat_id, f"⚠️ حدث خطأ غير متوقع: {e}")

            await put_queue(
                chat_id,
                original_chat_id,
                final_path if is_downloaded else f"vid_{vidid}",
                title,
                duration_min,
                user_name,
                vidid,
                user_id,
                "video" if video else "audio",
                forceplay=forceplay,
            )
            
            try:
                img = await get_thumb(vidid)
            except:
                img = config.STREAM_IMG_URL
                
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
            position = len(db.get(chat_id)) - 1
            button = aq_markup(_, chat_id)
            await app.send_message(
                chat_id=original_chat_id,
                text="🧚 " + _["queue_4"].format(position, title[:27], duration_min, user_name),
                reply_markup=InlineKeyboardMarkup(button),
            )
        else:
            if not forceplay:
                db[chat_id] = []
            await StreamController.join_call(chat_id, original_chat_id, file_path, video=False)
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
            position = len(db.get(chat_id)) - 1
            button = aq_markup(_, chat_id)
            await app.send_message(
                chat_id=original_chat_id,
                text="🧚 " + _["queue_4"].format(position, title[:27], duration_min, user_name),
                reply_markup=InlineKeyboardMarkup(button),
            )
        else:
            if not forceplay:
                db[chat_id] = []
            await StreamController.join_call(chat_id, original_chat_id, file_path, video=status)
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
            position = len(db.get(chat_id)) - 1
            button = aq_markup(_, chat_id)
            await app.send_message(
                chat_id=original_chat_id,
                text="🧚 " + _["queue_4"].format(position, title[:27], duration_min, user_name),
                reply_markup=InlineKeyboardMarkup(button),
            )
        else:
            if not forceplay:
                db[chat_id] = []
            
            # في اللايف نحاول نشغل الرابط مباشرة
            try:
                await StreamController.join_call(
                    chat_id,
                    original_chat_id,
                    link,
                    video=status,
                    image=thumbnail or None,
                )
            except Exception as e:
                # لو فشل اللايف، مفيش حل غير إنه الرابط مش شغال، لأن اللايف مينفعش يتحمل
                await safe_delete(mystic)
                return await app.send_message(original_chat_id, f"⚠️ فشل تشغيل البث المباشر. قد يكون الرابط منتهي الصلاحية.")

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
            
            try:
                img = await get_thumb(vidid)
            except:
                img = config.STREAM_IMG_URL
                
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
            position = len(db.get(chat_id)) - 1
            button = aq_markup(_, chat_id)
            await mystic.edit_text(
                text="🧚 " + _["queue_4"].format(position, title[:27], duration_min, user_name),
                reply_markup=InlineKeyboardMarkup(button),
            )
        else:
            if not forceplay:
                db[chat_id] = []
            await StreamController.join_call(
                chat_id,
                original_chat_id,
                link,
                video=status,
            )
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
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"
