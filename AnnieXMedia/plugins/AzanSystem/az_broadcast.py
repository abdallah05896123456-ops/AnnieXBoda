import asyncio
import random
from datetime import datetime
from pyrogram import filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait, InputUserDeactivated, UserIsBlocked, PeerIdInvalid

# استدعاء مكتبات السورس
from BrandrdXMusic import app

# استدعاء المتغيرات من ملف الإعدادات
from .az_conf import (
    AZAN_GROUP, 
    settings_db, 
    DEVS,
    CURRENT_DUA_STICKER
)

# --- [ 1. قوائم الرسائل (الصلاة على النبي & الأذكار) ] ---

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
    "رَبَّنَا آتِنَا فِي الدُّنْيَا حَسَنَةً وَفِي الآخِرَةِ حَسَنَةً وَقِنَا عَذَابَ النَّارِ 🤍"
]

JUMMAH_MESSAGES = [
    "إِنَّ اللَّهَ وَمَلَائِكَتَهُ يُصَلُّونَ عَلَى النَّبِيِّ.. أكثروا من الصلاة على الحبيب في يوم الجمعة 💙\nولا تنسوا قراءة سورة الكهف.",
    "جمعة مباركة.. لا تنسوا قراءة سورة الكهف والإكثار من الصلاة على النبي ﷺ 🤍",
    "في يوم الجمعة.. ساعة استجابة لا يوافقها عبد مسلم يدعو الله إلا استجاب له.. اذكروني بدعوة 💙",
    "نور الله قلبكم بذكره ورزقكم حبه وأعانكم على طاعته.. جمعة طيبة 🤍"
]

# --- [ 2. دالة النشر الأساسية (Core Function) ] ---

async def broadcast_message(text_message):
    """إرسال رسالة لجميع الجروبات المفعلة"""
    sent = 0
    failed = 0
    
    # جلب كل الجروبات المفعل فيها الأذان من الداتابيز
    async for doc in settings_db.find({"azan_active": True}):
        chat_id = doc.get("chat_id")
        if not chat_id: continue
        
        try:
            # إرسال الاستيكر إذا وجد
            if CURRENT_DUA_STICKER:
                try: await app.send_sticker(chat_id, CURRENT_DUA_STICKER)
                except: pass
            
            # إرسال النص
            await app.send_message(chat_id, f"<b>{text_message}</b>\n\n➻ sᴏᴜʀᴄᴇ : بُودَا | ʙᴏᴅَا")
            sent += 1
            await asyncio.sleep(0.8) # تأخير لتجنب الحظر
            
        except FloodWait as e:
            await asyncio.sleep(e.value)
            try: await app.send_message(chat_id, text_message)
            except: failed += 1
        except (InputUserDeactivated, UserIsBlocked, PeerIdInvalid):
            # تنظيف الداتابيز من الجروبات المحذوفة
            await settings_db.delete_one({"chat_id": chat_id})
            failed += 1
        except Exception:
            failed += 1
            
    return sent, failed

# --- [ 3. دوال الجدولة التلقائية ] ---

async def auto_send_random():
    """اختيار رسالة عشوائية (ذكر أو صلاة على النبي) وإرسالها"""
    # اختيار عشوائي: 50% أذكار - 50% صلاة على النبي
    if random.choice([True, False]):
        msg = random.choice(SALAWAT_LIST)
    else:
        msg = random.choice(BROADCAST_ATHKAR)
    
    await broadcast_message(msg)

async def auto_send_jummah():
    """إرسال رسائل خاصة بيوم الجمعة"""
    msg = random.choice(JUMMAH_MESSAGES)
    await broadcast_message(msg)

# يتم استدعاء هذه الدالة من ملف __init__ أو az_utils
def init_broadcast_schedule(scheduler):
    """ضبط مواعيد النشر التلقائي"""
    
    # 1. النشر في الأيام العادية (السبت إلى الخميس) - كل 9 ساعات
    # نختار ساعات محددة لضمان الانتظام: 9 صباحاً، 6 مساءً، 3 فجراً
    scheduler.add_job(
        lambda: asyncio.create_task(auto_send_random()),
        "cron",
        day_of_week='sat,sun,mon,tue,wed,thu',
        hour='3,9,18',
        minute=0
    )

    # 2. النشر يوم الجمعة - كل 3 ساعات (تكثيف)
    # الساعات: 0, 3, 6, 9, 15, 18, 21 (استثنينا 12 عشان صلاة الجمعة ليها رسالة خاصة)
    scheduler.add_job(
        lambda: asyncio.create_task(auto_send_random()),
        "cron",
        day_of_week='fri',
        hour='0,3,6,9,15,18,21',
        minute=0
    )

    # 3. تذكير صلاة الجمعة وسورة الكهف (الساعة 11:30 صباحاً بتوقيت القاهرة)
    scheduler.add_job(
        lambda: asyncio.create_task(auto_send_jummah()),
        "cron",
        day_of_week='fri',
        hour=11,
        minute=30
    )

# --- [ 4. أوامر النشر اليدوية للمطورين ] ---

@app.on_message(filters.regex(r"^(نشر الصلاة علي النبي|نشر الصلاه علي النبي)$") & filters.user(DEVS), group=AZAN_GROUP + 6)
async def broadcast_salawat(client, message: Message):
    """نشر صيغة صلاة على النبي عشوائية لكل الجروبات يدوياً"""
    status = await message.reply_text("جاري نشر الصلاة على النبي في جميع المجموعات...")
    
    selected_salawat = random.choice(SALAWAT_LIST)
    sent, failed = await broadcast_message(selected_salawat)
    
    await status.edit_text(
        f"✅ <b>تم النشر بنجاح!</b>\n\n"
        f"• تم الإرسال إلى: {sent} مجموعة\n"
        f"• فشل الإرسال إلى: {failed} مجموعة"
    )

@app.on_message(filters.regex(r"^(نشر ذكر|نشر اذكار|نشر أذكار)$") & filters.user(DEVS), group=AZAN_GROUP + 7)
async def broadcast_athkar(client, message: Message):
    """نشر ذكر عشوائي لكل الجروبات يدوياً"""
    status = await message.reply_text("جاري نشر تذكير بالأذكار في جميع المجموعات...")
    
    selected_thikr = random.choice(BROADCAST_ATHKAR)
    sent, failed = await broadcast_message(selected_thikr)
    
    await status.edit_text(
        f"✅ <b>تم نشر الأذكار بنجاح!</b>\n\n"
        f"• تم الإرسال إلى: {sent} مجموعة\n"
        f"• فشل الإرسال إلى: {failed} مجموعة"
    )

@app.on_message(filters.regex(r"^نشر عام ([\s\S]+)$") & filters.user(DEVS), group=AZAN_GROUP + 8)
async def broadcast_custom(client, message: Message):
    """نشر رسالة مخصصة يكتبها المطور"""
    text = message.matches[0].group(1) # استخراج النص بعد كلمة "نشر عام"
    
    if not text:
        return await message.reply("اكتب الرسالة التي تريد نشرها بعد الأمر.")
        
    status = await message.reply_text("جاري نشر رسالتك المخصصة...")
    
    sent, failed = await broadcast_message(text)
    
    await status.edit_text(
        f"✅ <b>تم النشر العام بنجاح!</b>\n\n"
        f"• النص: {text[:50]}...\n"
        f"• تم الإرسال إلى: {sent} مجموعة\n"
        f"• فشل الإرسال إلى: {failed} مجموعة"
    )
