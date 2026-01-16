# Authored By Certified Coders © 2025
from typing import Union
from pyrogram.types import InlineKeyboardButton

# =============================================================================
# ⚙️ MAIN SETTINGS MENU
# =============================================================================
def setting_markup(_, quality: str = "High"):
    buttons = [
        [
            InlineKeyboardButton(text=_["ST_B_1"], callback_data="AUTH_SETTINGS"),
            InlineKeyboardButton(text=_["ST_B_3"], callback_data="LANGUAGE_SETTINGS"),
        ],
        [
            InlineKeyboardButton(text=_["ST_B_2"], callback_data="PLAYBACK_SETTINGS"),
        ],
        [
            # أضفنا علامة القفل 🔐 للدلالة على أنها للأونر فقط
            InlineKeyboardButton(
                text=f"♥️ جودة الصوت : {quality.upper()}",
                callback_data="QUALITY_SETTINGS",
            ),
        ],
        [
            InlineKeyboardButton(text=_["ST_B_4"], callback_data="VOTE_SETTINGS"),
        ],
        [
            InlineKeyboardButton(text=_["CLOSE_BUTTON"], callback_data="close"),
        ],
    ]
    return buttons


# =============================================================================
# 🎚 QUALITY SETTINGS (OWNER ONLY)
# =============================================================================
def quality_settings_markup(_, current_quality: str):
    # تطبيع النص لحروف صغيرة للمقارنة
    q = current_quality.lower().strip() if current_quality else "high"

    # تحديد الزر النشط
    s_low = "✅ " if q == "low" else ""
    s_med = "✅ " if q == "medium" else ""
    s_high = "✅ " if q == "high" else ""
    s_best = "✅ " if q == "best" else ""

    buttons = [
        [
            # جودة منخفضة (توفير داتا وسرعة)
            InlineKeyboardButton(text=f"{s_low}Low (Saver)", callback_data="SET_QUALITY_low"),
            # جودة متوسطة (الافتراضي للتيليجرام)
            InlineKeyboardButton(text=f"{s_med}Medium (Std)", callback_data="SET_QUALITY_medium"),
        ],
        [
            # جودة عالية (HD / 192kbps)
            InlineKeyboardButton(text=f"{s_high}High (HD)", callback_data="SET_QUALITY_high"),
            # جودة قصوى (4K / 320kbps)
            InlineKeyboardButton(text=f"{s_best}Best (Studio)", callback_data="SET_QUALITY_best"),
        ],
        [
            InlineKeyboardButton(
                text=_["BACK_BUTTON"],
                callback_data="SETTINGS_BACK",
            ),
            InlineKeyboardButton(text=_["CLOSE_BUTTON"], callback_data="close"),
        ],
    ]
    return buttons


# =============================================================================
# 🗳 VOTE MODE SETTINGS
# =============================================================================
def vote_mode_markup(_, current, mode: Union[bool, str] = None):
    buttons = [
        [
            InlineKeyboardButton(text="Vᴏᴛɪɴɢ ᴍᴏᴅᴇ ➜", callback_data="VOTE_MODE_INFO"),
            InlineKeyboardButton(
                text=_["ST_B_5"] if mode == True else _["ST_B_6"],
                callback_data="TOGGLE_VOTE_MODE",
            ),
        ],
        [
            InlineKeyboardButton(text="-2", callback_data="DECREASE_VOTE_COUNT"),
            InlineKeyboardButton(
                text=f"ᴄᴜʀʀᴇɴᴛ : {current}",
                callback_data="CURRENT_VOTE_INFO",
            ),
            InlineKeyboardButton(text="+2", callback_data="INCREASE_VOTE_COUNT"),
        ],
        [
            InlineKeyboardButton(
                text=_["BACK_BUTTON"],
                callback_data="SETTINGS_BACK",
            ),
            InlineKeyboardButton(text=_["CLOSE_BUTTON"], callback_data="close"),
        ],
    ]
    return buttons


# =============================================================================
# 🔐 AUTH USERS SETTINGS
# =============================================================================
def auth_users_markup(_, status: Union[bool, str] = None):
    buttons = [
        [
            InlineKeyboardButton(text=_["ST_B_7"], callback_data="AUTH_USERS_INFO"),
            InlineKeyboardButton(
                text=_["ST_B_8"] if status == True else _["ST_B_9"],
                callback_data="TOGGLE_AUTH_MODE",
            ),
        ],
        [
            InlineKeyboardButton(text=_["ST_B_1"], callback_data="VIEW_AUTH_USERS"),
        ],
        [
            InlineKeyboardButton(
                text=_["BACK_BUTTON"],
                callback_data="SETTINGS_BACK",
            ),
            InlineKeyboardButton(text=_["CLOSE_BUTTON"], callback_data="close"),
        ],
    ]
    return buttons


# =============================================================================
# ▶️ PLAY MODE SETTINGS
# =============================================================================
def playmode_users_markup(
    _,
    Direct: Union[bool, str] = None,
    Group: Union[bool, str] = None,
    Playtype: Union[bool, str] = None,
):
    buttons = [
        [
            InlineKeyboardButton(text=_["ST_B_10"], callback_data="SEARCH_MODE_INFO"),
            InlineKeyboardButton(
                text=_["ST_B_11"] if Direct == True else _["ST_B_12"],
                callback_data="TOGGLE_SEARCH_MODE",
            ),
        ],
        [
            InlineKeyboardButton(text=_["ST_B_13"], callback_data="CHANNEL_MODE_INFO"),
            InlineKeyboardButton(
                text=_["ST_B_8"] if Group == True else _["ST_B_9"],
                callback_data="TOGGLE_CHANNEL_MODE",
            ),
        ],
        [
            InlineKeyboardButton(text=_["ST_B_14"], callback_data="PLAY_TYPE_INFO"),
            InlineKeyboardButton(
                text=_["ST_B_8"] if Playtype == True else _["ST_B_9"],
                callback_data="TOGGLE_PLAY_TYPE",
            ),
        ],
        [
            InlineKeyboardButton(
                text=_["BACK_BUTTON"],
                callback_data="SETTINGS_BACK",
            ),
            InlineKeyboardButton(text=_["CLOSE_BUTTON"], callback_data="close"),
        ],
    ]
    return buttons
