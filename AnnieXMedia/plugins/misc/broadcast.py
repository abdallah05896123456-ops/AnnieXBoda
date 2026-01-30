# Authored By Certified Coders 2026
# Module: Broadcast Background Tasks (Misc)

import asyncio
from pyrogram.enums import ChatMembersFilter
from AnnieXMedia import app
from AnnieXMedia.utils.database import (
    get_active_chats,
    get_authuser_names,
)
from AnnieXMedia.utils.formatters import alpha_to_int
from config import adminlist

async def auto_clean():
    """وظيفة تعمل في الخلفية لتحديث كاش المشرفين"""
    while not await asyncio.sleep(30):
        try:
            served_chats = await get_active_chats()
            for chat_id in served_chats:
                if chat_id not in adminlist:
                    adminlist[chat_id] = []
                    
                    # تحميل المشرفين الذين لديهم صلاحية إدارة المحادثات الصوتية
                    async for user in app.get_chat_members(
                        chat_id, filter=ChatMembersFilter.ADMINISTRATORS
                    ):
                        if getattr(user.privileges, 'can_manage_video_chats', False):
                            adminlist[chat_id].append(user.user.id)
                    
                    # تحميل المستخدمين المخولين من قاعدة البيانات
                    authusers = await get_authuser_names(chat_id)
                    for user in authusers:
                        user_id = await alpha_to_int(user)
                        adminlist[chat_id].append(user_id)
        except:
            continue

# بدء المهمة عند تشغيل البوت
asyncio.create_task(auto_clean())
