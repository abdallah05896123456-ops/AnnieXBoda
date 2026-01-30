# Authored By Certified Coders 2026
# Module: Waifu/Anime Commands (Tools)

from pyrogram import filters
import config
from AnnieXMedia import app
from AnnieXMedia.misc import SUDOERS

# تهيئة المتغير في الكونفج إذا لم يكن موجوداً
if not hasattr(config, "ANIMATION_MODE"):
    config.ANIMATION_MODE = False

@app.on_message(filters.command(["تفعيل الانمي", "تعطيل الانمي"]) & SUDOERS)
async def toggle_anime_mode(client, message):
    command = message.text
    
    if "تفعيل" in command:
        config.ANIMATION_MODE = True
        await message.reply_text("تم تفعيل وضع الانمي (الصور المتحركة) بنجاح.")
    else:
        config.ANIMATION_MODE = False
        await message.reply_text("تم تعطيل وضع الانمي بنجاح.")
