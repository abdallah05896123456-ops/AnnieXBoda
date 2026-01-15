# ================================
# __main__.py (TitanOS Integrated)
# ================================

import sys
import os
import asyncio
import importlib
import logging
from threading import Thread
from flask import Flask, render_template, request, redirect, url_for, Response, jsonify, session
from pyrogram import idle
from pytgcalls.exceptions import NoActiveGroupCall

# ------------------------
# إعدادات السيرفر والمسارات
# ------------------------
BASE_DIR = os.getcwd()
# محاولة إيجاد فولدر TitanOS سواء في الروت أو جوه AnnieXMedia
TITAN_DIR = os.path.join(BASE_DIR, 'TitanOS')
if not os.path.exists(TITAN_DIR):
    TITAN_DIR = os.path.join(BASE_DIR, 'AnnieXMedia', 'TitanOS')

app = Flask(__name__, template_folder=TITAN_DIR, static_folder=TITAN_DIR)
app.secret_key = "Titan_Super_Secret_Key_2025"
logging.getLogger('werkzeug').setLevel(logging.ERROR)

# بيانات الدخول (من ملفك)
ADMIN_USER = "Abdallah"
ADMIN_PASS = "asdfghjkl05896"

# متغيرات لتخزين التصميم في الرامات
CSS_CACHE = ""
JS_CACHE = ""

# --- دالة قراءة ملف التصميم (assets_bundle.txt) ---
def load_assets():
    global CSS_CACHE, JS_CACHE
    assets_path = os.path.join(TITAN_DIR, 'assets_bundle.txt')
    try:
        if os.path.exists(assets_path):
            with open(assets_path, "r", encoding="utf-8") as f:
                content = f.read()
                # فصل الـ CSS والـ JS
                if "---CSS---" in content and "---JS---" in content:
                    # بناخد اللي بين العلامتين
                    parts = content.split("---JS---")
                    css_raw = parts[0].split("---CSS---")[1]
                    JS_CACHE = parts[1].strip()
                    CSS_CACHE = css_raw.strip()
            print(f"✅ TitanOS Assets Loaded from: {assets_path}")
        else:
            print(f"⚠️ Warning: assets_bundle.txt not found at {assets_path}")
    except Exception as e:
        print(f"❌ Assets Error: {e}")

# تحميل التصميم عند بدء التشغيل
load_assets()

# ------------------------
# مسارات الموقع (Routes)
# ------------------------

# 1. تقديم ملفات الستايل والجافاسكريبت
@app.route('/static/css/style.css')
def serve_css():
    if not CSS_CACHE: load_assets()
    return Response(CSS_CACHE, mimetype='text/css')

@app.route('/static/js/app.js')
def serve_js():
    if not JS_CACHE: load_assets()
    return Response(JS_CACHE, mimetype='application/javascript')

# 2. نظام الدخول
@app.route('/')
def home():
    if session.get('user') == ADMIN_USER:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login_check():
    user = request.form.get('username')
    pw = request.form.get('password')
    
    if user == ADMIN_USER and pw == ADMIN_PASS:
        session['user'] = user
        return redirect(url_for('dashboard'))
    else:
        return render_template('login.html', error="بيانات خاطئة، حاول مرة أخرى!")

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

# 3. لوحة التحكم
@app.route('/dashboard')
def dashboard():
    if not session.get('user'): return redirect(url_for('home'))
    return render_template('dashboard.html')

@app.route('/logs')
def logs():
    if not session.get('user'): return redirect(url_for('home'))
    return render_template('logs.html')

# 4. الـ API (استقبال الأوامر من الموقع)
@app.route('/api/<action>/<chat_id>', methods=['POST'])
def api_handler(action, chat_id):
    if not session.get('user'): return jsonify({"ok": False, "msg": "Unauthorized"}), 401
    
    # هنا ممكن نربط الأوامر الحقيقية للبوت مستقبلاً
    # حالياً بنرجع رد "نجاح" عشان الزراير تنور في الموقع
    return jsonify({
        "ok": True, 
        "status": "Success", 
        "msg": f"Order {action} executed for {chat_id}"
    })

# دالة تشغيل السيرفر
def run_flask():
    try:
        app.run(host="0.0.0.0", port=8080, use_reloader=False)
    except Exception as e:
        print(f"❌ Flask Error: {e}")

# ------------------------
# كود تشغيل البوت الأساسي
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
    # 1. تشغيل الموقع في الخلفية
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()
    LOGGER("TitanOS").info("✅ Dashboard Server Started on Port 8080")

    # 2. تشغيل البوت
    if not config.STRING1 and not config.STRING2 and not config.STRING3 and not config.STRING4 and not config.STRING5:
        LOGGER(__name__).error("Please fill Pyrogram Session...")
        exit()

    try:
        await fetch_and_store_cookies()
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

    await bot_app.start()
    LOGGER("AnnieXMedia").info("✅ Bot Client Started")

    for all_module in ALL_MODULES:
        importlib.import_module("AnnieXMedia.plugins" + all_module)
    LOGGER("AnnieXMedia.plugins").info("✅ Modules Loaded...")

    await userbot.start()
    await StreamController.start()

    try:
        await StreamController.stream_call("http://docs.evostream.com/sample_content/assets/sintel1m720p.mp4")
    except:
        pass

    await StreamController.decorators()
    LOGGER("AnnieXMedia").info("🚀 Annie Music Started Successfully...")
    
    await idle()
    await bot_app.stop()
    await userbot.stop()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(init())
