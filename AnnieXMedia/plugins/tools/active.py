# Authored By Certified Coders 2026
# Module: Active Chats & Statistics (Admin Only)

from pyrogram import filters, Client
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from unidecode import unidecode

from AnnieXMedia import app
from AnnieXMedia.misc import SUDOERS
from AnnieXMedia.utils.database import (
    get_active_chats,
    get_active_video_chats,
    remove_active_chat,
    remove_active_video_chat,
)

# ==================================================================
# [2] القوائم العامة (للمطورين فقط)
# ==================================================================

# --- قائمة الكولات الصوتية ---
@app.on_message(filters.command(["activevc", "كولات", "الكولات"]) & SUDOERS)
async def activevc(_, message: Message):
    mystic = await message.reply_text("جاري جلب قائمة المكالمات الصوتية النشطة...")
    served_chats = await get_active_chats()
    text = ""
    j = 0
    for x in served_chats:
        try:
            chat = await app.get_chat(x)
            title = unidecode(chat.title).upper()
            link = f"<a href=https://t.me/{chat.username}>{title}</a>" if chat.username else title
            text += f"<b>{j + 1}.</b> {link}\n"
            j += 1
        except:
            await remove_active_chat(x)
    if not text:
        await mystic.edit_text(f"لا توجد مكالمات صوتية نشطة حاليا.")
    else:
        await mystic.edit_text(
            f"<b>قائمة المكالمات الصوتية النشطة حاليا :</b>\n\n{text}",
            disable_web_page_preview=True,
        )

# --- قائمة كولات الفيديو ---
@app.on_message(filters.command(["activevideo", "فيديو", "avc"]) & SUDOERS)
async def activevi_(_, message: Message):
    mystic = await message.reply_text("جاري جلب قائمة مكالمات الفيديو النشطة...")
    served_chats = await get_active_video_chats()
    text = ""
    j = 0
    for x in served_chats:
        try:
            chat = await app.get_chat(x)
            title = unidecode(chat.title).upper()
            link = f"<a href=https://t.me/{chat.username}>{title}</a>" if chat.username else title
            text += f"<b>{j + 1}.</b> {link} [<code>{x}</code>]\n"
            j += 1
        except:
            await remove_active_video_chat(x)
    if not text:
        await mystic.edit_text(f"لا توجد مكالمات فيديو نشطة حاليا.")
    else:
        await mystic.edit_text(
            f"<b>قائمة مكالمات الفيديو النشطة حاليا :</b>\n\n{text}",
            disable_web_page_preview=True,
        )

# --- إحصائيات العدد ---
@app.on_message(filters.command(["ac", "احصائيات", "av"]) & SUDOERS)
async def active_count(client: Client, message: Message):
    ac_audio = str(len(await get_active_chats()))
    ac_video = str(len(await get_active_video_chats()))
    await message.reply_text(
        f"<b><u>معلومات الكولات النشطة</u></b> :\n\nصوت : {ac_audio}\nفيديو  : {ac_video}",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("اغلاق", callback_data="close")]]
        )
    )
