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

# الاعدادات الفنية
SUDO_USERS = config.OWNER_ID if isinstance(config.OWNER_ID, list) else [config.OWNER_ID]
AI_STATUS = True
LIMIT_STATUS = True
DAILY_LIMIT = 100
AI_GROUP = 30 

context, counter = {}, {}
client_ai = AsyncClient()

def get_active_providers():
    # التحقق من وجود المزودين داخل المكتبة قبل استخدامهم
    target = ["DuckDuckGo", "Blackbox", "Bing", "You", "Liaobots", "OpenaiChat"]
    available = []
    for name in target:
        p_class = getattr(Providers, name, None)
        if p_class:
            available.append(p_class)
    return available

async def process_ai_logic(u_id, prompt, img=None):
    if u_id not in context:
        context[u_id] = []
    
    # تعليمات اجبار الرد المطول والمفصل
    system_instruction = (
        "انت نظام ذكاء اصطناعي فائق التطور. "
        "يجب ان تكون اجاباتك مطولة جدا ومفصلة وشاملة لكل جوانب الموضوع مع تقديم شرح تقني وافي. "
        "استخدم لغة عربية قوية او عامية مصرية ذكية حسب السياق. "
        "في حال تزويدك بصور قم بتحليل كل سنتيمتر فيها واستخرج كافة التفاصيل."
    )
    
    msgs = [{"role": "system", "content": system_instruction}] + \
           context[u_id] + [{"role": "user", "content": prompt}]
    
    active_providers = get_active_providers()
    
    for provider in active_providers:
        try:
            res = await client_ai.chat.completions.create(
                model="gpt-4o",
                messages=msgs,
                provider=provider,
                image=open(img, "rb") if img else None,
                timeout=25 
            )
            out = res.choices[0].message.content.strip()
            # حفظ اخر 10 رسائل لتعميق المحادثة
            context[u_id] = (context[u_id] + [{"role":"user","content":prompt}, {"role":"assistant","content":out}])[-10:]
            return out
        except:
            continue
    return None

@app.on_message(filters.regex(r"^(قفل|فتح) الذكاء$") & filters.user(SUDO_USERS))
async def ai_toggle_engine(_, m: Message):
    global AI_STATUS
    AI_STATUS = "فتح" in m.text
    await m.reply(f"تم {'تفعيل' if AI_STATUS else 'تعطيل'} محرك المعالجة بنجاح.")

@app.on_message(filters.regex(r"^تنظيف الذاكرة$") & filters.user(SUDO_USERS))
async def clear_ai_cache(_, m: Message):
    context.clear()
    await m.reply("تم تنظيف ذاكرة الرام لجميع العمليات.")

@app.on_message((filters.text | filters.photo) & ~filters.bot, group=AI_GROUP)
async def ai_main_handler(bot, m: Message):
    if not AI_STATUS and m.from_user.id not in SUDO_USERS: return
    
    uid, raw = m.from_user.id, (m.text or m.caption or "")
    match = re.match(r"^(ذكاء|ai|شات|بوت|bot)(\s|$)", raw, re.IGNORECASE)
    if not match: return

    now = time.time()
    counter[uid] = [t for t in counter.get(uid, []) if now - t < 86400]
    if LIMIT_STATUS and len(counter[uid]) >= DAILY_LIMIT and uid not in SUDO_USERS:
        return await m.reply("لقد تخطيت الحد المسموح به للاستخدام اليومي.")

    prompt = raw[match.end():].strip() if match else raw
    if not prompt and not m.photo: return

    path = await m.download() if m.photo else None
    await bot.send_chat_action(m.chat.id, enums.ChatAction.TYPING)
    
    status_msg = await m.reply("جاري معالجة طلبك وتحليله بعمق يرجى الانتظار.")
    start_t = time.time()
    
    ans = await process_ai_logic(uid, prompt, path)
    if path: os.remove(path)
        
    if ans:
        counter[uid].append(time.time())
        await status_msg.edit(f"{ans}\n\nسرعة المعالجة: {round(time.time()-start_t, 1)} ثانية")
    else:
        await status_msg.edit("نعتذر منك ولكن المحرك لا يستجيب حاليا يرجى المحاولة لاحقا.")
