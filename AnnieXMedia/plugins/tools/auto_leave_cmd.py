# Authored By Certified Coders 2026
# Module: Auto Leave Commands (Tools)

from pyrogram import filters
import config
from AnnieXMedia import app
from AnnieXMedia.misc import SUDOERS

@app.on_message(filters.command(["تفعيل المغادرة", "تعطيل المغادرة", "تفعيل مغادرة", "تعطيل مغادرة"]) & SUDOERS)
async def control_auto_leave(_, message):
    command = message.text
    if "تفعيل" in command:
        config.AUTO_LEAVING_ASSISTANT = True
        await message.reply_text("تم تفعيل وضع المغادرة التلقائية للحساب المساعد.\nسيقوم المساعد بمغادرة المجموعات غير النشطة تلقائياً.")
    elif "تعطيل" in command:
        config.AUTO_LEAVING_ASSISTANT = False
        await message.reply_text("تم تعطيل وضع المغادرة التلقائية.\nلن يغادر المساعد أي مجموعة الآن.")
