# Authored By Certified Coders © 2026
# AnnieX Core - Extreme Detailed Edition
# Features: Ultra-Long Responses, Vision, Multi-Provider Failover, No-Prefix

import asyncio, os, time, re
from pyrogram import filters, enums
from pyrogram.types import Message
from g4f.client import AsyncClient
from g4f.Provider import DuckDuckGo, Blackbox, Bing, You, Liaobots

from AnnieXMedia import app
import config

# --- الإعدادات الفنية ---
SUDO_USERS = config.OWNER_ID if isinstance(config.OWNER_ID, list) else [config.OWNER_ID]
AI_STATUS = True
LIMIT_STATUS = True
DAILY_LIMIT = 100 
AI_GROUP = 20 # الأولوية المثالية لعدم التعارض

# مخازن البيانات
context, counter = {}, {}
unlocked_users, continuous_mode = set(), set()
client_ai = AsyncClient()

# --- محرك المعالجة العميق (Logic Core) ---
async def process_ai_request(u_id, prompt, img=None):
    if u_id not in context: context[u_id] = []
    
    # التعليمات البرمجية لإجبار البوت على التطويل والتفصيل
    system_instruction = (
        "أنت نظام ذكاء اصطناعي فائق التطور مدمج داخل سورس AnnieXMedia. "
        "يجب أن تكون إجاباتك مطولة جداً، مفصلة، وشاملة لكل جوانب الموضوع. "
        "استخدم لغة عربية قوية أو عامية مصرية ذكية حسب السياق، "
        "وفي حال وجود صور، قم بتحليل كل سنتي فيها بدقة متناهية."
    )
    
    msgs = [{"role": "system", "content": system_instruction}] + \
           context[u_id] + [{"role": "user", "content": prompt}]
    
    # نظام الـ Failover (اللف على 5 مزودين لضمان عدم الفشل)
    for provider in [DuckDuckGo, Blackbox, Bing, You, Liaobots]:
        try:
            res = await client_ai.chat.completions.create(
                model="gpt-4o",
                messages=msgs,
                provider=provider,
                image=open(img, "rb") if img else None,
                timeout=15 # زيادة الوقت للسماح بالردود الطويلة
            )
            out = res.choices[0].message.content.strip()
            
            # حفظ السياق (زيادة الذاكرة لـ 10 رسائل لتعميق المحادثة)
            context[u_id] = (context[u_id] + [{"role":"user","content":prompt}, {"role":"assistant","content":out}])[-10:]
            return out
        except: continue
    return None

# --- أوامر التحكم (بدون بادئة) ---
@app.on_message(filters.regex(r"^(قفل|فتح) الذكاء$") & filters.user(SUDO_USERS))
async def ctrl_ai(_, m: Message):
    global AI_STATUS
    AI_STATUS = "فتح" in m.text
    await m.reply(f"**تم {'تفعيل' if AI_STATUS else 'تعطيل'} المحرك بنجاح.**")

@app.on_message(filters.regex(r"^ليمت (\d+)$") & filters.user(SUDO_USERS))
async def set_lim(_, m: Message):
    global DAILY_LIMIT
    DAILY_LIMIT = int(m.matches[0].group(1))
    await m.reply(f"**تم تحديث حد الاستخدام اليومي إلى: {DAILY_LIMIT}**")

@app.on_message(filters.regex(r"^تنظيف الذاكرة$") & filters.user(SUDO_USERS))
async def purge_ctx(_, m: Message):
    context.clear()
    await m.reply("**تم تنظيف ذاكرة النظام بالكامل.**")

@app.on_message(filters.regex(r"^(تصفير|مسح)$") & filters.private)
async def reset_user(_, m: Message):
    context.pop(m.from_user.id, None)
    await m.reply("**تم مسح سجل محادثاتك بنجاح.**")

# --- المعالج المركزي (Main Handler) ---
@app.on_message((filters.text | filters.photo) & ~filters.bot, group=AI_GROUP)
async def core_ai_handler(bot, m: Message):
    if not AI_STATUS and m.from_user.id not in SUDO_USERS: return
    
    uid, raw = m.from_user.id, (m.text or m.caption or "")
    
    # كشف البادئة بمرونة عالية
    match = re.match(r"^(ذكاء|ai|شات|بوت|bot)(\s|$)", raw, re.IGNORECASE)
    if not match and uid not in continuous_mode: return

    # فحص ليمت الاستخدام اليومي
    now = time.time()
    counter[uid] = [t for t in counter.get(uid, []) if now - t < 86400]
    if LIMIT_STATUS and len(counter[uid]) >= DAILY_LIMIT and uid not in SUDO_USERS:
        return await m.reply("**لقد تخطيت حدك اليومي من الأسئلة.**")

    prompt = raw[match.end():].strip() if match else raw
    if not prompt and not m.photo: return

    # تحميل الميديا والمعالجة
    path = await m.download() if m.photo else None
    await bot.send_chat_action(m.chat.id, enums.ChatAction.TYPING)
    
    status_msg = await m.reply("**جاري التفكير بعمق...**")
    start_time = time.time()
    
    ans = await process_ai_request(uid, prompt, path)
    
    if path: os.remove(path)
    
    if ans:
        counter[uid].append(time.time())
        speed = round(time.time() - start_time, 1)
        # تنسيق الرد النهائي
        await status_msg.edit(f"{ans}\n\n⏱ `{speed}s` | **AnnieX-Core**")
    else:
        await status_msg.edit("**فشل المحرك في توليد رد، يرجى المحاولة مرة أخرى.**")
