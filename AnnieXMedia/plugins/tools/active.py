# Authored By Certified Coders 2026
# Module: Unified Active VC Manager (Raw API Edition)
# Purpose: List VC participants WITHOUT joining the call + Global Admin Lists.

from pyrogram import filters, Client
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.raw.functions.channels import GetFullChannel
from pyrogram.raw.functions.phone import GetGroupCall
from unidecode import unidecode

from AnnieXMedia import app, userbot
from AnnieXMedia.misc import SUDOERS
from AnnieXMedia.utils.database import (
    get_active_chats,
    get_active_video_chats,
    remove_active_chat,
    remove_active_video_chat,
)

# ==================================================================
# [1] معرفة الموجودين في الكول (بدون انضمام المساعد)
# ==================================================================

@app.on_message(
    filters.command(["م ف ك", "مين في الكول"], prefixes=["", "/", "!", "."])
)
async def vc_participants_raw(client, message: Message):
    chat_id = message.chat.id
    mystic = await message.reply_text("جاري جلب القائمة...")

    try:
        # 1. تحويل معرف الجروب لصيغة Peer
        peer = await userbot.one.resolve_peer(chat_id)
        
        # 2. جلب تفاصيل القناة الكاملة للحصول على كائن الكول
        full_chat = await userbot.one.invoke(GetFullChannel(channel=peer))
        group_call = full_chat.full_chat.call

        if not group_call:
            return await mystic.edit_text("لا توجد مكالمة صوتية نشطة في هذه المجموعة.")

        # 3. جلب قائمة المشاركين من السيرفر مباشرة (دون الانضمام)
        # نقوم بطلب البيانات الخام للكول
        res = await userbot.one.invoke(GetGroupCall(
            call=group_call,
            limit=100  # حد أقصى لعدد الأعضاء المجلوبين
        ))
        
        participants = res.participants
        
        if not participants:
            return await mystic.edit_text("المكالمة فارغة.")

        # 4. تنسيق القائمة
        text = "**الموجودين في الكول**\n\n"
        count = 0
        
        # تجميع معرفات الأعضاء لجلب أسمائهم دفعة واحدة (أسرع)
        user_ids = [p.peer.user_id for p in participants]
        users_info = await app.get_users(user_ids)
        
        # تحويل قائمة المستخدمين لقاموس لسهولة الوصول
        users_map = {u.id: u.first_name for u in users_info}

        for participant in participants:
            try:
                user_id = participant.peer.user_id
                name = users_map.get(user_id, "مستخدم")
                
                # تحديد الحالة من بيانات السيرفر الخام
                # muted: هل المايك مقفول؟
                if participant.muted:
                    status = "يسـتـمع"
                else:
                    status = "يتكـلـم"

                count += 1
                text += f"{count}- {name} {status}\n"
            except:
                continue

        if count == 0:
            await mystic.edit_text("لا يوجد أعضاء حقيقيين.")
        else:
            await mystic.edit_text(text)

    except Exception as e:
        # غالباً الخطأ يكون أن المساعد ليس في الجروب
        if "CHANNEL_PRIVATE" in str(e):
            await mystic.edit_text("المساعد ليس عضواً في هذا الجروب، لا يمكنه رؤية الكول.")
        else:
            await mystic.edit_text(f"حدث خطأ: {e}")


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
