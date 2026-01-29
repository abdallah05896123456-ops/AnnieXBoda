# Authored By Certified Coders 2026
# Module: VC Watcher & Manager
# Purpose: Notify on VC events AND Control VC via plain text commands.

import random
from pyrogram import filters
from pyrogram.types import Message
from pyrogram.enums import ChatType
from pyrogram.errors import ChatSendPlainForbidden, ChatWriteForbidden, Forbidden, ChannelPrivate
from pyrogram.raw.functions.phone import CreateGroupCall, DiscardGroupCall
from pyrogram.raw.functions.channels import GetFullChannel

from AnnieXMedia import app, userbot
from AnnieXMedia.misc import SUDOERS
from config import OWNER_ID

# --- [ Helper Function ] ---
async def _safe_reply_text(message: Message, *args, **kwargs):
    chat = getattr(message, "chat", None)
    if not chat or chat.type == ChatType.CHANNEL:
        return
    try:
        await message.reply_text(*args, **kwargs)
    except (ChatSendPlainForbidden, ChatWriteForbidden, Forbidden, ChannelPrivate):
        pass

# ==================================================================
# [1] أوامر التحكم (بدون بادئات - كتابة فقط)
# ==================================================================

# --- فتح الكول ---
# prefixes="" تعني أن الأمر يعمل بدون أي علامات
@app.on_message(filters.command(["فتح الكول", "openvc"], prefixes="") & SUDOERS)
async def start_group_call(client, message: Message):
    chat_id = message.chat.id
    msg = await message.reply_text("انـتـظـر قـلـيـلا...")

    try:
        # استخدام المساعد لفتح الكول
        peer = await userbot.one.resolve_peer(chat_id)
        await userbot.one.invoke(
            CreateGroupCall(
                peer=peer,
                random_id=random.randint(10000, 999999999)
            )
        )
        await msg.edit_text("**تـم فـتـح الـمـكـالـمـة الـصـوتـيـة.**")
        
    except Exception as e:
        if "GROUPCALL_ALREADY_JOINED" in str(e):
             await msg.edit_text("**الـمـكـالـمـة مـفـتـوحـة بـالـفـعـل!**")
        elif "CHAT_ADMIN_REQUIRED" in str(e):
             await msg.edit_text("**فـشـل!** يـجـب أن يـكـون الـمـسـاعـد مـشـرفـاً.")
        else:
            await msg.edit_text(f"**حـدث خـطـأ:** `{e}`")

# --- قفل الكول ---
@app.on_message(filters.command(["قفل الكول", "closevc"], prefixes="") & SUDOERS)
async def end_group_call(client, message: Message):
    chat_id = message.chat.id
    msg = await message.reply_text("انـتـظـر قـلـيـلا...")

    try:
        peer = await userbot.one.resolve_peer(chat_id)
        full_chat = await userbot.one.invoke(GetFullChannel(channel=peer))
        
        if not full_chat.full_chat.call:
            return await msg.edit_text("**لا تـوجـد مـكـالـمـة نـشـطـة!**")
            
        await userbot.one.invoke(
            DiscardGroupCall(
                call=full_chat.full_chat.call
            )
        )
        await msg.edit_text("**تـم إغـلاق الـمـكـالـمـة الـصـوتـيـة.**")

    except Exception as e:
        await msg.edit_text(f"**حـدث خـطـأ:** `{e}`")

# ==================================================================
# [2] مراقبة الأحداث (إشعارات معربة بدون إيموجي)
# ==================================================================

@app.on_message(filters.video_chat_started & filters.group)
async def on_voice_chat_started(_, message: Message):
    await _safe_reply_text(message, "**تـم بـدء الـمـحـادثـة الـصـوتـيـة!**")


@app.on_message(filters.video_chat_ended & filters.group)
async def on_voice_chat_ended(_, message: Message):
    await _safe_reply_text(message, "**تـم إنـهـاء الـمـحـادثـة الـصـوتـيـة.**")


@app.on_message(filters.video_chat_members_invited & filters.group)
async def on_voice_chat_members_invited(_, message: Message):
    inviter = "شخص ما"
    if message.from_user:
        try:
            inviter = message.from_user.mention(message.from_user.first_name)
        except Exception:
            inviter = message.from_user.first_name or "شخص ما"

    invited = []
    vcmi = getattr(message, "video_chat_members_invited", None)
    users = getattr(vcmi, "users", []) if vcmi else []
    for user in users:
        try:
            name = user.first_name or "مستخدم"
            invited.append(f"[{name}](tg://user?id={user.id})")
        except Exception:
            continue

    if invited:
        await _safe_reply_text(
            message,
            f"قام {inviter} بدعوة {', '.join(invited)} للمحادثة الصوتية.",
        )


@app.on_message(filters.command("leavegroup", prefixes="") & filters.user(OWNER_ID) & filters.group)
async def leave_group(_, message: Message):
    await _safe_reply_text(message, "**جـارٍ مـغـادرة الـمـجـمـوعـة...**")
    try:
        await app.leave_chat(chat_id=message.chat.id, delete=True)
    except (ChatWriteForbidden, Forbidden, ChannelPrivate):
        pass
