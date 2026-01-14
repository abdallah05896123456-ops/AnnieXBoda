# ================================
# __main__.py AnnieXMedia
# ================================

import sys
import os
import asyncio
import importlib
from pyrogram import idle
from pytgcalls.exceptions import NoActiveGroupCall

# ------------------------
# Paths: مجلد pytgcalls المحلي + web modules
# ------------------------
sys.path.insert(0, os.getcwd())  # إجبار البوت يستخدم نسخة pytgcalls المحلية
sys.path.insert(0, os.path.join(os.getcwd(), "web"))  # إضافة مجلد web للـ imports

# ------------------------
# استيراد مكتبات AnnieXMedia
# ------------------------
import config
from AnnieXMedia import LOGGER, app, userbot
from AnnieXMedia.core.call import StreamController
from AnnieXMedia.misc import sudo
from AnnieXMedia.plugins import ALL_MODULES
from AnnieXMedia.utils.database import get_banned_users, get_gbanned
from AnnieXMedia.utils.cookie_handler import fetch_and_store_cookies
from config import BANNED_USERS

# ------------------------
# استيراد ملفات web مباشرة
# ------------------------
import Resource_Optimizer
import backend_bridge
import security_gate

# ========================
# دالة Init لتشغيل كل شيء
# ========================
async def init():
    # تحقق من أن أي من STRING1-5 موجود لتشغيل session
    if (
        not config.STRING1
        and not config.STRING2
        and not config.STRING3
        and not config.STRING4
        and not config.STRING5
    ):
        LOGGER(__name__).error(
            "ᴀssɪsᴛᴀɴᴛ sᴇssɪᴏɴ ɴᴏᴛ ғɪʟʟᴇᴅ, ᴘʟᴇᴀsᴇ ғɪʟʟ ᴀ ᴘʏʀᴏɢʀᴀᴍ sᴇssɪᴏɴ..."
        )
        exit()

    # ------------------------
    # تحميل ملفات الكوكيز
    # ------------------------
    try:
        await fetch_and_store_cookies()
        LOGGER("AnnieXMedia").info("ʏᴏᴜᴛᴜʙᴇ ᴄᴏᴏᴋɪᴇs ʟᴏᴀᴅᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ ✅")
    except Exception as e:
        LOGGER("AnnieXMedia").warning(f"⚠️ᴄᴏᴏᴋɪᴇ ᴇʀʀᴏʀ: {e}")

    # ------------------------
    # تهيئة صلاحيات sudo
    # ------------------------
    await sudo()

    # ------------------------
    # جلب المستخدمين المحظورين
    # ------------------------
    try:
        users = await get_gbanned()
        for user_id in users:
            BANNED_USERS.add(user_id)
        users = await get_banned_users()
        for user_id in users:
            BANNED_USERS.add(user_id)
    except:
        pass

    # ------------------------
    # تشغيل FastAPI backend
    # ------------------------
    await app.start()
    LOGGER("AnnieXMedia").info("FastAPI backend started ✅")

    # ------------------------
    # تحميل كل الـ plugins
    # ------------------------
    for all_module in ALL_MODULES:
        importlib.import_module("AnnieXMedia.plugins" + all_module)
    LOGGER("AnnieXMedia.plugins").info("ᴀɴɴɪᴇ's ᴍᴏᴅᴜʟᴇs ʟᴏᴀᴅᴇᴅ...")

    # ------------------------
    # تشغيل userbot و StreamController
    # ------------------------
    await userbot.start()
    await StreamController.start()

    # ------------------------
    # تشغيل مثال صوتي للتأكد من اتصال الـ Voice Chat
    # ------------------------
    try:
        await StreamController.stream_call(
            "http://docs.evostream.com/sample_content/assets/sintel1m720p.mp4"
        )
    except NoActiveGroupCall:
        LOGGER("AnnieXMedia").error(
            "ᴘʟᴇᴀsᴇ ᴛᴜʀɴ ᴏɴ ᴛʜᴇ ᴠᴏɪᴄᴇ ᴄʜᴀᴛ ᴏғ ʏᴏᴜʀ ʟᴏɢ ɢʀᴏᴜᴘ/ᴄʜᴀɴɴᴇʟ.\n\n"
            "ᴀɴɴɪᴇ ʙᴏᴛ sᴛᴏᴘᴘᴇᴅ..."
        )
        exit()
    except Exception:
        pass

    # ------------------------
    # Decorators و idle loop
    # ------------------------
    await StreamController.decorators()
    LOGGER("AnnieXMedia").info("Annie Music Robot Started Successfully...")
    await idle()

    # ------------------------
    # إيقاف كل شيء عند الخروج
    # ------------------------
    await app.stop()
    await userbot.stop()
    LOGGER("AnnieXMedia").info("Stopping Annie Music Bot...")

# ========================
# نقطة الدخول
# ========================
if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(init())
