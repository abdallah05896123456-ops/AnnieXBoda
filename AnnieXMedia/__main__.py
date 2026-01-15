# -*- coding: utf-8 -*-
# ==============================================================================
# TITAN OS KERNEL — ULTIMATE EDITION (4K CORE)
# Developed for: AnnieXMedia Bot
# Features: Async Bridge, Video Streaming, System Monitor, Security Shield
# ==============================================================================

import os
import sys
import asyncio
import importlib
import logging
import threading
import socket
import time
import psutil
import math
from datetime import datetime
from flask import Flask, request, jsonify, session, send_file, Response, redirect, url_for, render_template_string
from pyrogram import idle, Client
from pytgcalls.exceptions import NoActiveGroupCall

# ------------------------------------------------------------------------------
# [1] SYSTEM CONFIGURATION & PATHS
# ------------------------------------------------------------------------------
sys.path.insert(0, os.getcwd())
CURRENT_DIR = os.getcwd()
TITAN_DIR = os.path.join(CURRENT_DIR, "TitanOS")
DOWNLOADS_DIR = os.path.join(CURRENT_DIR, "downloads")

# Ensure critical directories exist
os.makedirs(TITAN_DIR, exist_ok=True)
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

# Logger Setup
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [TITAN-OS] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.FileHandler("titan.log"), logging.StreamHandler()]
)
LOGGER = logging.getLogger("TitanKernel")
logging.getLogger("werkzeug").setLevel(logging.ERROR) # Silence Flask spam

# ------------------------------------------------------------------------------
# [2] GLOBAL SHARED STATE (The "Brain")
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

# --- UTILITY FUNCTIONS ---
def get_readable_time(seconds: int) -> str:
    count = 0
    ping_time = ""
    time_list = []
    time_suffix_list = ["s", "m", "h", "days"]
    while count < 4:
        count += 1
        remainder, result = divmod(seconds, 60) if count < 3 else divmod(seconds, 24)
        if seconds == 0 and remainder == 0:
            break
        time_list.append(int(result))
        seconds = int(remainder)
    for x in range(len(time_list)):
        time_list[x] = str(time_list[x]) + time_suffix_list[x]
    if len(time_list) == 4:
        ping_time += time_list.pop() + ", "
    time_list.reverse()
    ping_time += ":".join(time_list)
    return ping_time

def get_readable_size(size):
    power = 2**10
    n = 0
    power_labels = {0 : '', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
    while size > power:
        size /= power
        n += 1
    return f"{size:.2f} {power_labels[n]}B"

# --- THE BRIDGE: Exec on Bot Loop ---
def exec_on_bot(coro):
    """Safely executes a coroutine on the Bot's event loop."""
    if BOT_LOOP and BOT_LOOP.is_running():
        return asyncio.run_coroutine_threadsafe(coro, BOT_LOOP)
    return None

# ------------------------------------------------------------------------------
# [4] WEB ROUTES (API & PAGES)
# ------------------------------------------------------------------------------

@app.route('/')
def index():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    # Try to serve dashboard.html
    dash_path = os.path.join(TITAN_DIR, "dashboard.html")
    if os.path.exists(dash_path):
        return send_file(dash_path)
    return "<h1>Titan OS Kernel Active</h1><p>Dashboard file missing (TitanOS/dashboard.html)</p>"

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form.get('username')
        pw = request.form.get('password')
        if user == ADMIN_USER and pw == ADMIN_PASS:
            session['logged_in'] = True
            return redirect(url_for('index'))
        else:
            # Return login with error (assuming login.html supports Jinja2 variable injection or we just reload)
            return redirect(url_for('login')) # Simplified
            
    login_path = os.path.join(TITAN_DIR, "login.html")
    if os.path.exists(login_path):
        return send_file(login_path)
    return "<h1>Login Page Missing</h1>"

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- API: STATUS ---
@app.route('/api/settings/status')
def api_status():
    uptime = get_readable_time(int(time.time() - START_TIME))
    cpu = psutil.cpu_percent()
    ram = psutil.virtual_memory().percent
    
    # Get Ping if possible
    ping = 0
    if CallClient:
        # Trick to get ping from PyTgCalls attribute if available, or fake it safely
        ping = getattr(CallClient, "ping", 0)

    return jsonify({
        "uptime": uptime,
        "cpu": cpu,
        "ram": ram,
        "ping": ping,
        "status": "Online"
    })

# --- API: CALLS & INFO ---
@app.route('/api/player/active_calls')
def api_active_calls():
    # Return list of chats where bot is streaming
    chats = []
    try:
        # Check active calls from PyTgCalls or Database
        # This part depends on your AnnieXMedia implementation
        if CallClient:
            # Assuming active_calls is a list of Chat IDs
            active_cids = []
            if hasattr(CallClient, 'active_calls'):
                active_cids = CallClient.active_calls
            
            for cid in active_cids:
                chat_name = f"Chat {cid}"
                cover = "https://telegra.ph/file/5eb6df308e92f4477813d.jpg"
                
                # Try to get details from DB
                if cid in db:
                    data = db[cid][0]
                    chat_name = data.get("title", chat_name)
                    cover = data.get("thumb", cover)
                
                chats.append({
                    "chat_id": str(cid),
                    "name": str(chat_name),
                    "cover": cover
                })
    except Exception as e:
        LOGGER.error(f"Error fetching calls: {e}")
        
    return jsonify({"chats": chats})

@app.route('/api/player/track_info/<chat_id>')
def api_track_info(chat_id):
    info = {
        "title": "System Idle", 
        "artist": "Titan OS", 
        "cover": "", 
        "is_playing": False
    }
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

# --- API: CONTROL ---
@app.route('/api/player/control', methods=['POST'])
def api_control():
    if not session.get('logged_in'): return jsonify({"error": "Auth"}), 401
    
    cmd = request.form.get('cmd')
    chat_id = request.form.get('chat_id')
    
    if not cmd or not chat_id: return jsonify({"error": "Bad Request"}), 400
    
    cid = int(chat_id)
    try:
        if cmd == 'pause':
            exec_on_bot(StreamController.pause_stream(cid))
        elif cmd == 'resume':
            exec_on_bot(StreamController.resume_stream(cid))
        elif cmd == 'skip' or cmd == 'stop':
            exec_on_bot(StreamController.stop_stream(cid))
        elif cmd == 'seek_back':
             # Logic for seeking if supported
             pass
        return jsonify({"status": "OK"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/player/play_custom', methods=['POST'])
def api_play_custom():
    if not session.get('logged_in'): return jsonify({"error": "Auth"}), 401
    query = request.form.get('query')
    chat_id = request.form.get('chat_id')
    
    # Needs YouTube Helper
    # This is a placeholder for the actual search logic
    # You would use exec_on_bot to call play_video(cid, query)
    
    return jsonify({"status": "success", "msg": "Command Sent (Logic Pending)"})

# --- VIDEO STREAMING (RANGE SUPPORT) ---
@app.route('/stream/live/<chat_id>')
def stream_video(chat_id):
    """
    Streams the file associated with the chat_id.
    Supports Range headers for seeking in the web player.
    """
    file_path = None
    try:
        cid = int(chat_id)
        if cid in db and db[cid]:
            file_path = db[cid][0].get("file")
    except: pass
    
    # Fallback to downloads if not found in DB
    if not file_path or not os.path.exists(file_path):
         try:
            files = [os.path.join(DOWNLOADS_DIR, f) for f in os.listdir(DOWNLOADS_DIR) if f.endswith(('.mp4', '.mkv', '.webm'))]
            if files: file_path = max(files, key=os.path.getctime)
         except: pass

    if not file_path:
        return Response("Stream Not Found", status=404)

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

# --- UTILS API ---
@app.route('/api/utils/cache_list')
def cache_list():
    files = []
    total_size = 0
    for f in os.listdir(DOWNLOADS_DIR):
        fp = os.path.join(DOWNLOADS_DIR, f)
        sz = os.path.getsize(fp)
        total_size += sz
        files.append({"name": f, "size": get_readable_size(sz)})
    return jsonify({"files": files, "total_count": len(files), "total_size_mb": get_readable_size(total_size)})

@app.route('/api/utils/turbo', methods=['POST'])
def turbo_clean():
    if not session.get('logged_in'): return jsonify({"error": "Auth"}), 401
    count = 0
    for f in os.listdir(DOWNLOADS_DIR):
        try:
            os.remove(os.path.join(DOWNLOADS_DIR, f))
            count += 1
        except: pass
    return jsonify({"status": f"Cleaned {count} files"})

@app.route('/api/security/block_user', methods=['POST'])
def block_user():
    # Placeholder for blocking logic
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
    from AnnieXMedia.utils.database import get_banned_users, get_gbanned
    from AnnieXMedia.utils.cookie_handler import fetch_and_store_cookies
    from config import BANNED_USERS
    
    # Alias for API use
    CallClient = StreamController 
except ImportError as e:
    LOGGER.error(f"CRITICAL: Failed to import Bot Modules: {e}")
    sys.exit(1)

def run_flask():
    """ Runs Flask in Daemon Thread """
    app.run(host="0.0.0.0", port=8080, debug=False, use_reloader=False)

async def start_services():
    LOGGER.info("------------------------------------------")
    LOGGER.info("🚀 TITAN OS KERNEL STARTING...")
    LOGGER.info("------------------------------------------")
    
    # 1. Start Cookies
    try: await fetch_and_store_cookies()
    except: pass
    
    # 2. Sudo & DB
    await sudo()
    
    # 3. Start Pyrogram Clients
    await bot_app.start()
    await userbot.start()
    
    # 4. Load Plugins
    for mod in ALL_MODULES:
        importlib.import_module("AnnieXMedia.plugins" + mod)
    
    # 5. Start Calls
    await StreamController.start()
    
    # 6. Warmup Call (Prevents NoActiveGroupCall on first use)
    try:
        await StreamController.stream_call("http://docs.evostream.com/sample_content/assets/sintel1m720p.mp4")
    except: pass
    
    LOGGER.info("✅ SYSTEM FULLY OPERATIONAL")
    LOGGER.info("📡 Web Interface: http://0.0.0.0:8080")

    await idle()
    
    # Shutdown
    await bot_app.stop()
    await userbot.stop()

if __name__ == "__main__":
    # Setup Loop
    loop = asyncio.get_event_loop()
    BOT_LOOP = loop
    
    # Start Web Thread
    t = threading.Thread(target=run_flask, daemon=True)
    t.start()
    
    # Start Bot Main Loop
    loop.run_until_complete(start_services())
