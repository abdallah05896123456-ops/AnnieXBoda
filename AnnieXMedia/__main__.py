# ================================
# __main__.py (All-in-One: Bot + TitanOS)
# ================================

import sys
import os
import asyncio
import importlib
import logging
from threading import Thread
from flask import Flask, render_template, jsonify
from pyrogram import idle
from pytgcalls.exceptions import NoActiveGroupCall

# ------------------------
# إعدادات السيرفر (Flask) داخل البوت
# ------------------------
# تحديد مكان فولدر TitanOS (بنفترض إنه في الروت جنب requirements.txt)
BASE_DIR = os.getcwd()
TITAN_DIR = os.path.join(BASE_DIR, 'TitanOS')

# تأكد إن الفولدر موجود، لو مش موجود حاول تدور عليه جوه AnnieXMedia
if not os.path.exists(TITAN_DIR):
    TITAN_DIR = os.path.join(BASE_DIR, 'AnnieXMedia', 'TitanOS')

app = Flask(__name__, template_folder=TITAN_DIR, static_folder=TITAN_DIR)
app.secret_key = "Titan_Integrated_Secret"

# إخفاء رسائل اللوج المزعجة للفلاسك
logging.getLogger('werkzeug').setLevel(logging.ERROR)

@app.route('/')
def home():
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/logs')
def logs():
    return render_template('logs.html')

@app.route('/api/<action>/<chat_id>', methods=['POST'])
def api_handler(action, chat_id):
    # هنا ممكن نربط مستقبلاً مع أوامر البوت الحقيقية
    return jsonify({"status": "Success", "msg": f"Command {action} executed"})

def run_flask_server():
    try:
        # تشغيل السيرفر على بورت 8080
        app.run(host="0.0.0.0", port=8080, use_reloader=False)
    except Exception as e:
        print(f"❌ TitanOS Port Error: {e}")

# ------------------------
# إعدادات البوت
# ------------------------
sys.path.insert(0, os.getcwd())
import config
from AnnieXMedia import LOGGER, app as bot_app, userbot
from AnnieXMedia.core.call import StreamController
from AnnieXMedia.misc import sudo
from AnnieXMedia.plugins import ALL_MODULES
from AnnieXMedia.utils.database import get_banned_users, get_gbanned
from AnnieXMedia.utils.cookie_handler import fetch_and_store_cookies
from config import BANNED_USERS

async def init():
    # 1. تشغيل سيرفر الموقع في الخلفية
    try:
        t = Thread(target=run_flask_server)
        t.daemon = True
        t.start()
        LOGGER("TitanOS").info(f"✅ Dashboard Integrated & Running on Port 8080 (Dir: {TITAN_DIR})")
    except Exception as e:
        LOGGER("TitanOS").error(f"❌ Failed to start Dashboard: {e}")

    # 2. فحوصات البوت المعتادة
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

    # 3. تشغيل البوت
    await bot_app.start()
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

    await bot_app.stop()
    await userbot.stop()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(init())
