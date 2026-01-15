# -*- coding: utf-8 -*-
# ==============================================================================
# TITAN OS KERNEL — ULTIMATE EDITION (DEBUG VERSION)
# Developed for: AnnieXMedia Bot
# Features: Async Bridge, Video Streaming, System Monitor, Security Shield
# ==============================================================================

import os
import sys
import asyncio
import importlib
import logging
import threading
import time
import psutil
from flask import Flask, request, jsonify, session, send_file, Response, redirect, url_for
from pyrogram import idle
from pytgcalls.exceptions import NoActiveGroupCall

# ------------------------------------------------------------------------------
# [1] SYSTEM DIAGNOSTICS & PATH CONFIGURATION (THE FIX)
# ------------------------------------------------------------------------------
# الحصول على المسار الجذري الحقيقي للملف
BASE_DIR = os.path.abspath(os.getcwd())
TITAN_DIR = os.path.join(BASE_DIR, "TitanOS")
DOWNLOADS_DIR = os.path.join(BASE_DIR, "downloads")

# --- DIAGNOSTIC BLOCK START ---
print("\n" + "="*60)
print("🔍 TITAN OS: SYSTEM DIAGNOSTICS STARTING...")
print(f"📂 Root Directory: {BASE_DIR}")
print(f"📂 Target HTML Directory: {TITAN_DIR}")

# 1. Check Directory
if not os.path.exists(TITAN_DIR):
    print(f"❌ [CRITICAL ERROR] Folder 'TitanOS' NOT FOUND in {BASE_DIR}")
    print("👉 ACTION REQUIRED: Create a folder named 'TitanOS' next to this file.")
    try:
        os.makedirs(TITAN_DIR, exist_ok=True)
        print("⚠️ [AUTO-FIX] Created empty 'TitanOS' folder for you.")
    except: pass
else:
    print(f"✅ [OK] Folder 'TitanOS' exists.")

# 2. Check Login File
LOGIN_FILE = os.path.join(TITAN_DIR, "login.html")
if not os.path.exists(LOGIN_FILE):
    print(f"❌ [MISSING FILE] 'login.html' not found inside TitanOS folder!")
    print(f"   Expected Path: {LOGIN_FILE}")
else:
    print(f"✅ [OK] 'login.html' found.")

# 3. Check Dashboard File
DASH_FILE = os.path.join(TITAN_DIR, "dashboard.html")
if not os.path.exists(DASH_FILE):
    print(f"❌ [MISSING FILE] 'dashboard.html' not found inside TitanOS folder!")
    print(f"   Expected Path: {DASH_FILE}")
else:
    print(f"✅ [OK] 'dashboard.html' found.")

print("="*60 + "\n")
# --- DIAGNOSTIC BLOCK END ---

os.makedirs(DOWNLOADS_DIR, exist_ok=True)

# Logger Setup
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [TITAN-OS] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.FileHandler("titan.log"), logging.StreamHandler()]
)
LOGGER = logging.getLogger("TitanKernel")
logging.getLogger("werkzeug").setLevel(logging.ERROR) 

# ------------------------------------------------------------------------------
# [2] GLOBAL SHARED STATE
# ------------------------------------------------------------------------------
BOT_LOOP = None
START_TIME = time.time()
ADMIN_USER = os.environ.get("TITAN_USER", "Abdallah")
ADMIN_PASS = os.environ.get("TITAN_PASS", "asdfghjkl05896")

# ------------------------------------------------------------------------------
# [3] FLASK APP ENGINE
# ------------------------------------------------------------------------------
app = Flask(__name__, template_folder=TITAN_DIR, static_folder=TITAN_DIR)
app.secret_key = os.urandom(24)

# --- HELPER FUNCTIONS ---
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

def get_readable_size(size):
    power = 2**10
    n = 0
    power_labels = {0 : '', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
    while size > power:
        size /= power
        n += 1
    return f"{size:.2f} {power_labels[n]}B"

def exec_on_bot(coro):
    if BOT_LOOP and BOT_LOOP.is_running():
        return asyncio.run_coroutine_threadsafe(coro, BOT_LOOP)
    return None

# ------------------------------------------------------------------------------
# [4] WEB ROUTES (WITH DEBUG RESPONSES)
# ------------------------------------------------------------------------------

@app.route('/')
def index():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    # Strict Check
    if os.path.exists(DASH_FILE):
        return send_file(DASH_FILE)
    
    # Debug Error Message in Browser
    return f"""
    <div style="background:#000;color:red;padding:20px;font-family:monospace;">
        <h1>CRITICAL ERROR: DASHBOARD MISSING</h1>
        <p>The system cannot find: <b>{DASH_FILE}</b></p>
        <p>Please upload 'dashboard.html' into the 'TitanOS' folder.</p>
    </div>
    """, 404

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form.get('username')
        pw = request.form.get('password')
        if user == ADMIN_USER and pw == ADMIN_PASS:
            session['logged_in'] = True
            return redirect(url_for('index'))
        else:
            return redirect(url_for('login')) # In real app, flash error

    # Strict Check
    if os.path.exists(LOGIN_FILE):
        return send_file(LOGIN_FILE)

    # Debug Error Message in Browser
    return f"""
    <div style="background:#000;color:red;padding:20px;font-family:monospace;">
        <h1>CRITICAL ERROR: LOGIN PAGE MISSING</h1>
        <p>The system cannot find: <b>{LOGIN_FILE}</b></p>
        <p>Please upload 'login.html' into the 'TitanOS' folder.</p>
    </div>
    """, 404

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- API ROUTES ---
@app.route('/api/settings/status')
def api_status():
    uptime = get_readable_time(int(time.time() - START_TIME))
    cpu = psutil.cpu_percent()
    ram = psutil.virtual_memory().percent
    ping = getattr(CallClient, "ping", 0) if CallClient else 0
    return jsonify({"uptime": uptime, "cpu": cpu, "ram": ram, "ping": ping, "status": "Online"})

@app.route('/api/player/active_calls')
def api_active_calls():
    chats = []
    try:
        if CallClient and hasattr(CallClient, 'active_calls'):
            for cid in CallClient.active_calls:
                chat_name = f"Chat {cid}"
                cover = "https://telegra.ph/file/5eb6df308e92f4477813d.jpg"
                if cid in db:
                    data = db[cid][0]
                    chat_name = data.get("title", chat_name)
                    cover = data.get("thumb", cover)
                chats.append({"chat_id": str(cid), "name": str(chat_name), "cover": cover})
    except Exception as e:
        LOGGER.error(f"Error fetching calls: {e}")
    return jsonify({"chats": chats})

@app.route('/api/player/track_info/<chat_id>')
def api_track_info(chat_id):
    info = {"title": "System Idle", "artist": "Titan OS", "cover": "", "is_playing": False}
    try:
        cid = int(chat_id)
        if cid in db and db[cid]:
            track = db[cid][0]
            info = {
                "title": track.get("title", "Unknown"),
                "artist": track.get("by", "Unknown"),
                "cover": track.get("thumb", ""),
                "is_playing": True,
                "stream_url": f"/stream/live/{cid}"
            }
    except: pass
    return jsonify(info)

@app.route('/api/player/control', methods=['POST'])
def api_control():
    if not session.get('logged_in'): return jsonify({"error": "Auth"}), 401
    cmd = request.form.get('cmd')
    chat_id = request.form.get('chat_id')
    if not cmd or not chat_id: return jsonify({"error": "Bad Request"}), 400
    cid = int(chat_id)
    try:
        if cmd == 'pause': exec_on_bot(StreamController.pause_stream(cid))
        elif cmd == 'resume': exec_on_bot(StreamController.resume_stream(cid))
        elif cmd == 'skip' or cmd == 'stop': exec_on_bot(StreamController.stop_stream(cid))
        return jsonify({"status": "OK"})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/player/play_custom', methods=['POST'])
def api_play_custom():
    if not session.get('logged_in'): return jsonify({"error": "Auth"}), 401
    return jsonify({"status": "success", "msg": "Command Sent (Logic Pending)"})

@app.route('/stream/live/<chat_id>')
def stream_video(chat_id):
    file_path = None
    try:
        cid = int(chat_id)
        if cid in db and db[cid]: file_path = db[cid][0].get("file")
    except: pass
    
    if not file_path or not os.path.exists(file_path):
         try:
            files = [os.path.join(DOWNLOADS_DIR, f) for f in os.listdir(DOWNLOADS_DIR) if f.endswith(('.mp4', '.mkv', '.webm'))]
            if files: file_path = max(files, key=os.path.getctime)
         except: pass

    if not file_path: return Response("Stream Not Found", status=404)

    file_size = os.path.getsize(file_path)
    range_header = request.headers.get('Range', None)
    if range_header:
        byte1, byte2 = 0, None
        m = range_header.replace('bytes=', '').split('-')
        byte1 = int(m[0])
        if m[1]: byte2 = int(m[1])
        byte2 = byte2 if byte2 else file_size - 1
        length = byte2 - byte1 + 1
        with open(file_path, 'rb') as f:
            f.seek(byte1)
            data = f.read(length)
        rv = Response(data, 206, mimetype="video/mp4", direct_passthrough=True)
        rv.headers.add('Content-Range', f'bytes {byte1}-{byte2}/{file_size}')
        rv.headers.add('Accept-Ranges', 'bytes')
        return rv
    else:
        return send_file(file_path, mimetype="video/mp4")

@app.route('/api/utils/cache_list')
def cache_list():
    files = []
    total_size = 0
    try:
        for f in os.listdir(DOWNLOADS_DIR):
            fp = os.path.join(DOWNLOADS_DIR, f)
            sz = os.path.getsize(fp)
            total_size += sz
            files.append({"name": f, "size": get_readable_size(sz)})
    except: pass
    return jsonify({"files": files, "total_count": len(files), "total_size_mb": get_readable_size(total_size)})

@app.route('/api/utils/turbo', methods=['POST'])
def turbo_clean():
    if not session.get('logged_in'): return jsonify({"error": "Auth"}), 401
    count = 0
    try:
        for f in os.listdir(DOWNLOADS_DIR):
            os.remove(os.path.join(DOWNLOADS_DIR, f))
            count += 1
    except: pass
    return jsonify({"status": f"Cleaned {count} files"})

@app.route('/api/security/block_user', methods=['POST'])
def block_user():
    return jsonify({"status": "Executed"})

# ------------------------------------------------------------------------------
# [5] BOT BOOTSTRAP
# ------------------------------------------------------------------------------
try:
    import config
    from AnnieXMedia import app as bot_app, userbot
    from AnnieXMedia.core.call import StreamController
    from AnnieXMedia.misc import sudo, db
    from AnnieXMedia.plugins import ALL_MODULES
    from AnnieXMedia.utils.cookie_handler import fetch_and_store_cookies
    
    CallClient = StreamController 
except ImportError as e:
    LOGGER.error(f"CRITICAL: Failed to import Bot Modules: {e}")
    # We don't exit here so the web server can still run and show errors
    CallClient = None
    bot_app = None

def run_flask():
    app.run(host="0.0.0.0", port=8080, debug=False, use_reloader=False)

async def start_services():
    LOGGER.info("------------------------------------------")
    LOGGER.info("🚀 TITAN OS KERNEL STARTING...")
    
    if bot_app:
        try: await fetch_and_store_cookies()
        except: pass
        await sudo()
        await bot_app.start()
        await userbot.start()
        for mod in ALL_MODULES: importlib.import_module("AnnieXMedia.plugins" + mod)
        await StreamController.start()
        LOGGER.info("✅ SYSTEM FULLY OPERATIONAL")
    else:
        LOGGER.warning("⚠️ BOT MODULES NOT LOADED (RUNNING IN WEB-ONLY MODE)")
    
    LOGGER.info("📡 Web Interface: http://0.0.0.0:8080")
    
    # Check Flask Files Status Again
    if not os.path.exists(os.path.join(TITAN_DIR, "login.html")):
        LOGGER.error("❌ WEB WARNING: 'login.html' is MISSING. Web interface won't work.")

    await idle()
    if bot_app:
        await bot_app.stop()
        await userbot.stop()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    BOT_LOOP = loop
    t = threading.Thread(target=run_flask, daemon=True)
    t.start()
    loop.run_until_complete(start_services())
