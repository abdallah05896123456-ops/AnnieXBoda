# تم التطوير بواسطة الزملاء المبرمجين 2026
# نظام المعالجة الذكي - نسخة الاستقرار الفائق
# مخصص لـ Fly.io | أداء نووي متوافق مع 16 نواة

import asyncio
import os
import time
import re
import g4f.Provider as Providers
from pyrogram import filters, enums
from pyrogram.types import Message
from g4f.client import AsyncClient

from AnnieXMedia import app
import config
from config import OWNER_ID, AI_HANDLER_GROUP, AI_API_KEY

# --- الإعدادات وصلاحيات الوصول ---
SUDO_USERS = OWNER_ID if isinstance(OWNER_ID, list) else [OWNER_ID]
AI_STATUS = True
LIMIT_STATUS = True
DAILY_LIMIT = 100
AI_MODE = "عام" 

# الذاكرة المؤقتة (الرام)
context = {}
counter = {}
PERMANENT_USERS = set() 
client_ai = AsyncClient()

def get_provider(name):
    """جلب المزود برمجياً لضمان استقرار التشغيل"""
    return getattr(Providers, name, None)

async def process_ai_logic(u_id, prompt, img=None):
    if u_id not in context:
        context[u_id] = []
    
    # مصفوفة المزودين (الأولوية لـ OpenAI الرسمي)
    p_list = [
        get_provider("OpenaiChat") or get_provider("Openai"),
        get_provider("Liaobots"),
        get_provider("Blackbox"),
        get_provider("DuckDuckGo")
    ]
    
    # تحديد نبرة الصوت (فصحى راقية)
    instruction = "أنت مساعد ذكي متمكن، قدم إجابات مطولة وهادئة باللغة العربية الفصحى."
    if AI_MODE == "تقني":
        instruction = "أنت خبير برمجيات محترف، قدم تحليلات هندسية دقيقة ومفصلة بالفصحى."

    msgs = [{"role": "system", "content": instruction}] + \
           context[u_id] + [{"role": "user", "content": prompt}]
    
    image_data = open(img, "rb").read() if img else None
    
    for p in p_list:
        if not p: continue
        try:
            # مهلة زمنية 25 ثانية لضمان سرعة الاستجابة
            res = await asyncio.wait_for(
                client_ai.chat.completions.create(
                    model="gpt-4o",
                    messages=msgs,
                    api_key=AI_API_KEY, # يسحب من GPT_4 في السكرتس
                    provider=p,
                    image=image_data
                ),
                timeout=25
            )
            if res and res.choices:
                out = res.choices[0].message.content.strip()
                context[u_id] = (context[u_id] + [{"role":"user","content":prompt}, {"role":"assistant","content":out}])[-12:]
                return out
        except:
            continue
    return None

# --- لوحة تحكم المطور (Owner Only) ---

@app.on_message(filters.regex(r"^(قفل الذكاء|فتح الذكاء)$") & filters.user(SUDO_USERS))
async def toggle_ai_engine(_, m: Message):
    global AI_STATUS
    AI_STATUS = "فتح" in m.text
    await m.reply_text(f"تم تنفيذ أمر {'تفعيل' if AI_STATUS else 'تعطيل'} نظام الذكاء الاصطناعي بنجاح.")

@app.on_message(filters.regex(r"^(قفل الليمت|فتح الليمت)$") & filters.user(SUDO_USERS))
async def toggle_limit_logic(_, m: Message):
    global LIMIT_STATUS
    LIMIT_STATUS = "فتح" in m.text
    await m.reply_text(f"تم {'تشغيل' if LIMIT_STATUS else 'إيقاف'} نظام الرقابة على حدود الاستهلاك.")

@app.on_message(filters.regex(r"^وضع ليميت (\d+)$") & filters.user(SUDO_USERS))
async def update_limit_value(_, m: Message):
    global DAILY_LIMIT
    DAILY_LIMIT = int(m.matches[0].group(1))
    await m.reply_text(f"تم ضبط سقف الاستخدام اليومي عند {DAILY_LIMIT} رسالة.")

@app.on_message(filters.regex(r"^(قفل الذكاء الدائم|فتح الذكاء الدائم)$") & filters.user(SUDO_USERS))
async def permanent_ai_control(_, m: Message):
    if not m.reply_to_message:
        return await m.reply_text("يرجى الرد على رسالة الشخص المطلوب.")
    target_id = m.reply_to_message.from_user.id
    if "فتح" in m.text:
        PERMANENT_USERS.add(target_id)
        await m.reply_text(f"تم تفعيل ميزة الذكاء الدائم للمستخدم: {target_id}.")
    else:
        PERMANENT_USERS.discard(target_id)
        await m.reply_text(f"تم إلغاء ميزة الذكاء الدائم للمستخدم: {target_id}.")

@app.on_message(filters.regex(r"^تغيير المود (تقني|عام)$") & filters.user(SUDO_USERS))
async def switch_ai_mode(_, m: Message):
    global AI_MODE
    AI_MODE = m.matches[0].group(1)
    await m.reply_text(f"تم تحويل نمط الردود إلى: {AI_MODE}.")

@app.on_message(filters.regex(r"^تنظيف الذاكرة$") & filters.user(SUDO_USERS))
async def clear_cache(_, m: Message):
    context.clear(); counter.clear()
    await m.reply_text("تم تطهير سجلات المعالجة والذاكرة المؤقتة.")

# --- المعالج الرئيسي الفعال ---

@app.on_message((filters.text | filters.photo) & ~filters.bot, group=AI_HANDLER_GROUP)
async def ai_master_handler(bot, m: Message):
    if not AI_STATUS and m.from_user.id not in SUDO_USERS: return
    
    uid, raw = m.from_user.id, (m.text or m.caption or "")
    is_perm = uid in PERMANENT_USERS
    match = re.match(r"^(ذكاء|بقولك)(\s|$)", raw, re.IGNORECASE)
    
    if not is_perm and not match: return

    prompt = raw[match.end():].strip() if (match and not is_perm) else raw
    if not prompt and not m.photo: prompt = "استمر في الحديث"

    # تدقيق الليميت
    now = time.time()
    if uid not in counter: counter[uid] = []
    counter[uid] = [t for t in counter[uid] if now - t < 86400]
    if LIMIT_STATUS and len(counter[uid]) >= DAILY_LIMIT and uid not in SUDO_USERS:
        return await m.reply_text(f"لقد استنفدت حصتك اليومية المحددة بـ {DAILY_LIMIT} رسالة.")

    path = await m.download() if m.photo else None
    await bot.send_chat_action(m.chat.id, enums.ChatAction.TYPING)
    
    # إرسال رسالة الانتظار أولاً
    status_msg = await m.reply_text("جـاري التفـكـير ...", quote=True)
    
    ans = await process_ai_logic(uid, prompt, path)
    if path: os.remove(path)
        
    if ans:
        counter[uid].append(time.time())
        await status_msg.edit(ans) # التعديل بالرد النهائي
    else:
        await status_msg.edit("نعتذر، المحرك لا يستجيب حالياً. يرجى إعادة المحاولة لاحقاً.")
