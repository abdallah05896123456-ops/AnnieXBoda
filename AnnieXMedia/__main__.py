# -*- coding: utf-8 -*-
# =========================================================
# TITAN OS | FINAL KERNEL (Authorized Version)
# =========================================================

import sys
import os
import asyncio
import importlib
import logging
import threading
from flask import Flask, request, redirect, url_for, jsonify, session, send_file, Response
from pyrogram import idle
from pytgcalls.exceptions import NoActiveGroupCall

# ---------------------------------------------------------
# [1] Path Engineering (هندسة المسارات)
# ---------------------------------------------------------
# 1. Force Python to see the root directory
sys.path.insert(0, os.getcwd())

# 2. Define critical paths
CURRENT_DIR = os.getcwd()
TITAN_DIR = os.path.join(CURRENT_DIR, "TitanOS")
DOWNLOADS_DIR = os.path.join(CURRENT_DIR, "downloads")

# 3. Create TitanOS folder if missing (Safety Check)
if not os.path.exists(TITAN_DIR):
    print(f"❌ Critical Error: TitanOS folder not found at {TITAN_DIR}")
    # Create dummy folder to prevent crash
    os.makedirs(TITAN_DIR, exist_ok=True)

# ---------------------------------------------------------
# [2] Web Engine (Flask Setup)
# ---------------------------------------------------------
app = Flask(__name__, template_folder=TITAN_DIR, static_folder=TITAN_DIR)
app.secret_key = "Titan_God_Mode_2025"
logging.getLogger('werkzeug').setLevel(logging.ERROR)

ADMIN_USER = "Abdallah"
ADMIN_PASS = "asdfghjkl05896"

# ---------------------------------------------------------
# [3] Bot Imports (Corrected for your Source)
# ---------------------------------------------------------
import config
from AnnieXMedia import LOGGER, app as bot_app, userbot
# ✅ هنا التصحيح: استيراد Call بدلاً من Annie
from AnnieXMedia.core.call import StreamController 
from AnnieXMedia.misc import sudo, db
from AnnieXMedia.plugins import ALL_MODULES
from AnnieXMedia.utils.database import get_banned_users, get_gbanned
from AnnieXMedia.utils.cookie_handler import fetch_and_store_cookies
from config import BANNED_USERS

# ---------------------------------------------------------
# [4] Web Routes (Controller)
# ---------------------------------------------------------

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
        return "<h1>Wrong Password!</h1>"
    
    # Use absolute path to guarantee file loading
    login_path = os.path.join(TITAN_DIR, "login.html")
    if os.path.exists(login_path):
        return send_file(login_path)
    return f"<h1>Error: login.html missing in {TITAN_DIR}</h1>"

@app.route('/dashboard')
def dashboard():
    if not session.get('user'): return redirect(url_for('login_page'))
    
    dash_path = os.path.join(TITAN_DIR, "dashboard.html")
    if os.path.exists(dash_path):
        return send_file(dash_path)
    return f"<h1>Error: dashboard.html missing in {TITAN_DIR}</h1>"

@app.route('/logs')
def view_logs():
    if not session.get('user'): return "Access Denied"
    log_file = os.path.join(CURRENT_DIR, "log.txt") 
    if os.path.exists(log_file):
        return send_file(log_file, mimetype="text/plain")
    return "No logs found."

@app.route('/stream/<chat_id>')
def stream_video(chat_id):
    if not session.get('user'): return "Access Denied", 403
    
    file_path = None
    try:
        cid = int(chat_id)
        if cid in db and db[cid]:
            track = db[cid][0]
            file_path = track.get("file")
    except: pass

    if not file_path and os.path.exists(DOWNLOADS_DIR):
        try:
            files = [os.path.join(DOWNLOADS_DIR, f) for f in os.listdir(DOWNLOADS_DIR) if f.endswith(('mp4','mp3','webm'))]
            if files: file_path = max(files, key=os.path.getctime)
        except: pass

    if not file_path or not os.path.exists(file_path):
        return "No Stream Found", 404

    # Range Support (Seeking Fix)
    range_header = request.headers.get('Range', None)
    if not range_header: return send_file(file_path)
    
    size = os.path.getsize(file_path)
    byte1, byte2 = 0, None
    m = range_header.replace('bytes=', '').split('-')
    byte1 = int(m[0])
    if m[1]: byte2 = int(m[1])
    length = size - byte1
    if byte2: length = byte2 + 1 - byte1
    
    with open(file_path, 'rb') as f:
        f.seek(byte1)
        data = f.read(length)
    
    rv = Response(data, 206, mimetype="video/mp4", direct_passthrough=True)
    rv.headers.add('Content-Range', f'bytes {byte1}-{byte1 + length - 1}/{size}')
    return rv

# --- API Endpoints ---
@app.route('/api/active_calls')
def api_active_calls():
    data = []
    try:
        # Accessing the 'active_calls' set from your Call class
        if hasattr(StreamController, 'active_calls'):
            data = [{"id": str(x), "name": "Active Chat"} for x in StreamController.active_calls]
    except: pass
    
    if not data: data = [{"id": "0", "name": "Waiting for Calls..."}]
    return jsonify({"chats": data})

@app.route('/api/track_info/<chat_id>')
def api_track_info(chat_id):
    info = {"title": "Idle", "artist": "", "cover": "", "stream_url": ""}
    try:
        cid = int(chat_id)
        if cid in db and db[cid]:
            track = db[cid][0]
            info = {
                "title": track.get("title", "Unknown"),
                "artist": track.get("dur", "Live"),
                "cover": track.get("thumb", "https://telegra.ph/file/5eb6df308e92f4477813d.jpg"),
                "stream_url": f"/stream/{cid}"
            }
    except: pass
    return jsonify(info)

@app.route('/api/<cmd>/<chat_id>', methods=['POST'])
def api_command(cmd, chat_id):
    async def exec_cmd():
        try:
            cid = int(chat_id)
            if cmd == 'pause': await StreamController.pause_stream(cid)
            elif cmd == 'resume': await StreamController.resume_stream(cid)
            elif cmd in ['skip', 'stop']: await StreamController.stop_stream(cid)
        except: pass

    try:
        asyncio.run_coroutine_threadsafe(exec_cmd(), bot_app.loop)
    except: pass
    return jsonify({"ok": True})

@app.route('/api/system/turbo', methods=['POST'])
def turbo_mode():
    import gc; gc.collect()
    return jsonify({"ok": True})

# ---------------------------------------------------------
# [5] Main Launcher (Combined Logic)
# ---------------------------------------------------------
def run_web():
    app.run(host="0.0.0.0", port=8080, debug=False, use_reloader=False)

async def init():
    print("---------------------------------------")
    print("🚀 TITAN OS + ANNIE MUSIC LAUNCHING...")
    print("---------------------------------------")

    # 1. Start Web Server in Background
    t = threading.Thread(target=run_web)
    t.daemon = True
    t.start()
    print("🌐 Dashboard: http://0.0.0.0:8080")

    # 2. Start Bot Logic
    if (
        not config.STRING1
        and not config.STRING2
        and not config.STRING3
        and not config.STRING4
        and not config.STRING5
    ):
        LOGGER(__name__).error("Assistant session not filled, please fill a pyrogram session...")
        return

    try:
        await fetch_and_store_cookies()
        LOGGER("AnnieXMedia").info("Cookies loaded successfully ✅")
    except Exception as e:
        LOGGER("AnnieXMedia").warning(f"Cookie Error: {e}")

    await sudo()

    try:
        users = await get_gbanned()
        for user_id in users:
            BANNED_USERS.add(user_id)
        users = await get_banned_users()
        for user_id in users:
            BANNED_USERS.add(user_id)
    except: pass

    await bot_app.start()
    for all_module in ALL_MODULES:
        importlib.import_module("AnnieXMedia.plugins" + all_module)

    LOGGER("AnnieXMedia.plugins").info("Annie's Modules Loaded...")

    await userbot.start()
    await StreamController.start()

    try:
        await StreamController.stream_call("http://docs.evostream.com/sample_content/assets/sintel1m720p.mp4")
    except NoActiveGroupCall:
        LOGGER("AnnieXMedia").error("Please turn on the voice chat of your log group/channel.\n\nAnnie Bot Stopped...")
        return
    except: pass

    await StreamController.decorators()
    LOGGER("AnnieXMedia").info("Titan OS Integration Successful! System Online.")
    
    await idle()
    
    await bot_app.stop()
    await userbot.stop()
    LOGGER("AnnieXMedia").info("Stopping Annie Music Bot...")

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(init())
