# -*- coding: utf-8 -*-
# =========================================================
# AnnieXMedia/__main__.py  —  Titan OS Web & Bot Launcher
# =========================================================
# Code Fixed by Gemini: Unified Loop & Proper Idle Handling
# =========================================================

import os
import sys
import asyncio
import importlib
import logging
import threading
import socket
import shutil
import gc
import inspect
from functools import wraps
from datetime import datetime
from flask import Flask, request, redirect, url_for, jsonify, session, send_file, Response, abort
from pyrogram import idle

# ---------- PATH SETUP ----------
sys.path.insert(0, os.getcwd())
CURRENT_DIR = os.getcwd()
TITAN_DIR = os.path.join(CURRENT_DIR, "TitanOS")
DOWNLOADS_DIR = os.path.join(CURRENT_DIR, "downloads")
LOG_FILE = os.path.join(CURRENT_DIR, "log.txt")

os.makedirs(TITAN_DIR, exist_ok=True)
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

# ---------- GLOBAL LOOP REFERENCE ----------
# This is crucial: One loop to rule them all.
main_loop = None 

# ---------- FLASK APP ----------
app = Flask(__name__, template_folder=TITAN_DIR, static_folder=TITAN_DIR)
app.secret_key = os.environ.get("TITAN_SESSION_KEY", "Titan_God_Mode_2025")

# reduce werkzeug logs
logging.getLogger('werkzeug').setLevel(logging.ERROR)
logger = logging.getLogger("TitanMain")
logger.setLevel(logging.INFO)
fh = logging.FileHandler(LOG_FILE)
fh.setFormatter(logging.Formatter("%(asctime)s — %(levelname)s — %(message)s"))
logger.addHandler(fh)
# Also log to console so you see errors in terminal
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter("%(asctime)s — %(levelname)s — %(message)s"))
logger.addHandler(console_handler)

# ---------- ADMIN CREDENTIALS ----------
ADMIN_USER = os.environ.get("TITAN_ADMIN_USER", "Abdallah")
ADMIN_PASS = os.environ.get("TITAN_ADMIN_PASS", "asdfghjkl05896")

# ---------- TRY IMPORT BOT COMPONENTS ----------
SYSTEM_READY = False
bot_app = None
userbot = None
StreamController = None
db = {}
YouTubeHelper = None
BANNED_USERS = set()

# optional helpers
try:
    import psutil
except Exception:
    psutil = None

try:
    import config
    from AnnieXMedia import app as bot_app, userbot, LOGGER as ANNIE_LOGGER
    from AnnieXMedia.core.call import StreamController as StreamController
    from AnnieXMedia.misc import db as db
    from AnnieXMedia.utils.database import get_banned_users, get_gbanned
    # YouTube helper if exists
    try:
        from AnnieXMedia import YouTube as YouTubeHelper
    except Exception:
        YouTubeHelper = None

    # optional cookie handler
    try:
        from AnnieXMedia.utils.cookie_handler import fetch_and_store_cookies
    except Exception:
        fetch_and_store_cookies = None

    # mark ready
    SYSTEM_READY = True
    logger.info("✅ AnnieXMedia modules imported — SYSTEM_READY = True")
except Exception as e:
    logger.warning(f"⚠️ Partial startup: could not import AnnieXMedia modules: {e}")
    # keep SYSTEM_READY False; endpoints will degrade gracefully

# ---------- UTIL: Safe Async Execution ----------

def run_coroutine_safe(func_or_coro=None, *args, **kwargs):
    """
    Execute a coroutine/function on the MAIN asyncio loop thread-safely.
    This fixes the 'Future attached to a different loop' error.
    """
    global main_loop

    if not main_loop:
        logger.error("Main Loop is not set yet!")
        return None

    try:
        coro = None
        # 1. If it's a coroutine object
        if inspect.iscoroutine(func_or_coro):
            coro = func_or_coro
        # 2. If it's an async function
        elif inspect.iscoroutinefunction(func_or_coro):
            coro = func_or_coro(*args, **kwargs)
        # 3. If it's a normal function, run it and check result
        elif callable(func_or_coro):
            result = func_or_coro(*args, **kwargs)
            if inspect.iscoroutine(result):
                coro = result
            else:
                return result # It was sync, return result directly
        
        if coro:
            # Submit to the MAIN loop from the Flask Thread
            if asyncio.iscoroutine(coro):
                future = asyncio.run_coroutine_threadsafe(coro, main_loop)
                return future
    except Exception:
        logger.exception("run_coroutine_safe failure")
        return None

# ---------- small async helpers ----------
async def safe_call_async(target, name, *args, **kwargs):
    """Call target.name(...) handling sync/async gracefully."""
    if not target:
        return None
    try:
        attr = getattr(target, name, None)
        if attr is None:
            return None
        if callable(attr):
            res = attr(*args, **kwargs)
            if asyncio.iscoroutine(res) or asyncio.isfuture(res):
                return await res
            return res
        return attr
    except Exception as e:
        logger.debug(f"safe_call_async error {e}")
        return None

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get("user") == ADMIN_USER:
            return f(*args, **kwargs)
        return jsonify({"error": "Auth Required"}), 401
    return decorated

# ---------- ROUTES: Frontend pages ----------
@app.route("/")
def root():
    if session.get("user") == ADMIN_USER:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login_page"))

@app.route("/login", methods=["GET", "POST"])
def login_page():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username == ADMIN_USER and password == ADMIN_PASS:
            session["user"] = ADMIN_USER
            return redirect(url_for("dashboard"))
        return "<h3>Invalid credentials</h3>", 403
    login_path = os.path.join(TITAN_DIR, "login.html")
    if os.path.exists(login_path):
        return send_file(login_path)
    return "<h3>Login page missing (TitanOS/login.html)</h3>", 404

@app.route("/dashboard")
def dashboard():
    if session.get("user") != ADMIN_USER:
        return redirect(url_for("login_page"))
    dash_path = os.path.join(TITAN_DIR, "dashboard.html")
    if os.path.exists(dash_path):
        return send_file(dash_path)
    return "<h3>dashboard.html missing in TitanOS folder</h3>", 404

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login_page"))

# ---------- ROUTES: Streaming (Range support) ----------
@app.route("/stream/<chat_id>")
def stream_route(chat_id):
    if session.get("user") != ADMIN_USER:
        return "Access Denied", 403

    file_path = None
    try:
        cid = int(chat_id)
        if isinstance(db, dict) and cid in db and db[cid]:
            track = db[cid][0]
            file_path = track.get("file") or track.get("filepath") or None
    except Exception:
        pass

    if not file_path or not os.path.exists(file_path):
        try:
            files = [os.path.join(DOWNLOADS_DIR, f) for f in os.listdir(DOWNLOADS_DIR) if f.lower().endswith(('.mp4', '.webm', '.mkv'))]
            if files:
                file_path = max(files, key=os.path.getctime)
        except Exception:
            file_path = None

    if not file_path or not os.path.exists(file_path):
        return "No Stream Found", 404

    range_header = request.headers.get("Range", None)
    file_size = os.path.getsize(file_path)
    if range_header:
        try:
            bytes_range = range_header.strip().split("=")[-1]
            start_str, end_str = bytes_range.split("-")
            start = int(start_str) if start_str else 0
            end = int(end_str) if end_str else file_size - 1
            end = min(end, file_size - 1)
            length = end - start + 1
            with open(file_path, "rb") as f:
                f.seek(start)
                data = f.read(length)
            rv = Response(data, 206, mimetype="video/mp4")
            rv.headers.add("Content-Range", f"bytes {start}-{end}/{file_size}")
            rv.headers.add("Accept-Ranges", "bytes")
            rv.headers.add("Content-Length", str(length))
            return rv
        except Exception as e:
            logger.exception("Range handling error")
            return send_file(file_path)
    return send_file(file_path)

# ---------- API: Active Calls ----------
@app.route("/api/active_calls")
def api_active_calls():
    chats = []
    try:
        # We need to run this on the main loop because StreamController objects are there
        # But for simple reads, direct access usually works if not changing state
        ac = getattr(StreamController, "active_calls", [])
        if callable(ac):
            # This is tricky in sync Flask, assuming ac() returns a list directly or needs await
            # If it needs await, we can't easily do it here blocking. 
            # Simplified: Try to read attribute if list
            pass 
        elif isinstance(ac, list) or isinstance(ac, set):
            chats = [{"chat_id": str(x), "name": f"Chat {x}", "cover": ""} for x in ac]
    except Exception:
        pass
    
    # Fallback to DB
    if not chats and isinstance(db, dict):
        try:
            keys = [k for k in db.keys() if isinstance(k, int)]
            chats = [{"chat_id": str(k), "name": db[k][0].get("title", str(k)) if db[k] else str(k), "cover": db[k][0].get("thumb", "") if db[k] else ""} for k in keys]
        except Exception:
            chats = []
    return jsonify({"chats": chats})

# ---------- API: Track Info ----------
@app.route("/api/track_info/<chat_id>")
def api_track_info(chat_id):
    info = {"title": "System Idle", "artist": "Titan OS", "cover": "", "stream_url": "", "is_playing": False}
    try:
        cid = int(chat_id)
        if isinstance(db, dict) and cid in db and db[cid]:
            t = db[cid][0]
            info = {
                "title": t.get("title", "Unknown"),
                "artist": t.get("by", "Unknown"),
                "cover": t.get("thumb", ""),
                "duration": t.get("dur", "Live"),
                "is_playing": True,
                "stream_url": f"/stream/{cid}",
                "players": t.get("players", [])
            }
    except Exception:
        pass
    return jsonify(info)

# ---------- API: Player Control (Uses run_coroutine_safe) ----------
@app.route("/api/player/control", methods=["POST"])
@require_auth
def api_player_control():
    cmd = request.form.get("cmd") or request.values.get("cmd")
    chat_id = request.form.get("chat_id") or request.values.get("chat_id")
    
    async def _exec():
        try:
            cid = int(chat_id)
        except:
            cid = None
            
        if cmd == "pause": await safe_call_async(StreamController, "pause_stream", cid)
        elif cmd == "resume": await safe_call_async(StreamController, "resume_stream", cid)
        elif cmd == "skip": await safe_call_async(StreamController, "stop_stream", cid)
        elif cmd == "stop": await safe_call_async(StreamController, "stop_stream", cid)
        else: logger.debug(f"Unknown command: {cmd}")

    run_coroutine_safe(_exec)
    return jsonify({"status": "scheduled", "command": cmd})

# ---------- API: Play Custom ----------
@app.route("/api/player/play_custom", methods=["POST"])
@require_auth
def api_play_custom():
    chat_id = request.form.get("chat_id") or request.values.get("chat_id")
    query = request.form.get("query") or request.values.get("query")
    
    async def _exec():
        try:
            cid = int(chat_id)
            link = None
            if YouTubeHelper and hasattr(YouTubeHelper, "search"):
                res = await safe_call_async(YouTubeHelper, "search", query, limit=1)
                if res and isinstance(res, list) and len(res) > 0:
                    link = res[0].get("link")
            if not link and "http" in query:
                link = query
            
            if link:
                await safe_call_async(StreamController, "join_call", chat_id=cid, original_chat_id=cid, link=link, video=True)
        except Exception:
            logger.exception("play_custom error")

    run_coroutine_safe(_exec)
    return jsonify({"status": "scheduled"})

# ---------- API: Utils ----------
@app.route("/api/utils/action", methods=["POST"])
@require_auth
def api_action():
    action = request.form.get("action")
    if action == "restart":
        # Force restart
        os.execl(sys.executable, sys.executable, *sys.argv)
    return jsonify({"status": "ok"})

@app.route("/api/health")
def api_health():
    return jsonify({"status": "ok", "system_ready": SYSTEM_READY})

# ---------- STARTUP LOGIC ----------

def run_flask():
    """Runs Flask in a separate thread, blocking that thread."""
    try:
        # Use host 0.0.0.0 for external access (Fly.io/VPS)
        app.run(host="0.0.0.0", port=8080, debug=False, use_reloader=False)
    except Exception:
        logger.exception("Flask server stopped")

async def start_services():
    """Starts the bot services on the main loop."""
    logger.info("Initializing Bot Services...")
    
    # 1. Config Check
    try:
        import config as cfg
        if not cfg.STRING1:
            logger.error("❌ No Pyrogram Session String found in config!")
    except:
        pass

    # 2. Start Bot Client
    if bot_app:
        try:
            await bot_app.start()
            logger.info("✅ Bot App Started")
        except Exception as e:
            logger.error(f"❌ Bot App Failed: {e}")

    # 3. Start Userbot
    if userbot:
        try:
            await userbot.start()
            logger.info("✅ Userbot Started")
        except Exception as e:
            logger.error(f"❌ Userbot Failed: {e}")

    # 4. Start StreamController
    if StreamController:
        try:
            # Check if start is async or sync
            if hasattr(StreamController, "start"):
                res = StreamController.start()
                if asyncio.iscoroutine(res):
                    await res
            logger.info("✅ StreamController Started")
        except Exception as e:
            logger.error(f"StreamController start error: {e}")

    logger.info("🚀 Titan System Fully Operational")

async def stop_services():
    logger.info("Stopping services...")
    if bot_app: 
        try: await bot_app.stop()
        except: pass
    if userbot:
        try: await userbot.stop()
        except: pass

def main():
    global main_loop
    
    # 1. Setup the Event Loop
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    main_loop = loop # Set the global reference for Flask to use

    # 2. Start Flask in a DAEMON thread
    # Daemon means if the main program (bot) dies, Flask dies too.
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info("🌐 Flask Server Thread Started")

    # 3. Run the async sequence
    try:
        # Initialize Clients
        loop.run_until_complete(start_services())
        
        # 4. IDLE - The most important part
        # This keeps the script running until Ctrl+C or kill signal
        logger.info("⏳ Idling... (Press Ctrl+C to stop)")
        idle() 
        
        # If idle() returns, it means we are shutting down
        loop.run_until_complete(stop_services())
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received")
    except Exception as e:
        logger.exception(f"Critical Error in Main Loop: {e}")
    finally:
        logger.info("Titan Main: Exiting")

if __name__ == "__main__":
    main()
