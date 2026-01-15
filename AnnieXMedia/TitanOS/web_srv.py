# -*- coding: utf-8 -*-
# ==============================================================================
# TITAN OS | ULTIMATE KERNEL (The Complete Backend Engine) - Updated Integrator
# تعديل لربط الويب بسورس AnnieXMedia بشكل أكثر صلابة
# ==============================================================================

import os
import sys
import asyncio
import psutil
import shutil
import socket
import logging
import gc
import inspect
import traceback
from datetime import datetime
from threading import Thread
from typing import Any

# [1] Library Imports
try:
    import uvicorn
    from git import Repo, GitCommandError
    from fastapi import FastAPI, Request, Response, Form, BackgroundTasks, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, FileResponse, StreamingResponse
    from fastapi.templating import Jinja2Templates
    from fastapi.staticfiles import StaticFiles
    from starlette.middleware.sessions import SessionMiddleware
    from starlette.middleware.cors import CORSMiddleware
except ImportError:
    print("\n❌ ERROR: Missing Libraries! Run: pip3 install fastapi uvicorn gitpython aiofiles\n")
    raise

# ------------------------------------------------------------------------------
# [2] Paths & Config
# ------------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
DOWNLOADS_DIR = os.path.join(ROOT_DIR, "downloads")
CACHE_DIR = os.path.join(ROOT_DIR, "cache")
RAW_FILES_DIR = os.path.join(ROOT_DIR, "raw_files")
LOG_FILE = os.path.join(ROOT_DIR, "log.txt")

if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# ------------------------------------------------------------------------------
# [3] Bot Integration (attempt imports - may run standalone)
# ------------------------------------------------------------------------------
SYSTEM_READY = False
CallClient = None
BotClient = None
QueueDB = {}
YouTubeHelper = None
Config = None
BANNED_USERS = set()

try:
    import config
    Config = config
    from config import BANNED_USERS as _BANS
    BANNED_USERS = _BANS

    # AnnieXMedia app client (the Pyrogram bot)
    from AnnieXMedia import app as BotClient

    # Stream controller (may be class or instance)
    from AnnieXMedia.core.call import StreamController as CallClient

    # helper & queue
    from AnnieXMedia import YouTube as YouTubeHelper
    from AnnieXMedia.misc import db as QueueDB

    # database utilities
    from AnnieXMedia.utils.database import (
        add_gban_user, remove_gban_user, get_banned_users,
        blacklist_chat, whitelist_chat, blacklisted_chats,
        autoend_on, autoend_off, is_autoend,
        maintenance_on, maintenance_off, is_maintenance,
        get_active_chats, get_active_video_chats,
        remove_active_chat, remove_active_video_chat
    )

    SYSTEM_READY = True
    print("✅ TitanOS Web: Engine Connected (DB, Call, Config, Admin Systems).")

except Exception as e:
    print("⚠️ TitanOS Web: Running in degraded/standalone mode. Import error:", e)
    # keep SYSTEM_READY = False

# ------------------------------------------------------------------------------
# [4] Server Initialization
# ------------------------------------------------------------------------------
app = FastAPI(title="TitanOS Ultimate", docs_url=None, redoc_url=None)
app.add_middleware(SessionMiddleware, secret_key=os.environ.get("TITAN_SECRET", "TITAN_GOD_KEY_2026"))
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

templates = Jinja2Templates(directory=BASE_DIR)

# Ensure folders
for folder in [DOWNLOADS_DIR, CACHE_DIR, RAW_FILES_DIR]:
    os.makedirs(folder, exist_ok=True)

# Mount static & downloads
if os.path.exists(DOWNLOADS_DIR):
    app.mount("/downloads", StaticFiles(directory=DOWNLOADS_DIR), name="downloads")
# optionally serve a static folder if exists
STATIC_DIR = os.path.join(BASE_DIR, "static")
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# ------------------------------------------------------------------------------
# [5] Utilities: safe call/get helpers (handles sync/async/method/property)
# ------------------------------------------------------------------------------
def _is_awaitable(obj: Any) -> bool:
    return asyncio.iscoroutine(obj) or inspect.isawaitable(obj)

async def safe_call(target: Any, attr: str, *args, **kwargs):
    """Try to call attribute `attr` on target. Supports sync/async functions and properties."""
    if not target:
        return None
    try:
        fn = getattr(target, attr, None)
        if fn is None:
            # maybe target is a class with classmethod/attribute
            return None
        # if it's a callable
        if callable(fn):
            result = fn(*args, **kwargs)
            if _is_awaitable(result):
                return await result
            return result
        # if not callable, just return the value
        return fn
    except Exception as e:
        # don't raise to keep endpoints resilient
        logging.debug(f"safe_call error on {attr}: {e}\n{traceback.format_exc()}")
        return None

async def safe_get_active_calls():
    """
    Obtain list of active call chat ids in a resilient way:
    - Try CallClient.active_calls property
    - Try CallClient.get_active_calls() method
    - Fallback to QueueDB keys or get_active_video_chats DB helper
    """
    try:
        # 1) direct attribute
        if CallClient:
            ac = getattr(CallClient, "active_calls", None)
            if ac:
                # If callable, call it
                if callable(ac):
                    res = ac()
                    if _is_awaitable(res):
                        res = await res
                    return list(res)
                # list-like
                return list(ac)
            # 2) try method names commonly used
            for method in ("get_active_calls", "active", "list_active_calls"):
                if hasattr(CallClient, method):
                    res = getattr(CallClient, method)()
                    if _is_awaitable(res):
                        res = await res
                    return list(res or [])
        # 3) database helper
        if SYSTEM_READY:
            try:
                res = await get_active_video_chats()
                return list(res or [])
            except:
                pass
        # 4) fallback from QueueDB
        if isinstance(QueueDB, dict):
            return [int(k) for k in QueueDB.keys() if str(k).isdigit()]
    except Exception as e:
        logging.debug("safe_get_active_calls error: %s", e)
    return []

def json_response(data, status_code=200):
    return JSONResponse(content=data, status_code=status_code)

# ------------------------------------------------------------------------------
# [6] Streaming Engine (Range support)
# ------------------------------------------------------------------------------
def get_current_media_path(chat_id):
    """Retrieves the file path playing in a specific chat"""
    if SYSTEM_READY:
        try:
            cid = int(chat_id)
            # QueueDB may be dict-like with chat_id keys
            if isinstance(QueueDB, dict) and cid in QueueDB and QueueDB[cid]:
                first = QueueDB[cid][0]
                if isinstance(first, dict) and first.get("file"):
                    return first.get("file")
        except Exception:
            pass

    # fallback to last downloaded mp4
    try:
        files = [os.path.join(DOWNLOADS_DIR, f) for f in os.listdir(DOWNLOADS_DIR) if f.lower().endswith(('.mp4', '.webm', '.mkv'))]
        if files:
            return max(files, key=os.path.getctime)
    except Exception:
        pass
    return None

def chunk_generator(file_path, start, end):
    """Reads file in chunks for smooth streaming"""
    with open(file_path, "rb") as f:
        f.seek(start)
        remaining = end - start + 1
        chunk_size = 1024 * 1024  # 1 MB
        while remaining > 0:
            read_size = min(chunk_size, remaining)
            data = f.read(read_size)
            if not data:
                break
            remaining -= len(data)
            yield data

@app.get("/stream/live/{chat_id}")
async def stream_media(chat_id: str, request: Request):
    """Live Video Stream Endpoint with Range support"""
    file_path = get_current_media_path(chat_id)
    if not file_path or not os.path.exists(file_path):
        return Response("No Active Stream / File Not Found", status_code=404)
    file_size = os.path.getsize(file_path)
    range_header = request.headers.get("range")
    if range_header:
        # parse "bytes=start-end"
        try:
            bytes_range = range_header.strip().split("=")[-1]
            start_str, end_str = bytes_range.split("-")
            start = int(start_str) if start_str else 0
            end = int(end_str) if end_str else file_size - 1
            end = min(end, file_size - 1)
            length = end - start + 1
            headers = {
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(length),
                "Content-Type": "video/mp4",
            }
            return StreamingResponse(chunk_generator(file_path, start, end), status_code=206, headers=headers)
        except Exception:
            # fallback to full file
            return FileResponse(file_path)
    # no range requested -> full file
    return FileResponse(file_path)

# ==============================================================================
# [7] API: Player Control & Info
# ==============================================================================
@app.get("/api/player/active_calls")
async def get_active_calls_api():
    """Returns list of active chats with metadata"""
    chats = []
    try:
        active_ids = await safe_get_active_calls()
        for cid in active_ids:
            try:
                name = str(cid)
                cover = "https://telegra.ph/file/5eb6df308e92f4477813d.jpg"
                # prefer QueueDB info if available
                if isinstance(QueueDB, dict) and cid in QueueDB and QueueDB[cid]:
                    data = QueueDB[cid][0]
                    name = data.get("title", name)[:80]
                    cover = data.get("thumb", cover)
                else:
                    # try BotClient.get_chat
                    chat = await safe_call(BotClient, "get_chat", cid)
                    if chat and getattr(chat, "title", None):
                        name = chat.title
                chats.append({"chat_id": str(cid), "name": name, "cover": cover})
            except Exception:
                continue
    except Exception:
        pass

    if not chats:
        chats = [{"chat_id": "0", "name": "System Idle", "cover": ""}]
    return json_response({"chats": chats})

@app.get("/api/player/track_info/{chat_id}")
async def get_track_info_api(chat_id: str):
    """Returns detailed info for UI Card"""
    info = {"title": "Titan OS", "artist": "Idle", "cover": "", "duration": "00:00", "is_playing": False, "stream_url": ""}
    try:
        cid = int(chat_id)
        # try QueueDB
        if isinstance(QueueDB, dict) and cid in QueueDB and QueueDB[cid]:
            t = QueueDB[cid][0]
            info = {
                "title": t.get("title", "Unknown")[:200],
                "artist": t.get("by", "Unknown")[:80],
                "cover": t.get("thumb", ""),
                "duration": t.get("dur", "Live"),
                "is_playing": True,
                "stream_url": f"/stream/live/{cid}",
                "ping": await safe_call(CallClient, "ping") if CallClient else None,
                "players": t.get("players") if isinstance(t, dict) else None,
            }
        else:
            # not playing, but maybe active call exists
            active = await safe_get_active_calls()
            if cid in active:
                info["is_playing"] = True
                info["stream_url"] = f"/stream/live/{cid}"
    except Exception:
        pass
    return json_response(info)

async def _get_cmd_and_cid(request: Request, form_data=None):
    """
    Helper to extract cmd & chat_id from form or JSON.
    Returns (cmd, cid) or (None, None).
    """
    cmd = None
    chat_id = None
    if form_data:
        cmd = form_data.get("cmd") or form_data.get("command") or form_data.get("action")
        chat_id = form_data.get("chat_id") or form_data.get("cid")
    else:
        # try json
        try:
            body = await request.json()
            cmd = body.get("cmd") or body.get("command") or body.get("action")
            chat_id = body.get("chat_id") or body.get("cid")
        except Exception:
            # fallback to form parsing
            try:
                data = await request.form()
                cmd = data.get("cmd") or data.get("command") or data.get("action")
                chat_id = data.get("chat_id") or data.get("cid")
            except Exception:
                pass
    return cmd, chat_id

@app.post("/api/player/control")
async def player_control_api(request: Request):
    """Controls: Pause, Resume, Skip, Stop, Focus"""
    # auth check
    if not request.session.get("user"):
        return json_response({"error": "Auth Required"}, 401)
    if not SYSTEM_READY:
        return json_response({"error": "Offline"}, 503)

    form = None
    try:
        form = await request.form()
    except Exception:
        pass
    cmd, chat_id = await _get_cmd_and_cid(request, form)

    if not cmd or not chat_id:
        return json_response({"error": "Missing cmd or chat_id"}, 400)

    try:
        cid = int(chat_id)
    except:
        return json_response({"error": "Invalid chat_id"}, 400)

    try:
        # map commands to callclient methods (try safe_call)
        if cmd in ("pause", "pause_stream"):
            res = await safe_call(CallClient, "pause_stream", cid)
        elif cmd in ("resume", "resume_stream"):
            res = await safe_call(CallClient, "resume_stream", cid)
        elif cmd in ("skip", "stop_stream"):
            # stop current stream and maybe play next in queue
            res = await safe_call(CallClient, "stop_stream", cid)
        elif cmd == "force_stop" or cmd == "force_stop_stream" or cmd == "stop":
            res = await safe_call(CallClient, "force_stop_stream", cid)
        elif cmd == "focus":
            # set focus chat id if supported
            try:
                setattr(CallClient, "turbo_chat_id", cid)
                res = {"focused": cid}
            except:
                res = await safe_call(CallClient, "focus_chat", cid)
        else:
            return json_response({"error": "Unknown command"}, 400)

        return json_response({"status": "Success", "command": cmd, "result": bool(res)})
    except Exception as e:
        logging.exception("player_control_api error")
        return json_response({"error": str(e)}, 500)

@app.post("/api/player/play_custom")
async def play_custom_api(request: Request):
    """Play a song by ID/Link directly (search & join)"""
    if not request.session.get("user"):
        return json_response({"error": "Auth Required"}, 401)
    if not SYSTEM_READY:
        return json_response({"error": "System Offline"}, 503)

    # accept form or json
    try:
        form = await request.form()
        chat_id = form.get("chat_id") or form.get("cid")
        query = form.get("query") or form.get("q")
    except Exception:
        try:
            body = await request.json()
            chat_id = body.get("chat_id") or body.get("cid")
            query = body.get("query") or body.get("q")
        except Exception:
            chat_id = None
            query = None

    if not chat_id or not query:
        return json_response({"error": "Missing chat_id or query"}, 400)

    try:
        cid = int(chat_id)
    except:
        return json_response({"error": "Invalid chat_id"}, 400)

    try:
        # Search via youtube helper
        results = await safe_call(YouTubeHelper, "search", query, limit=1) if YouTubeHelper else None
        if not results:
            return json_response({"error": "No results found"}, 404)
        link = results[0].get("link")
        title = results[0].get("title")
        # join call and play (video=True if youtube)
        await safe_call(CallClient, "join_call", chat_id=cid, original_chat_id=cid, link=link, video=True)
        return json_response({"status": "success", "msg": f"Playing: {title}", "chat_id": cid})
    except Exception as e:
        logging.exception("play_custom_api error")
        return json_response({"error": str(e)}, 500)

# ==============================================================================
# [8] API: Security & Moderation
# ==============================================================================
@app.post("/api/security/block_user")
async def block_user_api(request: Request):
    if not SYSTEM_READY:
        return json_response({"error": "Offline"}, 503)
    if not request.session.get("user"):
        return json_response({"error": "Auth Required"}, 401)
    try:
        form = await request.form()
        user_id = form.get("user_id") or form.get("id")
        action = form.get("action")
    except Exception:
        data = await request.json()
        user_id = data.get("user_id")
        action = data.get("action")
    try:
        uid = int(user_id)
    except:
        return json_response({"error": "Invalid user id"}, 400)
    try:
        if action == "enable":
            await add_gban_user(uid)
            BANNED_USERS.add(uid)
            return json_response({"status": "User Blocked", "id": uid})
        elif action == "disable":
            await remove_gban_user(uid)
            if uid in BANNED_USERS: BANNED_USERS.remove(uid)
            return json_response({"status": "User Unblocked", "id": uid})
        return json_response({"error": "Unknown action"}, 400)
    except Exception as e:
        logging.exception("block_user_api")
        return json_response({"error": str(e)}, 500)

@app.get("/api/security/blocked_users")
async def list_blocked_users():
    if not SYSTEM_READY:
        return json_response({"users": []})
    try:
        users = await get_banned_users()
        return json_response({"users": list(users)})
    except Exception:
        return json_response({"users": list(BANNED_USERS)})

@app.post("/api/security/blacklist_chat")
async def blacklist_chat_api(request: Request):
    if not SYSTEM_READY:
        return json_response({"error": "Offline"}, 503)
    if not request.session.get("user"):
        return json_response({"error": "Auth Required"}, 401)
    try:
        form = await request.form()
        chat_id = form.get("chat_id")
        action = form.get("action")
    except Exception:
        data = await request.json()
        chat_id = data.get("chat_id")
        action = data.get("action")
    try:
        cid = int(chat_id)
    except:
        return json_response({"error": "Invalid chat id"}, 400)
    try:
        if action == "enable":
            await blacklist_chat(cid)
            try:
                await safe_call(BotClient, "leave_chat", cid)
            except:
                pass
            return json_response({"status": "Chat Blacklisted", "id": cid})
        elif action == "disable":
            await whitelist_chat(cid)
            return json_response({"status": "Chat Whitelisted", "id": cid})
    except Exception as e:
        logging.exception("blacklist_chat_api")
        return json_response({"error": str(e)}, 500)

@app.get("/api/security/blacklisted_chats")
async def list_blacklisted_chats():
    if not SYSTEM_READY:
        return json_response({"chats": []})
    try:
        chats = await blacklisted_chats()
        return json_response({"chats": list(chats)})
    except Exception:
        return json_response({"chats": []})

# ==============================================================================
# [9] API: Settings & Status
# ==============================================================================
@app.post("/api/settings/maintenance")
async def toggle_maintenance(request: Request):
    if not SYSTEM_READY:
        return json_response({"error": "Offline"}, 503)
    if not request.session.get("user"):
        return json_response({"error": "Auth Required"}, 401)
    form = await request.form()
    action = form.get("action")
    try:
        if action == "enable":
            await maintenance_on()
            return json_response({"status": "Maintenance Mode ON 🔴"})
        else:
            await maintenance_off()
            return json_response({"status": "Maintenance Mode OFF 🟢"})
    except Exception as e:
        logging.exception("toggle_maintenance")
        return json_response({"error": str(e)}, 500)

@app.post("/api/settings/autoend")
async def toggle_autoend(request: Request):
    if not SYSTEM_READY:
        return json_response({"error": "Offline"}, 503)
    if not request.session.get("user"):
        return json_response({"error": "Auth Required"}, 401)
    form = await request.form()
    action = form.get("action")
    try:
        if action == "enable":
            await autoend_on()
            return json_response({"status": "AutoEnd ON 🟢"})
        else:
            await autoend_off()
            return json_response({"status": "AutoEnd OFF 🔴"})
    except Exception as e:
        logging.exception("toggle_autoend")
        return json_response({"error": str(e)}, 500)

@app.get("/api/settings/status")
async def get_system_status():
    if not SYSTEM_READY:
        return json_response({"maintenance": False, "autoend": False, "ping": 0, "ram": psutil.virtual_memory().percent, "cpu": psutil.cpu_percent()})
    try:
        m_status = await is_maintenance()
        a_status = await is_autoend()
    except Exception:
        m_status = False
        a_status = False
    pytgping = None
    try:
        pytgping = await safe_call(CallClient, "ping")
    except:
        pytgping = None
    return json_response({
        "maintenance": m_status,
        "autoend": a_status,
        "ping": pytgping or 0,
        "ram": psutil.virtual_memory().percent,
        "cpu": psutil.cpu_percent()
    })

# ==============================================================================
# [10] API: Utilities & Actions
# ==============================================================================
@app.post("/api/utils/turbo")
async def turbo_clean(request: Request):
    if not request.session.get("user"): return json_response({"error": "Auth Required"}, 401)
    deleted_files = 0
    cleaned_size = 0
    folders = [DOWNLOADS_DIR, CACHE_DIR, RAW_FILES_DIR]
    for folder in folders:
        if os.path.exists(folder):
            for f in os.listdir(folder):
                fp = os.path.join(folder, f)
                try:
                    cleaned_size += os.path.getsize(fp)
                    os.remove(fp)
                    deleted_files += 1
                except:
                    pass
    # clean pycache
    for root, dirs, files in os.walk(ROOT_DIR):
        for d in dirs:
            if d == "__pycache__":
                try:
                    shutil.rmtree(os.path.join(root, d))
                except:
                    pass
    gc.collect()
    return json_response({
        "status": "Turbo Executed 🚀",
        "files_removed": deleted_files,
        "space_freed_mb": f"{cleaned_size / (1024*1024):.2f} MB"
    })

@app.get("/api/utils/logs")
async def download_logs(request: Request):
    if not request.session.get("user"): return json_response({"error": "Auth Required"}, 401)
    if os.path.exists(LOG_FILE):
        return FileResponse(LOG_FILE, filename="log.txt")
    return json_response({"error": "No Log File Found"}, 404)

async def restart_process():
    await asyncio.sleep(2)
    os.execv(sys.executable, [sys.executable, "-m", "AnnieXMedia"])

async def update_process():
    try:
        if Config and getattr(Config, "UPSTREAM_BRANCH", None):
            os.system(f"git fetch origin {Config.UPSTREAM_BRANCH} &> /dev/null")
        os.system("git pull")
        await restart_process()
    except Exception as e:
        print(f"Update Failed: {e}")

@app.post("/api/utils/action")
async def system_action(request: Request, background_tasks: BackgroundTasks):
    if not request.session.get("user"): return json_response({"error": "Auth Required"}, 401)
    form = await request.form()
    action = form.get("action")
    if action == "restart":
        background_tasks.add_task(restart_process)
        return json_response({"status": "Restarting System... Please wait 15s"})
    elif action == "update":
        background_tasks.add_task(update_process)
        return json_response({"status": "Updating from Git & Restarting..."})
    return json_response({"error": "Unknown Action"}, 400)

@app.get("/api/utils/cache_list")
async def list_cache_files(request: Request):
    if not request.session.get("user"): return json_response({"error": "Auth Required"}, 401)
    files_list = []
    total_size = 0.0
    if os.path.exists(DOWNLOADS_DIR):
        for f in os.listdir(DOWNLOADS_DIR):
            fp = os.path.join(DOWNLOADS_DIR, f)
            try:
                size = os.path.getsize(fp) / (1024 * 1024)
                total_size += size
                files_list.append({"name": f, "size": f"{size:.2f} MB"})
            except:
                pass
    return json_response({
        "files": files_list,
        "total_count": len(files_list),
        "total_size_mb": f"{total_size:.2f} MB"
    })

# ==============================================================================
# [11] Frontend Routes (Templates)
# ==============================================================================
@app.get("/", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    if not request.session.get("user"):
        return RedirectResponse("/login")
    tpl = os.path.join(BASE_DIR, "dashboard.html")
    if os.path.exists(tpl):
        return templates.TemplateResponse("dashboard.html", {"request": request})
    # fallback message
    return HTMLResponse("<h1>TitanOS Kernel Active. Dashboard template not found.</h1>", 200)

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    tpl = os.path.join(BASE_DIR, "login.html")
    if os.path.exists(tpl):
        return templates.TemplateResponse("login.html", {"request": request})
    return HTMLResponse("<h1>Login Required</h1>", 200)

@app.post("/login")
async def perform_login(request: Request, username: str = Form(...), password: str = Form(...)):
    # NOTE: keep your credentials safe; replace with proper auth in production
    if username == "Abdallah" and password == "asdfghjkl05896":
        request.session["user"] = {"name": "Root", "username": username}
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid Credentials"})

@app.get("/logout")
async def perform_logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login")

# ==============================================================================
# [12] Startup helper & server runner
# ==============================================================================
@app.on_event("startup")
async def on_startup():
    print("🔌 TitanOS Web: Startup event - checking components...")
    print(" - SYSTEM_READY:", SYSTEM_READY)
    print(" - BotClient:", bool(BotClient))
    print(" - CallClient:", bool(CallClient))
    # Optionally you can attempt to start BotClient here if desired, but avoid auto-start to prevent double-run.

def start_server():
    """Starts the Uvicorn Server in a Thread"""
    t = Thread(target=uvicorn.run, args=(app,), kwargs={"host":"0.0.0.0", "port":8080, "log_level":"info"})
    t.daemon = True
    t.start()
    print("🚀 TitanOS Ultimate Kernel: Web Server Started on Port 8080")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
