# Authored By Certified Coders 2026
# AnnieX AI Core - Production Edition
# Optimized for Fly.io Secrets | official API Integration

import asyncio
import os
import time
import re
from pyrogram import filters, enums
from pyrogram.types import Message
from g4f.client import AsyncClient
from g4f.Provider import Openai, Liaobots, Blackbox, DuckDuckGo, RetryProvider

from AnnieXMedia import app
import config

# الاعدادات الفنية والتحكم في الموارد
SUDO_USERS = config.OWNER_ID if isinstance(config.OWNER_ID, list) else [config.OWNER_ID]
AI_STATUS = True
AI_GROUP = 30 

context = {}

# تهيئة العميل بنظام المحاولات المتعددة
# يتم وضع Openai في المقدمة لاستخدام مفتاح GPT_4
client_ai = AsyncClient(
    provider=RetryProvider([Openai, Liaobots, Blackbox, DuckDuckGo], shuffle=False)
)

async def process_ai_logic(u_id, prompt, img=None):
    if u_id not in context:
        context[u_id] = []
    
    # جلب المفتاح من سكرت Fly.io
    api_key = os.getenv("GPT_4")
    
    # تعليمات فرض الرد التقني المطول والمباشر لغويا
    system_instruction = (
        "تعامل كمساعد تقني محترف ومباشر. "
        "قدم اجابات مطولة تشمل كافة جوانب السؤال بلغة تقنية مختصره وفصحى. "
        "حلل الصور بدقة واستخرج كافة البيانات التقنية المتاحة."
    )
    
    msgs = [{"role": "system", "content": system_instruction}] + \
           context[u_id] + [{"role": "user", "content": prompt}]
    
    # معالجة بيانات الصورة إن وجدت
    image_data = open(img, "rb").read() if img else None
    
    try:
        res = await client_ai.chat.completions.create(
            model="gpt-4o",
            messages=msgs,
            api_key=api_key,
            image=image_data,
            timeout=30
        )
        if res and res.choices:
            out = res.choices[0].message.content.strip()
            # حفظ السياق لتعميق المحادثة
            context[u_id] = (context[u_id] + [{"role":"user","content":prompt}, {"role":"assistant","content":out}])[-10:]
            return out
    except Exception as e:
        print(f"AI Logic Error: {e}")
    return None

@app.on_message((filters.text | filters.photo) & ~filters.bot, group=AI_GROUP)
async def ai_main_handler(bot, m: Message):
    if not AI_STATUS and m.from_user.id not in SUDO_USERS:
        return
    
    uid, raw = m.from_user.id, (m.text or m.caption or "")
    match = re.match(r"^(ذكاء|ai|شات|بوت|bot|يا ذكاء)(\s|$)", raw, re.IGNORECASE)
    if not match:
        return

    prompt = raw[match.end():].strip() if match else raw
    if not prompt and not m.photo:
        return

    path = await m.download() if m.photo else None
    await bot.send_chat_action(m.chat.id, enums.ChatAction.TYPING)
    
    status_msg = await m.reply("يتم الان معالجة الطلب")
    start_t = time.time()
    
    ans = await process_ai_logic(uid, prompt, path)
    if path:
        os.remove(path)
        
    if ans:
        await status_msg.edit(f"{ans}\n\nزمن المعالجة: {round(time.time()-start_t, 1)} ثانية")
    else:
        await status_msg.edit("نعتذر منك ولكن المحرك لا يستجيب حاليا.")
