# Authored By Certified Coders 2026
# Module: Auto Leave Background Tasks (Misc)

import asyncio
from datetime import datetime
from pyrogram.enums import ChatType

import config
from AnnieXMedia import app
from AnnieXMedia.core.call import StreamController, autoend
from AnnieXMedia.utils.database import get_client, is_active_chat, is_autoend

# ─── وظيفة المغادرة التلقائية (Background Task) ────────────────

async def auto_leave():
    """وظيفة تعمل في الخلفية لفحص المجموعات والمغادرة منها"""
    while True:
        if config.AUTO_LEAVING_ASSISTANT:
            from AnnieXMedia.core.userbot import assistants
            for num in assistants:
                client = await get_client(num)
                left = 0
                try:
                    async for i in client.get_dialogs():
                        if i.chat.type in [ChatType.SUPERGROUP, ChatType.GROUP, ChatType.CHANNEL]:
                            # استثناء مجموعة السجل (Logger)
                            if i.chat.id != config.LOGGER_ID:
                                
                                # مغادرة 20 مجموعة في الدورة الواحدة لتجنب الحظر
                                if left == 20:
                                    break 
                                    
                                # المغادرة إذا لم تكن هناك مكالمة نشطة
                                if not await is_active_chat(i.chat.id):
                                    try:
                                        await client.leave_chat(i.chat.id)
                                        left += 1
                                        await asyncio.sleep(1) # تأخير بسيط بين كل مغادرة
                                    except:
                                        continue
                except:
                    pass
        # إعادة الفحص كل ساعة (أو حسب المحدد في الكونفج)
        await asyncio.sleep(config.AUTO_LEAVE_ASSISTANT_TIME or 3600)

# تشغيل المهمة فوراً عند بدء البوت
asyncio.create_task(auto_leave())


# ─── وظيفة إنهاء التشغيل عند خلو الكول ────────────────────────

async def auto_end():
    """وظيفة لإنهاء البث إذا كان الكول فارغاً لفترة محددة"""
    while not await asyncio.sleep(5):
        ender = await is_autoend()
        if not ender:
            continue
        for chat_id in autoend:
            timer = autoend.get(chat_id)
            if not timer:
                continue
            if datetime.now() > timer:
                if not await is_active_chat(chat_id):
                    autoend[chat_id] = {}
                    continue
                autoend[chat_id] = {}
                try:
                    await StreamController.stop_stream(chat_id)
                except:
                    continue
                try:
                    await app.send_message(
                        chat_id,
                        "تم انهاء التشغيل تلقائيا لعدم وجود مستمعين في المكالمة الصوتية.",
                    )
                except:
                    continue

# تشغيل المهمة فوراً عند بدء البوت
asyncio.create_task(auto_end())
