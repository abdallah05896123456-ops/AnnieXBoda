# Authored By Certified Coders © 2025
# Stream controller wrapper with Hyperion API fallback and robust media_path checks

import os
from random import randint
from typing import Union
from pathlib import Path

from pyrogram.types import InlineKeyboardMarkup

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

import aiohttp
import asyncio
import logging

log = logging.getLogger("AnnieXStream")

# Use env override if available
HYPERION_API_URL = os.getenv("HYPERION_API_URL", "https://hyperionengine.fly.dev").rstrip("/")


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
    """
    Main entry for streaming. Handles multiple stream types and uses
    Hyperion API as priority (returns HTTP streams) and falls back to local yt-dlp downloads.
    Ensures media_path passed to StreamController.join_call is never None and is a valid string/path/URL.
    """
    if not result:
        return

    forceplay = bool(forceplay)
    is_video = bool(video)

    # Helper: validate and resolve media source (url or local file)
    async def resolve_media_source(maybe_path_or_url, vidid_hint=None) -> Union[str, None]:
        """
        Input:
            maybe_path_or_url: could be:
                - an HTTP(S) URL (string)
                - an absolute or relative local file path
                - a filename (like 'abcd.mp3')
        Output:
            - a URL (http/https) or an absolute local path (string), or None if cannot resolve
        """
        if not maybe_path_or_url:
            return None

        # if it's already an http(s) url, accept it
        if isinstance(maybe_path_or_url, str) and (maybe_path_or_url.startswith("http://") or maybe_path_or_url.startswith("https://")):
            return maybe_path_or_url

        p = Path(str(maybe_path_or_url))

        # if absolute path and exists -> return absolute path
        if p.is_absolute() and p.exists():
            return str(p.resolve())

        # try relative path in common 'downloads' folder (bot working dir)
        candidate = Path.cwd() / p
        if candidate.exists():
            return str(candidate.resolve())

        # try downloads/<name> in working dir
        candidate2 = Path("downloads") / p.name
        if candidate2.exists():
            return str(candidate2.resolve())

        # try server downloads URL (Hyperion)
        server_url = f"{HYPERION_API_URL}/downloads/{p.name}"
        try:
            timeout = aiohttp.ClientTimeout(total=4)
            async with aiohttp.ClientSession(timeout=timeout) as sess:
                async with sess.head(server_url, allow_redirects=True) as head:
                    if head.status in (200, 206):
                        return server_url
        except Exception:
            # ignore network errors here
            pass

        # still not found
        return None

    # quick helper to call YouTube.download and return safe results
    async def yt_download_safe(vidid, mystic_obj, video_flag):
        try:
            file_path, direct = await YouTube.download(vidid, mystic_obj, video=bool(video_flag), videoid=vidid)
            return file_path, direct
        except Exception as e:
            log.exception("yt download error: %s", e)
            return None, None

    if forceplay:
        await StreamController.force_stop_stream(chat_id)

    # -------------- PLAYLIST HANDLING --------------
    if streamtype == "playlist":
        msg = f"{_['play_19']}\n\n"
        count = 0
        position = 0

        for search in result:
            if int(count) == config.PLAYLIST_FETCH_LIMIT:
                continue
            try:
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
                if not forceplay:
                    db[chat_id] = []
                file_path, direct = await yt_download_safe(vidid, mystic, is_video)
                if not file_path:
                    raise AssistantErr(_["play_14"])

                # Resolve media source (prefer HTTP stream if possible)
                media_src = None
                if isinstance(file_path, str) and (file_path.startswith("http://") or file_path.startswith("https://")):
                    media_src = file_path
                else:
                    media_src = await resolve_media_source(file_path, vidid_hint=vidid)

                if not media_src:
                    raise AssistantErr(_["play_14"])

                await StreamController.join_call(
                    chat_id,
                    original_chat_id,
                    media_src,
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

        if count == 0:
            return
        link_text = await ANNIEBIN(msg)
        lines = msg.count("\n")
        car = os.linesep.join(msg.split(os.linesep)[:17]) if lines >= 17 else msg
        try:
            carbon = await Carbon.generate(car, randint(100, 10000000))
            playlist_photo = carbon
        except Exception:
            playlist_photo = config.PLAYLIST_IMG_URL
        upl = close_markup(_)
        final_position = len(db.get(chat_id) or []) - 1
        if final_position < 0:
            final_position = 0
        return await app.send_photo(
            original_chat_id,
            photo=playlist_photo,
            caption=_["play_21"].format(final_position, link_text),
            reply_markup=upl,
        )

    # -------------- YOUTUBE SINGLE --------------
    elif streamtype == "youtube":
        link = result.get("link") if isinstance(result, dict) else None
        vidid = result.get("vidid") if isinstance(result, dict) else None
        title = (result.get("title") if isinstance(result, dict) else "") .title()
        duration_min = result.get("duration_min") if isinstance(result, dict) else ""
        thumbnail = result.get("thumb") if isinstance(result, dict) else None

        # Prefer Hyperion API / server-handled stream if YouTube.download already returns HTTP
        file_path, direct = await yt_download_safe(vidid, mystic, is_video)
        if not file_path:
            raise AssistantErr(_["play_14"])

        # Resolve media source
        media_src = None
        if isinstance(file_path, str) and (file_path.startswith("http://") or file_path.startswith("https://")):
            media_src = file_path
        else:
            media_src = await resolve_media_source(file_path, vidid_hint=vidid)

        if not media_src:
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
            button = aq_markup(_, chat_id)
            await app.send_message(
                chat_id=original_chat_id,
                text=_["queue_4"].format(position, title[:27], duration_min, user_name),
                reply_markup=InlineKeyboardMarkup(button),
            )
        else:
            if not forceplay:
                db[chat_id] = []
            # final safety: ensure media_src is str and not None
            if not media_src:
                raise AssistantErr(_["play_14"])
            await StreamController.join_call(
                chat_id,
                original_chat_id,
                media_src,
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

    # -------------- SOUNDCLOUD --------------
    elif streamtype == "soundcloud":
        file_path = result.get("filepath") if isinstance(result, dict) else result
        title = result.get("title") if isinstance(result, dict) else ""
        duration_min = result.get("duration_min") if isinstance(result, dict) else ""
        if not file_path:
            raise AssistantErr(_["play_14"])

        media_src = await resolve_media_source(file_path)
        if not media_src:
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
                text=_["queue_4"].format(position, title[:27], duration_min, user_name),
                reply_markup=InlineKeyboardMarkup(button),
            )
        else:
            if not forceplay:
                db[chat_id] = []
            await StreamController.join_call(chat_id, original_chat_id, media_src, video=False)
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
            run = await app.send_photo(
                original_chat_id,
                photo=config.SOUNCLOUD_IMG_URL,
                caption=_["stream_1"].format(
                    config.SUPPORT_CHAT, title[:23], duration_min, user_name
                ),
                reply_markup=InlineKeyboardMarkup(button),
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"

    # -------------- TELEGRAM (file already on TG) --------------
    elif streamtype == "telegram":
        file_path = result.get("path") if isinstance(result, dict) else None
        link = result.get("link") if isinstance(result, dict) else None
        title = (result.get("title") if isinstance(result, dict) else "").title()
        duration_min = result.get("dur") if isinstance(result, dict) else ""
        if not file_path:
            raise AssistantErr(_["play_14"])

        media_src = await resolve_media_source(file_path)
        if not media_src:
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
            position = len(db.get(chat_id)) - 1
            button = aq_markup(_, chat_id)
            await app.send_message(
                chat_id=original_chat_id,
                text=_["queue_4"].format(position, title[:27], duration_min, user_name),
                reply_markup=InlineKeyboardMarkup(button),
            )
        else:
            if not forceplay:
                db[chat_id] = []
            await StreamController.join_call(chat_id, original_chat_id, media_src, video=is_video)
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
            button = stream_markup(_, chat_id)
            run = await app.send_photo(
                original_chat_id,
                photo=config.TELEGRAM_VIDEO_URL if is_video else config.TELEGRAM_AUDIO_URL,
                caption=_["stream_1"].format(link, title[:23], duration_min, user_name),
                reply_markup=InlineKeyboardMarkup(button),
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"

    # -------------- LIVE --------------
    elif streamtype == "live":
        link = result.get("link") if isinstance(result, dict) else result
        vidid = result.get("vidid") if isinstance(result, dict) else None
        title = (result.get("title") if isinstance(result, dict) else "").title()
        thumbnail = result.get("thumb") if isinstance(result, dict) else None
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
            position = len(db.get(chat_id)) - 1
            button = aq_markup(_, chat_id)
            await app.send_message(
                chat_id=original_chat_id,
                text=_["queue_4"].format(position, title[:27], duration_min, user_name),
                reply_markup=InlineKeyboardMarkup(button),
            )
        else:
            if not forceplay:
                db[chat_id] = []
            n, file_path = await YouTube.video(link)
            if n == 0:
                raise AssistantErr(_["str_3"])
            if not file_path:
                raise AssistantErr(_["play_14"])

            media_src = None
            if isinstance(file_path, str) and (file_path.startswith("http://") or file_path.startswith("https://")):
                media_src = file_path
            else:
                media_src = await resolve_media_source(file_path, vidid_hint=vidid)

            if not media_src:
                raise AssistantErr(_["play_14"])

            await StreamController.join_call(
                chat_id,
                original_chat_id,
                media_src,
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
            button = stream_markup(_, chat_id)
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
            db[chat_id][0]["markup"] = "tg"

    # -------------- INDEX / M3U8 --------------
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
            position = len(db.get(chat_id)) - 1
            button = aq_markup(_, chat_id)
            await mystic.edit_text(
                text=_["queue_4"].format(position, title[:27], duration_min, user_name),
                reply_markup=InlineKeyboardMarkup(button),
            )
        else:
            if not forceplay:
                db[chat_id] = []
            media_src = await resolve_media_source(link)
            if not media_src:
                raise AssistantErr(_["play_14"])
            await StreamController.join_call(
                chat_id,
                original_chat_id,
                media_src,
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
            button = stream_markup(_, chat_id)
            run = await app.send_photo(
                original_chat_id,
                photo=config.STREAM_IMG_URL,
                caption=_["stream_2"].format(user_name),
                reply_markup=InlineKeyboardMarkup(button),
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"
            await mystic.delete()
