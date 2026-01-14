# ================================
# __main__.py (Linked with web_dashboard)
# ================================

import sys
import os
import asyncio
import importlib
from pyrogram import idle
from pytgcalls.exceptions import NoActiveGroupCall

# ------------------------
# Paths: أهم سطر عشان يشوف الملف اللي بره
# ------------------------
sys.path.insert(0, os.getcwd())

# ------------------------
# Imports
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
# 🔥 تشغيل TitanOS Dashboard 🔥
# ------------------------
try:
    # استدعاء الملف من الروت
    from web_dashboard import start_titan
    start_titan()
    LOGGER("TitanOS").info("✅ Dashboard Running on Port 8080")
except ImportError:
    LOGGER("TitanOS").warning("⚠️ web_dashboard.py not found in root!")
except Exception as e:
    LOGGER("TitanOS").error(f"❌ Dashboard Error: {e}")

# ========================
# Init Function
# ========================
async def init():
    if (
        not config.STRING1
        and not config.STRING2
        and not config.STRING3
        and not config.STRING4
        and not config.STRING5
    ):
        LOGGER(__name__).error("Please fill Pyrogram Session...")
        exit()

    try:
        await fetch_and_store_cookies()
        LOGGER("AnnieXMedia").info("YouTube Cookies Loaded ✅")
    except:
        pass

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
    LOGGER("AnnieXMedia").info("✅ Bot Client Started")

    for all_module in ALL_MODULES:
        importlib.import_module("AnnieXMedia.plugins" + all_module)
    LOGGER("AnnieXMedia.plugins").info("✅ Modules Loaded...")

    await userbot.start()
    await StreamController.start()

    try:
        await StreamController.stream_call(
            "http://docs.evostream.com/sample_content/assets/sintel1m720p.mp4"
        )
    except NoActiveGroupCall:
        LOGGER("AnnieXMedia").error("Please turn on Video Chat in Log Group!")
        exit()
    except:
        pass

    await StreamController.decorators()
    LOGGER("AnnieXMedia").info("🚀 Annie Music Started Successfully...")
    
    await idle()

    await app.stop()
    await userbot.stop()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(init())
