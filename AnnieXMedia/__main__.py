# -*- coding: utf-8 -*-
# =========================================================
# AnnieXMedia/__main__.py
# الإصدار النهائي: ربط فوري بين الموقع والبوت
# =========================================================

import os
import sys
import asyncio
import importlib
import logging
import threading
import socket
from flask import Flask, request, jsonify, session, send_file, Response, redirect, url_for
from pyrogram import idle
from pytgcalls.exceptions import NoActiveGroupCall

# ---------------------------------------------------------
# [1] إعداد المسارات (مهم جداً)
# ---------------------------------------------------------
sys.path.insert(0, os.getcwd())
CURRENT_DIR = os.getcwd()
TITAN_DIR = os.path.join(CURRENT_DIR, "TitanOS")
DOWNLOADS_DIR = os.path.join(CURRENT_DIR, "downloads")

# التأكد من وجود المجلدات
os.makedirs(TITAN_DIR, exist_ok=True)
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

# ---------------------------------------------------------
# [2] المتغيرات العامة (القلب النابض)
# ---------------------------------------------------------
# هذا المتغير هو سر الربط، سيحمل الـ Loop الخاص بالبوت
BOT_LOOP = None 

# إعدادات الأدمن (للدخول للموقع)
ADMIN_USER = "Abdallah"
ADMIN_PASS = "asdfghjkl05896"

# إعدادات اللوج
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(message)s")
LOGGER = logging.getLogger("TitanBridge")
logging.getLogger('werkzeug').setLevel(logging.ERROR)

# ---------------------------------------------------------
# [3] إعداد موقع الويب (Flask)
# ---------------------------------------------------------
app = Flask(__name__, template_folder=TITAN_DIR, static_folder=TITAN_DIR)
app.secret_key = "TITAN_GOD_KEY_2025"

# --- دالة الجسر (The Bridge) ---
# هذه الدالة تأخذ الأمر من Flask وتنفذه داخل البوت فوراً
def exec_on_bot(coroutine):
    global BOT_LOOP
    if BOT_LOOP and asyncio.iscoroutine(coroutine):
        future = asyncio.run_coroutine_threadsafe(coroutine, BOT_LOOP)
        return future
    return None

# --- صفحات الموقع ---
@app.route('/')
def home():
    if session.get('user') == ADMIN_USER:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login_page'))

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'POST':
        if request.form.get('username') == ADMIN_USER and request.form.get('password') == ADMIN_PASS:
            session['user'] = ADMIN_USER
            return redirect(url_for('dashboard'))
    
    login_file = os.path.join(TITAN_DIR, "login.html")
    if os.path.exists(login_file): return send_file(login_file)
    return "Login File Missing"

@app.route('/dashboard')
def dashboard():
    if not session.get('user'): return redirect(url_for('login_page'))
    dash_file = os.path.join(TITAN_DIR, "dashboard.html")
    if os.path.exists(dash_file): return send_file(dash_file)
    return "Dashboard File Missing"

# --- API التحكم (الأوامر الفورية) ---
@app.route('/api/player/control', methods=['POST'])
def player_control():
    # 1. استلام البيانات من الموقع
    cmd = request.form.get('cmd')
    chat_id = request.form.get('chat_id')
    
    if not cmd or not chat_id:
        return jsonify({"error": "Missing Data"}), 400

    try:
        cid = int(chat_id)
        
        # 2. تنفيذ الأمر فوراً عبر الجسر
        if cmd == 'pause':
            exec_on_bot(StreamController.pause_stream(cid))
        elif cmd == 'resume':
            exec_on_bot(StreamController.resume_stream(cid))
        elif cmd == 'skip' or cmd == 'stop':
            exec_on_bot(StreamController.stop_stream(cid))
            
        return jsonify({"status": "Executed", "cmd": cmd})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- API المعلومات (عشان الموقع يعرف البوت شغال ولا لأ) ---
@app.route('/api/track_info/<chat_id>')
def track_info(chat_id):
    info = {"title": "Idle", "is_playing": False}
    try:
        cid = int(chat_id)
        if cid in db and db[cid]:
            track = db[cid][0]
            info = {
                "title": track.get("title", "Unknown"),
                "cover": track.get("thumb", ""),
                "is_playing": True,
                "stream_url": f"/stream/{cid}"
            }
    except: pass
    return jsonify(info)

@app.route('/stream/<chat_id>')
def stream_video(chat_id):
    # دالة الفيديو (Stream)
    file_path = None
    try:
        cid = int(chat_id)
        if cid in db and db[cid]: file_path = db[cid][0].get("file")
    except: pass
    
    if not file_path:
        # البحث في التنزيلات كبديل
        try:
            files = [os.path.join(DOWNLOADS_DIR, f) for f in os.listdir(DOWNLOADS_DIR) if f.endswith('.mp4')]
            if files: file_path = max(files, key=os.path.getctime)
        except: pass

    if file_path and os.path.exists(file_path):
        return send_file(file_path)
    return "No Stream", 404

# ---------------------------------------------------------
# [4] استيراد ملفات البوت (أصلية)
# ---------------------------------------------------------
import config
from AnnieXMedia import app as bot_app, userbot
from AnnieXMedia.core.call import StreamController
from AnnieXMedia.misc import sudo, db
from AnnieXMedia.plugins import ALL_MODULES
from AnnieXMedia.utils.database import get_banned_users, get_gbanned
from AnnieXMedia.utils.cookie_handler import fetch_and_store_cookies
from config import BANNED_USERS

# ---------------------------------------------------------
# [5] التشغيل المتزامن (Flask + Pyrogram)
# ---------------------------------------------------------

def run_flask_server():
    # تشغيل الموقع على بورت 8080
    app.run(host="0.0.0.0", port=8080, debug=False, use_reloader=False)

async def init_bot():
    print("---------------------------------------")
    print("🚀 STARTING TITAN SYSTEM (WEB + BOT)...")
    print("---------------------------------------")

    # [أ] التحقق من الجلسات
    if not config.STRING1:
        LOGGER.error("Assistant session not filled!")
        sys.exit()

    # [ب] تحميل الكوكيز والداتا
    try:
        await fetch_and_store_cookies()
    except: pass
    
    await sudo()
    
    # [ج] تشغيل عملاء البوت
    await bot_app.start()
    for mod in ALL_MODULES:
        importlib.import_module("AnnieXMedia.plugins" + mod)
    LOGGER.info("Modules Loaded...")
    
    await userbot.start()
    await StreamController.start()

    # [د] تشغيل تجريبي للمكالمات (Warmup)
    try:
        await StreamController.stream_call("http://docs.evostream.com/sample_content/assets/sintel1m720p.mp4")
    except NoActiveGroupCall:
        LOGGER.error("Please Open Voice Chat in Log Group!")
    except: pass

    await StreamController.decorators()
    
    # طباعة الرابط
    try:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        print(f"\n✅ Web Dashboard: http://{local_ip}:8080")
    except:
        print(f"\n✅ Web Dashboard: http://0.0.0.0:8080")
        
    print("✅ Bot is Ready & Listening to Web Commands!")
    
    # [هـ] وضع الخمول (مهم جداً لاستقبال الأوامر)
    await idle()
    
    # [و] الإغلاق
    await bot_app.stop()
    await userbot.stop()

def main():
    global BOT_LOOP
    
    # 1. إعداد الـ Loop الرئيسي للبوت
    loop = asyncio.get_event_loop()
    BOT_LOOP = loop  # حفظ الـ Loop عشان Flask يستخدمه
    
    # 2. تشغيل الموقع في Thread منفصل (عشان ميعطلش البوت)
    t = threading.Thread(target=run_flask_server)
    t.daemon = True
    t.start()
    
    # 3. تشغيل البوت في الـ Thread الرئيسي
    loop.run_until_complete(init_bot())

if __name__ == "__main__":
    main()
