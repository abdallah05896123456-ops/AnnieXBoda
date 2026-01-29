# Authored By Certified Coders 2026
# Module: Export Chat Members - Arabic & No Emojis

import csv
from io import StringIO, BytesIO
from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from AnnieXMedia import app
from AnnieXMedia.utils.admin_filters import admin_filter

async def collect_members(chat_id, processing_msg):
    members_list = []
    async for member in app.get_chat_members(chat_id):
        # التحقق من وجود معرف أو اسم
        username = member.user.username if member.user.username else (member.user.first_name or "بدون اسم")
        
        members_list.append({
            "username": username,
            "userid": member.user.id
        })
        
        # تحديث الرسالة كل 100 عضو
        if len(members_list) % 100 == 0:
            try:
                await processing_msg.edit_text(f"تم جمع {len(members_list)} عضو حتى الان...")
            except Exception:
                pass
    return members_list

# ─── أمر استخراج الأعضاء ──────────────────────────────────────────────

@app.on_message(filters.command(["الاعضاء", "users", "members"], prefixes=["", "/", "!", "."]) & admin_filter)
async def user_command(_, message):
    keyboard = InlineKeyboardMarkup(
        [[
            InlineKeyboardButton("ملف CSV", callback_data="members_csv"),
            InlineKeyboardButton("ملف TXT", callback_data="members_txt")
        ]]
    )
    await message.reply_text(
        "اختر الصيغة التي تريد استخراج ملف الاعضاء بها",
        reply_markup=keyboard
    )

# ─── معالجة ضغط الأزرار ──────────────────────────────────────────────

@app.on_callback_query(filters.regex("^members_"))
async def members_format_callback(_, callback_query):
    format_choice = callback_query.data.split("_")[1].lower()
    
    await callback_query.answer()
    
    try:
        await callback_query.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    processing_msg = await callback_query.message.reply_text("جاري جمع الاعضاء يرجى الانتظار...")
    chat_id = callback_query.message.chat.id

    members_list = await collect_members(chat_id, processing_msg)

    if not members_list:
        await processing_msg.edit_text("لم يتم العثور على اعضاء او حدث خطأ.")
        return

    if format_choice == "csv":
        csv_text = StringIO()
        writer = csv.DictWriter(csv_text, fieldnames=["username", "userid"])
        writer.writeheader()
        for member in members_list:
            writer.writerow(member)
        csv_str = csv_text.getvalue()
        file_bytes = BytesIO(csv_str.encode("utf-8"))
        file_name = "members.csv"
        caption_text = "تفضل قائمة اعضاء المجموعة بصيغة CSV."
    else:
        text_lines = []
        for member in members_list:
            # إضافة @ للمعرفات لتسهيل النسخ
            name_display = f"@{member['username']}" if member['username'] != "بدون اسم" and not " " in member['username'] else member['username']
            text_lines.append(f"{name_display} - {member['userid']}")
            
        txt_str = "\n".join(text_lines)
        file_bytes = BytesIO(txt_str.encode("utf-8"))
        file_name = "members.txt"
        caption_text = "تفضل قائمة اعضاء المجموعة بصيغة TXT."

    file_bytes.seek(0)

    try:
        await app.send_document(
            chat_id,
            document=file_bytes,
            caption=caption_text,
            file_name=file_name
        )
    except Exception as e:
        await processing_msg.edit_text(f"فشل ارسال الملف: {e}")
        return
    
    await processing_msg.delete()

    try:
        await callback_query.message.delete()
    except Exception:
        pass
