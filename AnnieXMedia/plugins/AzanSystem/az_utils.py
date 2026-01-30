# Authored By Certified Coders © 2026
# System: Azan Maestro (Enterprise V9.0 - Strict Edition)
# Location: AnnieXMedia/plugins/AzanSystem/az_utils.py
# Purpose:
#   - Global Broadcast to ALL MongoDB Chats (chatsdb).
#   - Single Link Extraction (Efficiency Optimization).
#   - Silent Execution (No processing messages).
#   - Direct Stream Controller Access (No UI Buttons).
#   - Robust Error Handling and Detailed Logging.

import asyncio
import aiohttp
import random
import re
import time
import os
import logging
import pytz
import functools
import traceback
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

# --- [ Scheduling & Telegram Client ] ---
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pyrogram import enums, filters
from pyrogram.types import Message
from pyrogram.errors import (
    FloodWait,
    PeerIdInvalid,
    ChannelInvalid,
    UserNotParticipant,
    ChatAdminRequired,
    RPCError
)

# --- [ Internal Imports ] ---
from AnnieXMedia import app, YouTube
from AnnieXMedia.core.call import StreamController
# [تطوير] استيراد قائمة المساعدين لحل مشكلة الانضمام
from AnnieXMedia.core.userbot import assistants

# --- [ Database Imports ] ---
# استيراد قاعدة البيانات الشاملة لضمان الوصول لكل الجروبات
from AnnieXMedia.utils.database import chatsdb, remove_served_chat

# --- [ Configuration & Local DB ] ---
from .az_conf import (
    settings_db,
    resources_db,
    azan_logs_db,
    local_cache,
    CURRENT_RESOURCES,
    CURRENT_DUA_STICKER,
    DEVS,
    MORNING_DUAS,
    NIGHT_DUAS
)

# --- [ Logging Setup ] ---
logging.basicConfig(
    format='%(asctime)s - [AzanUtils] - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("Azan_Maestro_Live")

# --- [ Constants & Global Variables ] ---
CAIRO_TZ = pytz.timezone('Africa/Cairo')
# [تطوير] تقليل العدد قليلاً لضمان استقرار FFmpeg حتى مع السيرفر القوي
MAX_CONCURRENT_STREAMS = 20  
stream_semaphore = asyncio.Semaphore(MAX_CONCURRENT_STREAMS)
scheduler = AsyncIOScheduler(timezone=CAIRO_TZ)


# ==================================================================
# [SECTION 1] Helpers & Decorators
# ==================================================================

def retry_operation(max_retries=3, delay=2):
    """
    Decorator: يعيد محاولة تنفيذ الدالة في حالة الفشل.
    مفيد لتجاوز أخطاء الشبكة المؤقتة.
    """
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
            # إذا فشلت كل المحاولات، نرفع الخطأ الأخير
            logger.error(f"Function {func.__name__} failed after {max_retries} retries.")
            raise last_exc
        return wrapper
    return decorator

def get_readable_time() -> str:
    """إرجاع الوقت الحالي بتنسيق مقروء للوجات."""
    return datetime.now(CAIRO_TZ).strftime("%Y-%m-%d %I:%M:%S %p")

def extract_vidid(url: str) -> Optional[str]:
    """استخراج معرّف الفيديو من رابط يوتيوب."""
    match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11}).*", url)
    return match.group(1) if match else None


# ==================================================================
# [SECTION 2] Database Management
# ==================================================================

async def get_chat_doc(chat_id: int) -> Dict[str, Any]:
    """
    جلب إعدادات الجروب من قاعدة البيانات.
    إذا لم تكن موجودة، يتم إنشاء وثيقة افتراضية مفعلة.
    """
    # 1. البحث في الكاش المحلي أولاً للسرعة
    if chat_id in local_cache:
        return local_cache[chat_id]

    # 2. البحث في المونجو
    try:
        doc = await settings_db.find_one({"chat_id": chat_id})
        
        # 3. الإنشاء التلقائي إذا لم يوجد
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
            logger.info(f"🆕 Created new Azan config for chat: {chat_id}")
        
        # 4. التحديث في الكاش
        local_cache[chat_id] = doc
        return doc

    except Exception as e:
        logger.error(f"DB Error in get_chat_doc({chat_id}): {e}")
        return {}

async def update_doc(chat_id: int, key: str, value, sub_key: str = None):
    """تحديث قيمة معينة في إعدادات الجروب."""
    try:
        if sub_key:
            await settings_db.update_one(
                {"chat_id": chat_id}, 
                {"$set": {f"prayers.{sub_key}": value}}, 
                upsert=True
            )
            if chat_id in local_cache:
                local_cache[chat_id].setdefault("prayers", {})[sub_key] = value
        else:
            await settings_db.update_one(
                {"chat_id": chat_id}, 
                {"$set": {key: value}}, 
                upsert=True
            )
            if chat_id in local_cache:
                local_cache[chat_id][key] = value
    except Exception as e:
        logger.error(f"DB Error update_doc({chat_id}): {e}")

async def check_rights(user_id: int, chat_id: int) -> bool:
    """التحقق من صلاحيات المستخدم (مطور أو مشرف)."""
    if user_id in DEVS:
        return True
    try:
        mem = await app.get_chat_member(chat_id, user_id)
        if mem.status in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
            return True
    except Exception:
        pass
    return False

@retry_operation(max_retries=3, delay=2)
async def load_resources():
    """تحميل روابط الصلوات والاستيكرات من قاعدة البيانات."""
    try:
        # تحميل بيانات الروابط
        stored_res = await resources_db.find_one({"type": "azan_data"})
        if stored_res:
            saved_data = stored_res.get("data", {})
            for key, val in saved_data.items():
                if key in CURRENT_RESOURCES:
                    CURRENT_RESOURCES[key].update(val)
        
        # تحميل استيكر الأذكار
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
    except Exception as e:
        logger.error(f"Critical Error loading resources: {e}")


# ==================================================================
# [SECTION 3] Stream Logic (The Core Engine)
# ==================================================================

# [تطوير] جعل play_target اختيارياً لمنع الأخطاء عند الاستدعاء اليدوي
async def start_azan_stream(chat_id: int, prayer_key: str, play_target: str = None, force_test: bool = False):
    """
    تشغيل الأذان في مجموعة واحدة باستخدام الرابط المجهز مسبقاً.
    - يتخطى واجهة الأزرار.
    - لا يرسل رسائل تجهيز.
    - يتعامل مع الأخطاء بذكاء.
    """
    async with stream_semaphore:
        # التحقق من البيانات
        res = CURRENT_RESOURCES.get(prayer_key)
        if not res:
            logger.error(f"start_azan_stream: missing resource for {prayer_key}")
            return

        # [تطوير] استخدام الرابط المخزن إذا لم يتم تمرير هدف (لحل مشكلة التست)
        if not play_target:
            play_target = res.get("link")

        try:
            # --- [ الخطوة 1: إرسال الوسائط ] ---
            
            # أ) إرسال الاستيكر (إن وجد)
            if res.get("sticker"):
                try:
                    await app.send_sticker(chat_id, res["sticker"])
                except Exception:
                    logger.debug(f"Could not send sticker to {chat_id}")

            # ب) إرسال النص (بالنص القديم حرفياً)
            caption = f"<b>حان الآن موعد اذان {res.get('name','')}</b>\n<b>بالتوقيت المحلي لمدينة القاهره 🕌</b>"
            try:
                await app.send_message(chat_id, caption)
            except Exception:
                logger.debug("Failed to send azan caption")

            # --- [ الخطوة 1.5 (تطوير): التحقق من وجود المساعد ] ---
            # هذا الكود يمنع خطأ JOIN ERROR ومحاولة الانضمام التلقائي
            try:
                assistant = assistants[0]
                try:
                    await assistant.get_chat_member(chat_id, "me")
                except UserNotParticipant:
                    if force_test: logger.info(f"Assistant joining {chat_id}...")
                    try:
                        invite_link = await app.export_chat_invite_link(chat_id)
                        await assistant.join_chat(invite_link)
                        await asyncio.sleep(1) # انتظار بسيط للتفعيل
                    except Exception as join_err:
                        logger.warning(f"Auto-Join failed for {chat_id}: {join_err}")
            except Exception as e:
                logger.error(f"Assistant check error: {e}")

            # --- [ الخطوة 2: الانضمام والتشغيل ] ---
            try:
                # نستخدم StreamController مباشرة لتخطي أي لوجيك إضافي
                await StreamController.join_call(
                    chat_id, 
                    chat_id, 
                    play_target, 
                    video=False
                )
                
                if force_test:
                    try:
                        await app.send_message(chat_id, "✅ تجربة الأذان تمت بنجاح (بث مباشر).")
                    except: pass
            
            except FloodWait as fw:
                # الانتظار في حالة الضغط
                logger.warning(f"FloodWait in {chat_id}: sleeping {fw.value}s")
                await asyncio.sleep(fw.value + 1)
                await StreamController.join_call(chat_id, chat_id, play_target, video=False)
            
            except (PeerIdInvalid, ChannelInvalid, UserNotParticipant):
                # البوت مطرود أو الجروب محذوف -> تنظيف الداتابيز
                logger.warning(f"Invalid Chat {chat_id} — removing from DB")
                await remove_served_chat(chat_id)
                await settings_db.delete_one({"chat_id": chat_id})
                if chat_id in local_cache:
                    del local_cache[chat_id]
            
            except Exception as e:
                # أخطاء التشغيل الأخرى (مثل مشاكل ffmpeg)
                logger.error(f"Silent Stream Error {chat_id}: {e}")
                if force_test:
                    try:
                        await app.send_message(chat_id, f"حدث خطأ أثناء تشغيل الأذان: {e}")
                    except: pass

            # --- [ الخطوة 3: تسجيل اللوج ] ---
            if not force_test:
                try:
                    now = datetime.now(CAIRO_TZ)
                    log_key = f"{chat_id}_{now.strftime('%Y-%m-%d_%H:%M')}"
                    
                    # منع التكرار
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
                    logger.debug("Failed to insert azan log")

        except Exception as e:
            logger.critical(f"start_azan_stream total failure for {chat_id}: {e}")


# ==================================================================
# [SECTION 4] Global Broadcast (Optimization Logic)
# ==================================================================

async def broadcast_azan(prayer_key: str):
    """
    دالة البث الشامل:
    1. تستخرج الرابط مرة واحدة (توفير موارد).
    2. تلف على كل الجروبات في chatsdb.
    3. تطلق مهام متوازية للبث.
    """
    res = CURRENT_RESOURCES.get(prayer_key)
    if not res:
        logger.error(f"Cannot broadcast {prayer_key}: Resource missing.")
        return
    
    start_time = time.time()
    logger.info(f"📢 STARTING BROADCAST: {prayer_key} at {get_readable_time()}")
    
    # --- [ المرحلة 1: تجهيز الرابط مركزياً ] ---
    try:
        # [تطوير] التعامل مع الروابط المباشرة لتجنب أخطاء YouTube
        if "youtube" in res["link"] or "youtu.be" in res["link"]:
            play_target, is_stream = await YouTube.download(
                res["link"], 
                None, 
                video=False, 
                videoid=False
            )
        else:
            play_target = res["link"] # استخدام الرابط المباشر كما هو
            
        # إذا فشل التحميل، نستخدم الرابط الخام
        if not play_target:
            play_target = res["link"]
            logger.warning("Download failed, using raw link.")
        else:
            logger.info("Direct link extracted successfully.")

    except Exception as e:
        logger.error(f"Global Download Failed: {e}. Fallback to raw link.")
        play_target = res["link"]

    # --- [ المرحلة 2: التوزيع الجماعي ] ---
    active_tasks = 0
    
    # نستخدم chatsdb.find() للوصول لكل الجروبات التي دخلها البوت
    async for chat in chatsdb.find({"chat_id": {"$lt": 0}}):
        c_id = chat.get("chat_id")
        
        # التحقق من إعدادات الجروب (هل الأذان مفعل؟)
        doc = await get_chat_doc(c_id)
        
        is_active = doc.get("azan_active", True)
        is_prayer_active = doc.get("prayers", {}).get(prayer_key, True)

        if is_active and is_prayer_active:
            # إطلاق المهمة في الخلفية (Fire and Forget)
            asyncio.create_task(
                start_azan_stream(c_id, prayer_key, play_target)
            )
            active_tasks += 1
            
            # [تطوير] فاصل زمني 0.2 لمنع الحظر مع العدد الكبير من الطلبات
            await asyncio.sleep(0.2)

    elapsed = time.time() - start_time
    logger.info(f"🏁 Broadcast Completed. Targets: {active_tasks}. Time: {elapsed:.2f}s")


async def send_duas_batch(dua_list, setting_key, title, target_chat_id: Optional[int] = None):
    """
    إرسال الأذكار (الصباح / المساء) بشكل عشوائي.
    """
    selected = random.sample(dua_list, min(4, len(dua_list)))
    
    # الالتزام بالإيموجي الموجودة في الملف القديم فقط
    dua_emojis = ["💕", "🤍", "🤎"]
    
    text = f"<b>{title}</b>\n\n"
    for d in selected:
        emo = random.choice(dua_emojis)
        text += f"• {d} {emo}\n\n"
    # الالتزام بالنص القديم حرفياً
    text += "<b>تقبل الله منا ومنكم صالح الاعمال</b>"

    # أ) إرسال لجروب محدد
    if target_chat_id:
        try:
            if CURRENT_DUA_STICKER:
                await app.send_sticker(target_chat_id, CURRENT_DUA_STICKER)
        except: pass
        try:
            await app.send_message(target_chat_id, text)
        except: pass
        return

    # ب) إرسال جماعي للجروبات المفعلة
    async for entry in settings_db.find({setting_key: True}):
        try:
            c_id = entry.get("chat_id")
            if c_id:
                # إرسال الاستيكر
                if CURRENT_DUA_STICKER:
                    try: await app.send_sticker(c_id, CURRENT_DUA_STICKER)
                    except: pass
                
                # إرسال النص
                try:
                    await app.send_message(c_id, text)
                except FloodWait as f:
                    await asyncio.sleep(f.value)
                except: pass
                
                await asyncio.sleep(1.2)
        except Exception:
            continue


# ==================================================================
# [SECTION 5] Scheduler & Timings
# ==================================================================

async def get_azan_times() -> Optional[Dict[str, str]]:
    """جلب مواقيت الصلاة من API خارجي."""
    try:
        timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            # استخدام Aladhan API (طريقة 5 - الهيئة المصرية العامة للمساحة)
            url = "http://api.aladhan.com/v1/timingsByCity"
            params = {
                "city": "Cairo",
                "country": "Egypt",
                "method": "5"
            }
            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data["data"]["timings"]
                else:
                    logger.error(f"API Error: Status {resp.status}")
                    return None
    except Exception as e:
        logger.error(f"Failed to fetch Azan times: {e}")
        return None

async def update_scheduler():
    """
    تحديث الجدولة اليومية:
    1. تحميل الموارد.
    2. جلب المواقيت.
    3. جدولة مهام البث.
    """
    logger.info("🔄 Running daily scheduler update...")
    
    # 1. تحديث الموارد
    await load_resources()
    
    # 2. جلب المواقيت
    times = await get_azan_times()
    if not times:
        logger.warning("Could not fetch times, scheduler update aborted.")
        return
    
    # 3. تنظيف المهام القديمة
    for job in scheduler.get_jobs():
        if str(job.id).startswith("azan_"):
            job.remove()
        
    # 4. إضافة المهام الجديدة
    now = datetime.now(CAIRO_TZ)
    scheduled_count = 0
    
    for key in CURRENT_RESOURCES.keys():
        if key in times:
            t_str = times[key].split(" ")[0]
            try:
                h, m = map(int, t_str.split(":"))
                
                # جدولة المهمة باستخدام Cron Trigger
                scheduler.add_job(
                    broadcast_azan, 
                    "cron", 
                    hour=h, 
                    minute=m, 
                    args=[key], 
                    id=f"azan_{key}",
                    misfire_grace_time=300
                )
                scheduled_count += 1
            except ValueError:
                continue
                
    logger.info(f"✅ Scheduler updated successfully. {scheduled_count} prayers scheduled.")


def init_azan_scheduler():
    """
    بدء تشغيل النظام بالكامل.
    يتم استدعاء هذه الدالة عند تشغيل البوت.
    """
    try:
        if not scheduler.running:
            # أ) جدولة التحديث اليومي للمواقيت (الساعة 12:05 ص)
            scheduler.add_job(
                lambda: asyncio.create_task(update_scheduler()), 
                "cron", 
                hour=0, 
                minute=5, 
                id="daily_sync"
            )
            
            # ب) جدولة أذكار الصباح (7:00 ص)
            scheduler.add_job(
                lambda: asyncio.create_task(send_duas_batch(MORNING_DUAS, "dua_active", "أذكار الصباح")), 
                "cron", 
                hour=7, 
                minute=0, 
                id="m_duas"
            )
            
            # ج) جدولة أذكار المساء (8:00 م)
            scheduler.add_job(
                lambda: asyncio.create_task(send_duas_batch(NIGHT_DUAS, "night_dua_active", "أذكار المساء")), 
                "cron", 
                hour=20, 
                minute=0, 
                id="e_duas"
            )
            
            # بدء المجدول
            scheduler.start()
            
            # تشغيل التحديث فوراً عند الإقلاع
            loop = asyncio.get_event_loop()
            loop.create_task(update_scheduler())
            
            logger.info("🚀 Azan System (Enterprise V9) Started Successfully.")
            
    except Exception as e:
        logger.critical(f"Failed to initialize Azan Scheduler: {e}")
