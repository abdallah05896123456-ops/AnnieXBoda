# Authored By Certified Coders © 2026
# ⚡ THE ULTIMATE STREAM CONTROLLER: FULL & FAST EDITION ⚡

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
from AnnieXMedia.utils.database import add_active_video_chat, is_active_chat
from AnnieXMedia.utils.exceptions import AssistantErr
from AnnieXMedia.utils.inline import aq_markup, close_markup, stream_markup
from AnnieXMedia.utils.pastebin import ANNIEBIN
from AnnieXMedia.utils.stream.queue import put_queue, put_queue_index
from AnnieXMedia.utils.thumbnails import get_thumb
from AnnieXMedia.utils.errors import capture_internal_err


# === نظام الحذف الآمن ===
async def safe_delete(message):
    try:
        await message.delete()
    except:
        pass


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

    # توحيد المنطق البرمجي
    forceplay = bool(forceplay)
    is_video = True if video else False

    # إيقاف التشغيل الحالي إذا طلب العضو "تشغيل إجباري"
    if forceplay:
        await StreamController.force_stop_stream(chat_id)

    # ---------------------------
    # 1. نظام قوائم التشغيل (Playlist)
    # ---------------------------
    if streamtype == "playlist":
        msg = f"{_['play_19']}\n\n"
        count = 0
        
        for search in result:
            if int(count) == config.PLAYLIST_FETCH_LIMIT:
                continue
            try:
                # جلب التفاصيل من كود اليوتيوب الجديد
                title, duration_min, duration_sec, thumbnail, vidid = await YouTube.details(
                    search, videoid=search
                )
            except Exception:
                continue

            if str(duration_min) == "None":
                continue
            if duration_sec and duration_sec > config.DURATION_LIMIT:
                continue

            if await is_active_chat(chat_id):
                # إذا كانت المجموعة مشغلة بالفعل، أضف للطابور فقط
                await put_queue(
                    chat_id,
                    original_chat_id,
                    f"vid_{vidid}",
                    title,
                    duration_min,
                    user_name,
                    vidid,
                    user_id,
                    "video" if is_video else "audio",
                )
                position = len(db.get(chat_id)) - 1
                count += 1
                msg += f"{count}. {title[:70]}\n"
                msg += f"{_['play_20']} {position}\n\n"
            else:
                # إذا كانت المجموعة صامتة، ابدأ التشغيل فوراً
                if not forceplay:
                    db[chat_id] = []
                
                try:
                    file_path, direct = await YouTube.download(
                        vidid, mystic, video=is_video, videoid=vidid
                    )
                except:
                    continue
                
                if not file_path:
                    continue

                await StreamController.join_call(
                    chat_id,
                    original_chat_id,
                    file_path,
                    video=is_video,
                    image=thumbnail,
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
                    "video" if is_video else "audio",
                    forceplay=forceplay,
                )
                
                img = await get_thumb(vidid)
                button = stream_markup(_, chat_id)
                
                try:
                    run = await app.send_photo(
                        original_chat_id,
                        photo=img,
                        caption=_["stream_1"].format(
                            f"https://t.me/{app.username}?start=info_{vidid}",
                            title[:23],
                            duration_min,
                            user_name,
                        ),
                        reply_markup=InlineKeyboardMarkup(button),
                    )
                    db[chat_id][0]["mystic"] = run
                    db[chat_id][0]["markup"] = "stream"
                except FloodWait as e:
                    await asyncio.sleep(e.value)
                except:
                    pass
                count += 1

        if count == 0:
            return
        
        # إنشاء رابط Pastebin وإرسال صورة الكاربون
        link = await ANNIEBIN(msg)
        try:
            lines = msg.count("\n")
            car = os.linesep.join(msg.split(os.linesep)[:17]) if lines >= 17 else msg
            playlist_photo = await Carbon.generate(car, randint(100, 10000000))
        except:
            playlist_photo = config.PLAYLIST_IMG_URL
        
        return await app.send_photo(
            original_chat_id,
            photo=playlist_photo,
            caption=_["play_21"].format(len(db.get(chat_id)) - 1, link),
            reply_markup=close_markup(_),
        )

    # ---------------------------
    # 2. نظام اليوتيوب وسبوتيفاي
    # ---------------------------
    elif streamtype == "youtube" or spotify:
        link = result.get("link")
        vidid = result.get("vidid")
        title = (result.get("title", "Unknown")).title()
        duration_min = result.get("duration_min", "00:00")
        thumbnail = result.get("thumb")

        try:
            # استخدام المحرك السريع للتحميل
            file_path, direct = await YouTube.download(
                vidid, mystic, video=is_video, videoid=vidid
            )
        except:
            raise AssistantErr(_["play_14"])
        
        if not file_path:
            raise AssistantErr(_["play_14"])

        if await is_active_chat(chat_id):
            await put_queue(
                chat_id,
                original_chat_id,
                file_path if direct else f"vid_{vidid}",
                title,
                duration_min,
                user_name,
                vidid,
                user_id,
                "video" if is_video else "audio",
            )
            position = len(db.get(chat_id)) - 1
            await safe_delete(mystic)
            return await app.send_message(
                original_chat_id,
                text=_["queue_4"].format(position, title[:27], duration_min, user_name),
                reply_markup=InlineKeyboardMarkup(aq_markup(_, chat_id)),
            )
        else:
            if not forceplay:
                db[chat_id] = []
            
            await StreamController.join_call(
                chat_id,
                original_chat_id,
                file_path,
                video=is_video,
                image=thumbnail,
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
                "video" if is_video else "audio",
                forceplay=forceplay,
            )
            
            img = await get_thumb(vidid)
            await safe_delete(mystic)
            run = await app.send_photo(
                original_chat_id,
                photo=img,
                caption=_["stream_1"].format(
                    f"https://t.me/{app.username}?start=info_{vidid}",
                    title[:23],
                    duration_min,
                    user_name,
                ),
                reply_markup=InlineKeyboardMarkup(stream_markup(_, chat_id)),
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "stream"

    # ---------------------------
    # 3. نظام ساوند كلاود (SoundCloud)
    # ---------------------------
    elif streamtype == "soundcloud":
        file_path = result.get("filepath")
        title = result.get("title")
        duration_min = result.get("duration_min")
        
        if await is_active_chat(chat_id):
            await put_queue(chat_id, original_chat_id, file_path, title, duration_min, user_name, streamtype, user_id, "audio")
            position = len(db.get(chat_id)) - 1
            await safe_delete(mystic)
            return await app.send_message(original_chat_id, text=_["queue_4"].format(position, title[:27], duration_min, user_name), reply_markup=InlineKeyboardMarkup(aq_markup(_, chat_id)))
        else:
            if not forceplay:
                db[chat_id] = []
            await StreamController.join_call(chat_id, original_chat_id, file_path, video=False)
            await put_queue(chat_id, original_chat_id, file_path, title, duration_min, user_name, streamtype, user_id, "audio", forceplay=forceplay)
            await safe_delete(mystic)
            run = await app.send_photo(original_chat_id, photo=config.SOUNCLOUD_IMG_URL, caption=_["stream_1"].format(config.SUPPORT_CHAT, title[:23], duration_min, user_name), reply_markup=InlineKeyboardMarkup(stream_markup(_, chat_id)))
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"

    # ---------------------------
    # 4. ملفات التيليجرام (Telegram Files)
    # ---------------------------
    elif streamtype == "telegram":
        file_path = result.get("path")
        link = result.get("link")
        title = (result.get("title")).title()
        duration_min = result.get("dur", result.get("duration_min", "00:00"))
        
        if await is_active_chat(chat_id):
            await put_queue(chat_id, original_chat_id, file_path, title, duration_min, user_name, streamtype, user_id, "video" if is_video else "audio")
            position = len(db.get(chat_id)) - 1
            await safe_delete(mystic)
            return await app.send_message(original_chat_id, text=_["queue_4"].format(position, title[:27], duration_min, user_name), reply_markup=InlineKeyboardMarkup(aq_markup(_, chat_id)))
        else:
            if not forceplay:
                db[chat_id] = []
            await StreamController.join_call(chat_id, original_chat_id, file_path, video=is_video)
            await put_queue(chat_id, original_chat_id, file_path, title, duration_min, user_name, streamtype, user_id, "video" if is_video else "audio", forceplay=forceplay)
            if is_video:
                await add_active_video_chat(chat_id)
            await safe_delete(mystic)
            run = await app.send_photo(original_chat_id, photo=config.TELEGRAM_VIDEO_URL if is_video else config.TELEGRAM_AUDIO_URL, caption=_["stream_1"].format(link, title[:23], duration_min, user_name), reply_markup=InlineKeyboardMarkup(stream_markup(_, chat_id)))
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"

    # ---------------------------
    # 5. البث المباشر والإندكس (Live/Index)
    # ---------------------------
    elif streamtype in ["live", "index"]:
        if streamtype == "live":
            link, vidid = result.get("link"), result.get("vidid")
            title, duration_min, thumb = (result.get("title")).title(), "Live Track", result.get("thumb")
            n, file_path = await YouTube.video(link)
            if n == 0: raise AssistantErr(_["str_3"])
        else:
            link = result
            title, duration_min, vidid, thumb, file_path = "ɪɴᴅᴇx ᴏʀ ᴍ3ᴜ8", "00:00", None, None, link

        if await is_active_chat(chat_id):
            await put_queue(chat_id, original_chat_id, f"live_{vidid}" if vidid else "index_url", title, duration_min, user_name, vidid if vidid else link, user_id, "video" if is_video else "audio")
            position = len(db.get(chat_id)) - 1
            await safe_delete(mystic)
            return await app.send_message(original_chat_id, text=_["queue_4"].format(position, title[:27], duration_min, user_name), reply_markup=InlineKeyboardMarkup(aq_markup(_, chat_id)))
        else:
            if not forceplay:
                db[chat_id] = []
            await StreamController.join_call(chat_id, original_chat_id, file_path, video=is_video, image=thumb)
            await put_queue(chat_id, original_chat_id, f"live_{vidid}" if vidid else "index_url", title, duration_min, user_name, vidid if vidid else link, user_id, "video" if is_video else "audio", forceplay=forceplay)
            await safe_delete(mystic)
            img = await get_thumb(vidid) if vidid else config.STREAM_IMG_URL
            run = await app.send_photo(original_chat_id, photo=img, caption=_["stream_1"].format(link, title[:23], duration_min, user_name), reply_markup=InlineKeyboardMarkup(stream_markup(_, chat_id)))
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"
