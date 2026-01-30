# Authored By Certified Coders 2026
# Module: Broadcast System (Tools) - Clean Text

import asyncio
from pyrogram import filters, Client
from pyrogram.enums import ChatMembersFilter, ChatType
from pyrogram.errors import FloodWait, UserAlreadyParticipant

from AnnieXMedia import app
from AnnieXMedia.misc import SUDOERS
from AnnieXMedia.utils.database import (
    get_client,
    get_served_chats,
    get_served_users,
)
from AnnieXMedia.utils.decorators.language import language

IS_BROADCASTING = False

@app.on_message(filters.command(["broadcast", "اذاعة", "إذاعة", "نشر", "عم"]) & SUDOERS)
@language
async def braodcast_message(client, message, _):
    global IS_BROADCASTING
    
    # ─── 1. التحقق وتجهيز البيانات ───
    query = ""
    if message.reply_to_message:
        x = message.reply_to_message.id
        y = message.chat.id
    else:
        if len(message.command) < 2:
            return await message.reply_text(
                "**طريقة الاستخدام:**\n"
                "نشر + النص\n"
                "أو الرد على رسالة بـ نشر\n\n"
                "**الانواع المتاحة:**\n"
                "-تثبيت : لتثبيت الرسالة بدون صوت\n"
                "-عام : لتثبيت الرسالة بصوت (مزعج)\n"
                "-مساعد : للنشر عبر حساب المساعد\n"
                "-خاص : للنشر في الخاص للمستخدمين\n"
                "-انضمام : يتبعها معرف الجروب، لجعل المساعد ينضم ويرسل هناك"
            )
        
        # استخراج النص الخام
        query = message.text.split(None, 1)[1]
    
    # ─── 2. منطق الانضمام والنشر في جروب محدد ───
    if "-انضمام" in message.text:
        try:
            parts = message.text.split()
            target_chat = None
            msg_content = ""
            
            # استخراج اليوزر والنص
            for word in parts:
                if word.startswith("@") or "t.me" in word:
                    target_chat = word
                elif word not in ["-انضمام", "/نشر", "نشر"]:
                    msg_content += word + " "
            
            if not target_chat:
                return await message.reply_text("يجب كتابة معرف الجروب او الرابط بعد كلمة -انضمام")
            
            await message.reply_text(f"جاري محاولة انضمام المساعد الى {target_chat}...")
            
            # استخدام المساعد الأول
            from AnnieXMedia.core.userbot import assistants
            ub_client = await get_client(assistants[0])
            
            # محاولة الانضمام
            try:
                if "+" in target_chat: 
                    await ub_client.join_chat(target_chat)
                else: 
                    await ub_client.join_chat(target_chat)
            except UserAlreadyParticipant:
                pass
            except Exception as e:
                return await message.reply_text(f"فشل انضمام المساعد: {e}")

            # الإرسال
            try:
                await asyncio.sleep(1)
                
                if message.reply_to_message:
                    await ub_client.forward_messages(target_chat, y, x)
                elif msg_content.strip():
                    await ub_client.send_message(target_chat, msg_content)
                else:
                    return await message.reply_text("تم الانضمام، ولكن لا يوجد نص لارساله.")
                    
                await message.reply_text("تم الانضمام والنشر بنجاح.")
            except Exception as e:
                await message.reply_text(f"تم الانضمام، ولكن فشل الارسال: {e}")
            
            return 

        except Exception as e:
            return await message.reply_text(f"حدث خطأ غير متوقع: {e}")

    # ─── 3. تجهيز النص للاذاعة العامة ───
    if not message.reply_to_message:
        flags = ["-عام", "-تثبيت", "-بدون بوت", "-مساعد", "-خاص"]
        for flag in flags:
            query = query.replace(flag, "")
        
        if query.strip() == "":
            return await message.reply_text("لا يوجد نص لارساله بعد حذف العلامات.")

    IS_BROADCASTING = True
    status_msg = await message.reply_text("جار بدء الاذاعة...")

    # ─── 4. الاذاعة عبر البوت (للمجموعات) ───
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
                    try: await m.pin(disable_notification=True); pin += 1
                    except: continue
                elif "-عام" in message.text:
                    try: await m.pin(disable_notification=False); pin += 1
                    except: continue
                
                sent += 1
                await asyncio.sleep(0.2)
            except FloodWait as fw:
                flood_time = int(fw.value)
                if flood_time > 200: continue
                await asyncio.sleep(flood_time)
            except:
                continue
        try:
            await message.reply_text(f"**تم الاذاعة في:** {sent} مجموعة.\n**تم التثبيت في:** {pin} مجموعة.")
        except: pass

    # ─── 5. الاذاعة للاعضاء (الخاص) ───
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
                if flood_time > 200: continue
                await asyncio.sleep(flood_time)
            except: pass
        try:
            await message.reply_text(f"**تم الاذاعة لـ:** {susr} مستخدم في الخاص.")
        except: pass

    # ─── 6. الاذاعة عبر المساعد (لتشغيل البوتات) ───
    if "-مساعد" in message.text:
        try: await status_msg.edit_text("جار الاذاعة عبر الحساب المساعد... (قد يستغرق وقتا)")
        except: pass
        
        text = "**تقرير نشر المساعد:**\n"
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
                        await asyncio.sleep(1.5) # تأخير لمنع الحظر
                    except FloodWait as fw:
                        flood_time = int(fw.value)
                        if flood_time > 200: continue
                        await asyncio.sleep(flood_time)
                    except:
                        continue
            text += f"**المساعد {num}:** نشر في {sent} محادثة.\n"
        try:
            await message.reply_text(text)
        except: pass
            
    IS_BROADCASTING = False
