# Authored By Certified Coders © 2026
# System: Stream Controller (Full Armored Edition)
# Fix: Complete File + Smart Button Hiding for Azan

import asyncio
import os
from typing import Union
from random import randint

from pyrogram.types import InlineKeyboardMarkup
from pyrogram.errors import FloodWait

import config
from AnnieXMedia import Carbon, YouTube, app
from AnnieXMedia.core.call import StreamController
from AnnieXMedia.misc import db
from AnnieXMedia.utils.database import (
    add_active_video_chat,
    is_active_chat,
)
from AnnieXMedia.utils.exceptions import AssistantErr
from AnnieXMedia.utils.inline import aq_markup, close_markup, stream_markup
from AnnieXMedia.utils.pastebin import ANNIEBIN
from AnnieXMedia.utils.stream.queue import put_queue, put_queue_index
from AnnieXMedia.utils.thumbnails import get_thumb
from AnnieXMedia.utils.errors import capture_internal_err

async def safe_delete(message):
    """حذف الرسائل بأمان"""
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

    # ============================================================
    # 🛡️ نظام الحماية من الأزرار (The Anti-Button Shield)
    # ============================================================
    should_hide_buttons = False
    
    # [1] فحص الإشارة القادمة من السيستم (System Flag)
    # هذا يأتي من ملف az_utils.py عند تشغيل الأذان
    if isinstance(result, dict) and result.get("no_buttons") is True:
        should_hide_buttons = True

    # [2] فحص العناوين والنصوص (Keyword Filter) - حماية إضافية
    # لو العنوان فيه كلمة تدل على الصلاة، اخفي الأزرار فوراً
    if isinstance(result, dict):
        title_check = str(result.get("title", "")).lower()
        desc_check = str(result.get("description", "")).lower()
        
        # قائمة الكلمات المحظورة
        forbidden_keywords = [
            "أذان", "اذان", "azan", "prayer", "صلاة", 
            "فجر", "ظهر", "عصر", "مغرب", "عشاء", 
            "توقيت", "القاهرة", "cairo"
        ]
        
        if any(k in title_check for k in forbidden_keywords) or \
           any(k in desc_check for k in forbidden_keywords):
            should_hide_buttons = True

    # [3] دالة المعالجة الذكية (The Resolver)
    # دي اللي بتتحكم: هل نبعت كيبورد ولا لأ؟
    def resolve_markup(markup_func, *args):
        # لو الحماية مفعلة (أذان)، رجع None فوراً
        if should_hide_buttons:
            return None
        
        # لو مفيش حماية (أغنية عادية)، حاول تعمل الكيبورد
        try:
            return InlineKeyboardMarkup(markup_func(*args))
        except:
            return None

    # ============================================================

    # تنظيف القناة لو التشغيل إجباري (زي الأذان)
    if forceplay:
        await StreamController.force_stop_stream(chat_id)

    # 1. PLAYLIST MODE
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
            except Exception:
                continue

            if str(duration_min) == "None": continue
            if duration_sec and duration_sec > config.DURATION_LIMIT: continue

            if await is_active_chat(chat_id):
                await put_queue(
                    chat_id, original_chat_id, f"vid_{vidid}", title, duration_min,
                    user_name, vidid, user_id, "video" if is_video else "audio",
                )
                position = len(db.get(chat_id)) - 1
                count += 1
                msg += f"{count}. {title[:70]}\n"
                msg += f"{_['play_20']} {position}\n\n"
            else:
                if not forceplay: db[chat_id] = []
                try:
                    file_path, direct = await YouTube.download(
                        vidid, mystic, video=is_video, videoid=vidid
                    )
                except Exception: raise AssistantErr(_["play_14"])

                await StreamController.join_call(
                    chat_id, original_chat_id, file_path, video=is_video, image=thumbnail,
                )
                await put_queue(
                    chat_id, original_chat_id, file_path if direct else f"vid_{vidid}",
                    title, duration_min, user_name, vidid, user_id,
                    "video" if is_video else "audio", forceplay=forceplay,
                )
                img = await get_thumb(vidid)
                await safe_delete(mystic)
                caption_text = "🧚 " + _["stream_1"].format(
                    f"https://t.me/{app.username}?start=info_{vidid}",
                    title[:23], duration_min, user_name,
                )
                try:
                    run = await app.send_photo(
                        original_chat_id, photo=img, caption=caption_text,
                        reply_markup=resolve_markup(stream_markup, _, chat_id),
                    )
                    db[chat_id][0]["mystic"] = run
                    db[chat_id][0]["markup"] = "stream"
                except Exception: pass

        if count == 0: return
        link = await ANNIEBIN(msg)
        try:
            carbon = await Carbon.generate(msg, randint(100, 10000000))
            playlist_photo = carbon
        except: playlist_photo = config.PLAYLIST_IMG_URL
        upl = resolve_markup(close_markup, _)
        final_position = len(db.get(chat_id) or []) - 1
        return await app.send_photo(
            original_chat_id, photo=playlist_photo,
            caption="🧚 " + _["play_21"].format(final_position, link),
            reply_markup=upl,
        )

    # 2. YOUTUBE MODE (AZAN MAIN TARGET)
    elif streamtype == "youtube":
        link = result.get("link")
        vidid = result.get("vidid")
        title = (result.get("title")).title()
        duration_min = result.get("duration_min")
        thumbnail = result.get("thumb")

        try:
            file_path, direct = await YouTube.download(
                vidid, mystic, video=is_video, videoid=vidid
            )
        except Exception: raise AssistantErr(_["play_14"])

        if not file_path: raise AssistantErr(_["play_14"])

        if await is_active_chat(chat_id):
            await put_queue(
                chat_id, original_chat_id, file_path if direct else f"vid_{vidid}",
                title, duration_min, user_name, vidid, user_id,
                "video" if is_video else "audio",
            )
            position = len(db.get(chat_id)) - 1
            await safe_delete(mystic)
            
            # 🔥 تطبيق الحماية هنا (رسالة الانتظار)
            await app.send_message(
                chat_id=original_chat_id,
                text="🧚 " + _["queue_4"].format(position, title[:27], duration_min, user_name),
                reply_markup=resolve_markup(aq_markup, _, chat_id),
            )
        else:
            if not forceplay: db[chat_id] = []
            await StreamController.join_call(
                chat_id, original_chat_id, file_path, video=is_video, image=thumbnail,
            )
            await put_queue(
                chat_id, original_chat_id, file_path if direct else f"vid_{vidid}",
                title, duration_min, user_name, vidid, user_id,
                "video" if is_video else "audio", forceplay=forceplay,
            )
            img = await get_thumb(vidid)
            await safe_delete(mystic)
            caption_text = "🧚 " + _["stream_1"].format(
                f"https://t.me/{app.username}?start=info_{vidid}",
                title[:23], duration_min, user_name,
            )
            try:
                # 🔥 تطبيق الحماية هنا (رسالة التشغيل الأساسية)
                run = await app.send_photo(
                    original_chat_id, photo=img, caption=caption_text,
                    reply_markup=resolve_markup(stream_markup, _, chat_id),
                )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "stream"
            except Exception:
                try:
                    # Fallback Text Message
                    run = await app.send_message(
                        original_chat_id, text=caption_text,
                        reply_markup=resolve_markup(stream_markup, _, chat_id)
                    )
                    db[chat_id][0]["mystic"] = run
                    db[chat_id][0]["markup"] = "stream"
                except: pass

    # 3. SOUNDCLOUD MODE
    elif streamtype == "soundcloud":
        file_path = result.get("filepath")
        title = result.get("title")
        duration_min = result.get("duration_min")
        
        if await is_active_chat(chat_id):
            await put_queue(
                chat_id, original_chat_id, file_path, title, duration_min,
                user_name, streamtype, user_id, "audio",
            )
            position = len(db.get(chat_id)) - 1
            await app.send_message(
                chat_id=original_chat_id,
                text="🧚 " + _["queue_4"].format(position, title[:27], duration_min, user_name),
                reply_markup=resolve_markup(aq_markup, _, chat_id),
            )
        else:
            if not forceplay: db[chat_id] = []
            await StreamController.join_call(chat_id, original_chat_id, file_path, video=False)
            await put_queue(
                chat_id, original_chat_id, file_path, title, duration_min,
                user_name, streamtype, user_id, "audio", forceplay=forceplay,
            )
            await safe_delete(mystic)
            run = await app.send_photo(
                original_chat_id, photo=config.SOUNCLOUD_IMG_URL,
                caption="🧚 " + _["stream_1"].format(
                    config.SUPPORT_CHAT, title[:23], duration_min, user_name
                ),
                reply_markup=resolve_markup(stream_markup, _, chat_id),
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"

    # 4. TELEGRAM FILES
    elif streamtype == "telegram":
        file_path = result.get("path")
        link = result.get("link")
        title = (result.get("title")).title()
        duration_min = result.get("dur", result.get("duration_min", "00:00"))

        if await is_active_chat(chat_id):
            await put_queue(
                chat_id, original_chat_id, file_path, title, duration_min,
                user_name, streamtype, user_id, "video" if is_video else "audio",
            )
            position = len(db.get(chat_id)) - 1
            await app.send_message(
                chat_id=original_chat_id,
                text="🧚 " + _["queue_4"].format(position, title[:27], duration_min, user_name),
                reply_markup=resolve_markup(aq_markup, _, chat_id),
            )
        else:
            if not forceplay: db[chat_id] = []
            await StreamController.join_call(chat_id, original_chat_id, file_path, video=is_video)
            await put_queue(
                chat_id, original_chat_id, file_path, title, duration_min,
                user_name, streamtype, user_id, "video" if is_video else "audio", forceplay=forceplay,
            )
            if is_video: await add_active_video_chat(chat_id)
            
            await safe_delete(mystic)
            run = await app.send_photo(
                original_chat_id,
                photo=config.TELEGRAM_VIDEO_URL if is_video else config.TELEGRAM_AUDIO_URL,
                caption="🧚 " + _["stream_1"].format(link, title[:23], duration_min, user_name),
                reply_markup=resolve_markup(stream_markup, _, chat_id),
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"

    # 5. LIVE / INDEX MODE
    elif streamtype == "live":
        link = result.get("link")
        vidid = result.get("vidid")
        title = (result.get("title")).title()
        thumbnail = result.get("thumb")
        duration_min = "Live Track"

        if await is_active_chat(chat_id):
            await put_queue(
                chat_id, original_chat_id, f"live_{vidid}", title, duration_min,
                user_name, vidid, user_id, "video" if is_video else "audio",
            )
            position = len(db.get(chat_id)) - 1
            await app.send_message(
                chat_id=original_chat_id,
                text="🧚 " + _["queue_4"].format(position, title[:27], duration_min, user_name),
                reply_markup=resolve_markup(aq_markup, _, chat_id),
            )
        else:
            if not forceplay: db[chat_id] = []
            
            n, file_path = await YouTube.video(link)
            if n == 0: raise AssistantErr(_["str_3"])

            await StreamController.join_call(
                chat_id, original_chat_id, file_path, video=is_video, image=thumbnail or None,
            )
            await put_queue(
                chat_id, original_chat_id, f"live_{vidid}", title, duration_min,
                user_name, vidid, user_id, "video" if is_video else "audio", forceplay=forceplay,
            )
            img = await get_thumb(vidid)
            await safe_delete(mystic)
            
            run = await app.send_photo(
                original_chat_id, photo=img,
                caption="🧚 " + _["stream_1"].format(
                    f"https://t.me/{app.username}?start=info_{vidid}",
                    title[:23], duration_min, user_name,
                ),
                reply_markup=resolve_markup(stream_markup, _, chat_id),
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"

    elif streamtype == "index":
        link = result
        title = "رابط خارجي"
        duration_min = "00:00"

        if await is_active_chat(chat_id):
            await put_queue_index(
                chat_id, original_chat_id, "index_url", title, duration_min,
                user_name, link, "video" if is_video else "audio",
            )
            position = len(db.get(chat_id)) - 1
            await mystic.edit_text(
                text="🧚 " + _["queue_4"].format(position, title[:27], duration_min, user_name),
                reply_markup=resolve_markup(aq_markup, _, chat_id),
            )
        else:
            if not forceplay: db[chat_id] = []
            await StreamController.join_call(
                chat_id, original_chat_id, link, video=is_video,
            )
            await put_queue_index(
                chat_id, original_chat_id, "index_url", title, duration_min,
                user_name, link, "video" if is_video else "audio", forceplay=forceplay,
            )
            await safe_delete(mystic)
            
            run = await app.send_photo(
                original_chat_id, photo=config.STREAM_IMG_URL,
                caption="🧚 " + _["stream_2"].format(user_name),
                reply_markup=resolve_markup(stream_markup, _, chat_id),
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"
