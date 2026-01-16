# Authored By Certified Coders © 2025
# System Settings Module - Clean Dashboard Style (No Emojis)

from pyrogram import filters
from pyrogram.enums import ChatType
from pyrogram.errors import MessageNotModified
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from AnnieXMedia import app
from AnnieXMedia.utils.database import (
    add_nonadmin_chat,
    get_authuser,
    get_authuser_names,
    get_playmode,
    get_playtype,
    get_upvote_count,
    is_nonadmin_chat,
    is_skipmode,
    remove_nonadmin_chat,
    set_playmode,
    set_playtype,
    set_upvotes,
    skip_off,
    skip_on,
)
from AnnieXMedia.utils.decorators.admins import ActualAdminCB
from AnnieXMedia.utils.decorators.language import language, languageCB
from AnnieXMedia.utils.inline.settings import (
    auth_users_markup,
    playmode_users_markup,
    setting_markup,
    vote_mode_markup,
    quality_settings_markup,
)
from AnnieXMedia.utils.inline.start import private_panel
from config import BANNED_USERS, OWNER_ID, SUDO_USERS

# متغير الجودة الافتراضي
CURRENT_SESSION_QUALITY = "High"

# ─── SETTINGS MESSAGE ──────────────────────────────────────────────

@app.on_message(filters.command(["settings", "setting"]) & filters.group & ~BANNED_USERS)
@language
async def settings_mar(client, message: Message, _):
    buttons = setting_markup(_, quality=CURRENT_SESSION_QUALITY)
    await message.reply_text(
        _["setting_1"].format(app.mention, message.chat.id, message.chat.title),
        reply_markup=InlineKeyboardMarkup(buttons),
    )

# ─── SETTINGS CALLBACK (HELPER) ─────────────────────────────────────

@app.on_callback_query(filters.regex(r"^SETTINGS_BACK$") & ~BANNED_USERS)
@languageCB
async def settings_cb(client, callback: CallbackQuery, _):
    try:
        await callback.answer(_["set_cb_5"])
    except Exception:
        pass
    buttons = setting_markup(_, quality=CURRENT_SESSION_QUALITY)
    return await callback.edit_message_text(
        _["setting_1"].format(app.mention, callback.message.chat.id, callback.message.chat.title),
        reply_markup=InlineKeyboardMarkup(buttons),
    )

# ─── SETTINGS BACK (PRIVATE vs. GROUP) ──────────────────────────────

@app.on_callback_query(filters.regex(r"^SETTINGS_PRIVATE_BACK$") & ~BANNED_USERS)
@languageCB
async def settings_back_markup(client, callback: CallbackQuery, _):
    try:
        await callback.answer()
    except Exception:
        pass

    if callback.message.chat.type == ChatType.PRIVATE:
        await app.resolve_peer(OWNER_ID)
        buttons = private_panel(_)
        return await callback.edit_message_text(
            _["start_2"].format(callback.from_user.mention, app.mention),
            reply_markup=InlineKeyboardMarkup(buttons),
        )
    else:
        buttons = setting_markup(_, quality=CURRENT_SESSION_QUALITY)
        return await callback.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))

# ─── QUALITY CONTROL (OWNER DASHBOARD) ──────────────────────────────

@app.on_callback_query(filters.regex(r"^(QUALITY_SETTINGS|SET_QUALITY_)") & ~BANNED_USERS)
async def quality_control_handler(client, callback: CallbackQuery):
    global CURRENT_SESSION_QUALITY
    user_id = callback.from_user.id
    
    # التحقق من الصلاحيات (Sudo/Owner)
    if user_id != OWNER_ID and user_id not in SUDO_USERS:
        return await callback.answer(
            "تنبيه أمني: لا تملك الصلاحيات الكافية للوصول إلى إعدادات نواة النظام.",
            show_alert=True
        )

    data = callback.data

    # عرض لوحة التحكم
    if data == "QUALITY_SETTINGS":
        await callback.answer()
        return await callback.edit_message_text(
            text=(
                "ــ لـوحـة تـحـكـم جـودة الـخـادم ــ\n"
                "ــــــــــــــــــــــــــــــــــــــــــــــــــــ\n\n"
                f"حالة المعالجة الحالية : {CURRENT_SESSION_QUALITY}\n\n"
                "[ التقرير التقني ]\n"
                "يؤثر تغيير إعدادات الجودة بشكل مباشر على استهلاك النطاق الترددي (Bandwidth) "
                "وسرعة استجابة الخادم للأوامر الصوتية والمرئية.\n\n"
                "[ الخيارات المتاحة ]\n"
                "ـ Low : وضع توفير الموارد (أسرع استجابة)\n"
                "ـ Medium : الوضع القياسي (متوازن)\n"
                "ـ High : دقة عالية (موصى به للاستقرار)\n"
                "ـ Best : وضع الاستوديو (يتطلب اتصال شبكي قوي)"
            ),
            reply_markup=InlineKeyboardMarkup(
                quality_settings_markup(None, current_quality=CURRENT_SESSION_QUALITY)
            )
        )

    # تنفيذ أمر تغيير الجودة
    elif data.startswith("SET_QUALITY_"):
        target_quality = data.split("_")[2]
        
        # حفظ التغييرات
        CURRENT_SESSION_QUALITY = target_quality.title()
        
        await callback.answer(f"تم تحديث بروتوكول الجودة بنجاح إلى: {CURRENT_SESSION_QUALITY}", show_alert=True)
        
        return await callback.edit_message_text(
            text=(
                "ــ لـوحـة تـحـكـم جـودة الـخـادم ــ\n"
                "ــــــــــــــــــــــــــــــــــــــــــــــــــــ\n\n"
                f"[ تم الحفظ ] : {CURRENT_SESSION_QUALITY}\n\n"
                "تم تطبيق الإعدادات الجديدة على كافة عمليات البث القادمة.\n"
                "يمكنك تعديل المستوى مرة أخرى من الخيارات أدناه."
            ),
            reply_markup=InlineKeyboardMarkup(
                quality_settings_markup(None, current_quality=CURRENT_SESSION_QUALITY)
            )
        )

# ─── INFO CALLBACKS (SYSTEM PANELS) ─────────────────────────────────

@app.on_callback_query(
    filters.regex(
        r"^(SEARCH_MODE_INFO|PLAY_TYPE_INFO|CHANNEL_MODE_INFO|AUTH_USERS_INFO|CURRENT_VOTE_INFO|VOTE_MODE_INFO|PLAYBACK_SETTINGS|AUTH_SETTINGS|VOTE_SETTINGS)$"
    ) & ~BANNED_USERS
)
@languageCB
async def without_admin_rights(client, callback: CallbackQuery, _):
    command = callback.matches[0].group(1)
    
    # تحويل التنبيهات إلى نصوص رسمية
    if command == "SEARCH_MODE_INFO":
        try:
            return await callback.answer(_["setting_2"], show_alert=True)
        except Exception:
            return
    if command == "CHANNEL_MODE_INFO":
        try:
            return await callback.answer(_["setting_5"], show_alert=True)
        except Exception:
            return
    if command == "PLAY_TYPE_INFO":
        try:
            return await callback.answer(_["setting_6"], show_alert=True)
        except Exception:
            return
    if command == "AUTH_USERS_INFO":
        try:
            return await callback.answer(_["setting_3"], show_alert=True)
        except Exception:
            return
    if command == "VOTE_MODE_INFO":
        try:
            return await callback.answer(_["setting_8"], show_alert=True)
        except Exception:
            return
    if command == "CURRENT_VOTE_INFO":
        current = await get_upvote_count(callback.message.chat.id)
        try:
            return await callback.answer(_["setting_9"].format(current), show_alert=True)
        except Exception:
            return
    if command == "PLAYBACK_SETTINGS":
        try:
            await callback.answer(_["set_cb_2"], show_alert=True)
        except Exception:
            pass
        playmode = await get_playmode(callback.message.chat.id)
        Direct = True if playmode == "Direct" else None
        is_non_admin = await is_nonadmin_chat(callback.message.chat.id)
        Group = True if not is_non_admin else None
        playty = await get_playtype(callback.message.chat.id)
        Playtype = None if playty == "Everyone" else True
        buttons = playmode_users_markup(_, Direct, Group, Playtype)
    if command == "AUTH_SETTINGS":
        try:
            await callback.answer(_["set_cb_1"], show_alert=True)
        except Exception:
            pass
        is_non_admin = await is_nonadmin_chat(callback.message.chat.id)
        buttons = auth_users_markup(_, True) if not is_non_admin else auth_users_markup(_)
    if command == "VOTE_SETTINGS":
        mode = await is_skipmode(callback.message.chat.id)
        current = await get_upvote_count(callback.message.chat.id)
        buttons = vote_mode_markup(_, current, mode)
    try:
        return await callback.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
    except MessageNotModified:
        return

# ─── VOTE COUNT ADJUSTMENT ──────────────────────────────────────────

@app.on_callback_query(filters.regex(r"^(INCREASE_VOTE_COUNT|DECREASE_VOTE_COUNT)$") & ~BANNED_USERS)
@ActualAdminCB
async def vote_count_adjust(client, callback: CallbackQuery, _):
    command = callback.matches[0].group(1)
    
    if not await is_skipmode(callback.message.chat.id):
        return await callback.answer(_["setting_10"], show_alert=True)
    
    current = await get_upvote_count(callback.message.chat.id)
    
    if command == "DECREASE_VOTE_COUNT":
        final = current - 2
        if final < 2:
            final = 2
            await callback.answer(_["setting_11"], show_alert=True)
        await set_upvotes(callback.message.chat.id, final)
    else:  # INCREASE_VOTE_COUNT
        final = current + 2
        if final > 15:
            final = 15
            await callback.answer(_["setting_12"], show_alert=True)
        await set_upvotes(callback.message.chat.id, final)
    
    buttons = vote_mode_markup(_, final, True)
    
    try:
        return await callback.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
    except MessageNotModified:
        return

# ─── PLAYMODE / PLAYTYPE CHANGE ─────────────────────────────────────

@app.on_callback_query(
    filters.regex(r"^(TOGGLE_SEARCH_MODE|TOGGLE_CHANNEL_MODE|TOGGLE_PLAY_TYPE)$") & ~BANNED_USERS
)
@ActualAdminCB
async def playmode_ans(client, callback: CallbackQuery, _):
    command = callback.matches[0].group(1)
    
    if command == "TOGGLE_CHANNEL_MODE":
        is_non_admin = await is_nonadmin_chat(callback.message.chat.id)
        if not is_non_admin:
            await add_nonadmin_chat(callback.message.chat.id)
            Group = None
        else:
            await remove_nonadmin_chat(callback.message.chat.id)
            Group = True
        playmode = await get_playmode(callback.message.chat.id)
        Direct = True if playmode == "Direct" else None
        playty = await get_playtype(callback.message.chat.id)
        Playtype = None if playty == "Everyone" else True
        buttons = playmode_users_markup(_, Direct, Group, Playtype)
    
    elif command == "TOGGLE_SEARCH_MODE":
        try:
            await callback.answer(_["set_cb_3"], show_alert=True)
        except Exception:
            pass
        playmode = await get_playmode(callback.message.chat.id)
        if playmode == "Direct":
            await set_playmode(callback.message.chat.id, "Inline")
            Direct = None
        else:
            await set_playmode(callback.message.chat.id, "Direct")
            Direct = True
        is_non_admin = await is_nonadmin_chat(callback.message.chat.id)
        Group = True if not is_non_admin else None
        playty = await get_playtype(callback.message.chat.id)
        Playtype = False if playty == "Everyone" else True
        buttons = playmode_users_markup(_, Direct, Group, Playtype)
    
    elif command == "TOGGLE_PLAY_TYPE":
        try:
            await callback.answer(_["set_cb_3"], show_alert=True)
        except Exception:
            pass
        playty = await get_playtype(callback.message.chat.id)
        if playty == "Everyone":
            await set_playtype(callback.message.chat.id, "Admin")
            Playtype = False
        else:
            await set_playtype(callback.message.chat.id, "Everyone")
            Playtype = True
        playmode = await get_playmode(callback.message.chat.id)
        Direct = True if playmode == "Direct" else None
        is_non_admin = await is_nonadmin_chat(callback.message.chat.id)
        Group = True if not is_non_admin else None
        buttons = playmode_users_markup(_, Direct, Group, Playtype)
    
    try:
        return await callback.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
    except MessageNotModified:
        return

# ─── AUTH USERS (AUTH / AUTHLIST) ─────────────────────────────────────

@app.on_callback_query(filters.regex(r"^(TOGGLE_AUTH_MODE|VIEW_AUTH_USERS)$") & ~BANNED_USERS)
@ActualAdminCB
async def authusers_mar(client, callback: CallbackQuery, _):
    command = callback.matches[0].group(1)
    
    if command == "VIEW_AUTH_USERS":
        _authusers = await get_authuser_names(callback.message.chat.id)
        if not _authusers:
            try:
                return await callback.answer(_["setting_4"], show_alert=True)
            except Exception:
                return
        else:
            try:
                await callback.answer(_["set_cb_4"], show_alert=True)
            except Exception:
                pass
            counter = 0
            await callback.edit_message_text(_["auth_6"])
            msg = _["auth_7"].format(callback.message.chat.title)
            for note in _authusers:
                _note = await get_authuser(callback.message.chat.id, note)
                user_id = _note["auth_user_id"]
                admin_id = _note["admin_id"]
                admin_name = _note["admin_name"]
                try:
                    user_obj = await app.get_users(user_id)
                    user_name = user_obj.first_name
                    counter += 1
                except Exception:
                    continue
                msg += f"{counter}➤ {user_name}[<code>{user_id}</code>]\n"
                msg += f"   {_['auth_8']} {admin_name}[<code>{admin_id}</code>]\n\n"
            upl = InlineKeyboardMarkup(
                [[
                    InlineKeyboardButton(text=_["BACK_BUTTON"], callback_data="AUTH_SETTINGS"),
                    InlineKeyboardButton(text=_["CLOSE_BUTTON"], callback_data="close")
                ]]
            )
            try:
                return await callback.edit_message_text(msg, reply_markup=upl)
            except MessageNotModified:
                return
    
    try:
        await callback.answer(_["set_cb_3"], show_alert=True)
    except Exception:
        pass
    
    if command == "TOGGLE_AUTH_MODE":
        is_non_admin = await is_nonadmin_chat(callback.message.chat.id)
        if not is_non_admin:
            await add_nonadmin_chat(callback.message.chat.id)
            buttons = auth_users_markup(_)
        else:
            await remove_nonadmin_chat(callback.message.chat.id)
            buttons = auth_users_markup(_, True)
    
    try:
        return await callback.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
    except MessageNotModified:
        return

# ─── VOTE MODE CHANGE ────────────────────────────────────────────────

@app.on_callback_query(filters.regex(r"^TOGGLE_VOTE_MODE$") & ~BANNED_USERS)
@ActualAdminCB
async def vote_change(client, callback: CallbackQuery, _):
    try:
        await callback.answer(_["set_cb_3"], show_alert=True)
    except Exception:
        pass
    
    mod = None
    if await is_skipmode(callback.message.chat.id):
        await skip_off(callback.message.chat.id)
    else:
        mod = True
        await skip_on(callback.message.chat.id)
    
    current = await get_upvote_count(callback.message.chat.id)
    buttons = vote_mode_markup(_, current, mod)
    
    try:
        return await callback.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
    except MessageNotModified:
        return
