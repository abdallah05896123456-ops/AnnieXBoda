# Authored By Certified Coders 2026
# Module: XO Admin Control Panel (Tools)

from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from AnnieXMedia import app
from AnnieXMedia.misc import SUDOERS
import config

# ─── Initialize Configs ───
if not hasattr(config, "XO_ENABLED"):
    config.XO_ENABLED = True
if not hasattr(config, "XO_CHEAT"):
    config.XO_CHEAT = False 

# ─── Admin Panel Command ───

@app.on_message(filters.command(["كيب اكس او"], prefixes=["", "/", "!"]) & SUDOERS)
async def xo_admin_panel(_, message):
    await send_control_panel(message)

async def send_control_panel(message):
    # Status Indicators
    status_txt = "Enabled" if config.XO_ENABLED else "Disabled"
    cheat_txt = "Active (AI is Stupid)" if config.XO_CHEAT else "Inactive (AI is Smart)"

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"Game Status : {status_txt}", callback_data="xo_adm_toggle"),
        ],
        [
            InlineKeyboardButton(f"Cheat Mode : {cheat_txt}", callback_data="xo_adm_cheat"),
        ],
        [
            InlineKeyboardButton("Close Panel", callback_data="xo_adm_close")
        ]
    ])

    text = (
        "**Welcome to XO System Control Panel .**\n\n"
        "**Settings Overview :**\n"
        f"**Game State :** {status_txt} .\n"
        f"**Cheat Mode :** {cheat_txt} .\n\n"
        "**Cheat Mode Effect :**\n"
        "If Active, the AI will ignore difficulty levels and play randomly, allowing you to win easily .\n\n"
        "**Click buttons to change settings .**"
    )

    if isinstance(message, CallbackQuery):
        try:
            await message.edit_message_text(text, reply_markup=keyboard)
        except:
            pass
    else:
        await message.reply_text(text, reply_markup=keyboard)

# ─── Callback Handler ───

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
