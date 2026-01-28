# Authored By Certified Coders © 2026
# System: Azan Utilities (Live Stream Edition)
# Location: AnnieXMedia/plugins/AzanSystem/az_utils.py
# Purpose: Send sticker + plain caption, use direct live streaming link (no UI buttons),
#          robust error handling for pytgcalls / yt-dlp issues.

import asyncio
import aiohttp
import random
import re
import time
import os
import logging
import pytz
import functools
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pyrogram import enums
from pyrogram.errors import FloodWait, PeerIdInvalid, ChannelInvalid

# --- [ Imports from Source ] ---
from AnnieXMedia import app, YouTube
# Stream controller (Call handler) exported from core.call as StreamController
from AnnieXMedia.core.call import StreamController

# --- [ Configuration & Database ] ---
from .az_conf import (
    settings_db, resources_db, azan_logs_db, local_cache,
    CURRENT_RESOURCES, CURRENT_DUA_STICKER, DEVS,
    MORNING_DUAS, NIGHT_DUAS
)

# --- [ Logging ] ---
logging.basicConfig(
    format='%(asctime)s - [AzanUtils] - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("Azan_Maestro_Live")

# --- [ Constants & Scheduler ] ---
CAIRO_TZ = pytz.timezone('Africa/Cairo')
MAX_CONCURRENT_STREAMS = 10
stream_semaphore = asyncio.Semaphore(MAX_CONCURRENT_STREAMS)
scheduler = AsyncIOScheduler(timezone=CAIRO_TZ)

# ==================================================================
# [1] Helpers & small utilities
# ==================================================================

def retry_operation(max_retries=3, delay=2):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(1, max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exc = e
                    logger.debug(f"Retry {attempt}/{max_retries} for {func.__name__}: {e}")
                    if attempt < max_retries:
                        await asyncio.sleep(delay)
            # raise last exception to caller after retries
            raise last_exc
        return wrapper
    return decorator

def extract_vidid(url: str) -> Optional[str]:
    match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11}).*", url)
    return match.group(1) if match else None

# ==================================================================
# [2] DB / cache / rights management
# ==================================================================

async def get_chat_doc(chat_id: int) -> Dict[str, Any]:
    if chat_id in local_cache:
        return local_cache[chat_id]
    doc = await settings_db.find_one({"chat_id": chat_id})
    if not doc:
        doc = {
            "chat_id": chat_id,
            "azan_active": True,
            "forced_active": False,
            "dua_active": True,
            "forced_dua_active": False,
            "night_dua_active": True,
            "prayers": {k: True for k in CURRENT_RESOURCES.keys()}
        }
        await settings_db.insert_one(doc)
    local_cache[chat_id] = doc
    return doc

async def update_doc(chat_id: int, key: str, value, sub_key: str = None):
    try:
        if sub_key:
            await settings_db.update_one({"chat_id": chat_id}, {"$set": {f"prayers.{sub_key}": value}}, upsert=True)
            if chat_id in local_cache:
                local_cache[chat_id].setdefault("prayers", {})[sub_key] = value
        else:
            await settings_db.update_one({"chat_id": chat_id}, {"$set": {key: value}}, upsert=True)
            if chat_id in local_cache:
                local_cache[chat_id][key] = value
    except Exception as e:
        logger.error(f"DB Error update_doc({chat_id},{key}): {e}")

async def check_rights(user_id: int, chat_id: int) -> bool:
    if user_id in DEVS:
        return True
    try:
        mem = await app.get_chat_member(chat_id, user_id)
        if mem.status in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
            return True
    except Exception:
        pass
    return False

@retry_operation(max_retries=3, delay=1)
async def load_resources():
    stored_res = await resources_db.find_one({"type": "azan_data"})
    if stored_res:
        saved_data = stored_res.get("data", {})
        for key, val in saved_data.items():
            if key in CURRENT_RESOURCES:
                CURRENT_RESOURCES[key].update(val)
    dua_res = await resources_db.find_one({"type": "dua_sticker"})
    if dua_res:
        try:
            from AnnieXMedia.plugins.AzanSystem import az_conf
            az_conf.CURRENT_DUA_STICKER = dua_res.get("sticker_id")
            global CURRENT_DUA_STICKER
            CURRENT_DUA_STICKER = dua_res.get("sticker_id")
        except Exception:
            pass
    logger.info("✅ Azan resources loaded.")

# ==================================================================
# [3] Streaming logic (LIVE-first approach)
# ==================================================================

async def start_azan_stream(chat_id: int, prayer_key: str, force_test: bool = False):
    """
    Play azan in the voice chat:
    - send sticker (if exists)
    - send plain caption message (no controls)
    - try to use direct live streaming link (preferred)
    - fallback to local file if returned
    - robust handling of pytgcalls / FloodWait / PeerIdInvalid
    """
    async with stream_semaphore:
        res = CURRENT_RESOURCES.get(prayer_key)
        if not res:
            logger.error(f"start_azan_stream: missing resource for {prayer_key}")
            return

        try:
            # 1) send sticker (if any)
            if res.get("sticker"):
                try:
                    await app.send_sticker(chat_id, res["sticker"])
                except Exception:
                    # don't fail if sticker cannot be sent
                    logger.debug(f"Could not send sticker to {chat_id}")

            # 2) send caption (plain text)
            caption = f"<b>حان الآن موعد اذان {res.get('name','')}</b>\n<b>بالتوقيت المحلي لمدينة القاهره 🕌</b>"
            try:
                await app.send_message(chat_id, caption)
            except Exception:
                logger.debug("Failed to send azan caption (non-fatal)")

            # 3) obtain play target (LIVE/direct preferred)
            link = res.get("link")
            play_target = None
            # Try to get direct streaming link through YouTube.download API:
            # - preferred: (direct_link, True) => direct live link
            # - else if local file returned (path, False) => play local file
            try:
                # Call YouTube.download but don't force blocking download; the function in project already
                # returns (direct_link, True) when it can provide a stream URL, otherwise local path.
                # We pass a lightweight mystic message to allow progress updates if the function uses it.
                mystic_msg = None
                try:
                    mystic_msg = await app.send_message(chat_id, "⏳ تجهيز البث...", disable_notification=True)
                except:
                    mystic_msg = None

                file_or_link, is_stream = await YouTube.download(link, mystic_msg, video=False, videoid=False)

                # If got direct stream link -> use it (LIVE)
                if file_or_link and is_stream:
                    play_target = file_or_link  # direct URL (fast, live)
                # If returned a local file path (downloaded) -> prefer it only if exists
                elif file_or_link and not is_stream and os.path.exists(file_or_link):
                    play_target = file_or_link
                else:
                    # fallback: use original link if nothing returned
                    play_target = link

                # cleanup mystic message if exist
                try:
                    if mystic_msg:
                        await asyncio.sleep(0.5)
                        await mystic_msg.delete()
                except:
                    pass

            except Exception as e:
                # If YouTube.download fails completely, fallback to original link
                logger.warning(f"YouTube.download failed for {link}: {e}")
                play_target = link
                try:
                    if mystic_msg:
                        await mystic_msg.delete()
                except:
                    pass

            if not play_target:
                logger.error(f"No play target for prayer {prayer_key} in chat {chat_id}")
                return

            # 4) Play using StreamController (project's Call class)
            try:
                # StreamController.join_call(self, chat_id, original_chat_id, link, video=None, image=None)
                # We call with original_chat_id==chat_id for simplicity
                await StreamController.join_call(chat_id, chat_id, play_target, video=False)
                if force_test:
                    try:
                        await app.send_message(chat_id, "✅ تجربة الأذان تمت بنجاح (بث مباشر).")
                    except: pass
            except FloodWait as e:
                logger.info(f"FloodWait in join_call: sleeping {e.value}s")
                await asyncio.sleep(e.value)
                try:
                    await StreamController.join_call(chat_id, chat_id, play_target, video=False)
                except Exception as e2:
                    logger.error(f"Retry join_call failed: {e2}")
                    if force_test:
                        await app.send_message(chat_id, f"خطأ في تشغيل البث بعد الانتظار: {e2}")
            except (PeerIdInvalid, ChannelInvalid):
                # chat invalid - remove from settings
                logger.warning(f"Invalid peer/channel {chat_id} — removing from DB")
                try:
                    await settings_db.delete_one({"chat_id": chat_id})
                except:
                    pass
            except Exception as e:
                # This is where pytgcalls' internal yt-dlp errors may appear.
                logger.error(f"Silent Stream Error {chat_id}: {e}")
                if force_test:
                    try:
                        await app.send_message(chat_id, f"حدث خطأ أثناء تشغيل الأذان: {e}")
                    except:
                        pass

            # 5) log to azan_logs_db (like original)
            if not force_test:
                try:
                    now = datetime.now(CAIRO_TZ)
                    log_key = f"{chat_id}_{now.strftime('%Y-%m-%d_%H:%M')}"
                    if not await azan_logs_db.find_one({"key": log_key}):
                        await azan_logs_db.insert_one({
                            "chat_id": chat_id,
                            "chat_title": "مجموعة",
                            "date": now.strftime("%Y-%m-%d"),
                            "time": now.strftime("%I:%M %p"),
                            "timestamp": time.time(),
                            "key": log_key,
                            "prayer_key": prayer_key
                        })
                except Exception:
                    logger.debug("Failed to insert azan log (non-fatal)")

        except Exception as e:
            logger.error(f"start_azan_stream total failure for {chat_id}: {e}")

# ==================================================================
# [4] Timings API and broadcast helpers
# ==================================================================

async def get_azan_times() -> Optional[Dict[str, str]]:
    # Aladhan: timings by city Cairo using method 5 as before
    try:
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get("http://api.aladhan.com/v1/timingsByCity", params={"city":"Cairo","country":"Egypt","method":"5"}) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data["data"]["timings"]
    except Exception as e:
        logger.warning(f"get_azan_times failed: {e}")
    return None

async def broadcast_azan(prayer_key: str):
    async for entry in settings_db.find({"azan_active": True}):
        c_id = entry.get("chat_id")
        prayers = entry.get("prayers", {})
        if c_id and prayers.get(prayer_key, True):
            # spawn tasks but avoid flooding DB at once
            asyncio.create_task(start_azan_stream(c_id, prayer_key, force_test=False))
            await asyncio.sleep(2)  # small gap between starts

async def send_duas_batch(dua_list, setting_key, title, target_chat_id: Optional[int] = None):
    selected = random.sample(dua_list, min(4, len(dua_list)))
    dua_emojis = ["💕", "🤍", "🤎"]
    text = f"<b>{title}</b>\n\n"
    for d in selected:
        emo = random.choice(dua_emojis)
        text += f"• {d} {emo}\n\n"
    text += "<b>تقبل الله منا ومنكم صالح الاعمال</b>"

    if target_chat_id:
        try:
            if CURRENT_DUA_STICKER:
                await app.send_sticker(target_chat_id, CURRENT_DUA_STICKER)
        except:
            pass
        try:
            await app.send_message(target_chat_id, text)
        except:
            pass
        return

    async for entry in settings_db.find({setting_key: True}):
        try:
            c_id = entry.get("chat_id")
            if c_id:
                if CURRENT_DUA_STICKER:
                    try: await app.send_sticker(c_id, CURRENT_DUA_STICKER)
                    except: pass
                try:
                    await app.send_message(c_id, text)
                except: pass
                await asyncio.sleep(1.2)
        except Exception:
            continue

# ==================================================================
# [5] Scheduler maintenance
# ==================================================================

async def update_scheduler():
    await load_resources()
    times = await get_azan_times()
    if not times:
        logger.warning("update_scheduler: timings not available")
        return
    # remove existing azan jobs
    for job in scheduler.get_jobs():
        if str(job.id).startswith("azan_"):
            job.remove()
    now = datetime.now(CAIRO_TZ)
    for key in CURRENT_RESOURCES.keys():
        if key in times:
            t = times[key].split(" ")[0]
            try:
                h, m = map(int, t.split(":"))
            except:
                continue
            # schedule job with cron (local Cairo TZ)
            scheduler.add_job(broadcast_azan, "cron", hour=h, minute=m, args=[key], id=f"azan_{key}")
    logger.info("Scheduler updated with azan times.")

def init_azan_scheduler():
    try:
        if not scheduler.running:
            # daily sync
            scheduler.add_job(lambda: asyncio.create_task(update_scheduler()), "cron", hour=0, minute=5, id="daily_update")
            # duas
            scheduler.add_job(lambda: asyncio.create_task(send_duas_batch(MORNING_DUAS, "dua_active", "أذكار الصباح")), "cron", hour=7, minute=0, id="morning_duas")
            scheduler.add_job(lambda: asyncio.create_task(send_duas_batch(NIGHT_DUAS, "night_dua_active", "أذكار المساء")), "cron", hour=20, minute=0, id="evening_duas")
            scheduler.start()
            # initial population
            try:
                loop = asyncio.get_event_loop()
                loop.create_task(update_scheduler())
            except Exception:
                pass
    except Exception as e:
        logger.error(f"init_azan_scheduler failed: {e}")
