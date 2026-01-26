from pyrogram.types import InlineKeyboardButton
import config

def song_markup(_, vidid):
    # جلب رابط الدعم بشكل مرن لتفادي أخطاء التشغيل
    support_link = getattr(config, "SUPPORT_GROUP", getattr(config, "SUPPORT_CHAT", "https://t.me/M_R_B_V"))
    
    return [
        [
            InlineKeyboardButton(
                text="• صـوت •",
                callback_data=f"song_helper audio|{vidid}",
            ),
        ],
        [
            InlineKeyboardButton(
                text="• فـيـديـو •",
                callback_data=f"song_helper video|{vidid}",
            ),
        ],
        [
            InlineKeyboardButton(
                text="• قـنـاة الـدعـم •",
                url=support_link,
            ),
        ],
        [
            InlineKeyboardButton(
                text="• إغـلاق •", 
                callback_data="close"
            ),
        ],
    ]
