# -*- coding: utf-8 -*-
# ==============================================================================
# TITAN OS KERNEL — NUCLEAR EDITION (ROOT PATH FIX)
# Architecture: Multi-Threaded Flask + Async Pyrogram Bridge
# Status: Production Ready | Auto-Path Correction Enabled
# ==============================================================================

import os
import sys
import asyncio
import importlib
import logging
import threading
import time
import psutil
import traceback
import json
from flask import Flask, request, jsonify, session, send_file, redirect, url_for
from pyrogram import idle
from logging.handlers import RotatingFileHandler

# ------------------------------------------------------------------------------
# [1] INTELLIGENT PATH FINDER (ROOT FIX)
# ------------------------------------------------------------------------------
# 1. تحديد مكان ملف التشغيل الحالي (داخل AnnieXMedia)
CURRENT_FILE_DIR = os.path.dirname(os.path.abspath(__file__))

# 2. العودة خطوة للخلف للوصول للجذر (حيث يوجد TitanOS كما في الصورة)
ROOT_DIR = os.path.dirname(CURRENT_FILE_DIR)

# 3. تحديد المسارات الصحيحة
TITAN_DIR = os.path.join(ROOT_DIR, "TitanOS")
DOWNLOADS_DIR = os.path.join(ROOT_DIR, "downloads")
LOG_FILE = os.path.join(ROOT_DIR, "titan.log")

# 4. التأكد من وجود المجلدات وإنشاؤها إذا لزم الأمر
os.makedirs(TITAN_DIR, exist_ok=True)
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

# ------------------------------------------------------------------------------
# [2] ADVANCED LOGGING SYSTEM
# ------------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=2),
        logging.StreamHandler()
    ]
)
LOGGER = logging.getLogger("TitanKernel")
logging.getLogger("werkzeug").setLevel(logging.ERROR)

# طباعة تقرير المسارات للتأكد
print(f"\n{'='*50}")
print(f"🚀 TITAN OS: PATH CORRECTION APPLIED")
print(f"📍 Script Location: {CURRENT_FILE_DIR}")
print(f"📂 Project Root:    {ROOT_DIR}")
print(f"🎯 GUI Path:        {TITAN_DIR}")

if not os.path.exists(os.path.join(TITAN_DIR, "login.html")):
    LOGGER.critical("⚠️ CRITICAL: 'login.html' NOT FOUND in the expected path!")
    LOGGER.critical(f"👉 Please ensure 'TitanOS' folder is at: {TITAN_DIR}")
else:
    print(f"✅ GUI Integrity Check Passed.")
print(f"{'='*50}\n")

# ------------------------------------------------------------------------------
# [3] GLOBAL STATE & CREDENTIALS
# ------------------------------------------------------------------------------
BOT_LOOP = None
START_TIME = time.time()
ADMIN_USER = os.environ.get("TITAN_USER", "Abdallah")
ADMIN_PASS = os.environ.get("TITAN_PASS", "asdfghjkl05896")

# ------------------------------------------------------------------------------
# [4] FLASK ENGINE (Web Interface)
# ------------------------------------------------------------------------------
# تحديد مجلد القوالب (Templates) بشكل صريح للمسار المصحح
app = Flask(__name__, template_folder=TITAN_DIR, static_folder=TITAN_DIR)
app.secret_key = os.urandom(24)

# --- UTILS ---
def get_readable_time(seconds: int) -> str:
    count = 0
    time_list = []
    time_suffix_list = ["s", "m", "h", "days"]
    while count < 4:
        count += 1
        remainder, result = divmod(seconds, 60) if count < 3 else divmod(seconds, 24)
        if seconds == 0 and remainder == 0: break
        time_list.append(int(result))
        seconds = int(remainder)
    for x in range(len(time_list)):
        time_list[x] = str(time_list[x]) + time_suffix_list[x]
    if len(time_list) == 4: time_list.pop()
    time_list.reverse()
    return ":".join(time_list) if time_list else "0s"

def run_async_task(coro):
    if BOT_LOOP and BOT_LOOP.is_running():
        return asyncio.run_coroutine_threadsafe(coro, BOT_LOOP)
    return None

# --- WEB ROUTES ---

@app.route('/')
def index():
    if not session.get('logged_in'):
        return redirect('/login')
    
    dash_file = os.path.join(TITAN_DIR, "dashboard.html")
    if os.path.exists(dash_file):
        return send_file(dash_file)
    return "<h1>Titan OS Active (Dashboard File Missing)</h1>"

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        try:
            u = request.form.get('username')
            p = request.form.get('password')
            
            if u == ADMIN_USER and p == ADMIN_PASS:
                session['logged_in'] = True
                LOGGER.info(f"✅ Successful Login by: {u}")
                return jsonify({"status": "success", "message": "Access Granted"})
            else:
                LOGGER.warning(f"❌ Failed Login Attempt: {u}")
                return jsonify({"status": "error", "message": "Invalid Credentials"}), 401
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    if session.get('logged_in'): return redirect('/')
    
    login_file = os.path.join(TITAN_DIR, "login.html")
    if os.path.exists(login_file):
        return send_file(login_file)
    
    return f"<h1>CRITICAL ERROR: Login File Missing at {TITAN_DIR}/login.html</h1>"

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

# --- API ENDPOINTS ---

@app.route('/api/settings/status')
def api_status():
    uptime = get_readable_time(int(time.time() - START_TIME))
    cpu = psutil.cpu_percent()
    ram = psutil.virtual_memory().percent
    
    ping = 0
    try:
        if CallClient: ping = getattr(CallClient, "ping", 0)
    except: pass

    return jsonify({
        "status": "Online",
        "uptime": uptime,
        "cpu": cpu,
        "ram": ram,
        "ping": ping,
        "bot_connected": bool(bot_app and bot_app.is_connected)
    })

@app.route('/api/player/active_calls')
def api_active_calls():
    chats = []
    try:
        if CallClient and hasattr(CallClient, 'active_calls'):
            for cid in CallClient.active_calls:
                chat_info = {"chat_id": str(cid), "name": f"Chat {cid}", "cover": ""}
                if 'db' in globals() and cid in db:
                    try:
                        data = db[cid][0]
                        chat_info['name'] = data.get("title", chat_info['name'])
                        chat_info['cover'] = data.get("thumb", "")
                    except: pass
                chats.append(chat_info)
    except Exception as e:
        LOGGER.error(f"API Error (active_calls): {e}")
    return jsonify({"chats": chats})

@app.route('/api/player/control', methods=['POST'])
def api_control():
    if not session.get('logged_in'): return jsonify({"error": "Unauthorized"}), 401
    
    cmd = request.form.get('cmd')
    chat_id = request.form.get('chat_id')
    
    if not CallClient:
        return jsonify({"error": "Bot Core Not Ready"}), 503

    try:
        cid = int(chat_id)
        if cmd == 'pause':
            run_async_task(StreamController.pause_stream(cid))
        elif cmd == 'resume':
            run_async_task(StreamController.resume_stream(cid))
        elif cmd == 'skip':
            run_async_task(StreamController.stop_stream(cid))
        
        LOGGER.info(f"🕹️ Command Executed: {cmd} on {cid}")
        return jsonify({"status": "OK", "command": cmd})
    except Exception as e:
        LOGGER.error(f"Command Execution Failed: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/utils/logs')
def api_logs():
    if not session.get('logged_in'): return "Auth Required", 401
    try:
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()[-100:]
            return "<pre>" + "".join(lines) + "</pre>"
    except: return "No Logs Available"

# ------------------------------------------------------------------------------
# [5] BOT BOOTSTRAP (The Bridge Construction)
# ------------------------------------------------------------------------------
bot_app = None
userbot = None
CallClient = None
db = {}
StreamController = None

def load_bot_modules():
    global bot_app, userbot, CallClient, db, StreamController
    try:
        LOGGER.info("🔌 Loading AnnieXMedia Core...")
        # تأكد من أننا داخل المجلد الصحيح للاستيراد
        sys.path.append(ROOT_DIR) 
        
        import config
        from AnnieXMedia import app as _bot, userbot as _ub
        from AnnieXMedia.core.call import StreamController as _SC
        from AnnieXMedia.misc import sudo as _sudo, db as _db
        from AnnieXMedia.plugins import ALL_MODULES
        from AnnieXMedia.utils.cookie_handler import fetch_and_store_cookies
        
        bot_app = _bot
        userbot = _ub
        StreamController = _SC
        CallClient = _SC
        db = _db
        
        return True, ALL_MODULES, _sudo, fetch_and_store_cookies
    except ImportError as e:
        LOGGER.critical(f"❌ CRITICAL IMPORT ERROR: {e}")
        traceback.print_exc()
        return False, [], None, None

def run_flask_server():
    """تشغيل السيرفر في خيط منفصل"""
    try:
        LOGGER.info("📡 Starting Web Interface on Port 8080...")
        app.run(host="0.0.0.0", port=8080, debug=False, use_reloader=False)
    except Exception as e:
        LOGGER.critical(f"🔥 Web Server Crash: {e}")

async def start_bot_services():
    """تشغيل البوت والخدمات"""
    global BOT_LOOP
    BOT_LOOP = asyncio.get_running_loop()
    
    success, modules, sudo_func, cookie_func = load_bot_modules()
    
    if success:
        LOGGER.info("🍪 Fetching Cookies...")
        try: await cookie_func()
        except: pass
        
        LOGGER.info("🛡️ Initializing Sudo & DB...")
        await sudo_func()
        
        LOGGER.info("🤖 Starting Telegram Clients...")
        await bot_app.start()
        await userbot.start()
        
        LOGGER.info("🧩 Loading Plugins...")
        for mod in modules:
            try:
                importlib.import_module("AnnieXMedia.plugins" + mod)
            except Exception as e:
                LOGGER.error(f"Failed to load plugin {mod}: {e}")
        
        LOGGER.info("🎧 Starting Voice Client...")
        await StreamController.start()
        
        LOGGER.info("✅ TITAN OS KERNEL: ALL SYSTEMS ONLINE")
        await idle()
        
        LOGGER.info("🛑 Stopping Services...")
        await bot_app.stop()
        await userbot.stop()
    else:
        LOGGER.warning("⚠️ Running in WEB-ONLY Mode (Bot Failed to Load)")
        while True:
            await asyncio.sleep(3600)

if __name__ == "__main__":
    # تشغيل الويب
    flask_thread = threading.Thread(target=run_flask_server, daemon=True)
    flask_thread.start()
    
    # تشغيل البوت
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(start_bot_services())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        LOGGER.critical(f"☠️ FATAL CRASH: {e}")
        traceback.print_exc()
