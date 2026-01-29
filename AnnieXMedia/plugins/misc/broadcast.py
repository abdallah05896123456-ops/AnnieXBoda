# Authored By Certified Coders 2026
# Module: Broadcast System - No Emojis, No Underscores, Assistant Auto-Join

import asyncio
from pyrogram import filters, Client
from pyrogram.enums import ChatMembersFilter, ChatType
from pyrogram.errors import FloodWait, UserAlreadyParticipant

from AnnieXMedia import app
from AnnieXMedia.misc import SUDOERS
from AnnieXMedia.utils.database import (
    get_active_chats,
    get_authuser_names,
    get_client,
    get_served_chats,
    get_served_users,
)
from AnnieXMedia.utils.decorators.language import language
from AnnieXMedia.utils.formatters import alpha_to_int
from config import adminlist

IS_BROADCASTING = False

@app.on_message(filters.command(["broadcast", "اذاعة", "إذاعة", "نشر", "عم"]) & SUDOERS)
@language
async def braodcast_message(client, message, _):
    global IS_BROADCASTING
    
    # ─── التحقق من المدخلات ───
    if message.reply_to_message:
        x = message.reply_to_message.id
        y = message.chat.id
    else:
        if len(message.command) < 2:
            return await message.reply_text(
                "يجب كتابة نص أو الرد على رسالة للاذاعة.\n\n"
                "الانواع المتاحة:\n"
                "-تثبيت : لتثبيت الرسالة بدون صوت\n"
                "-عام : لتثبيت الرسالة بصوت\n"
                "-مساعد : للنشر عبر المساعد (لتفعيل البوتات)\n"
                "-خاص : للنشر في الخاص\n"
                "-انضمام : يتبعها يوزر الجروب، لجعل المساعد ينضم ويرسل الرسالة هناك"
            )
        
        # استخراج النص
        query = message.text.split(None, 1)[1]
    
    # ─── منطق الانضمام والنشر في جروب محدد ───
    if "-انضمام" in message.text:
        # المتوقع: نشر -انضمام @username الرسالة
        try:
            parts = message.text.split()
            # البحث عن اليوزر نيم (الكلمة التي تبدأ بـ @ أو رابط تليجرام)
            target_chat = None
            msg_content = ""
            
            for word in parts:
                if word.startswith("@") or "t.me" in word:
                    target_chat = word
                elif word not in ["-انضمام", "/نشر", "/اذاعة", "نشر", "اذاعة"]:
                    msg_content += word + " "
            
            if not target_chat:
                return await message.reply_text("يجب كتابة معرف الجروب او الرابط بعد كلمة -انضمام")
            
            if not msg_content and not message.reply_to_message:
                return await message.reply_text("لا يوجد نص لارساله.")

            await message.reply_text(f"جاري محاولة انضمام المساعد الى {target_chat} والنشر...")
            
            # استخدام المساعد الأول للانضمام
            from AnnieXMedia.core.userbot import assistants
            ub_client = await get_client(assistants[0])
            
            try:
                await ub_client.join_chat(target_chat)
            except UserAlreadyParticipant:
                pass
            except Exception as e:
                return await message.reply_text(f"فشل انضمام المساعد: {e}")

            # إرسال الرسالة
            try:
                if message.reply_to_message:
                    await ub_client.forward_messages(target_chat, y, x)
                else:
                    await ub_client.send_message(target_chat, msg_content)
                await message.reply_text("تم الانضمام والنشر بنجاح.")
            except Exception as e:
                await message.reply_text(f"فشل الارسال: {e}")
            
            return # إنهاء الدالة هنا لأن هذا وضع خاص

        except Exception as e:
            return await message.reply_text(f"حدث خطأ في عملية الانضمام: {e}")

    # ─── تنظيف النص من الفلاجات للاذاعة العامة ───
    if not message.reply_to_message:
        flags = ["-عام", "-تثبيت", "-بدون بوت", "-مساعد", "-خاص"]
        for flag in flags:
            query = query.replace(flag, "")
        
        if query.strip() == "":
            return await message.reply_text("لا يوجد نص لارساله بعد حذف العلامات.")

    IS_BROADCASTING = True
    await message.reply_text("جار بدء الاذاعة...")

    # ─── 1. الاذاعة عبر البوت (للمجموعات) ───
    if "-مساعد" not in message.text and "-بدون بوت" not in message.text:
        sent = 0
        pin = 0
        chats = []
        schats = await get_served_chats()
        for chat in schats:
            chats.append(int(chat["chat_id"]))
        
        for i in chats:
            try:
                m = (
                    await app.forward_messages(i, y, x)
                    if message.reply_to_message
                    else await app.send_message(i, text=query)
                )
                
                if "-تثبيت" in message.text:
                    try:
                        await m.pin(disable_notification=True)
                        pin += 1
                    except:
                        continue
                elif "-عام" in message.text:
                    try:
                        await m.pin(disable_notification=False)
                        pin += 1
                    except:
                        continue
                sent += 1
                await asyncio.sleep(0.2)
            except FloodWait as fw:
                flood_time = int(fw.value)
                if flood_time > 200:
                    continue
                await asyncio.sleep(flood_time)
            except:
                continue
        try:
            await message.reply_text(f"تم الاذاعة في {sent} مجموعة.\nتم التثبيت في {pin} مجموعة.")
        except:
            pass

    # ─── 2. الاذاعة للاعضاء (الخاص) ───
    if "-خاص" in message.text:
        susr = 0
        served_users = []
        susers = await get_served_users()
        for user in susers:
            served_users.append(int(user["user_id"]))
        
        for i in served_users:
            try:
                m = (
                    await app.forward_messages(i, y, x)
                    if message.reply_to_message
                    else await app.send_message(i, text=query)
                )
                susr += 1
                await asyncio.sleep(0.2)
            except FloodWait as fw:
                flood_time = int(fw.value)
                if flood_time > 200:
                    continue
                await asyncio.sleep(flood_time)
            except:
                pass
        try:
            await message.reply_text(f"تم الاذاعة لـ {susr} مستخدم في الخاص.")
        except:
            pass

    # ─── 3. الاذاعة عبر المساعد (لتشغيل البوتات) ───
    if "-مساعد" in message.text:
        aw = await message.reply_text("جار الاذاعة عبر الحساب المساعد...")
        text = "تقرير نشر المساعد:\n"
        from AnnieXMedia.core.userbot import assistants

        for num in assistants:
            sent = 0
            client = await get_client(num)
            async for dialog in client.get_dialogs():
                if dialog.chat.type in [
                    ChatType.SUPERGROUP,
                    ChatType.GROUP,
                    ChatType.CHANNEL
                ]:
                    try:
                        await client.forward_messages(
                            dialog.chat.id, y, x
                        ) if message.reply_to_message else await client.send_message(
                            dialog.chat.id, text=query
                        )
                        sent += 1
                        await asyncio.sleep(2.0) 
                    except FloodWait as fw:
                        flood_time = int(fw.value)
                        if flood_time > 200:
                            continue
                        await asyncio.sleep(flood_time)
                    except:
                        continue
            text += f"المساعد {num}: نشر في {sent} محادثة.\n"
        try:
            await aw.edit_text(text)
        except:
            pass
            
    IS_BROADCASTING = False

# ─── تنظيف قائمة الادمن تلقائيا ───
async def auto_clean():
    while not await asyncio.sleep(10):
        try:
            served_chats = await get_active_chats()
            for chat_id in served_chats:
                if chat_id not in adminlist:
                    adminlist[chat_id] = []
                    async for user in app.get_chat_members(
                        chat_id, filter=ChatMembersFilter.ADMINISTRATORS
                    ):
                        if getattr(user.privileges, 'can_manage_video_chats', False):
                            adminlist[chat_id].append(user.user.id)
                    authusers = await get_authuser_names(chat_id)
                    for user in authusers:
                        user_id = await alpha_to_int(user)
                        adminlist[chat_id].append(user_id)
        except:
            continue

asyncio.create_task(auto_clean())
