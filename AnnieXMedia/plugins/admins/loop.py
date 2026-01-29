# Authored By Certified Coders 2026
# Module: Loop Stream - Arabic Commands + Language Support

from pyrogram import filters
from pyrogram.types import Message

from AnnieXMedia import app
from AnnieXMedia.utils.database import get_loop, set_loop
from AnnieXMedia.utils.decorators import AdminRightsCheck
from AnnieXMedia.utils.inline import close_markup
from config import BANNED_USERS


@app.on_message(
    filters.command(["loop", "cloop", "تكرار", "كرر"], prefixes=["", "/", "!", "."]) 
    & filters.group 
    & ~BANNED_USERS
)
@AdminRightsCheck
async def admins(cli, message: Message, _, chat_id):
    usage = _["admin_17"]
    if len(message.command) != 2:
        return await message.reply_text(usage)
    
    state = message.text.split(None, 1)[1].strip()
    
    # حالة التكرار برقم معين (مثلاً: تكرار 3)
    if state.isnumeric():
        state = int(state)
        if 1 <= state <= 10:
            got = await get_loop(chat_id)
            if got != 0:
                state = got + state
            if int(state) > 10:
                state = 10
            await set_loop(chat_id, state)
            return await message.reply_text(
                text=_["admin_18"].format(state, message.from_user.mention),
                reply_markup=close_markup(_),
            )
        else:
            return await message.reply_text(_["admin_17"])
    
    # حالة التفعيل (تكرار تفعيل / تكرار عام)
    elif state.lower() in ["enable", "تفعيل", "عام"]:
        await set_loop(chat_id, 10)
        return await message.reply_text(
            text=_["admin_18"].format(state, message.from_user.mention),
            reply_markup=close_markup(_),
        )
    
    # حالة التعطيل (تكرار تعطيل / تكرار قفل)
    elif state.lower() in ["disable", "تعطيل", "قفل", "الغاء"]:
        await set_loop(chat_id, 0)
        return await message.reply_text(
            _["admin_19"].format(message.from_user.mention),
            reply_markup=close_markup(_),
        )
    
    else:
        return await message.reply_text(usage)
