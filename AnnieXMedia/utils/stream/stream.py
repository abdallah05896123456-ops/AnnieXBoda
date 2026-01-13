# Authored By Certified Coders © 2025
# 🛡️ FULL STREAM CONTROLLER: 6 MODES + SAFETY
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

# === Helper for Safe Deletion ===
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

    forceplay = bool(forceplay)
    is_video = True if video else False

    if forceplay:
        await StreamController.force_stop_stream(chat_id)

    # ==========================
    # 1. PLAYLIST MODE
    # ==========================
    if streamtype == "playlist":
        msg = f"{_['play_19']}\n\n"
        count = 0
        for search in result:
            if int(count) == config.PLAYLIST_FETCH_LIMIT:
                continue
            try:
                title, duration_min, duration_sec, thumbnail, vidid = await YouTube.details(
                    search, videoid=search
                )
            except:
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
                    "video" if is_video else "audio",
                )
                count += 1
                msg += f"{count}. {title[:70]}\n"
                msg += f"{_['play_20']} {len(db.get(chat_id)) - 1}\n\n"
            else:
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
                except:
                    pass

        if count == 0:
            return
        link = await ANNIEBIN(msg)
        try:
            carbon = await Carbon.generate(msg.split("\n")[:10], randint(100, 1000000))
        except:
            carbon = config.PLAYLIST_IMG_URL
        return await app.send_photo(
            original_chat_id,
            photo=carbon,
            caption=_["play_21"].format(len(db.get(chat_id) or []) - 1, link),
            reply_markup=close_markup(_),
        )

    # ==========================
    # 2. YOUTUBE MODE
    # ==========================
    elif streamtype == "youtube":
        link = result.get("link")
        vidid = result.get("vidid")
        title = (result.get("title", "Unknown")).title()
        duration_min = result.get("duration_min", "00:00")
        thumbnail = result.get("thumb")

        try:
            file_path, direct = await YouTube.download(
                vidid, mystic, video=is_video, videoid=vidid
            )
        except Exception:
            await safe_delete(mystic)
            # return await app.send_message(original_chat_id, _["play_14"])
            raise AssistantErr(_["play_14"])
        
        if not file_path:
            await safe_delete(mystic)
            # return await app.send_message(original_chat_id, _["play_14"])
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
            await safe_delete(mystic)
            await app.send_message(
                original_chat_id,
                _["queue_4"].format(len(db.get(chat_id)) - 1, title[:27], duration_min, user_name),
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

    # ==========================
    # 3. SOUNDCLOUD MODE
    # ==========================
    elif streamtype == "soundcloud":
        file_path = result.get("filepath")
        title = result.get("title")
        duration_min = result.get("duration_min")
        
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
            await safe_delete(mystic)
            await app.send_message(
                original_chat_id,
                _["queue_4"].format(len(db.get(chat_id)) - 1, title[:27], duration_min, user_name),
                reply_markup=InlineKeyboardMarkup(aq_markup(_, chat_id)),
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
            await safe_delete(mystic)
            run = await app.send_photo(
                original_chat_id,
                photo=config.SOUNCLOUD_IMG_URL,
                caption=_["stream_1"].format(
                    config.SUPPORT_CHAT, title[:23], duration_min, user_name
                ),
                reply_markup=InlineKeyboardMarkup(stream_markup(_, chat_id)),
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"

    # ==========================
    # 4. TELEGRAM FILES MODE
    # ==========================
    elif streamtype == "telegram":
        file_path = result.get("path")
        link = result.get("link")
        title = (result.get("title")).title()
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
                "video" if is_video else "audio",
            )
            await safe_delete(mystic)
            await app.send_message(
                original_chat_id,
                _["queue_4"].format(len(db.get(chat_id)) - 1, title[:27], duration_min, user_name),
                reply_markup=InlineKeyboardMarkup(aq_markup(_, chat_id)),
            )
        else:
            if not forceplay:
                db[chat_id] = []
            await StreamController.join_call(chat_id, original_chat_id, file_path, video=is_video)
            await put_queue(
                chat_id,
                original_chat_id,
                file_path,
                title,
                duration_min,
                user_name,
                streamtype,
                user_id,
                "video" if is_video else "audio",
                forceplay=forceplay,
            )
            if is_video:
                await add_active_video_chat(chat_id)
            await safe_delete(mystic)
            run = await app.send_photo(
                original_chat_id,
                photo=config.TELEGRAM_VIDEO_URL if is_video else config.TELEGRAM_AUDIO_URL,
                caption=_["stream_1"].format(link, title[:23], duration_min, user_name),
                reply_markup=InlineKeyboardMarkup(stream_markup(_, chat_id)),
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"

    # ==========================
    # 5. LIVE MODE
    # ==========================
    elif streamtype == "live":
        link = result.get("link")
        vidid = result.get("vidid")
        title = (result.get("title")).title()
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
                "video" if is_video else "audio",
            )
            await safe_delete(mystic)
            await app.send_message(
                original_chat_id,
                _["queue_4"].format(len(db.get(chat_id)) - 1, title[:27], duration_min, user_name),
                reply_markup=InlineKeyboardMarkup(aq_markup(_, chat_id)),
            )
        else:
            if not forceplay:
                db[chat_id] = []
            
            n, file_path = await YouTube.video(link)
            if n == 0:
                raise AssistantErr(_["str_3"])
            if not file_path:
                raise AssistantErr(_["play_14"])

            await StreamController.join_call(
                chat_id,
                original_chat_id,
                file_path,
                video=is_video,
                image=thumbnail or None,
            )
            await put_queue(
                chat_id,
                original_chat_id,
                f"live_{vidid}",
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
            db[chat_id][0]["markup"] = "tg"

    # ==========================
    # 6. INDEX MODE
    # ==========================
    elif streamtype == "index":
        link = result
        title = "ɪɴᴅᴇx ᴏʀ ᴍ3ᴜ8 ʟɪɴᴋ"
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
                "video" if is_video else "audio",
            )
            await mystic.edit_text(
                text=_["queue_4"].format(len(db.get(chat_id)) - 1, title[:27], duration_min, user_name),
                reply_markup=InlineKeyboardMarkup(aq_markup(_, chat_id)),
            )
        else:
            if not forceplay:
                db[chat_id] = []
            await StreamController.join_call(
                chat_id,
                original_chat_id,
                link,
                video=is_video,
            )
            await put_queue_index(
                chat_id,
                original_chat_id,
                "index_url",
                title,
                duration_min,
                user_name,
                link,
                "video" if is_video else "audio",
                forceplay=forceplay,
            )
            await safe_delete(mystic)
            run = await app.send_photo(
                original_chat_id,
                photo=config.STREAM_IMG_URL,
                caption=_["stream_2"].format(user_name),
                reply_markup=InlineKeyboardMarkup(stream_markup(_, chat_id)),
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"
