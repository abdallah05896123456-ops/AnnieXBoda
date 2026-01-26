# Authored By Certified Coders © 2026
# TITAN AI SYSTEM - AnnieXMedia PREMIUM EDITION
# Features: Vision, Continuous Chat, Global/User Limit Controls, No-Prefix Commands

import asyncio
import os
import time
import re
from pyrogram import filters, enums
from pyrogram.types import Message
from g4f.client import AsyncClient
import config

# ==========================================================
# الإعـدادات الـتـقـنـيـة والـمـتـغـيـرات الـعـالـمـيـة
# ==========================================================

# جلب أيدي المطور من الكونفنج
OWNER_ID = config.OWNER_ID[0] if isinstance(config.OWNER_ID, list) else config.OWNER_ID

# حالات النظام البرمجية
AI_STATUS = True        # حالة نظام الذكاء العام
LIMIT_STATUS = True     # حالة نظام القيود اليومية
DAILY_LIMIT = 40        # الحد الأقصى المسموح به للمستخدم العادي

# مخازن البيانات الرقمية (تعتمد على RAM Disk لسرعة المعالجة)
user_context = {}         # حفظ سياق المحادثات لضمان الفهم المستمر
usage_counter = {}        # تتبع عدد الاستخدامات لكل هوية رقمية
permanent_users = set()   # قائمة المستخدمين في وضع الاستجابة المستمرة
unlocked_users = set()    # المستخدمين المستثنين من القيود اليومية يدوياً

# تهيئة المحرك البرمجي للذكاء الاصطناعي
ai_engine = AsyncClient()

# ==========================================================
# دالات الـمـنـطـق والـتـحـقـق مـن الـقـيـود
# ==========================================================

def is_user_limited(user_id):
    """التحقق البرمجي من تجاوز المستخدم للحد المسموح به"""
    if user_id == OWNER_ID or user_id in unlocked_users:
        return False
    
    if not LIMIT_STATUS:
        return False
        
    now_timestamp = time.time()
    if user_id not in usage_counter:
        usage_counter[user_id] = []
        
    # تطهير السجلات القديمة التي تجاوزت دورة الـ 24 ساعة
    usage_counter[user_id] = [t for t in usage_counter[user_id] if now_timestamp - t < 86400]
    
    return len(usage_counter[user_id]) >= DAILY_LIMIT

def update_usage_record(user_id):
    """تسجيل عملية استخدام جديدة في قاعدة بيانات الرام"""
    if user_id != OWNER_ID and user_id not in unlocked_users:
        if user_id not in usage_counter:
            usage_counter[user_id] = []
        usage_counter[user_id].append(time.time())

async def fetch_ai_logic(user_id, prompt, image_data=None):
    """المحرك الرئيسي لعمليات المعالجة العصبية (نص + رؤية)"""
    if user_id not in user_context:
        user_context[user_id] = []
        
    # بناء هيكل الرسالة البرمجية
    input_message = [{"role": "user", "content": prompt}]
    system_instruction = (
        "أنت نظام ذكاء اصطناعي فائق التطور مدمج داخل سورس AnnieXMedia. "
        "يجب أن تكون إجاباتك مطولة، دقيقة، وباللغة العربية الفصحى أو العامية المصرية الذكية. "
        "في حال تزويدك بصورة، قم بتحليلها بدقة متناهية واستخرج منها كافة التفاصيل."
    )
    
    try:
        # طلب المعالجة من موديل GPT-4o المتطور
        execution = await ai_engine.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": system_instruction}] + user_context[user_id] + input_message,
            image=open(image_data, "rb") if image_data else None
        )
        
        result_text = execution.choices[0].message.content.strip()
        
        # إدارة الذاكرة الدورية (حفظ آخر 10 تفاعلات لضمان استمرارية السياق)
        user_context[user_id].append({"role": "user", "content": prompt})
        user_context[user_id].append({"role": "assistant", "content": result_text})
        user_context[user_id] = user_context[user_id][-10:]
        
        return result_text
    except Exception as error_log:
        print(f"Critical AI Engine Error: {error_log}")
        return None

# ==========================================================
# أوامـر الـتـحـكـم والـسـيـطـرة (لـلـمـطـور فـقـط)
# ==========================================================

# أوامر بدون بادئة باستخدام Regex
@app.on_message(filters.regex(r"^(قفل الذكاء|تعطيل الذكاء)$") & filters.user(OWNER_ID))
async def cmd_lock_ai_global(_, message: Message):
    global AI_STATUS
    AI_STATUS = False
    await message.reply_text("تـم إيـقـاف وتـعـطـيل مـحـرك الـذكـاء الاصـطـنـاعـي بـشـكـل كـلـي مـن قـبـل الـمـطـور الـمـسـؤول.")

@app.on_message(filters.regex(r"^(فتح الذكاء|تفعيل الذكاء)$") & filters.user(OWNER_ID))
async def cmd_unlock_ai_global(_, message: Message):
    global AI_STATUS
    AI_STATUS = True
    await message.reply_text("تـم تـفـعـيل ونـشـر مـحـرك الـذكـاء الاصـطـنـاعـي بـشـكـل كـلـي لـجـمـيـع الـمـسـتـخـدمـيـن.")

@app.on_message(filters.regex(r"^(قفل الليمت|تفعيل القيود)$") & filters.user(OWNER_ID))
async def cmd_lock_limit_global(_, message: Message):
    global LIMIT_STATUS
    LIMIT_STATUS = True
    await message.reply_text("تـم تـفـعـيل نـظـام الـقـيـود والـحـدود الـيـومـيـة لـجـمـيـع الـمـسـتـخـدمـيـن.")

@app.on_message(filters.regex(r"^(فتح الليمت|تعطيل القيود)$") & filters.user(OWNER_ID))
async def cmd_unlock_limit_global(_, message: Message):
    global LIMIT_STATUS
    LIMIT_STATUS = False
    await message.reply_text("تـم إلـغـاء وتـعـطـيل نـظـام الـقـيـود الـيـومـيـة، الـذكـاء الآن مـتـاح لـلـجـمـيـع بـدون حـدود.")

@app.on_message(filters.regex(r"^(فتح ليمت)$") & filters.user(OWNER_ID))
async def cmd_grant_access(_, message: Message):
    if not message.reply_to_message:
        return await message.reply_text("يـجـب الـرد عـلـى رسـالـة الـمـسـتـخـدم الـمـراد مـنـحـه الـصـلاحـيـات لـتـنـفـيذ هـذا الأمـر.")
    
    target_uid = message.reply_to_message.from_user.id
    unlocked_users.add(target_uid)
    await message.reply_text(f"تـم مـنـح الـمـسـتـخـدم ذو الأيـدي {target_uid} صـلاحـيـة الـوصـول الـدائم بـدون قـيـود.")

# ==========================================================
# أوامـر الـمـسـتـخـدمـيـن والـوظـائف الـعـامـة
# ==========================================================

@app.on_message(filters.regex(r"^(مسح|تصفير)$") & filters.private)
async def cmd_clear_history(_, message: Message):
    uid = message.from_user.id
    if uid in user_context:
        user_context[uid] = []
    await message.reply_text("تـم تـصـفـيـر ذاكرة الـمـحـادثـة الـخـاصـة بـك والـبـدء مـن نـقـطـة الـصـفـر.")

@app.on_message(filters.regex(r"^(ذكاء دائم)$"))
async def cmd_toggle_permanent(_, message: Message):
    if not AI_STATUS and message.from_user.id != OWNER_ID:
        return
    
    uid = message.from_user.id
    if uid in permanent_users:
        permanent_users.remove(uid)
        await message.reply_text("تـم إيـقـاف وضـع الاسـتـجـابة الـمـسـتـمـرة، سـأرد الآن فـقـط عـنـد اسـتـخـدام الأوامـر.")
    else:
        permanent_users.add(uid)
        await message.reply_text("تـم تـفـعـيل وضـع الاسـتـجـابة الـمـسـتـمـرة، سـأقـوم بـالـرد عـلـى كـل رسـائـلـك تـلـقـائـيـاً.")

# ==========================================================
# الـمـعـالـج الـمركـزي والـتـفـاعـل الـذكـي
# ==========================================================

@app.on_message((filters.text | filters.photo) & ~filters.bot)
async def main_engine_handler(client, message: Message):
    global AI_STATUS
    
    # التحقق من حالة النظام العامة
    if not AI_STATUS and message.from_user.id != OWNER_ID:
        return

    uid = message.from_user.id
    cid = message.chat.id
    
    # تحليل محتوى الرسالة وتحديد البادئات بدون اسلاش
    raw_text = message.text or message.caption or ""
    
    # فحص الأوامر
    is_chat_cmd = raw_text.startswith(("شات ", "ذكاء ", "ai "))
    is_ai_active = uid in permanent_users
    
    # الخروج في حال عدم وجود مبرر للرد
    if not is_chat_cmd and not is_ai_active:
        return
        
    # التحقق من قيود الاستخدام اليومي
    if is_user_limited(uid):
        return await message.reply_text("تـم تـخـطـي الـحـد الأقـصـى لـاسـتـخـدام أداة الـذكـاء الاصـطـنـاعـي لـهـذا الـيـوم.")

    # معالجة النص البرومبت
    if is_chat_cmd:
        # استخراج السؤال بعد كلمة "شات" أو "ذكاء"
        prompt_content = raw_text.split(None, 1)[1] if " " in raw_text else "ماذا يمكنني أن أفعل لك؟"
    else:
        prompt_content = raw_text if raw_text else "حلل المحتوى المرفق"

    # معالجة الوسائط المتعددة (Vision Logic)
    media_file = None
    if message.photo:
        loading_msg = await message.reply_text("جـاري تـحـمـيـل الـمـيـديـا الـمـرفـقـة لـلـمـعـالـجـة...")
        media_file = await message.download()
        await loading_msg.delete()

    # تفعيل وضع الكتابة البصري
    await client.send_chat_action(cid, enums.ChatAction.TYPING)
    processing_msg = await message.reply_text("جـاري الـتـفـكـيـر")

    # استدعاء محرك الذكاء الاصطناعي
    final_output = await fetch_ai_logic(uid, prompt_content, media_file)
    
    # تنظيف المخلفات الرقمية من السيرفر
    if media_file and os.path.exists(media_file):
        os.remove(media_file)

    # تسليم النتيجة النهائية
    if final_output:
        update_usage_record(uid)
        await processing_msg.edit(f"{final_output}\n\nAnnieXMedia AI System")
    else:
        await processing_msg.edit("نـعـتـذر، فـشـل الـمـحـرك فـي جـلـب الـرد، يـرجـى الـمـحـاولة لاحـقـاً.")

# ==========================================================
# نـهـايـة الـمـلـف الـبـرمـجـي - AnnieXMedia
# ==========================================================
