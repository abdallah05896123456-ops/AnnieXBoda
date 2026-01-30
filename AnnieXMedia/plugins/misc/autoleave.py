# Authored By Certified Coders © 2025
import asyncio
from datetime import datetime

from pyrogram import filters
from pyrogram.enums import ChatType
from pyrogram.types import Message

import config
from AnnieXMedia import app
from AnnieXMedia.core.call import StreamController, autoend
from AnnieXMedia.utils.database import get_client, is_active_chat, is_autoend

# متغير للتحكم في حالة المغادرة (الافتراضي: متوقف)
AUTO_LEAVE_STATE = False

async def auto_leave():
    # نستخدم المتغير global للوصول لحالة التشغيل
    global AUTO_LEAVE_STATE
    
    if config.AUTO_LEAVING_ASSISTANT:
        while not await asyncio.sleep(config.AUTO_LEAVE_ASSISTANT_TIME):
            # إذا كانت المغادرة متوقفة، تخطي الدورة الحالية
            if not AUTO_LEAVE_STATE:
                continue

            from AnnieXMedia.core.userbot import assistants

            for num in assistants:
                client = await get_client(num)
                left = 0
                try:
                    async for i in client.get_dialogs():
                        if i.chat.type in [
                            ChatType.SUPERGROUP,
                            ChatType.GROUP,
                            ChatType.CHANNEL,
                        ]:
                            if (
                                i.chat.id != config.LOGGER_ID
                                and i.chat.id != -1002077986660
                                and i.chat.id != -1002166290494
                            ):
                                if left == 20:
                                    continue
                                if not await is_active_chat(i.chat.id):
                                    try:
                                        await client.leave_chat(i.chat.id)
                                        left += 1
                                    except:
                                        continue
                except:
                    pass


asyncio.create_task(auto_leave())


async def auto_end():
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
                    # تم التعريب وإزالة الايموجي
                    await app.send_message(
                        chat_id,
                        "قام البوت بمغادرة المحادثة الصوتية تلقائيا لعدم وجود مستمعين",
                    )
                except:
                    continue


asyncio.create_task(auto_end())


# ==========================================
# أوامر التحكم في المغادرة التلقائية
# ==========================================

# أمر التفعيل
@app.on_message(filters.command(["تفعيل المغادرة", "شغل المغادرة"], prefixes="") & filters.user(config.OWNER_ID))
async def enable_auto_leave(client, message: Message):
    global AUTO_LEAVE_STATE
    if AUTO_LEAVE_STATE:
        await message.reply_text("المغادرة التلقائية مفعلة بالفعل")
    else:
        AUTO_LEAVE_STATE = True
        await message.reply_text("تم تفعيل المغادرة التلقائية للمساعد")

# أمر الإيقاف
@app.on_message(filters.command(["ايقاف المغادرة", "وقف المغادرة", "تعطيل المغادرة"], prefixes="") & filters.user(config.OWNER_ID))
async def disable_auto_leave(client, message: Message):
    global AUTO_LEAVE_STATE
    if not AUTO_LEAVE_STATE:
        await message.reply_text("المغادرة التلقائية متوقفة بالفعل")
    else:
        AUTO_LEAVE_STATE = False
        await message.reply_text("تم ايقاف المغادرة التلقائية للمساعد")
