# Authored By Certified Coders 2026
# Module: Assistant Management (Join/Leave) - Arabic Version (Specific Texts)

import asyncio
from pyrogram import filters
from pyrogram.enums import ChatMemberStatus
from pyrogram.types import ChatJoinRequest
from pyrogram.errors import (
    ChatAdminRequired,
    UserAlreadyParticipant,
    UserNotParticipant,
    ChannelPrivate,
    FloodWait,
    PeerIdInvalid,
    ChatWriteForbidden,
)
from AnnieXMedia import app
from AnnieXMedia.utils.admin_filters import dev_filter, admin_filter, sudo_filter
from AnnieXMedia.utils.database import get_assistant

ACTIVE_STATUSES = {
    ChatMemberStatus.OWNER,
    ChatMemberStatus.ADMINISTRATOR,
    ChatMemberStatus.MEMBER,
    ChatMemberStatus.RESTRICTED,
}

async def _is_participant(client, chat_id: int, user_id: int) -> bool:
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in ACTIVE_STATUSES
    except (UserNotParticipant, PeerIdInvalid):
        return False
    except Exception as e:
        return False

async def join_userbot(app, chat_id: int, chat_username: str = None) -> str:
    userbot = await get_assistant(chat_id)
    try:
        member = await app.get_chat_member(chat_id, userbot.id)
        if member.status == ChatMemberStatus.BANNED:
            try:
                await app.unban_chat_member(chat_id, userbot.id)
                member = await app.get_chat_member(chat_id, userbot.id)
            except ChatAdminRequired:
                return "**أحتاج إلى صلاحية 'فك الحظر' لإضافة المساعد.**"
        if member.status in ACTIVE_STATUSES:
            return "**المساعد موجود بالفعل في الجروب.**"
    except (UserNotParticipant, PeerIdInvalid):
        pass

    invite = None
    if chat_username:
        invite = chat_username if chat_username.startswith("@") else f"@{chat_username}"
    else:
        try:
            link = await app.create_chat_invite_link(chat_id)
            invite = link.invite_link
        except ChatAdminRequired:
            return "**أحتاج إلى صلاحية 'دعوة المستخدمين' لإضافة المساعد.**"

    max_retries = 3
    for attempt in range(max_retries):
        try:
            await userbot.join_chat(invite)
            # --- [ تعديل رسالة الدخول ] ---
            return "**تـم دخـول الحسـاب المسـاعد بنـجاح .**"
        except UserAlreadyParticipant:
            return "**المساعد موجود بالفعل.**"
        except FloodWait as e:
            if attempt == max_retries - 1:
                return f"**فشل الانضمام بسبب ضغط التليجرام (FloodWait).**"
            await asyncio.sleep(e.value)
        except Exception as e:
            return f"**حدث خطأ أثناء الانضمام:** `{str(e)}`"

@app.on_chat_join_request()
async def approve_join_request(client, chat_join_request: ChatJoinRequest):
    userbot = await get_assistant(chat_join_request.chat.id)
    if chat_join_request.from_user.id != userbot.id:
        return

    chat_id = chat_join_request.chat.id
    try:
        if await _is_participant(client, chat_id, userbot.id):
            return

        max_retries = 3
        for attempt in range(max_retries):
            try:
                await client.approve_chat_join_request(chat_id, userbot.id)
                break
            except UserAlreadyParticipant:
                return
            except FloodWait as e:
                if attempt == max_retries - 1:
                    return
                await asyncio.sleep(e.value)
            except (ChatAdminRequired, PeerIdInvalid):
                return

        try:
            # رسالة الموافقة التلقائية
            await client.send_message(chat_id, "**تـم دخـول الحسـاب المسـاعد بنـجاح .**")
        except ChatWriteForbidden:
            pass
    except Exception as e:
        pass

# --- [ أمر انضمام المساعد ] ---
@app.on_message(
    filters.command(["ادخل", "انضم", "دخول المساعد", "userbotjoin"], prefixes=["/", "!", ".", ""])
    & (filters.group | filters.private)
    & admin_filter
    & sudo_filter
)
async def join_group(app, message):
    chat_id = message.chat.id
    status_message = await message.reply("**انتظر قليلاً، جاري دعوة المساعد...**")
    try:
        me = await app.get_me()
        chat_member = await app.get_chat_member(chat_id, me.id)
        if chat_member.status != ChatMemberStatus.ADMINISTRATOR:
            await status_message.edit_text("**يجب أن أكون مشرفاً (Admin) لإضافة المساعد.**")
            return
    except ChatAdminRequired:
        await status_message.edit_text("**لا أمتلك الصلاحيات الكافية.**")
        return
    except Exception as e:
        await status_message.edit_text(f"**حدث خطأ في التحقق:** `{str(e)}`")
        return

    chat_username = message.chat.username or None
    response = await join_userbot(app, chat_id, chat_username)
    try:
        await status_message.edit_text(response)
    except ChatWriteForbidden:
        pass

# --- [ أمر خروج المساعد ] ---
@app.on_message(
    filters.command(["اخرج", "غادر", "خروج المساعد", "userbotleave"], prefixes=["/", "!", ".", ""])
    & filters.group
    & admin_filter
    & sudo_filter
)
async def leave_one(app, message):
    chat_id = message.chat.id
    try:
        userbot = await get_assistant(chat_id)
        try:
            member = await userbot.get_chat_member(chat_id, userbot.id)
            if member.status not in ACTIVE_STATUSES:
                await message.reply("**المساعد غير موجود في هذا الجروب.**")
                return
        except UserNotParticipant:
            await message.reply("**المساعد غير موجود في هذا الجروب.**")
            return

        max_retries = 3
        for attempt in range(max_retries):
            try:
                await userbot.leave_chat(chat_id)
                try:
                    # --- [ تعديل رسالة الخروج ] ---
                    await app.send_message(chat_id, "**تـم خـروج الحسـاب المسـاعد بنـجاح .**")
                except ChatWriteForbidden:
                    pass
                return
            except FloodWait as e:
                if attempt == max_retries - 1:
                    await message.reply("**فشل الخروج بسبب ضغط التليجرام (FloodWait).**")
                    return
                await asyncio.sleep(e.value)
            except ChannelPrivate:
                await message.reply("**خطأ: الجروب خاص أو تم حذفي منه.**")
                return
            except Exception as e:
                await message.reply(f"**حدث خطأ أثناء الخروج:** `{str(e)}`")
                return
    except Exception as e:
        await message.reply(f"**خطأ غير متوقع:** `{str(e)}`")

# --- [ أمر مغادرة كل الجروبات ] ---
@app.on_message(filters.command(["مغادرة الكل", "leaveall"], prefixes=["."]) & dev_filter)
async def leave_all(app, message):
    left = 0
    failed = 0
    status_message = await message.reply("**جاري خروج المساعد من جميع الجروبات...**")
    try:
        userbot = await get_assistant(message.chat.id)
        async for dialog in userbot.get_dialogs():
            if dialog.chat.id == -1002014167331:
                continue
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    await userbot.leave_chat(dialog.chat.id)
                    left += 1
                    break
                except FloodWait as e:
                    if attempt == max_retries - 1:
                        failed += 1
                        break
                    await asyncio.sleep(e.value)
                except Exception:
                    failed += 1
                    break

            try:
                await status_message.edit_text(
                    f"**جاري المغادرة...**\nتم الخروج: `{left}`\nفشل: `{failed}`"
                )
            except ChatWriteForbidden:
                pass
            await asyncio.sleep(0.5)
    except FloodWait as e:
        await asyncio.sleep(e.value)
    except Exception as e:
        pass
    finally:
        try:
            await app.send_message(
                message.chat.id,
                f"**انتهت العملية.**\nتم الخروج من: `{left}` جروب.\nفشل في: `{failed}` جروب.",
            )
        except ChatWriteForbidden:
            pass
