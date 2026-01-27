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

# --- [ الدوال المساعدة وإدارة البيانات ] ---

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

# --- [ دالة تشغيل الأذان (مع إصلاح الأزرار) ] ---
async def start_azan_stream(chat_id, prayer_key, force_test=False):
    """تشغيل بث الأذان في الجروب مع منع ظهور الأخطاء"""
    res = CURRENT_RESOURCES[prayer_key]
    
    fake_result = {
        "link": res["link"], 
        "vidid": res["vidid"], 
        "title": f"أذان {res['name']}", 
        "duration_min": "05:00", 
        "thumb": f"https://img.youtube.com/vi/{res['vidid']}/hqdefault.jpg"
    }
    
    # --- [ الحل الجذري: تعريف مفاتيح الترجمة للأزرار ] ---
    # هذا القاموس يمنع KeyError في ملفات السورس الأساسية
    _ = {
        "queue_4": "<b>🔢 الترتيب: #{}</b>",
        "stream_1": "<b>🔘 جاري التشغيل...</b>",
        "play_3": "<b>❌ فشل.</b>",
        "CLOSE_BUTTON": "إغلاق ❌", 
        "BACK_BUTTON": "رجوع",
        "S_B_1": "تشغيل ▶️",
        "S_B_2": "إيقاف ⏸",
        "S_B_3": "تخطي ⏭",
        "S_B_4": "إنهاء ⏹",
        "PL_1": "قائمة التشغيل",
        "QM_2": "تمت الإضافة"
    }

    try:
        # إرسال الاستيكر
        if res.get("sticker"):
            await app.send_sticker(chat_id, res["sticker"])
    except: pass

    caption = f"<b>حان الآن موعد اذان {res['name']}</b>\n<b>بالتوقيت المحلي لمدينة القاهره 🕌</b>"
    
    try:
        mystic = await app.send_message(chat_id, caption)
        try:
            # تشغيل الستريم مع Force Play لقطع الأغنية الحالية
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
            logger.info(f"تم تشغيل أذان {res['name']} في الجروب {chat_id}")
        
        except FloodWait as e:
            # التعامل مع ضغط الطلبات
            await asyncio.sleep(e.value)
            await stream(_, mystic, app.id, fake_result, chat_id, "خدمة الأذان", chat_id, video=False, streamtype="youtube", forceplay=True)
        
        except Exception as e:
            # تجاهل أخطاء تعديل الرسالة البسيطة
            if "CLOSE_BUTTON" in str(e) or "EditMessage" in str(e):
                return
            if force_test:
                await app.send_message(chat_id, f"خطأ في الستريم: {e}")
            logger.error(f"Stream Error in {chat_id}: {e}")
            
    except Exception as e:
        if force_test:
            try: await app.send_message(chat_id, f"خطأ في الارسال: {e}")
            except: pass
        return

    # تسجيل العملية في السجلات (للمتابعة فقط)
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

# --- [ جلب المواقيت والبث الجماعي ] ---
async def get_azan_times():
    """جلب مواقيت الصلاة من API خارجي مع إعادة المحاولة"""
    url = "http://api.aladhan.com/v1/timingsByCity?city=Cairo&country=Egypt&method=5"
    for attempt in range(3): # ثلاث محاولات في حال الفشل
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
    """دالة المجدول: تدور على كل الجروبات وتشغل الأذان"""
    async for entry in settings_db.find({"azan_active": True}):
        c_id = entry.get("chat_id")
        prayers = entry.get("prayers", {})
        
        # التأكد من أن الجروب مفعل هذه الصلاة تحديداً
        if c_id and prayers.get(prayer_key, True):
            asyncio.create_task(start_azan_stream(c_id, prayer_key, force_test=False))
            # تأخير بسيط لمنع الحظر
            await asyncio.sleep(2)

async def send_duas_batch(dua_list, setting_key, title, target_chat_id=None):
    """إرسال الأذكار (الصباح/المساء)"""
    selected = random.sample(dua_list, min(4, len(dua_list)))
    dua_emojis = ["💕", "🤍", "🤎"]
    text = f"<b>{title}</b>\n\n"
    for d in selected: 
        emo = random.choice(dua_emojis)
        text += f"• {d} {emo}\n\n"
    text += "<b>تقبل الله منا ومنكم صالح الاعمال</b>"
    
    # لو الهدف شات محدد (تست)
    if target_chat_id:
        if CURRENT_DUA_STICKER: 
            try: await app.send_sticker(target_chat_id, CURRENT_DUA_STICKER)
            except: pass
        await app.send_message(target_chat_id, text)
        return

    # البث الجماعي للأذكار
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

# --- [ إعداد المجدول الزمني ] ---
scheduler = AsyncIOScheduler(timezone="Africa/Cairo")

async def update_scheduler():
    """تحديث مهام المجدول بناءً على مواقيت اليوم"""
    logger.info("تحديث المجدول الزمني للأذان...")
    await load_resources()
    times = await get_azan_times()
    
    if not times:
        logger.error("فشل في جلب المواقيت لتحديث المجدول!")
        return
    
    # حذف الوظائف القديمة للأذان فقط
    for job in scheduler.get_jobs():
        if job.id.startswith("azan_"): job.remove()
        
    # إضافة الوظائف الجديدة
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
            logger.info(f"تم جدولة أذان {key} الساعة {h}:{m}")

def init_azan_scheduler():
    """بدء تشغيل المجدول (يتم استدعاؤها من ملف خارجي لضمان الأمان)"""
    try:
        if not scheduler.running:
            # تحديث يومي الساعة 12:05 صباحاً
            scheduler.add_job(update_scheduler, "cron", hour=0, minute=5)
            
            # أذكار الصباح الساعة 7
            scheduler.add_job(
                lambda: asyncio.create_task(send_duas_batch(MORNING_DUAS, "dua_active", "أذكار الصباح")), 
                "cron", hour=7, minute=0
            )
            
            # أذكار المساء الساعة 8
            scheduler.add_job(
                lambda: asyncio.create_task(send_duas_batch(NIGHT_DUAS, "night_dua_active", "أذكار المساء")), 
                "cron", hour=20, minute=0
            )
            
            scheduler.start()
            
            # تحديث فوري عند البدء
            loop = asyncio.get_event_loop()
            loop.create_task(update_scheduler())
            logger.info("تم تشغيل نظام جدولة الأذان بنجاح.")
    except Exception as e:
        logger.error(f"خطأ في تشغيل المجدول: {e}")
