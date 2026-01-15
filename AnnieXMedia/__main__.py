# Authored By Certified Coders © 2025
# Modified for Titan OS Integration
import sys
import os
import threading
import uvicorn
import asyncio
import importlib

# السطر ده بيجبر البوت يستخدم مجلد pytgcalls المحلي بدل اللي نازل من النت
sys.path.insert(0, os.getcwd())

from pyrogram import idle
from pytgcalls.exceptions import NoActiveGroupCall

import config
from AnnieXMedia import LOGGER, app, userbot
from AnnieXMedia.core.call import StreamController
from AnnieXMedia.misc import sudo
from AnnieXMedia.plugins import ALL_MODULES
from AnnieXMedia.utils.database import get_banned_users, get_gbanned
from AnnieXMedia.utils.cookie_handler import fetch_and_store_cookies
from config import BANNED_USERS

# ==============================================================================
# [1] إعداد واجهة Titan OS (الويب)
# ==============================================================================
# نحاول استيراد ملف الويب من المسار: AnnieXMedia -> TitanOS -> web_srv.py
try:
    from AnnieXMedia.TitanOS.web_srv import app as titan_app
    WEB_AVAILABLE = True
except ImportError as e:
    # لن نوقف البوت إذا فشل الويب، فقط سنطبع تحذير
    print(f"\n⚠️ Web Interface Error: {e}")
    print("Continuing in Bot-Only Mode...\n")
    WEB_AVAILABLE = False

def start_web_server():
    """تشغيل سيرفر الويب في خلفية النظام"""
    # نستخدم log_level='error' عشان ما يزحم الكونسول
    uvicorn.run(titan_app, host="0.0.0.0", port=8080, log_level="error")
# ==============================================================================


async def init():
    if (
        not config.STRING1
        and not config.STRING2
        and not config.STRING3
        and not config.STRING4
        and not config.STRING5
    ):
        LOGGER(__name__).error("ᴀssɪsᴛᴀɴᴛ sᴇssɪᴏɴ ɴᴏᴛ ғɪʟʟᴇᴅ, ᴘʟᴇᴀsᴇ ғɪʟʟ ᴀ ᴘʏʀᴏɢʀᴀᴍ sᴇssɪᴏɴ...")
        exit()

    # ✅ Try to fetch cookies at startup
    try:
        await fetch_and_store_cookies()
        LOGGER("AnnieXMedia").info("ʏᴏᴜᴛᴜʙᴇ ᴄᴏᴏᴋɪᴇs ʟᴏᴀᴅᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ ✅")
    except Exception as e:
        LOGGER("AnnieXMedia").warning(f"⚠️ᴄᴏᴏᴋɪᴇ ᴇʀʀᴏʀ: {e}")


    await sudo()

    try:
        users = await get_gbanned()
        for user_id in users:
            BANNED_USERS.add(user_id)
        users = await get_banned_users()
        for user_id in users:
            BANNED_USERS.add(user_id)
    except:
        pass

    await app.start()
    for all_module in ALL_MODULES:
        importlib.import_module("AnnieXMedia.plugins" + all_module)

    LOGGER("AnnieXMedia.plugins").info("ᴀɴɴɪᴇ's ᴍᴏᴅᴜʟᴇs ʟᴏᴀᴅᴇᴅ...")

    await userbot.start()
    await StreamController.start()

    # تشغيل فيديو تجريبي للتأكد من عمل البوت (كود قديم مهم)
    try:
        await StreamController.stream_call("http://docs.evostream.com/sample_content/assets/sintel1m720p.mp4")
    except NoActiveGroupCall:
        LOGGER("AnnieXMedia").error(
            "ᴘʟᴇᴀsᴇ ᴛᴜʀɴ ᴏɴ ᴛʜᴇ ᴠᴏɪᴄᴇ ᴄʜᴀᴛ ᴏғ ʏᴏᴜʀ ʟᴏɢ ɢʀᴏᴜᴘ/ᴄʜᴀɴɴᴇʟ.\n\nᴀɴɴɪᴇ ʙᴏᴛ sᴛᴏᴘᴘᴇᴅ..."
        )
        exit()
    except:
        pass

    await StreamController.decorators()
    LOGGER("AnnieXMedia").info(
        "\x41\x6e\x6e\x69\x65\x20\x4d\x75\x73\x69\x63\x20\x52\x6f\x62\x6f\x74\x20\x53\x74\x61\x72\x74\x65\x64\x20\x53\x75\x63\x63\x65\x73\x73\x66\x75\x6c\x6c\x79\x2e\x2e\x2e"
    )

    # ==============================================================================
    # [2] تشغيل الويب قبل الدخول في وضع الخمول
    # ==============================================================================
    if WEB_AVAILABLE:
        LOGGER("TitanOS").info("🚀 Starting Dashboard on Port 8080...")
        # تشغيل الفلاسك في Thread منفصل لكي لا يوقف البوت
        web_thread = threading.Thread(target=start_web_server, daemon=True)
        web_thread.start()
    # ==============================================================================

    await idle()
    await app.stop()
    await userbot.stop()
    LOGGER("AnnieXMedia").info("sᴛᴏᴘᴘɪɴɢ ᴀɴɴɪᴇ ᴍᴜsɪᴄ ʙᴏᴛ ...")


if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(init())
