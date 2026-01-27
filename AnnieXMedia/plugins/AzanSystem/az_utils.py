# Authored By Certified Coders © 2026
# System: Azan Utils V12 | Permanent Zero-Keyboard | Error Suppression

import asyncio
import aiohttp
import random
import re
import time
import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pyrogram import enums
from pyrogram.errors import FloodWait

# استدعاء مكتبات السورس الأساسية
from AnnieXMedia import app
from AnnieXMedia.utils.stream.stream import stream

# استدعاء المتغيرات من ملف الإعدادات (Relative Import)
from .az_conf import (
    settings_db, resources_db, azan_logs_db, local_cache, 
    CURRENT_RESOURCES, CURRENT_DUA_STICKER, DEVS, 
    MORNING_DUAS, NIGHT_DUAS
)

# إعداد السجلات (Logging) لمتابعة الأخطاء في التيرمينال
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Azan_System_Utils")

# --- [ 1. الدوال المساعدة وإدارة البيانات ] ---

async def load_resources():
    """تحميل الروابط والاستيكرات المحفوظة في الداتابيز"""
    try:
        stored_res = await resources_db.find_one({"type": "azan_data"})
        if stored_res:
            saved_data = stored_res.get("data", {})
            for key, val in saved_data.items():
                if key in CURRENT_RESOURCES: 
                    CURRENT_RESOURCES[key].update(val)
        
        dua_res = await resources_db.find_one({"type": "dua_sticker"})
        if dua_res:
            import AnnieXMedia.plugins.AzanSystem.az_conf as conf_module
            conf_module.CURRENT_DUA_STICKER = dua_res.get("sticker_id")
            global CURRENT_DUA_STICKER
            CURRENT_DUA_STICKER = dua_res.get("sticker_id")
    except Exception as e:
        logger.error(f"خطأ في تحميل الموارد: {e}")

def extract_vidid(url):
    """استخراج أيدي الفيديو من رابط يوتيوب"""
    match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11}).*", url)
    return match.group(1) if match else None

async def get_chat_doc(chat_id):
    """جلب إعدادات الجروب أو إنشاء إعدادات افتراضية"""
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

async def update_doc(chat_id, key, value, sub_key=None):
    """تحديث إعداد معين لجروب في الداتابيز والكاش"""
    if sub_key:
        await settings_db.update_one(
            {"chat_id": chat_id}, 
            {"$set": {f"prayers.{sub_key}": value}}, 
            upsert=True
        )
        if chat_id in local_cache:
            if "prayers" not in local_cache[chat_id]:
                local_cache[chat_id]["prayers"] = {}
            local_cache[chat_id]["prayers"][sub_key] = value
    else:
        await settings_db.update_one(
            {"chat_id": chat_id}, 
            {"$set": {key: value}}, 
            upsert=True
        )
        if chat_id in local_cache: 
            local_cache[chat_id][key] = value

async def check_rights(user_id, chat_id):
    """فحص صلاحيات المستخدم (مشرف أو مطور)"""
    if user_id in DEVS: return True
    try:
        mem = await app.get_chat_member(chat_id, user_id)
        if mem.status in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]: 
            return True
    except: pass
    return False

# --- [ 2. دالة تشغيل الأذان (بدون أزرار وبدون أخطاء) ] ---

async def start_azan_stream(chat_id, prayer_key, force_test=False):
    """تشغيل بث الأذان (استيكر + نص + صوت) مع منع ظهور أزرار التحكم تماماً"""
    res = CURRENT_RESOURCES[prayer_key]
    
    fake_result = {
        "link": res["link"], 
        "vidid": res["vidid"], 
        "title": f"أذان {res['name']}", 
        "duration_min": "05:00", 
        "thumb": f"https://img.youtube.com/vi/{res['vidid']}/hqdefault.jpg"
    }
    
    # 🔥 هنا السر: نجعل كافة مفاتيح الأزرار فارغة تماماً
    # سورس البوت الأساسي عندما يجد النص فارغاً لن يقوم بإنشاء أي زر Inline
    _ = {
        "queue_4": "<b>🔢 الـتـرتـيـب: #{}</b>",
        "stream_1": "<b>🔘 جـاري تـشـغـيـل الـأذان...</b>",
        "play_3": "<b>❌ فـشـل الـبـث.</b>",
        # كتم كافة مفاتيح الأزرار لمنع ظهورها
        "CLOSE_BUTTON": "", "BACK_BUTTON": "",
        "S_B_1": "", "S_B_2": "", "S_B_3": "", "S_B_4": "",
        "PL_1": "", "QM_2": ""
    }

    try:
        # إرسال الاستيكر أولاً
        if res.get("sticker"):
            await app.send_sticker(chat_id, res["sticker"])
    except: pass

    caption = f"<b>حـان الـآن مـوعـد اذان {res['name']}</b>\n<b>بـالـتـوقـيـت الـمـحـلـي لـمـديـنـة الـقـاهـره 🕌</b>"
    
    try:
        # إرسال رسالة التنبيه النصية
        mystic = await app.send_message(chat_id, caption)
        
        try:
            # تشغيل الستريم بوضع Force Play لقطع أي صوت آخر
            await stream(
                _, 
                mystic, 
                app.id, 
                fake_result, 
                chat_id, 
                "خدمة الأذان", 
                chat_id, 
                video=False, 
                streamtype="youtube", 
                forceplay=True
            )
            # تم حذف سطر مسح الأزرار لأنه لن تظهر أزرار من الأساس بهذا التعديل
            logger.info(f"تم تشغيل أذان {res['name']} في {chat_id} بنجاح (بدون أزرار).")
        
        except FloodWait as e:
            await asyncio.sleep(e.value)
            await stream(_, mystic, app.id, fake_result, chat_id, "خدمة الأذان", chat_id, video=False, streamtype="youtube", forceplay=True)
        
        except Exception:
            # كتم كافة الأخطاء المتعلقة بالأزرار (Markup) في سورس الستريم
            pass
            
    except Exception:
        return

    # تسجيل العملية في السجلات
    if not force_test:
        try:
            now = datetime.now()
            log_key = f"{chat_id}_{now.strftime('%Y-%m-%d_%H:%M')}" 
            if not await azan_logs_db.find_one({"key": log_key}):
                await azan_logs_db.insert_one({
                    "chat_id": chat_id,
                    "date": now.strftime("%Y-%m-%d"),
                    "key": log_key
                })
        except: pass

# --- [ 3. جلب المواقيت والبث الجماعي ] ---

async def get_azan_times():
    """جلب مواقيت الصلاة من API خارجي"""
    url = "http://api.aladhan.com/v1/timingsByCity?city=Cairo&country=Egypt&method=5"
    for attempt in range(3):
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data["data"]["timings"]
        except Exception:
            await asyncio.sleep(2)
    return None

async def broadcast_azan(prayer_key):
    """نظام البث الجماعي للجروبات المفعلة"""
    async for entry in settings_db.find({"azan_active": True}):
        c_id = entry.get("chat_id")
        prayers = entry.get("prayers", {})
        if c_id and prayers.get(prayer_key, True):
            asyncio.create_task(start_azan_stream(c_id, prayer_key, force_test=False))
            await asyncio.sleep(1.5) # تأخير بسيط لتفادي ضغط السيرفر

async def send_duas_batch(dua_list, setting_key, title, target_chat_id=None):
    """إرسال أذكار الصباح والمساء"""
    selected = random.sample(dua_list, min(4, len(dua_list)))
    text = f"<b>{title}</b>\n\n"
    for d in selected: 
        text += f"• {d} 🤍\n\n"
    text += "<b>تـقـبـل الـلـه مـنـا ومـنـكـم صـالـح الـأعـمـال</b>"
    
    if target_chat_id:
        if CURRENT_DUA_STICKER: 
            try: await app.send_sticker(target_chat_id, CURRENT_DUA_STICKER)
            except: pass
        await app.send_message(target_chat_id, text)
        return

    async for entry in settings_db.find({setting_key: True}):
        try:
            c_id = entry.get("chat_id")
            if c_id:
                if CURRENT_DUA_STICKER: 
                    try: await app.send_sticker(c_id, CURRENT_DUA_STICKER)
                    except: pass
                await app.send_message(c_id, text)
                await asyncio.sleep(1.5)
        except: continue

# --- [ 4. إعداد المجدول الزمني ] ---

scheduler = AsyncIOScheduler(timezone="Africa/Cairo")

async def update_scheduler():
    """تحديث مهام المجدول بناءً على مواقيت الصلاة الجديدة"""
    logger.info("تـحـديـث الـمـجـدول الـزمـنـي لـلـأذان...")
    await load_resources()
    times = await get_azan_times()
    
    if not times:
        logger.error("فشل جلب المواقيت لتحديث المجدول!")
        return
    
    # حذف مهام الأذان القديمة
    for job in scheduler.get_jobs():
        if job.id.startswith("azan_"): job.remove()
        
    # إضافة مواعيد اليوم
    for key in CURRENT_RESOURCES.keys():
        if key in times:
            t = times[key].split(" ")[0]
            h, m = map(int, t.split(":"))
            scheduler.add_job(
                broadcast_azan, 
                "cron", 
                hour=h, 
                minute=m, 
                args=[key], 
                id=f"azan_{key}"
            )
            logger.info(f"تم جدولة أذان {key} في الساعة {h}:{m}")

def init_azan_scheduler():
    """بدء تشغيل المجدول الزمني"""
    try:
        if not scheduler.running:
            # تحديث المواعيد يومياً 12:05 ص
            scheduler.add_job(update_scheduler, "cron", hour=0, minute=5)
            
            # جدولة الأذكار
            scheduler.add_job(lambda: asyncio.create_task(send_duas_batch(MORNING_DUAS, "dua_active", "أذكار الصباح")), "cron", hour=7, minute=0)
            scheduler.add_job(lambda: asyncio.create_task(send_duas_batch(NIGHT_DUAS, "night_dua_active", "أذكار المساء")), "cron", hour=20, minute=0)
            
            scheduler.start()
            
            loop = asyncio.get_event_loop()
            loop.create_task(update_scheduler())
            logger.info("نظام الأذان يعمل الآن (بدون كيبورد).")
    except Exception as e:
        logger.error(f"خطأ في تشغيل المجدول: {e}")
