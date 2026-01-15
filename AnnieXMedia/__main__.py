# -*- coding: utf-8 -*-
# =========================================================
# AnnieXMedia/__main__.py  —  Titan OS Web & Bot Launcher
# =========================================================
# تم تحسين الربط بين الويب و قلب البوت — Author: assistant
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

# ---------- PATH SETUP ----------
sys.path.insert(0, os.getcwd())
CURRENT_DIR = os.getcwd()
TITAN_DIR = os.path.join(CURRENT_DIR, "TitanOS")
DOWNLOADS_DIR = os.path.join(CURRENT_DIR, "downloads")
LOG_FILE = os.path.join(CURRENT_DIR, "log.txt")

os.makedirs(TITAN_DIR, exist_ok=True)
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

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

# ---------- ADMIN CREDENTIALS (تغيير مستحسن) ----------
ADMIN_USER = os.environ.get("TITAN_ADMIN_USER", "Abdallah")
ADMIN_PASS = os.environ.get("TITAN_ADMIN_PASS", "asdfghjkl05896")

# ---------- TRY IMPORT BOT COMPONENTS ----------
SYSTEM_READY = False
bot_app = None
userbot = None
StreamController = None
db = {}
YouTubeHelper = None
LOGGER = logger
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

# ---------- UTIL: event loop references ----------
bot_loop = None                 # will point to the main asyncio loop when bot starts
_background_loop = None         # fallback/background loop (runs in separate thread)
_background_thread = None

def _ensure_background_loop():
    """Start a dedicated background asyncio loop in a daemon thread (non-blocking)."""
    global _background_loop, _background_thread
    if _background_loop and _background_loop.is_running():
        return _background_loop
    # create loop and thread
    _background_loop = asyncio.new_event_loop()
    def _run_loop(loop):
        try:
            asyncio.set_event_loop(loop)
            loop.run_forever()
        except Exception as e:
            logger.exception("Background loop crashed")
    _background_thread = threading.Thread(target=_run_loop, args=(_background_loop,), daemon=True)
    _background_thread.start()
    # small wait until loop becomes ready
    return _background_loop

def run_coroutine_safe(func_or_coro=None, *args, **kwargs):
    """
    Robust scheduler for coroutines and sync functions.
    - Accepts: coroutine object, async function, or sync callable.
    - If bot_loop exists and running => schedule there (non-blocking).
    - Otherwise schedule on a background loop thread (non-blocking).
    - If given a sync function (or returns non-coroutine), call it directly and return its result.
    Returns:
      - concurrent.futures.Future when scheduled on an event loop
      - direct result for sync callables
      - None on error
    """
    global bot_loop, _background_loop

    try:
        # If a coroutine object is passed directly
        if inspect.iscoroutine(func_or_coro):
            coro = func_or_coro

        # If an async function (callable) is passed
        elif inspect.iscoroutinefunction(func_or_coro):
            coro = func_or_coro(*args, **kwargs)

        # If a callable (sync or returns coroutine)
        elif callable(func_or_coro):
            result = func_or_coro(*args, **kwargs)
            if inspect.iscoroutine(result):
                coro = result
            else:
                # sync result, return directly
                return result
        else:
            # Nothing meaningful passed
            return None

        # At this point we have a coroutine object `coro`
        # 1) Prefer bot_loop if available and running
        if bot_loop and isinstance(bot_loop, asyncio.AbstractEventLoop) and bot_loop.is_running():
            try:
                fut = asyncio.run_coroutine_threadsafe(coro, bot_loop)
                return fut
            except Exception:
                logger.exception("run_coroutine_threadsafe failed on bot_loop; falling back to background loop")

        # 2) Use background loop thread (non-blocking)
        try:
            bg = _ensure_background_loop()
            fut = asyncio.run_coroutine_threadsafe(coro, bg)
            return fut
        except Exception:
            logger.exception("Scheduling on background loop failed; attempting blocking run")

        # 3) Last-resort: blocking run (should be rare)
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            res = loop.run_until_complete(coro)
            return res
        finally:
            try:
                loop.close()
            except:
                pass

    except Exception:
        logger.exception("run_coroutine_safe general failure")
        return None

# ---------- small async helpers ----------
async def _maybe_await(obj):
    if asyncio.iscoroutine(obj) or asyncio.isfuture(obj):
        return await obj
    return obj

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
    return "<h3>Login page missing (templates/login.html)</h3>", 404

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
        ac = getattr(StreamController, "active_calls", None)
        if ac:
            if callable(ac):
                try:
                    res = ac()
                    chats = [{"chat_id": str(x), "name": f"Chat {x}", "cover": ""} for x in res] if res else []
                except Exception:
                    chats = [{"chat_id": str(x), "name": f"Chat {x}", "cover": ""} for x in ac] if hasattr(ac, "__iter__") else []
            else:
                chats = [{"chat_id": str(x), "name": f"Chat {x}", "cover": ""} for x in ac] if hasattr(ac, "__iter__") else []
    except Exception:
        logger.debug("api_active_calls: StreamController.active_calls not available")
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

# ---------- API: Player Control ----------
@app.route("/api/player/control", methods=["POST"])
@require_auth
def api_player_control():
    cmd = request.form.get("cmd") or request.values.get("cmd")
    chat_id = request.form.get("chat_id") or request.values.get("chat_id")
    if not cmd or not chat_id:
        return jsonify({"error": "Missing cmd or chat_id"}), 400

    async def _exec():
        try:
            cid = int(chat_id)
        except:
            cid = None
        try:
            if cmd in ("pause", "pause_stream"):
                await safe_call_async(StreamController, "pause_stream", cid)
            elif cmd in ("resume", "resume_stream"):
                await safe_call_async(StreamController, "resume_stream", cid)
            elif cmd in ("skip", "stop", "stop_stream"):
                await safe_call_async(StreamController, "stop_stream", cid)
            elif cmd in ("force_stop", "force_stop_stream"):
                await safe_call_async(StreamController, "force_stop_stream", cid)
            elif cmd == "focus":
                try:
                    setattr(StreamController, "turbo_chat_id", cid)
                except:
                    pass
            else:
                logger.debug(f"Unknown command received: {cmd}")
        except Exception:
            logger.exception("Error executing player control")

    try:
        # Accept both coroutine-object and function-ref usages from callers
        run_coroutine_safe(_exec)  # pass function (preferred)
    except Exception:
        logger.exception("Failed to schedule player control")
    return jsonify({"status": "scheduled", "command": cmd})

# ---------- API: Play Custom (youtube search & join) ----------
@app.route("/api/player/play_custom", methods=["POST"])
@require_auth
def api_play_custom():
    chat_id = request.form.get("chat_id") or request.values.get("chat_id")
    query = request.form.get("query") or request.values.get("query")
    if not chat_id or not query:
        return jsonify({"error": "Missing chat_id or query"}), 400

    async def _exec():
        try:
            cid = int(chat_id)
        except:
            cid = None
        try:
            link = None
            title = None
            if YouTubeHelper and hasattr(YouTubeHelper, "search"):
                res = await safe_call_async(YouTubeHelper, "search", query, limit=1)
                if res and isinstance(res, list) and len(res) > 0:
                    link = res[0].get("link")
                    title = res[0].get("title")
            if not link and (query.startswith("http://") or query.startswith("https://")):
                link = query
                title = os.path.basename(query)
            if not link:
                return {"error": "No results"}
            await safe_call_async(StreamController, "join_call", chat_id=cid, original_chat_id=cid, link=link, video=True)
            return {"status": "playing", "title": title}
        except Exception:
            logger.exception("play_custom error")
            return {"error": "play_custom failed"}

    run_coroutine_safe(_exec)
    return jsonify({"status": "scheduled", "chat_id": chat_id})

# ---------- API: Security (gbans & blacklist) ----------
@app.route("/api/security/block_user", methods=["POST"])
@require_auth
def api_block_user():
    user_id = request.form.get("user_id") or request.values.get("user_id")
    action = request.form.get("action") or request.values.get("action")
    if not user_id or not action:
        return jsonify({"error": "Missing parameters"}), 400

    async def _exec():
        try:
            uid = int(user_id)
        except:
            return {"error": "Invalid user id"}
        try:
            if action == "enable":
                if 'add_gban_user' in globals():
                    await safe_call_async(globals().get('add_gban_user'), "__call__", uid)
                try:
                    BANNED_USERS.add(uid)
                except:
                    pass
                return {"status": "blocked", "id": uid}
            else:
                if 'remove_gban_user' in globals():
                    await safe_call_async(globals().get('remove_gban_user'), "__call__", uid)
                try:
                    BANNED_USERS.discard(uid)
                except:
                    pass
                return {"status": "unblocked", "id": uid}
        except Exception:
            logger.exception("block_user error")
            return {"error": "block_user failed"}

    run_coroutine_safe(_exec)
    return jsonify({"status": "scheduled"})

@app.route("/api/security/blacklist_chat", methods=["POST"])
@require_auth
def api_blacklist_chat():
    chat_id = request.form.get("chat_id") or request.values.get("chat_id")
    action = request.form.get("action") or request.values.get("action")
    if not chat_id or not action:
        return jsonify({"error": "Missing parameters"}), 400

    async def _exec():
        try:
            cid = int(chat_id)
        except:
            return {"error": "Invalid chat id"}
        try:
            if action == "enable" and 'blacklist_chat' in globals():
                await safe_call_async(globals().get('blacklist_chat'), "__call__", cid)
                try:
                    await safe_call_async(bot_app, "leave_chat", cid)
                except:
                    pass
                return {"status": "blacklisted", "id": cid}
            elif action == "disable" and 'whitelist_chat' in globals():
                await safe_call_async(globals().get('whitelist_chat'), "__call__", cid)
                return {"status": "whitelisted", "id": cid}
            return {"error": "No action performed"}
        except Exception:
            logger.exception("blacklist_chat error")
            return {"error": "blacklist_chat failed"}

    run_coroutine_safe(_exec)
    return jsonify({"status": "scheduled"})

# ---------- API: Settings & Status ----------
@app.route("/api/settings/status")
def api_settings_status():
    try:
        m_status = False
        a_status = False
        if SYSTEM_READY:
            try:
                # call DB helpers if present (sync-run small coros)
                if globals().get('is_maintenance'):
                    m_status = asyncio.get_event_loop().run_until_complete(safe_call_async(globals().get('is_maintenance'), "__call__"))
            except:
                m_status = False
            try:
                if globals().get('is_autoend'):
                    a_status = asyncio.get_event_loop().run_until_complete(safe_call_async(globals().get('is_autoend'), "__call__"))
            except:
                a_status = False
        ram = psutil.virtual_memory().percent if psutil else 0
        cpu = psutil.cpu_percent() if psutil else 0
        ping = 0
        try:
            if StreamController:
                ping = asyncio.get_event_loop().run_until_complete(safe_call_async(StreamController, "ping"))
        except:
            ping = 0
        return jsonify({"maintenance": m_status, "autoend": a_status, "ram": ram, "cpu": cpu, "ping": ping})
    except Exception:
        logger.exception("status error")
        return jsonify({"error": "status failed"}), 500

# ---------- API: Utils (turbo, cache list, logs, update, restart) ----------
@app.route("/api/utils/turbo", methods=["POST"])
@require_auth
def api_turbo():
    deleted = 0
    freed = 0
    try:
        for folder in (DOWNLOADS_DIR, os.path.join(CURRENT_DIR, "cache"), os.path.join(CURRENT_DIR, "raw_files")):
            if os.path.exists(folder):
                for f in os.listdir(folder):
                    fp = os.path.join(folder, f)
                    try:
                        freed += os.path.getsize(fp)
                        os.remove(fp)
                        deleted += 1
                    except:
                        pass
        for root, dirs, files in os.walk(CURRENT_DIR):
            for d in dirs:
                if d == "__pycache__":
                    try: shutil.rmtree(os.path.join(root, d))
                    except: pass
        gc.collect()
        return jsonify({"status": "Turbo Executed", "files_removed": deleted, "space_freed_mb": f"{freed/(1024*1024):.2f}"})
    except Exception:
        logger.exception("turbo error")
        return jsonify({"error": "turbo failed"}), 500

@app.route("/api/utils/cache_list")
@require_auth
def api_cache_list():
    files = []
    total = 0.0
    try:
        for f in os.listdir(DOWNLOADS_DIR):
            fp = os.path.join(DOWNLOADS_DIR, f)
            try:
                size_mb = os.path.getsize(fp)/(1024*1024)
                files.append({"name": f, "size": f"{size_mb:.2f} MB"})
                total += size_mb
            except:
                pass
    except:
        pass
    return jsonify({"files": files, "total_count": len(files), "total_size_mb": f"{total:.2f}"})

@app.route("/api/utils/logs")
@require_auth
def api_logs():
    if os.path.exists(LOG_FILE):
        return send_file(LOG_FILE, mimetype="text/plain")
    return jsonify({"error": "No logs found"}), 404

def _restart_now():
    try:
        python = sys.executable
        os.execv(python, [python] + sys.argv)
    except Exception:
        logger.exception("restart failed")

@app.route("/api/utils/action", methods=["POST"])
@require_auth
def api_action():
    action = request.form.get("action") or request.values.get("action")
    if not action:
        return jsonify({"error": "Missing action"}), 400
    if action == "restart":
        threading.Thread(target=_restart_now, daemon=True).start()
        return jsonify({"status": "restarting"})
    if action == "update":
        try:
            os.system("git pull")
            threading.Thread(target=_restart_now, daemon=True).start()
            return jsonify({"status": "updating and restarting"})
        except Exception:
            logger.exception("update failed")
            return jsonify({"error": "update failed"}), 500
    return jsonify({"error": "unknown action"}), 400

# ---------- SIMPLE HELPER PAGES ----------
@app.route("/api/health")
def api_health():
    return jsonify({"status": "ok", "system_ready": SYSTEM_READY})

# ---------- AUTH PROTECTED LOG VIEW ----------
@app.route("/logs")
@require_auth
def logs_page():
    if os.path.exists(LOG_FILE):
        return send_file(LOG_FILE)
    return "No logs"

# ---------- STARTUP / LAUNCH LOGIC ----------
def run_flask():
    try:
        # threaded=False to avoid extra threads; Flask runs in its own thread started by init_and_start
        app.run(host="0.0.0.0", port=8080, debug=False, use_reloader=False)
    except Exception:
        logger.exception("Flask server stopped unexpectedly")

async def init_and_start():
    """Main async startup sequence — starts web server thread, then bot & controllers."""
    global bot_loop
    # 1) Start Flask in thread
    t = threading.Thread(target=run_flask, daemon=True)
    t.start()
    logger.info("🚀 Flask server started on port 8080")

    # 2) Print access URLs
    try:
        hn = socket.gethostname()
        ip = socket.gethostbyname(hn)
        logger.info(f"Dashboard: http://{ip}:8080 (login: {ADMIN_USER})")
    except:
        logger.info("Dashboard: http://0.0.0.0:8080")

    # 3) Validate config strings (from AnnieXMedia.config)
    try:
        import config as cfg
        strings_ok = any(getattr(cfg, f"STRING{i}", None) for i in range(1,6))
        if not strings_ok:
            logger.error("No Pyrogram session STRING found in config — aborting bot start")
    except Exception:
        logger.warning("config import failed or no session strings")

    # 4) Try to fetch cookies (non-fatal)
    if 'fetch_and_store_cookies' in globals() and fetch_and_store_cookies:
        try:
            await fetch_and_store_cookies()
            logger.info("Cookies loaded")
        except Exception:
            logger.warning("fetch_and_store_cookies failed")

    # 5) Setup banned users
    try:
        if 'get_gbanned' in globals() and callable(globals().get('get_gbanned')):
            gb = await globals().get('get_gbanned')()
            for u in gb: BANNED_USERS.add(u)
        if 'get_banned_users' in globals() and callable(globals().get('get_banned_users')):
            bu = await globals().get('get_banned_users')()
            for u in bu: BANNED_USERS.add(u)
    except Exception:
        logger.debug("could not prefetch banned users")

    # 6) Start bot_app and userbot (if present)
    if bot_app:
        try:
            # store loop
            bot_loop = asyncio.get_event_loop()
            await bot_app.start()
            logger.info("Bot (bot_app) started")
        except Exception:
            logger.exception("Failed to start bot_app")

    if userbot:
        try:
            await userbot.start()
            logger.info("userbot started")
        except Exception:
            logger.exception("Failed to start userbot")

    # 7) Start StreamController if present
    if StreamController:
        try:
            if hasattr(StreamController, "start"):
                maybe = StreamController.start()
                if asyncio.iscoroutine(maybe):
                    await maybe
            logger.info("StreamController started")
        except Exception:
            logger.exception("StreamController start failed")

        # OPTIONAL: try to auto-start a sample stream (non-fatal)
        try:
            sample = "http://docs.evostream.com/sample_content/assets/sintel1m720p.mp4"
            for name in ("stream_call", "stream_call_now", "stream_call_url", "stream_caller", "stream_call_link", "stream_call"):
                if hasattr(StreamController, name):
                    maybe = getattr(StreamController, name)(sample)
                    if asyncio.iscoroutine(maybe):
                        await maybe
                    break
        except Exception:
            logger.debug("No auto sample stream started (ok)")

    # 8) mark ready
    logger.info("Titan Main: Initialization complete")
    return

def main():
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(init_and_start())
        try:
            if bot_app and hasattr(bot_app, "idle"):
                loop.run_until_complete(bot_app.idle())
        except Exception:
            loop.run_forever()
    except KeyboardInterrupt:
        logger.info("Interrupted — shutting down")
    finally:
        try:
            if bot_app and hasattr(bot_app, "stop"):
                run_coroutine_safe(bot_app.stop)
            if userbot and hasattr(userbot, "stop"):
                run_coroutine_safe(userbot.stop)
        except Exception:
            pass
        logger.info("Exiting")

if __name__ == "__main__":
    main()
