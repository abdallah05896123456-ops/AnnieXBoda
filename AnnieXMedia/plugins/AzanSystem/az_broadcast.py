# Authored By Certified Coders © 2026
# System: AnnieX Advanced Broadcaster (Clean - No Footer)
# Location: AnnieXMedia/plugins/AzanSystem/az_broadcast.py

import asyncio
import random
import logging
import time
from typing import Tuple

from pyrogram import filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait, InputUserDeactivated, UserIsBlocked, PeerIdInvalid, ChannelInvalid

# --- [ Imports from Source ] ---
from AnnieXMedia import app

# --- [ Configuration & Database ] ---
from .az_conf import (
    AZAN_GROUP, 
    settings_db, 
    DEVS,
    CURRENT_DUA_STICKER
)

# --- [ Advanced Logging ] ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Azan_Broadcaster")

# ==========================================================
# 📜 [1] القوائم (النصوص كما هي بالظبط مع الإيموجي)
# ==========================================================

SALAWAT_LIST = [
    "إِنَّ اللَّهَ وَمَلَائِكَتَهُ يُصَلُّونَ عَلَى النَّبِيِّ ۚ يَا أَيُّهَا الَّذِينَ آمَنُوا صَلُّوا عَلَيْهِ وَسَلِّمُوا تَسْلِيمًا 💙",
    "اللَّهُمَّ صَلِّ وَسَلِّمْ عَلَى نَبِيِّنَا مُحَمَّدٍ 🤍",
    "اللهم صلِّ على محمد وعلى آل محمد كما صليت على إبراهيم وعلى آل إبراهيم إنك حميد مجيد 💙",
    "اللهم بارك على محمد وعلى آل محمد كما باركت على إبراهيم وعلى آل إبراهيم إنك حميد مجيد 🤍",
    "من صلى عليّ صلاة صلى الله عليه بها عشراً.. اللهم صل وسلم على نبينا محمد 💙",
    "أكثروا من الصلاة على النبي في يوم الجمعة.. اللهم صل وسلم على نبينا محمد 🤍",
    "صلوا على من بكى شوقاً لرؤيتنا.. اللهم صل وسلم على نبينا محمد 💙",
    "صلوا على شفيعكم يوم القيامة.. اللهم صل وسلم على نبينا محمد 🤍"
]

BROADCAST_ATHKAR = [
    "سُبْحَانَ اللَّهِ وَبِحَمْدِهِ، سُبْحَانَ اللَّهِ الْعَظِيمِ 💙",
    "لَا حَوْلَ وَلَا قُوَّةَ إِلَّا بِاللَّهِ الْعَلِيِّ الْعَظِيمِ 🤍",
    "أَسْتَغْفِرُ اللَّهَ الْعَظِيمَ وَأَتُوبُ إِلَيْهِ 💙",
    "لَا إِلَهَ إِلَّا أَنْتَ سُبْحَانَكَ إِنِّي كُنْتُ مِنَ الظَّالِمِينَ 🤍",
    "اللَّهُمَّ أَنْتَ رَبِّي لا إِلَهَ إِلَّا أَنْتَ، خَلَقْتَنِي وَأَنَا عَبْدُكَ، وَأَنَا عَلَى عَهْدِكَ وَوَعْدِكَ مَا اسْتَطَعْتُ 💙",
    "الْحَمْدُ لِلَّهِ حَمْدًا كَثِيرًا طَيِّبًا مُبَارَكًا فِيهِ 🤍",
    "اللَّهُمَّ إِنِّي أَسْأَلُكَ الْعَفْوَ وَالْعَافِيَةَ فِي الدُّنْيَا وَالآخِرَةِ 💙",
    "رَبَّنَا آتِنَا فِي الدُّنْيَا حَسَنَةً وَفِي الآخِرَةِ حَسَنَةً وَقِنَا عَذَابَ النَّارِ 🤍",
    "اللهم مصرف القلوب صرف قلوبنا على طاعتك 🤲",
    "سبحان الله والحمد لله ولا إله إلا الله والله أكبر 🍃"
]

JUMMAH_MESSAGES = [
    "إِنَّ اللَّهَ وَمَلَائِكَتَهُ يُصَلُّونَ عَلَى النَّبِيِّ.. أكثروا من الصلاة على الحبيب في يوم الجمعة 💙\nولا تنسوا قراءة سورة الكهف.",
    "جمعة مباركة.. لا تنسوا قراءة سورة الكهف والإكثار من الصلاة على النبي ﷺ 🤍",
    "في يوم الجمعة.. ساعة استجابة لا يوافقها عبد مسلم يدعو الله إلا استجاب له.. اذكروني بدعوة 💙",
    "نور الله قلبكم بذكره ورزقكم حبه وأعانكم على طاعته.. جمعة طيبة 🤍"
]

# ==========================================================
# ⚙️ [2] محرك البث الذكي (Batch Processing Engine)
# ==========================================================

async def send_safe_message(chat_id: int, text: str, is_pin: bool) -> bool:
    """
    إرسال رسالة آمنة (تم إزالة التذييل نهائياً).
    """
    try:
        # إرسال الاستيكر (لو موجود)
        if CURRENT_DUA_STICKER:
            try: await app.send_sticker(chat_id, CURRENT_DUA_STICKER)
            except: pass
        
        # إرسال النص (نظيف)
        msg = await app.send_message(chat_id, f"<b>{text}</b>")
        
        # التثبيت
        if is_pin:
            try: await msg.pin(disable_notification=True)
            except: pass
            
        return True

    except FloodWait as e:
        logger.warning(f"FloodWait detected: {e.value}s")
        await asyncio.sleep(e.value + 1)
        try:
            await app.send_message(chat_id, f"<b>{text}</b>")
            return True
        except: return False

    except (InputUserDeactivated, UserIsBlocked, PeerIdInvalid, ChannelInvalid):
        # تنظيف الجروبات الميتة
        await settings_db.delete_one({"chat_id": chat_id})
        return False

    except Exception:
        return False

async def broadcast_core_engine(text_message: str, is_pin: bool = False) -> Tuple[int, int, float]:
    """
    المحرك الرئيسي: يعالج الرسائل في دفعات لزيادة السرعة ومنع الحظر.
    """
    start_time = time.time()
    sent = 0
    failed = 0
    tasks = []
    
    # النشر فقط للمفعلين (Azan Active)
    cursor = settings_db.find({"azan_active": True})
    
    async for doc in cursor:
        chat_id = doc.get("chat_id")
        if not chat_id: continue
        
        tasks.append(send_safe_message(chat_id, text_message, is_pin))
        
        # معالجة كل 20 رسالة دفعة واحدة
        if len(tasks) >= 20:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for res in results:
                if res is True: sent += 1
                else: failed += 1
            
            tasks = []
            await asyncio.sleep(1.0) 
            
    # المتبقي
    if tasks:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for res in results:
            if res is True: sent += 1
            else: failed += 1

    duration = time.time() - start_time
    logger.info(f"Broadcast Finished. Sent: {sent}, Failed: {failed}")
    return sent, failed, duration

# ==========================================================
# ⏰ [3] التشغيل التلقائي
# ==========================================================

async def execute_auto_random():
    """اختيار عشوائي للنشر التلقائي"""
    if random.choice([True, False]):
        msg = random.choice(SALAWAT_LIST)
    else:
        msg = random.choice(BROADCAST_ATHKAR)
    await broadcast_core_engine(msg, is_pin=False)

async def execute_auto_jummah():
    """رسائل الجمعة"""
    msg = random.choice(JUMMAH_MESSAGES)
    await broadcast_core_engine(msg, is_pin=True)

def init_broadcast_schedule(scheduler):
    """تهيئة الجدولة"""
    
    def safe_runner(coro):
        try: app.loop.create_task(coro())
        except: pass

    # الأيام العادية
    scheduler.add_job(
        safe_runner, "cron", 
        day_of_week='sat,sun,mon,tue,wed,thu', 
        hour='3,9,18', minute=0, 
        args=[execute_auto_random], id="brd_normal"
    )

    # الجمعة
    scheduler.add_job(
        safe_runner, "cron", 
        day_of_week='fri', 
        hour='0,3,6,9,15,18,21', minute=0, 
        args=[execute_auto_random], id="brd_friday"
    )

    # الكهف
    scheduler.add_job(
        safe_runner, "cron", 
        day_of_week='fri', 
        hour=11, minute=30, 
        args=[execute_auto_jummah], id="brd_kahf"
    )

# ==========================================================
# 👮 [4] التحكم اليدوي (بدون إيموجي في الإحصائيات)
# ==========================================================

@app.on_message(filters.regex(r"^(نشر الصلاة علي النبي|نشر الصلاه علي النبي)$") & filters.user(DEVS), group=AZAN_GROUP + 6)
async def manual_salawat(client, message: Message):
    status = await message.reply_text("جاري نشر الصلاة على النبي...")
    msg = random.choice(SALAWAT_LIST)
    
    sent, failed, time_taken = await broadcast_core_engine(msg)
    
    # نص الإحصائيات بدون إيموجي حسب طلبك
    await status.edit_text(
        f"**تم النشر بنجاح**\n\n"
        f"**المرسل:** {sent}\n"
        f"**الفشل:** {failed}\n"
        f"**الوقت:** {time_taken:.2f} ثانية"
    )

@app.on_message(filters.regex(r"^(نشر ذكر|نشر اذكار|نشر أذكار)$") & filters.user(DEVS), group=AZAN_GROUP + 7)
async def manual_athkar(client, message: Message):
    status = await message.reply_text("جاري نشر الأذكار...")
    msg = random.choice(BROADCAST_ATHKAR)
    
    sent, failed, time_taken = await broadcast_core_engine(msg)
    
    await status.edit_text(
        f"**تم نشر الأذكار بنجاح**\n\n"
        f"**المرسل:** {sent}\n"
        f"**الفشل:** {failed}\n"
        f"**الوقت:** {time_taken:.2f} ثانية"
    )

@app.on_message(filters.regex(r"^نشر عام ([\s\S]+)$") & filters.user(DEVS), group=AZAN_GROUP + 8)
async def manual_custom(client, message: Message):
    text = message.matches[0].group(1)
    if not text:
        return await message.reply("**اكتب الرسالة بعد الأمر مباشرة**")
        
    status = await message.reply_text("جاري النشر العام...")
    
    do_pin = "-pin" in text
    clean_text = text.replace("-pin", "").strip()
    
    sent, failed, time_taken = await broadcast_core_engine(clean_text, is_pin=do_pin)
    
    await status.edit_text(
        f"**تم النشر العام بنجاح**\n\n"
        f"**النص:** {clean_text[:50]}...\n"
        f"**تثبيت:** {'نعم' if do_pin else 'لا'}\n"
        f"**المرسل:** {sent}\n"
        f"**الفشل:** {failed}\n"
        f"**الوقت:** {time_taken:.2f} ثانية"
    )
