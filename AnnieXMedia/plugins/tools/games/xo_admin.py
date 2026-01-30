# Authored By Certified Coders 2026
# Module: XO Admin Control Panel (Arabic Version)

from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from AnnieXMedia import app
from AnnieXMedia.misc import SUDOERS
import config

# ─── إعدادات افتراضية ───
if not hasattr(config, "XO_ENABLED"):
    config.XO_ENABLED = True
if not hasattr(config, "XO_CHEAT"):
    config.XO_CHEAT = False 

# ─── أمر لوحة التحكم ───

@app.on_message(filters.command(["كيب اكس او", "تعطيل اكس او", "تفعيل اكس او"], prefixes=["", "/", "!"]) & SUDOERS)
async def xo_admin_panel(_, message):
    await send_control_panel(message)

async def send_control_panel(message):
    # نصوص الحالة
    status_txt = "مفعل" if config.XO_ENABLED else "معطل"
    cheat_txt = "نشط (الذكاء غبي)" if config.XO_CHEAT else "غير نشط (الذكاء حاد)"

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"حالة اللعبة : {status_txt}", callback_data="xo_adm_toggle"),
        ],
        [
            InlineKeyboardButton(f"وضع الغش : {cheat_txt}", callback_data="xo_adm_cheat"),
        ],
        [
            InlineKeyboardButton(f"اغلاق اللوحة", callback_data="xo_adm_close")
        ]
    ])

    text = (
        "**مرحباً بك في لوحة تحكم نظام XO .**\n\n"
        "**نظرة عامة على الإعدادات :**\n"
        f"**حالة اللعبة :** {status_txt} .\n"
        f"**وضع الغش :** {cheat_txt} .\n\n"
        "**تأثير وضع الغش :**\n"
        "عند تفعيله، سيلعب البوت بشكل عشوائي تماماً (غبي) ليسمح لك بالفوز بسهولة مهما كانت الصعوبة .\n\n"
        "**اضغط الازرار لتغيير الإعدادات .**"
    )

    if isinstance(message, CallbackQuery):
        try:
            await message.edit_message_text(text, reply_markup=keyboard)
        except:
            pass
    else:
        await message.reply_text(text, reply_markup=keyboard)

# ─── معالجة الازرار ───

@app.on_callback_query(filters.regex(r"^xo_adm_") & SUDOERS)
async def xo_admin_callbacks(_, query: CallbackQuery):
    data = query.data
    
    if data == "xo_adm_toggle":
        config.XO_ENABLED = not config.XO_ENABLED
        await send_control_panel(query)
        
    elif data == "xo_adm_cheat":
        config.XO_CHEAT = not config.XO_CHEAT
        await send_control_panel(query)

    elif data == "xo_adm_close":
        await query.message.delete()
