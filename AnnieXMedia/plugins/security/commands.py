# Authored By Certified Coders © 2026
# Security Module: Admin Commands Interface
# Logic: Command handling, Locking system, & Group management

import asyncio
from pyrogram import filters, enums
from pyrogram.types import (
    Message, ChatPermissions, ChatPrivileges, 
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
)

from AnnieXMedia import app
from AnnieXMedia.misc import SUDOERS
from config import BANNED_USERS
from .database import (
    update_lock, get_locks, set_warn_limit_db, 
    update_user_warns
)
from .helpers import has_permission, force_delete

# --- خرائط البيانات والترجمة ---

LOCK_MAP = {
    "الروابط": "links", "المعرفات": "usernames", "التاك": "hashtags",
    "الشارحه": "slashes", "التثبيت": "pin", "المتحركه": "animations",
    "الشات": "all", "الصور": "photos", "الملصقات": "stickers",
    "الملفات": "docs", "البوتات": "bots", "التكرار": "flood",
    "الكلايش": "long_msgs", "الانلاين": "inline", "الفيديو": "videos",
    "البصمات": "voice", "السيلفي": "video_notes", "الماركدوان": "markdown",
    "التوجيه": "forward", "الاغاني": "audio", "الصوت": "voice",
    "الجهات": "contacts", "الاشعارات": "service", "السب": "porn_text",
    "الاباحي": "porn_media"
}

PRETTY_MAP = {
    "الروابط": "الروابط", "المعرفات": "المعرفات", "التاك": "التاك",
    "الشارحه": "الشارحة", "التثبيت": "التثبيت", "المتحركه": "المتحركة",
    "الشات": "الشات", "الصور": "الصور", "الملصقات": "الملصقات",
    "الملفات": "الملفات", "البوتات": "البوتات", "التكرار": "التكرار",
    "الكلايش": "الكلايش", "الانلاين": "الانلاين", "الفيديو": "الفيديو",
    "البصمات": "البصمات", "السيلفي": "السيلفي", "الماركدوان": "الماركدوان",
    "التوجيه": "التوجيه", "الاغاني": "الاغاني", "الصوت": "الصوت",
    "الجهات": "الجهات", "الاشعارات": "الاشعارات", "السب": "السب",
    "الاباحي": "الاباحي"
}

# ==========================================
# أوامر الإدارة المباشرة (سماح، كتم، فك)
# ==========================================

@app.on_message(filters.regex(r"^(سماح|شد سماح|كتم|شد ميوت|فك الكتم)$") & filters.group & ~BANNED_USERS)
async def admin_cmds_handler(_, message: Message):
    if not await has_permission(message.chat.id, message.from_user.id): 
        return await message.reply("هذا الامر مخصص للمشرفين فقط.")
        
    cmd = message.text
    
    # تحديد المستخدم المستهدف
    if message.reply_to_message:
        target_user = message.reply_to_message.from_user
    else:
        return await message.reply("يجب الرد على رسالة المستخدم لتنفيذ هذا الامر.")
    
    u_id = target_user.id
    mention = target_user.mention
    
    try:
        if cmd == "سماح":
            await app.promote_chat_member(message.chat.id, u_id, privileges=ChatPrivileges(can_manage_chat=True, can_delete_messages=True, can_restrict_members=True))
            await message.reply(f"تم منح صلاحيات الادمن لـ {mention}")
        elif cmd == "شد سماح":
            await app.promote_chat_member(message.chat.id, u_id, privileges=ChatPrivileges(can_manage_chat=False))
            await message.reply(f"تم سحب صلاحيات الادمن من {mention}")
        elif cmd == "كتم":
            await app.restrict_chat_member(message.chat.id, u_id, ChatPermissions(can_send_messages=False))
            await message.reply(f"تم كتم المستخدم {mention}")
        elif cmd in ["شد ميوت", "فك الكتم"]:
            await app.restrict_chat_member(message.chat.id, u_id, ChatPermissions(can_send_messages=True))
            await message.reply(f"تم فك الكتم عن {mention}")
    except Exception:
        await message.reply("حدث خطأ، تأكد من صلاحيات البوت.")

@app.on_message(filters.regex(r"^(تحذيرات )(\d+)$") & filters.group & ~BANNED_USERS)
async def set_warns_cmd(_, message: Message):
    if not await has_permission(message.chat.id, message.from_user.id): 
        return await message.reply("هذا الامر مخصص للمشرفين فقط.")
    
    limit = int(message.matches[0].group(2))
    await set_warn_limit_db(message.chat.id, limit)
    await message.reply(f"تم تحديد حد التحذيرات بـ {limit} تحذير.")

# ==========================================
# أوامر التنظيف والتدمير
# ==========================================

@app.on_message(filters.regex(r"^(مسح|تنظيف)($| )") & filters.group & ~BANNED_USERS)
async def destructive_clear(_, message: Message):
    if not await has_permission(message.chat.id, message.from_user.id): 
        return await message.reply("هذا الامر مخصص للمشرفين فقط.")
        
    if message.reply_to_message:  
        start_id = message.reply_to_message.id
        end_id = message.id  
        msg_ids = list(range(start_id, end_id + 1))  
        for i in range(0, len(msg_ids), 100):  
            try: await app.delete_messages(message.chat.id, msg_ids[i:i+100])  
            except: continue  
        deleted = len(msg_ids)  
    else:
        parts = message.text.split()
        num = int(parts[1]) if len(parts) > 1 else 100  
        deleted = await force_delete(message.chat.id, message.id, num)
    
    temp = await message.reply(f"تم مسح {deleted} رسالة بنجاح.")  
    await asyncio.sleep(3)
    await temp.delete()

@app.on_message(filters.regex(r"^(تدمير ذاتي)$") & filters.group & ~BANNED_USERS)
async def self_destruct(_, message: Message):
    if not await has_permission(message.chat.id, message.from_user.id): 
        return await message.reply("هذا الامر مخصص للمشرفين فقط.")
        
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("تـدمـيـر 500 رسـالـة", callback_data="total_destruction")]])
    await message.reply("هل انت متأكد من بدء عملية التدمير الذاتي لآخر 500 رسالة؟", reply_markup=kb)

# ==========================================
# أوامر القفل والفتح (Locking Logic)
# ==========================================

@app.on_message(filters.regex(r"^(قفل |فتح )(.*)$") & filters.group & ~BANNED_USERS)
async def toggle_lock_cmd(_, message: Message):
    if not await has_permission(message.chat.id, message.from_user.id): 
        return await message.reply("هذا الامر مخصص للمشرفين فقط.")
    
    action = message.matches[0].group(1).strip()
    item = message.matches[0].group(2).strip()
    
    key = LOCK_MAP.get(item)
    if not key: return
    
    current_locks = await get_locks(message.chat.id)

    if action == "قفل":
        if key in current_locks:
             return await message.reply("هذا الامر مقفل بالفعل.")
        await update_lock(message.chat.id, key, True)
        await message.reply(f"تم قفل {PRETTY_MAP[item]} بنجاح.")
    else: 
        if key not in current_locks:
             return await message.reply("هذا الامر مفتوح بالفعل.")
        await update_lock(message.chat.id, key, False)
        await message.reply(f"تم فتح {PRETTY_MAP[item]} بنجاح.")

# ==========================================
# لوحة الإعدادات التفاعلية
# ==========================================

async def get_settings_kb(chat_id):
    kb = []
    active = await get_locks(chat_id)
    items = list(LOCK_MAP.items())
    for i in range(0, len(items), 2):
        row = []
        n1, k1 = items[i]; s1 = "مقفل" if k1 in active else "مفتوح"
        row.append(InlineKeyboardButton(f"{n1}: {s1}", callback_data=f"trg_{k1}"))
        if i + 1 < len(items):
            n2, k2 = items[i+1]; s2 = "مقفل" if k2 in active else "مفتوح"
            row.append(InlineKeyboardButton(f"{n2}: {s2}", callback_data=f"trg_{k2}"))
        kb.append(row)
    kb.append([InlineKeyboardButton("اغلاق اللوحة", callback_data="close_sec")])
    return InlineKeyboardMarkup(kb)

@app.on_message(filters.regex(r"^(الاعدادات|locks)$") & filters.group & ~BANNED_USERS)
async def settings_panel(_, message: Message):
    if not await has_permission(message.chat.id, message.from_user.id): 
        return await message.reply("هذا الامر مخصص للمشرفين فقط.")
    await message.reply_text(f"اعدادات الحماية لمجموعة: {message.chat.title}", reply_markup=await get_settings_kb(message.chat.id))

# ==========================================
# معالج التفاعلات (Callback Handler)
# ==========================================

@app.on_callback_query(filters.regex("^(trg_|u_|close_sec|total_destruction)"))
async def security_callback_handler(_, cb: CallbackQuery):
    if not await has_permission(cb.message.chat.id, cb.from_user.id): 
        return await cb.answer("هذا الامر مخصص للمشرفين فقط.", show_alert=True)
        
    if cb.data == "close_sec": 
        return await cb.message.delete()
        
    if cb.data == "total_destruction":  
        await cb.answer("جاري النسف...", show_alert=True)  
        deleted = await force_delete(cb.message.chat.id, cb.message.id, 500)  
        await app.send_message(cb.message.chat.id, f"تم تدمير {deleted} رسالة بنجاح.")  
        await cb.message.delete()

    elif cb.data.startswith("trg_"):  
        key = cb.data.replace("trg_", "")
        locks = await get_locks(cb.message.chat.id)
        is_locked = key in locks
        await update_lock(cb.message.chat.id, key, not is_locked)
        await cb.message.edit_reply_markup(reply_markup=await get_settings_kb(cb.message.chat.id))

    elif cb.data.startswith("u_unmute_"):  
        u_id = int(cb.data.split("_")[2])  
        try:
            await app.restrict_chat_member(cb.message.chat.id, u_id, ChatPermissions(can_send_messages=True))  
            await cb.message.edit("تم فك الكتم عن المستخدم بنجاح.")
        except: pass
