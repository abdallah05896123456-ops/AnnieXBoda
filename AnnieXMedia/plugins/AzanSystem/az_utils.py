# Authored By Certified Coders © 2026
# System: Azan Maestro (Enterprise V14 - Full Automation)
# Location: AnnieXMedia/plugins/AzanSystem/az_utils.py
# Features:
# - Auto Join (Smart Assistant)
# - Force Start Voice Chat (CreateGroupCall)
# - Auto Leave After Azan (Cleanup)
# - High Concurrency for Strong Servers

import asyncio
import aiohttp
import random
import re
import time
import logging
import pytz
import functools
from datetime import datetime
from typing import Optional, Dict, Any

# --- [ Scheduling & Telegram Client ] ---
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pyrogram import enums
from pyrogram.raw.functions.phone import CreateGroupCall
from pyrogram.errors import (
    FloodWait,
    PeerIdInvalid,
    ChannelInvalid,
    UserNotParticipant,
    UserAlreadyParticipant,
    GroupcallAlreadyJoined,
    GroupcallInvalid,
    ChatAdminRequired
)

# --- [ Internal Imports ] ---
from AnnieXMedia import app, YouTube
from AnnieXMedia.core.call import StreamController
# استيراد قائمة المساعدين لتوزيع الحمل
from AnnieXMedia.core.userbot import assistants

# --- [ Database Imports ] ---
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
    format='%(asctime)s - [AzanEngine] - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("Azan_Maestro_Pro")

# --- [ Constants & Global Variables ] ---
CAIRO_TZ = pytz.timezone('Africa/Cairo')
# عدد العمليات المتوازية (تم ضبطه ليتناسب مع سيرفرك القوي 16 كور)
MAX_CONCURRENT_STREAMS = 20  
stream_semaphore = asyncio.Semaphore(MAX_CONCURRENT_STREAMS)
scheduler = AsyncIOScheduler(timezone=CAIRO_TZ)
# مدة الأذان التقريبية بالثواني (بعدها البوت هيخرج من الكول)
AZAN_DURATION_SECONDS = 240  # 4 دقائق


# ==================================================================
# [SECTION 1] Helpers & Decorators
# ==================================================================

def retry_operation(max_retries=3, delay=2):
    """
    Decorator: يعيد محاولة تنفيذ الدالة في حالة الفشل.
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
                    if attempt < max_retries:
                        await asyncio.sleep(delay)
            logger.error(f"Function {func.__name__} failed after {max_retries} retries.")
            raise last_exc
        return wrapper
    return decorator

def extract_vidid(url: str) -> Optional[str]:
    """استخراج معرّف الفيديو من رابط يوتيوب."""
    match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11}).*", url)
    return match.group(1) if match else None

# ==================================================================
# [SECTION 2] Database Management
# ==================================================================

async def get_chat_doc(chat_id: int) -> Dict[str, Any]:
    """جلب إعدادات الجروب مع الكاش"""
    if chat_id in local_cache:
        return local_cache[chat_id]
    try:
        doc = await settings_db.find_one({"chat_id": chat_id})
        if not doc:
            doc = {
                "chat_id": chat_id,
                "azan_active": True,
                "forced_active": False,
                "dua_active": True,
                "night_dua_active": True,
                "prayers": {k: True for k in CURRENT_RESOURCES.keys()}
            }
            await settings_db.insert_one(doc)
        local_cache[chat_id] = doc
        return doc
    except Exception:
        return {}

async def update_doc(chat_id: int, key: str, value, sub_key: str = None):
    """تحديث الداتابيز"""
    try:
        if sub_key:
            await settings_db.update_one({"chat_id": chat_id}, {"$set": {f"prayers.{sub_key}": value}}, upsert=True)
            if chat_id in local_cache: local_cache[chat_id].setdefault("prayers", {})[sub_key] = value
        else:
            await settings_db.update_one({"chat_id": chat_id}, {"$set": {key: value}}, upsert=True)
            if chat_id in local_cache: local_cache[chat_id][key] = value
    except Exception:
        pass

async def check_rights(user_id: int, chat_id: int) -> bool:
    """التحقق من الصلاحيات"""
    if user_id in DEVS: return True
    try:
        mem = await app.get_chat_member(chat_id, user_id)
        return mem.status in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]
    except: return False

@retry_operation(max_retries=3)
async def load_resources():
    """تحميل الروابط والاستيكرات"""
    try:
        stored_res = await resources_db.find_one({"type": "azan_data"})
        if stored_res:
            for k, v in stored_res.get("data", {}).items():
                if k in CURRENT_RESOURCES: CURRENT_RESOURCES[k].update(v)
        
        dua_res = await resources_db.find_one({"type": "dua_sticker"})
        if dua_res:
            global CURRENT_DUA_STICKER
            CURRENT_DUA_STICKER = dua_res.get("sticker_id")
        logger.info("✅ Resources Loaded.")
    except Exception as e:
        logger.error(f"Resource Load Error: {e}")

# ==================================================================
# [SECTION 3] Smart Assistant Logic (Join & Force Start)
# ==================================================================

async def prepare_call_environment(chat_id: int, assistant, force_log: bool = False):
    """
    تجهيز بيئة الاتصال بالكامل:
    1. التأكد من انضمام المساعد للجروب.
    2. التأكد من أن المكالمة الصوتية مفتوحة (وفتحها إجبارياً لو مغلقة).
    """
    # 1. الانضمام للجروب
    try:
        await assistant.get_chat_member(chat_id, "me")
    except UserNotParticipant:
        try:
            invite_link = await app.export_chat_invite_link(chat_id)
            if "+" in invite_link: 
                await assistant.join_chat(invite_link)
            else: 
                chat = await app.get_chat(chat_id)
                if chat.username: 
                    await assistant.join_chat(chat.username)
            # انتظار بسيط بعد الانضمام لتجنب الأخطاء
            await asyncio.sleep(1.5)
        except Exception as e:
            if force_log: logger.error(f"Failed to join {chat_id}: {e}")
            return False

    # 2. فتح المكالمة إجبارياً (Force Start)
    try:
        # فحص حالة الكول أولاً
        try:
            await assistant.get_group_call(chat_id)
        except (GroupcallInvalid, GroupcallAlreadyJoined):
            # الكول مش شغال أو فيه مشكلة بسيطة -> نكمل لمحاولة الإنشاء
            pass 
        except Exception:
            pass

        # محاولة إنشاء الكول باستخدام Raw Functions
        try:
            peer = await assistant.resolve_peer(chat_id)
            await assistant.invoke(CreateGroupCall(
                peer=peer,
                random_id=random.randint(0, 100000)
            ))
            if force_log: logger.info(f"🆕 Voice Chat Started forcibly in {chat_id}")
            await asyncio.sleep(2) # انتظار الانتشار
        except Exception as e:
            # تجاهل الأخطاء التي تعني أن الكول يعمل بالفعل
            if "GROUPCALL_ALREADY_JOINED" in str(e) or "SCHEDULED" in str(e):
                pass
            elif "CHAT_ADMIN_REQUIRED" in str(e):
                if force_log: logger.warning(f"Assistant needs Admin rights in {chat_id} to start call.")
            else:
                if force_log: logger.debug(f"Create Call Info {chat_id}: {e}")

    except Exception as e:
        logger.error(f"Call preparation error: {e}")
    
    return True

# ==================================================================
# [SECTION 4] Stream Execution Engine
# ==================================================================

async def start_azan_stream(chat_id: int, prayer_key: str, play_target: str = None, force_test: bool = False):
    """
    محرك التشغيل الذكي للأذان.
    """
    # التحقق من التفعيل (إلا في حالة التست)
    if not force_test:
        doc = await get_chat_doc(chat_id)
        if not doc.get("azan_active", True):
            return

    async with stream_semaphore:
        res = CURRENT_RESOURCES.get(prayer_key)
        if not res: return
        if not play_target: play_target = res.get("link")

        try:
            # 1. إرسال الوسائط (الاستيكر والنص)
            if res.get("sticker"):
                try: await app.send_sticker(chat_id, res["sticker"])
                except: pass
            
            caption = f"<b>حان الآن موعد اذان {res.get('name','')}</b>\n<b>بالتوقيت المحلي لمدينة القاهره 🕌</b>"
            try: await app.send_message(chat_id, caption)
            except: pass

            # 2. اختيار مساعد وتجهيز الكول
            # اختيار مساعد عشوائي لتوزيع الحمل
            assistant = random.choice(assistants)
            
            success = await prepare_call_environment(chat_id, assistant, force_log=force_test)
            if not success and force_test:
                await app.send_message(chat_id, "⚠️ فشل تجهيز المساعد أو الكول (تأكد من الصلاحيات).")

            # 3. تشغيل البث
            try:
                await StreamController.join_call(
                    chat_id, 
                    chat_id, 
                    play_target, 
                    video=False
                )
                if force_test: await app.send_message(chat_id, "✅ البث بدأ بنجاح.")

                # 4. جدولة إيقاف الكول (Auto-Leave) بعد انتهاء الأذان
                # نقوم بإنشاء مهمة منفصلة للانتظار والخروج حتى لا نعطل باقي الجروبات
                asyncio.create_task(stop_stream_after_delay(chat_id, AZAN_DURATION_SECONDS))

            except FloodWait as fw:
                await asyncio.sleep(fw.value + 1)
                await StreamController.join_call(chat_id, chat_id, play_target, video=False)
                asyncio.create_task(stop_stream_after_delay(chat_id, AZAN_DURATION_SECONDS))
            
            except Exception as e:
                # محاولة أخيرة لو الكول لسه مقفول
                if "No active videochat" in str(e) or "GROUPCALL_INVALID" in str(e):
                    await prepare_call_environment(chat_id, assistant, force_log=True)
                    await asyncio.sleep(2)
                    try: 
                        await StreamController.join_call(chat_id, chat_id, play_target, video=False)
                        asyncio.create_task(stop_stream_after_delay(chat_id, AZAN_DURATION_SECONDS))
                    except: pass
                
                if force_test: await app.send_message(chat_id, f"❌ خطأ: {e}")

            # 5. تسجيل اللوج
            if not force_test:
                try:
                    now = datetime.now(CAIRO_TZ)
                    log_key = f"{chat_id}_{now.strftime('%Y-%m-%d_%H:%M')}"
                    if not await azan_logs_db.find_one({"key": log_key}):
                        await azan_logs_db.insert_one({
                            "chat_id": chat_id,
                            "key": log_key,
                            "prayer_key": prayer_key,
                            "time": now.strftime("%I:%M %p")
                        })
                except: pass

        except Exception as e:
            logger.error(f"Stream Error {chat_id}: {e}")

async def stop_stream_after_delay(chat_id: int, delay: int):
    """
    وظيفة تنتظر انتهاء مدة الأذان ثم تخرج المساعد من الكول.
    """
    await asyncio.sleep(delay)
    try:
        # استخدام دالة الإيقاف من الكور للخروج النظيف
        await StreamController.stop_stream(chat_id)
        # أو يمكن استخدام force_stop_stream لو أردت تنظيف القائمة بالكامل
    except Exception:
        pass

# ==================================================================
# [SECTION 5] Global Broadcast Loop
# ==================================================================

async def broadcast_azan(prayer_key: str):
    res = CURRENT_RESOURCES.get(prayer_key)
    if not res: return
    
    logger.info(f"📢 STARTING BROADCAST: {prayer_key}")
    
    # 1. تجهيز الرابط مرة واحدة
    try:
        if "youtube" in res["link"]:
             play_target, _ = await YouTube.download(res["link"], None, video=False, videoid=False)
        else:
             play_target = res["link"]
        if not play_target: play_target = res["link"]
    except:
        play_target = res["link"]

    tasks = []
    # 2. اللف على الجروبات المفعلة فقط
    async for doc in settings_db.find({"azan_active": True}):
        c_id = doc.get("chat_id")
        if not c_id: continue
        
        # التأكد إن الصلاة دي مفعلة في الجروب
        if doc.get("prayers", {}).get(prayer_key, True):
            tasks.append(start_azan_stream(c_id, prayer_key, play_target))
            
            # كل 20 جروب نبعتهم دفعة واحدة
            if len(tasks) >= 20:
                await asyncio.gather(*tasks, return_exceptions=True)
                tasks = []
                # راحة بسيطة جداً
                await asyncio.sleep(0.5) 

    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    
    logger.info("🏁 Broadcast Completed.")


async def send_duas_batch(dua_list, setting_key, title, target_chat_id: Optional[int] = None):
    """دالة نشر الأذكار (لا تفتح كول، فقط رسائل)"""
    selected = random.sample(dua_list, min(4, len(dua_list)))
    dua_emojis = ["💕", "🤍", "🤎"]
    text = f"<b>{title}</b>\n\n"
    for d in selected:
        emo = random.choice(dua_emojis)
        text += f"• {d} {emo}\n\n"
    text += "<b>تقبل الله منا ومنكم صالح الاعمال</b>"

    if target_chat_id:
        try:
            if CURRENT_DUA_STICKER: await app.send_sticker(target_chat_id, CURRENT_DUA_STICKER)
            await app.send_message(target_chat_id, text)
        except: pass
        return

    async for entry in settings_db.find({setting_key: True}):
        try:
            c_id = entry.get("chat_id")
            if c_id:
                if CURRENT_DUA_STICKER:
                    try: await app.send_sticker(c_id, CURRENT_DUA_STICKER)
                    except: pass
                try: await app.send_message(c_id, text)
                except FloodWait as f: await asyncio.sleep(f.value)
                except: pass
                await asyncio.sleep(1.2)
        except: continue


# ==================================================================
# [SECTION 6] Scheduler & Init
# ==================================================================

async def get_azan_times() -> Optional[Dict[str, str]]:
    try:
        timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            url = "http://api.aladhan.com/v1/timingsByCity"
            params = {"city": "Cairo", "country": "Egypt", "method": "5"}
            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data["data"]["timings"]
    except: return None

async def update_scheduler():
    logger.info("🔄 Update Scheduler...")
    await load_resources()
    times = await get_azan_times()
    if not times: return
    
    for job in scheduler.get_jobs():
        if str(job.id).startswith("azan_"): job.remove()
        
    for key in CURRENT_RESOURCES.keys():
        if key in times:
            t_str = times[key].split(" ")[0]
            try:
                h, m = map(int, t_str.split(":"))
                scheduler.add_job(broadcast_azan, "cron", hour=h, minute=m, args=[key], id=f"azan_{key}")
            except: continue
    logger.info("✅ Scheduler Updated.")

def init_azan_scheduler():
    if not scheduler.running:
        scheduler.add_job(lambda: asyncio.create_task(update_scheduler()), "cron", hour=0, minute=5)
        scheduler.add_job(lambda: asyncio.create_task(send_duas_batch(MORNING_DUAS, "dua_active", "أذكار الصباح")), "cron", hour=7, minute=0)
        scheduler.add_job(lambda: asyncio.create_task(send_duas_batch(NIGHT_DUAS, "night_dua_active", "أذكار المساء")), "cron", hour=20, minute=0)
        scheduler.start()
        asyncio.get_event_loop().create_task(update_scheduler())
