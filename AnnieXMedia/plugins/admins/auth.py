# Authored By Certified Coders 2026
# Module: Auth Users (Bot Admins) - Arabic & No Emojis

from pyrogram import filters
from pyrogram.types import Message

from AnnieXMedia import app
from AnnieXMedia.utils import extract_user, int_to_alpha
from AnnieXMedia.utils.database import (
    delete_authuser,
    get_authuser,
    get_authuser_names,
    save_authuser,
)
from AnnieXMedia.utils.decorators import AdminActual, language
from AnnieXMedia.utils.inline import close_markup
from config import BANNED_USERS, adminlist


# --- [ أمر رفع أدمن في البوت ] ---
@app.on_message(
    filters.command(["رفع ادمن", "auth"], prefixes=["", "/", "!", "."]) 
    & filters.group 
    & ~BANNED_USERS
)
@AdminActual
async def auth(client, message: Message, _):
    if not message.reply_to_message:
        if len(message.command) != 2:
            return await message.reply_text("**يرجى الرد على العضو أو كتابة المعرف لرفعه.**")
    
    user = await extract_user(message)
    token = await int_to_alpha(user.id)
    _check = await get_authuser_names(message.chat.id)
    count = len(_check)
    
    if int(count) == 25:
        return await message.reply_text("**لا يمكن رفع المزيد، تم الوصول للحد الأقصى (25 أدمن).**")
    
    if token not in _check:
        assis = {
            "auth_user_id": user.id,
            "auth_name": user.first_name,
            "admin_id": message.from_user.id,
            "admin_name": message.from_user.first_name,
        }
        get = adminlist.get(message.chat.id)
        if get:
            if user.id not in get:
                get.append(user.id)
        await save_authuser(message.chat.id, token, assis)
        return await message.reply_text(f"**تم رفع {user.mention} أدمن في البوت بنجاح.**")
    else:
        return await message.reply_text(f"**{user.mention} أدمن في البوت بالفعل.**")


# --- [ أمر تنزيل أدمن من البوت ] ---
@app.on_message(
    filters.command(["تنزيل ادمن", "unauth"], prefixes=["", "/", "!", "."]) 
    & filters.group 
    & ~BANNED_USERS
)
@AdminActual
async def unauthusers(client, message: Message, _):
    if not message.reply_to_message:
        if len(message.command) != 2:
            return await message.reply_text("**يرجى الرد على العضو أو كتابة المعرف لتنزيله.**")
    
    user = await extract_user(message)
    token = await int_to_alpha(user.id)
    deleted = await delete_authuser(message.chat.id, token)
    get = adminlist.get(message.chat.id)
    if get:
        if user.id in get:
            get.remove(user.id)
    if deleted:
        return await message.reply_text(f"**تم تنزيل {user.mention} من صلاحيات البوت.**")
    else:
        return await message.reply_text(f"**{user.mention} ليس أدمن في البوت أصلاً.**")


# --- [ أمر عرض قائمة الادمنية ] ---
@app.on_message(
    filters.command(["الادمنية", "authlist", "authusers"], prefixes=["", "/", "!", "."]) 
    & filters.group 
    & ~BANNED_USERS
)
@language
async def authusers(client, message: Message, _):
    _wtf = await get_authuser_names(message.chat.id)
    if not _wtf:
        return await message.reply_text("**لا يوجد أدمنية مرفوعين في هذا الجروب.**")
    else:
        j = 0
        mystic = await message.reply_text("**جاري جلب القائمة...**")
        text = f"**قائمة أدمنية البوت في {message.chat.title}:**\n\n"
        for umm in _wtf:
            _umm = await get_authuser(message.chat.id, umm)
            user_id = _umm["auth_user_id"]
            admin_id = _umm["admin_id"]
            admin_name = _umm["admin_name"]
            try:
                user = (await app.get_users(user_id)).first_name
                j += 1
            except:
                continue
            text += f"{j}- {user} [`{user_id}`]\n"
            text += f"   بواسطة: {admin_name} [`{admin_id}`]\n\n"
        
        await mystic.edit_text(text, reply_markup=close_markup(_))
