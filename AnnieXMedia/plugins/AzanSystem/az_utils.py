# Authored By Certified Coders © 2026
# System: Azan Utils V14 | Absolute Zero-Keyboard | Fully Complete
# This file handles the logic, timings, and silent broadcasting.

import asyncio
import aiohttp
import random
import re
import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pyrogram import enums
from pyrogram.errors import FloodWait

# استدعاء مكتبات السورس الأساسية
from AnnieXMedia import app
from AnnieXMedia.utils.stream.stream import stream

# استدعاء المتغيرات من ملف الإعدادات
from .az_conf import (
    settings_db, resources_db, azan_logs_db, local_cache, 
    CURRENT_RESOURCES, CURRENT_DUA_STICKER, DEVS, 
    MORNING_DUAS, NIGHT_DUAS
)

# إعداد السجلات (Logging) لمتابعة النظام
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Azan_System_Utils")

# ==========================================================
# 🛡️ 1. كـائـن الـاعـتـراض (The Keyboard Interceptor)
# ==========================================================

class SilentMystic:
    """كائن ذكي يعترض رسائل التعديل ويحذف الأزرار قبل وصولها للتليجرام"""
    def __init__(self, real_message):
        self.real_message = real_message
        self.chat = real_message.chat
        self.id = real_message.id

    async def edit_text(self, text, *args, **kwargs):
        # حذف معامل reply_markup إجبارياً لمنع ظهور الأزرار
        try:
            return await self.real_message.edit_text(
                text=text, 
                reply_markup=None, 
                disable_web_page_preview=True
            )
        except Exception:
            pass

    async def edit_media(self, media, *args, **kwargs):
        # اعتراض تعديل الصور (Thumbnail) وحذف أزرار التحكم منها
        try:
            return await self.real_message.edit_media(
                media=media, 
                reply_markup=None
            )
        except Exception:
            pass

    async def edit_reply_markup(self, reply_markup=None, *args, **kwargs):
        # قتل أي محاولة لتحديث الأزرار فقط
        return True

    def __getattr__(self, name):
        # تمرير أي دالة أخرى (مثل delete أو reply) للمسج الحقيقي
        return getattr(self.real_message, name)

# ==========================================================
# ⚙️ 2. الـدوال الـمـسـاعـدة وإدارة الـبيـانـات
# ==========================================================

async def load_resources():
    """تحميل روابط الأذان واستيكر الأذكار من قاعدة البيانات"""
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
        logger.error(f"خـطـأ فـي تـحـمـيـل الـمـوارد: {e}")

def extract_vidid(url):
    """استخراج ID الفيديو من روابط يوتيوب"""
    match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11}).*", url)
    return match.group(1) if match else None

async def get_chat_doc(chat_id):
    """جلب وثيقة إعدادات الجروب أو إنشاء واحدة جديدة"""
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
    """تحديث إعدادات الجروب في الداتابيز والكاش"""
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
    """التحقق من صلاحية المستخدم (مطور أو أدمن)"""
    if user_id in DEVS: return True
    try:
        mem = await app.get_chat_member(chat_id, user_id)
        if mem.status in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]: 
            return True
    except: pass
    return False

# ==========================================================
# 🕌 3. دالـة تـشـغـيـل الـأذان (الـبـث الـنـظـيـف)
# ==========================================================

async def start_azan_stream(chat_id, prayer_key, force_test=False):
    """تشغيل بث الأذان بدون كيبورد تحكم نهائياً وبدون أخطاء"""
    res = CURRENT_RESOURCES[prayer_key]
    
    fake_result = {
        "link": res["link"], 
        "vidid": res["vidid"], 
        "title": f"أذان {res['name']}", 
        "duration_min": "05:00", 
        "thumb": f"https://img.youtube.com/vi/{res['vidid']}/hqdefault.jpg"
    }
    
    # قاموس لغات فارغ تماماً للأزرار لضمان عدم رسمها في الـ core
    _ = {
        "queue_4": "<b>🔢 الـتـرتـيـب: #{}</b>",
        "stream_1": "<b>🔘 جـاري تـشـغـيـل الـأذان...</b>",
        "play_3": "<b>❌ فـشـل الـبـث.</b>",
        "CLOSE_BUTTON": "", "BACK_BUTTON": "",
        "S_B_1": "", "S_B_2": "", "S_B_3": "", "S_B_4": "",
        "PL_1": "", "QM_2": ""
    }

    try:
        # إرسال الاستيكر
        if res.get("sticker"):
            await app.send_sticker(chat_id, res["sticker"])
    except: pass

    caption = f"<b>حـان الـآن مـوعـد اذان {res['name']}</b>\n<b>بـالـتـوقـيـت الـمـحـلـي لـمـديـنـة الـقـاهـره 🕌</b>"
    
    try:
        # 1. إرسال الرسالة الحقيقية
        real_msg = await app.send_message(chat_id, caption)
        
        # 2. تحويلها لرسالة صامتة ترفض الأزرار
        silent_mystic = SilentMystic(real_msg)
        
        # 3. استدعاء الستريم بالـ Mystic الصامت
        try:
            await stream(
                _, 
                silent_mystic, 
                app.id, 
                fake_result, 
                chat_id, 
                "خدمة الأذان", 
                chat_id, 
                video=False, 
                streamtype="youtube", 
                forceplay=True
            )
            logger.info(f"تم تشغيل أذان {res['name']} في {chat_id} (Zero Keyboard Mode)")
        except Exception:
            pass # كتم أي أخطاء من السورس تتعلق بالأزرار
            
    except Exception as e:
        if force_test: await app.send_message(chat_id, f"خـطـأ: {e}")
        return

    # تسجيل العملية في اللوج
    if not force_test:
        try:
            now = datetime.now()
            log_key = f"{chat_id}_{now.strftime('%Y-%m-%d_%H:%M')}" 
            if not await azan_logs_db.find_one({"key": log_key}):
                await azan_logs_db.insert_one({"chat_id": chat_id, "date": now.strftime("%Y-%m-%d"), "key": log_key})
        except: pass

# ==========================================================
# 🌍 4. جـلـب الـمـواقـيـت والـبـث الـجـمـاعـي
# ==========================================================

async def get_azan_times():
    """جلب مواقيت الصلاة من API القاهرة"""
    url = "http://api.aladhan.com/v1/timingsByCity?city=Cairo&country=Egypt&method=5"
    for attempt in range(3):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data["data"]["timings"]
        except: await asyncio.sleep(2)
    return None

async def broadcast_azan(prayer_key):
    """المجدول: تشغيل الأذان لكل الجروبات المفعلة"""
    async for entry in settings_db.find({"azan_active": True}):
        c_id = entry.get("chat_id")
        prayers = entry.get("prayers", {})
        if c_id and prayers.get(prayer_key, True):
            asyncio.create_task(start_azan_stream(c_id, prayer_key))
            await asyncio.sleep(1.5)

async def send_duas_batch(dua_list, setting_key, title, target_chat_id=None):
    """نشر الأذكار الصباحية والمسائية"""
    selected = random.sample(dua_list, min(4, len(dua_list)))
    text = f"<b>{title}</b>\n\n"
    for d in selected: text += f"• {d} 🤍\n\n"
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
                if CURRENT_DUA_STICKER: await app.send_sticker(c_id, CURRENT_DUA_STICKER)
                await app.send_message(c_id, text)
                await asyncio.sleep(1.5)
        except: continue

# ==========================================================
# ⏰ 5. إعـداد الـمـجـدول الـزمـنـي
# ==========================================================

scheduler = AsyncIOScheduler(timezone="Africa/Cairo")

async def update_scheduler():
    """تحديث جدول مواعيد اليوم"""
    logger.info("تحديث المجدول الزمني للأذان...")
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

def init_azan_scheduler():
    """تشغيل النظام بالكامل"""
    try:
        if not scheduler.running:
            scheduler.add_job(update_scheduler, "cron", hour=0, minute=5)
            scheduler.add_job(lambda: asyncio.create_task(send_duas_batch(MORNING_DUAS, "dua_active", "أذكار الصباح")), "cron", hour=7, minute=0)
            scheduler.add_job(lambda: asyncio.create_task(send_duas_batch(NIGHT_DUAS, "night_dua_active", "أذكار المساء")), "cron", hour=20, minute=0)
            scheduler.start()
            asyncio.get_event_loop().create_task(update_scheduler())
            logger.info("نظام الأذان يعمل الآن بتقنية الحجب الكامل للأزرار.")
    except Exception as e:
        logger.error(f"خـطـأ فـي تـشـغـيـل الـمـجـدول: {e}")
