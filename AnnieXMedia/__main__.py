# Authored By Certified Coders © 2025
# Modified for Titan OS Integration (Fast-Start Edition)
import sys
import os
import threading
import uvicorn
import asyncio
import importlib

# إجبار استخدام المجلد المحلي
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
# [1] إعداد واجهة Titan OS
# ==============================================================================
try:
    from AnnieXMedia.TitanOS.web_srv import app as titan_app
    WEB_AVAILABLE = True
except ImportError as e:
    print(f"\n⚠️ Web Interface Error: {e}\n")
    WEB_AVAILABLE = False

def start_web_server():
    # تشغيل السيرفر بصمت (بدون إزعاج في السجلات)
    uvicorn.run(titan_app, host="0.0.0.0", port=8080, log_level="error")
# ==============================================================================

async def init():
    # 🔥 تشغيل الموقع فوراً في البداية (قبل أي شيء آخر)
    # هذا يمنع خطأ "Connection Refused" في المنصات السحابية
    if WEB_AVAILABLE:
        print("🚀 TitanOS: Starting Dashboard instantly on Port 8080...")
        web_thread = threading.Thread(target=start_web_server, daemon=True)
        web_thread.start()

    # --------------------------------------------------------------------------
    # بداية تحميل البوت الطبيعي
    # --------------------------------------------------------------------------
    if (
        not config.STRING1
        and not config.STRING2
        and not config.STRING3
        and not config.STRING4
        and not config.STRING5
    ):
        LOGGER(__name__).error("Session not filled!")
        exit()

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

    # تجربة الاتصال (Sintel Test)
    try:
        await StreamController.stream_call("http://docs.evostream.com/sample_content/assets/sintel1m720p.mp4")
    except NoActiveGroupCall:
        LOGGER("AnnieXMedia").error("Please turn on VC. Bot stopped.")
        exit()
    except:
        pass

    await StreamController.decorators()
    LOGGER("AnnieXMedia").info("Annie Music Robot Started Successfully... Titan OS is Ready 🛸")
    
    await idle()
    await app.stop()
    await userbot.stop()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(init())
