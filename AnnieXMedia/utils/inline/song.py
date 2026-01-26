from pyrogram.types import InlineKeyboardButton
import config

def song_markup(_, vidid):
    return [
        [
            InlineKeyboardButton(
                text="تـحـمـيـل صـوت",
                callback_data=f"song_helper audio|{vidid}",
            ),
        ],
        [
            InlineKeyboardButton(
                text="تـحـمـيـل فـيـديـو",
                callback_data=f"song_helper video|{vidid}",
            ),
        ],
        [
            InlineKeyboardButton(
                text="قـنـاة الـدعـم",
                url=config.SUPPORT_GROUP,
            ),
        ],
        [
            InlineKeyboardButton(
                text="إغـلاق", 
                callback_data="close"
            ),
        ],
    ]
