# Authored By Certified Coders © 2026
# System: Azan Utilities (Silent Stream Edition)
# Location: AnnieXMedia/plugins/AzanSystem/az_utils.py
# Mod: Removed 'stream' function calls to eliminate buttons. Uses Direct Play.
# Patch: if yt-dlp option fails, try download via YouTube.download and pass local file.

import asyncio
import aiohttp
import random
import re
import time
import logging
import pytz
import functools
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pyrogram import enums
from pyrogram.errors import FloodWait, PeerIdInvalid, ChannelInvalid

# --- [ Imports from Source ] ---
from AnnieXMedia import app, YouTube
# استبدال stream بـ StreamController للتشغيل المباشر الصامت
from AnnieXMedia.core.call import StreamController

# --- [ Configuration & Database ] ---
# تأكد إن ملف az_conf.py موجود جنبه في نفس الفولدر
from .az_conf import (
    settings_db, resources_db, azan_logs_db, local_cache, 
    CURRENT_RESOURCES, CURRENT_DUA_STICKER, DEVS, 
    MORNING_DUAS, NIGHT_DUAS
)

# --- [ Advanced Logging Setup ] ---
logging.basicConfig(
    format='%(asctime)s - [AzanUtils] - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("Azan_Maestro_Silent")

# --- [ Constants & Concurrency Control ] ---
CAIRO_TZ = pytz.timezone('Africa/Cairo')
MAX_CONCURRENT_STREAMS = 10
stream_semaphore = asyncio.Semaphore(MAX_CONCURRENT_STREAMS)
scheduler = AsyncIOScheduler(timezone=CAIRO_TZ)

# ==================================================================
# 🧠 [1] Decorators & Helpers
# ==================================================================

def retry_operation(max_retries=3, delay=2):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(1, max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries:
                        logger.error(f"❌ Function {func.__name__} failed: {e}")
                        raise e
                    await asyncio.sleep(delay)
        return wrapper
    return decorator

def run_async_task(async_func, *args, **kwargs):
    try:
        loop = app.loop
        if loop.is_running():
            loop.create_task(async_func(*args, **kwargs))
        else:
            logger.critical("🚨 Main Event Loop is NOT running!")
    except Exception as e:
        logger.error(f"❌ Safety Bridge Error: {e}")

def extract_vidid(url: str) -> Optional[str]:
    match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11}).*", url)
    return match.group(1) if match else None

# ==================================================================
# 🔐 [2] Permission & Data Management
# ==================================================================

async def check_rights(user_id: int, chat_id: int) -> bool:
    if user_id in DEVS: return True
    try:
        member = await app.get_chat_member(chat_id, user_id)
        if member.status in [enums.ChatMemberStatus.OWNER, enums.ChatMemberStatus.ADMINISTRATOR]:
            return True
    except Exception: pass
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
            # محاولة استيراد ديناميكي لتجنب Circular Import
            from AnnieXMedia.plugins.AzanSystem import az_conf
            az_conf.CURRENT_DUA_STICKER = dua_res.get("sticker_id")
            global CURRENT_DUA_STICKER
            CURRENT_DUA_STICKER = dua_res.get("sticker_id")
        except: pass
    
    logger.info("✅ Resources synchronized.")

async def get_chat_doc(chat_id: int) -> Dict[str, Any]:
    if chat_id in local_cache: return local_cache[chat_id]
    
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

async def update_doc(chat_id: int, key: str, value: Any, sub_key: str = None):
    try:
        if sub_key:
            await settings_db.update_one({"chat_id": chat_id}, {"$set": {f"prayers.{sub_key}": value}}, upsert=True)
            if chat_id in local_cache: local_cache[chat_id].setdefault("prayers", {})[sub_key] = value
        else:
            await settings_db.update_one({"chat_id": chat_id}, {"$set": {key: value}}, upsert=True)
            if chat_id in local_cache: local_cache[chat_id][key] = value
    except Exception as e:
        logger.error(f"DB Error {chat_id}: {e}")

# ==================================================================
# 🕌 [3] Streaming Logic (التعديل الجذري هنا: إزالة الأزرار)
# ==================================================================

async def start_azan_stream(chat_id: int, prayer_key: str, force_test: bool = False):
    async with stream_semaphore:
        res = CURRENT_RESOURCES.get(prayer_key)
        if not res:
            logger.error(f"No resource for prayer key: {prayer_key}")
            return
        
        try:
            # 1. إرسال الاستيكر (بدون أزرار)
            if res.get("sticker"):
                try: await app.send_sticker(chat_id, res["sticker"])
                except: pass

            # 2. إرسال الرسالة النصية (نص فقط - Plain Text)
            caption = (
                f"<b>حان الآن موعد اذان {res.get('name','')}</b>\n"
                f"<b>بالتوقيت المحلي لمدينة القاهره 🕌</b>"
            )
            await app.send_message(chat_id, caption)

            link = res.get("link")
            # لو الرابط يوتيوب حاول نحمّله محلياً ثم نمرّر مسار الملف لتجنّب yt-dlp داخل pytgcalls
            tried_local = False
            local_path = None

            if link and ("youtube.com" in link or "youtu.be" in link):
                vid = extract_vidid(link)
                if vid:
                    mystic = None
                    try:
                        # رسالة مؤقتة للتحميل (YouTube.download قد تحتاج رسالة لتعديل الحالة)
                        try: mystic = await app.send_message(chat_id, "⏳ جاري تجهيز بث الأذان...")
                        except: mystic = None

                        # YouTube.download(videoid, mystic, videoid=True, video=video)
                        # نحمّل كـ audio (video=False)
                        file_path, direct = await YouTube.download(vid, mystic, videoid=True, video=False)
                        if file_path and os.path.exists(file_path):
                            local_path = file_path
                            tried_local = True
                    except Exception as e:
                        logger.warning(f"Local download fallback failed for {chat_id}, vid={vid}: {e}")
                    finally:
                        # حذف رسالة الحالة المؤقتة إن نجح الإرسال
                        try:
                            if mystic:
                                await mystic.delete()
                        except: pass

            # 3. التشغيل: إذا عندنا ملف محلي استخدمه، وإلا جرّب الرابط مباشرة
            play_target = local_path if tried_local and local_path else link

            if not play_target:
                logger.error(f"No playable link/path for prayer {prayer_key} in chat {chat_id}")
                return

            try:
                # StreamController.join_call(self, chat_id, original_chat_id, link, video=None, image=None)
                await StreamController.join_call(chat_id, chat_id, play_target, video=False)
                if force_test: logger.info(f"Test OK (Silent): {chat_id}")
            except FloodWait as e:
                await asyncio.sleep(e.value)
                await StreamController.join_call(chat_id, chat_id, play_target, video=False)
            except (PeerIdInvalid, ChannelInvalid):
                await settings_db.delete_one({"chat_id": chat_id})
            except Exception as e:
                logger.error(f"Silent Stream Error {chat_id}: {e}")
                # لو الخطأ جاي من yt-dlp وخطأ الخيار، حاولنا التنزيل المحلي؛ إذا لم نجح نرسل تحذير
                try:
                    await app.send_message(chat_id, f"حدث خطأ أثناء تشغيل الأذان: {e}")
                except: pass

            # تسجيل الدخول في اللوقز (مثل القديم)
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
                except: pass

        except Exception as e:
            logger.error(f"Access Error {chat_id}: {e}")

# ==================================================================
# 🌐 [4] API Manager
# ==================================================================

async def get_azan_times() -> Optional[Dict[str, str]]:
    url = "http://api.aladhan.com/v1/timingsByCity"
    params = {"city": "Cairo", "country": "Egypt", "method": "5"}
    headers = {"User-Agent": "Mozilla/5.0 (AnnieX)"}
    timeout = aiohttp.ClientTimeout(total=15)
    
    for attempt in range(1, 4):
        try:
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data["data"]["timings"]
        except Exception:
            await asyncio.sleep(2 * attempt)
    return None

async def broadcast_azan(prayer_key):
    async for entry in settings_db.find({"azan_active": True}):
        c_id = entry.get("chat_id")
        prayers = entry.get("prayers", {})
        if c_id and prayers.get(prayer_key, True):
            asyncio.create_task(start_azan_stream(c_id, prayer_key, force_test=False))
            await asyncio.sleep(3)

async def send_duas_batch(dua_list, setting_key, title, target_chat_id=None):
    selected = random.sample(dua_list, min(4, len(dua_list)))
    dua_emojis = ["💕", "🤍", "🤎"]
    text = f"<b>{title}</b>\n\n"
    for d in selected: 
        emo = random.choice(dua_emojis)
        text += f"• {d} {emo}\n\n"
    text += "<b>تقبل الله منا ومنكم صالح الاعمال</b>"
    
    if target_chat_id:
        if CURRENT_DUA_STICKER: await app.send_sticker(target_chat_id, CURRENT_DUA_STICKER)
        await app.send_message(target_chat_id, text)
        return

    async for entry in settings_db.find({setting_key: True}):
        try:
            c_id = entry.get("chat_id")
            if c_id:
                if CURRENT_DUA_STICKER: await app.send_sticker(c_id, CURRENT_DUA_STICKER)
                await app.send_message(c_id, text)
                await asyncio.sleep(2)
        except: continue

async def update_scheduler():
    await load_resources()
    times = await get_azan_times()
    if not times: return
    for job in scheduler.get_jobs():
        if job.id.startswith("azan_"): job.remove()
    for key in CURRENT_RESOURCES.keys():
        if key in times:
            t = times[key].split(" ")[0]
            h, m = map(int, t.split(":"))
            scheduler.add_job(broadcast_azan, "cron", hour=h, minute=m, args=[key], id=f"azan_{key}")

# --- [ إعداد المجدول (تم التعديل لمنع التشغيل التلقائي) ] ---

def init_azan_scheduler():
    try:
        if not scheduler.running:
            scheduler.add_job(update_scheduler, "cron", hour=0, minute=5)
            scheduler.add_job(lambda: asyncio.create_task(send_duas_batch(MORNING_DUAS, "dua_active", "أذكار الصباح")), "cron", hour=7, minute=0)
            scheduler.add_job(lambda: asyncio.create_task(send_duas_batch(NIGHT_DUAS, "night_dua_active", "أذكار المساء")), "cron", hour=20, minute=0)
            scheduler.start()
            asyncio.get_event_loop().create_task(update_scheduler())
    except Exception as e:
        print(f"Azan Scheduler Error: {e}")
