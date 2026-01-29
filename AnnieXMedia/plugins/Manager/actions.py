# Authored By Certified Coders 2026
# Module: Group Actions (Pin, Title, Photo) - Arabic & No Emojis

from pyrogram import filters
from pyrogram.enums import ChatType
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from AnnieXMedia import app
from AnnieXMedia.utils.admin_filters import admin_filter

# ------------------- دوال مساعدة ------------------- #

def is_group(message: Message) -> bool:
    return message.chat.type not in (ChatType.PRIVATE, ChatType.BOT)

async def has_permission(user_id: int, chat_id: int, permission: str) -> bool:
    try:
        member = await app.get_chat_member(chat_id, user_id)
        return bool(getattr(getattr(member, "privileges", None), permission, False) or getattr(member, "status", "") in ("creator",))
    except Exception:
        return False

def _view_btn(msg: Message):
    try:
        return InlineKeyboardMarkup([[InlineKeyboardButton("عرض الرسالة", url=msg.link)]])
    except Exception:
        return None

# ------------------- تثبيت الرسائل ------------------- #

@app.on_message(filters.command(["تثبيت", "pin"], prefixes=["/", "!", ".", ""]) & admin_filter)
async def pin(_, message: Message):
    if not is_group(message):
        return await message.reply_text("**هذا الأمر يعمل فقط في الجروبات.**")

    if not message.reply_to_message:
        return await message.reply_text("**قم بالرد على الرسالة لتثبيتها.**")

    if not await has_permission(message.from_user.id, message.chat.id, "can_pin_messages"):
        return await message.reply_text("**ليس لديك صلاحية تثبيت الرسائل.**")

    try:
        await message.reply_to_message.pin()
        await message.reply_text(
            f"**تم تثبيت الرسالة بنجاح.**\n\n**المجموعة:** {message.chat.title}\n**بواسطة:** {message.from_user.mention}",
            reply_markup=_view_btn(message.reply_to_message)
        )
    except Exception as e:
        await message.reply_text(f"**فشل تثبيت الرسالة:**\n`{e}`")

# ------------------- إلغاء التثبيت ------------------- #

@app.on_message(filters.command(["الغاء التثبيت", "unpin"], prefixes=["/", "!", ".", ""]) & admin_filter)
async def unpin(_, message: Message):
    if not is_group(message):
        return await message.reply_text("**هذا الأمر يعمل فقط في الجروبات.**")

    if not message.reply_to_message:
        return await message.reply_text("**قم بالرد على الرسالة لإلغاء تثبيتها.**")

    if not await has_permission(message.from_user.id, message.chat.id, "can_pin_messages"):
        return await message.reply_text("**ليس لديك صلاحية تثبيت الرسائل.**")

    try:
        await message.reply_to_message.unpin()
        await message.reply_text(
            f"**تم إلغاء تثبيت الرسالة بنجاح.**\n\n**المجموعة:** {message.chat.title}\n**بواسطة:** {message.from_user.mention}",
            reply_markup=_view_btn(message.reply_to_message)
        )
    except Exception as e:
        await message.reply_text(f"**فشل إلغاء التثبيت:**\n`{e}`")

# ------------------- تغيير الصورة والاسم والوصف ------------------- #

@app.on_message(filters.command(["تغيير الصورة", "ضع صورة", "setphoto"], prefixes=["/", "!", ".", ""]) & admin_filter)
async def set_photo(_, message: Message):
    if not is_group(message):
        return await message.reply_text("**هذا الأمر يعمل فقط في الجروبات.**")
    if not message.reply_to_message:
        return await message.reply_text("**قم بالرد على صورة أو ملف.**")
    if not await has_permission(message.from_user.id, message.chat.id, "can_change_info"):
        return await message.reply_text("**ليس لديك صلاحية تغيير معلومات الجروب.**")

    target = message.reply_to_message
    file_id = None

    if getattr(target, "photo", None):
        file_id = target.photo.file_id
    elif getattr(target, "document", None) and getattr(target.document, "mime_type", ""):
        if target.document.mime_type.startswith("image/"):
            file_id = target.document.file_id

    if not file_id:
        return await message.reply_text("**يرجى الرد على ملف صورة صالح.**")

    try:
        await app.set_chat_photo(chat_id=message.chat.id, photo=file_id)
        await message.reply_text(f"**تم تحديث صورة الجروب بنجاح.**\nبواسطة {message.from_user.mention}")
    except Exception as e:
        await message.reply_text(f"**فشل تغيير الصورة:**\n`{e}`")

@app.on_message(filters.command(["حذف الصورة", "removephoto"], prefixes=["/", "!", ".", ""]) & admin_filter)
async def remove_photo(_, message: Message):
    if not is_group(message):
        return await message.reply_text("**هذا الأمر يعمل فقط في الجروبات.**")
    if not await has_permission(message.from_user.id, message.chat.id, "can_change_info"):
        return await message.reply_text("**ليس لديك صلاحية تغيير معلومات الجروب.**")
    try:
        await app.delete_chat_photo(message.chat.id)
        await message.reply_text(f"**تم حذف صورة الجروب.**\nبواسطة {message.from_user.mention}")
    except Exception as e:
        await message.reply_text(f"**فشل حذف الصورة:**\n`{e}`")

@app.on_message(filters.command(["تغيير الاسم", "settitle"], prefixes=["/", "!", ".", ""]) & admin_filter)
async def set_title(_, message: Message):
    if not is_group(message):
        return await message.reply_text("**هذا الأمر يعمل فقط في الجروبات.**")
    if not await has_permission(message.from_user.id, message.chat.id, "can_change_info"):
        return await message.reply_text("**ليس لديك صلاحية تغيير معلومات الجروب.**")

    title = None
    if len(message.command) > 1:
        title = message.text.split(None, 1)[1].strip()
    elif message.reply_to_message and getattr(message.reply_to_message, "text", None):
        title = message.reply_to_message.text.strip()

    if not title:
        return await message.reply_text("**يرجى كتابة الاسم الجديد.**")

    try:
        await message.chat.set_title(title)
        await message.reply_text(f"**تم تغيير اسم الجروب إلى:** {title}\nبواسطة {message.from_user.mention}")
    except Exception as e:
        await message.reply_text(f"**فشل تغيير الاسم:**\n`{e}`")


@app.on_message(filters.command(["تغيير الوصف", "setdiscription"], prefixes=["/", "!", ".", ""]) & admin_filter)
async def set_description(_, message: Message):
    if not is_group(message):
        return await message.reply_text("**هذا الأمر يعمل فقط في الجروبات.**")
    if not await has_permission(message.from_user.id, message.chat.id, "can_change_info"):
        return await message.reply_text("**ليس لديك صلاحية تغيير معلومات الجروب.**")

    desc = None
    if len(message.command) > 1:
        desc = message.text.split(None, 1)[1].strip()
    elif message.reply_to_message and getattr(message.reply_to_message, "text", None):
        desc = message.reply_to_message.text.strip()

    if not desc:
        return await message.reply_text("**يرجى كتابة الوصف الجديد.**")

    try:
        await message.chat.set_description(desc)
        await message.reply_text(f"**تم تحديث وصف الجروب.**\nبواسطة {message.from_user.mention}")
    except Exception as e:
        await message.reply_text(f"**فشل تغيير الوصف:**\n`{e}`")
