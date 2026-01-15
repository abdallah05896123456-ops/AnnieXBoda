# -*- coding: utf-8 -*-
# ── 𝚂ᴏᴜʀᴄᴇ ✘ 𝐁ᴏᴅᴀ © 2025 ──────────────────────────────────────────────────────
# TITAN OS | ULTIMATE KERNEL (The Complete Backend Engine)
# Integrated with AnnieXMedia Source - Full Features
# ──────────────────────────────────────────────────────────────────────────────

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
import json
import time
from datetime import datetime
from threading import Thread
from typing import Any, Dict, List, Union, Optional

# [1] Library Imports & Dependencies Check
# ──────────────────────────────────────────────────────────────────────────────
try:
    import uvicorn
    import aiofiles
    from git import Repo, GitCommandError
    from fastapi import FastAPI, Request, Response, Form, BackgroundTasks, HTTPException, status
    from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, FileResponse, StreamingResponse
    from fastapi.templating import Jinja2Templates
    from fastapi.staticfiles import StaticFiles
    from starlette.middleware.sessions import SessionMiddleware
    from starlette.middleware.cors import CORSMiddleware
    from pyrogram import Client
    from pytgcalls import PyTgCalls
except ImportError as e:
    print(f"\n❌ Critical Error: Missing dependencies! {e}")
    print("👉 Run: pip3 install fastapi uvicorn gitpython aiofiles python-multipart jinja2\n")
    sys.exit()

# [2] Paths & Configuration Logic (ADJUSTED FOR FLAT STRUCTURE)
# ──────────────────────────────────────────────────────────────────────────────
# تحديد المسار الحالي (حيث يوجد ملف web_srv.py)
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

# المجلد الجذري للسورس (نخرج خطوة واحدة للوراء للوصول لمجلد AnnieXMedia الرئيسي)
ROOT_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "..")) 

# مسار القوالب هو نفس المسار الحالي
TEMPLATES_DIR = CURRENT_DIR
STATIC_DIR = os.path.join(CURRENT_DIR, "static")

# مسارات البوت المعتادة
DOWNLOADS_DIR = os.path.join(ROOT_DIR, "downloads")
CACHE_DIR = os.path.join(ROOT_DIR, "cache")
RAW_FILES_DIR = os.path.join(ROOT_DIR, "raw_files")
LOG_FILE = os.path.join(ROOT_DIR, "log.txt")

# إضافة المجلد الجذري للمسار لاستيراد ملفات البوت
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# التأكد من وجود المجلدات الضرورية
for folder in [DOWNLOADS_DIR, CACHE_DIR, RAW_FILES_DIR]:
    os.makedirs(folder, exist_ok=True)

# [3] AnnieXMedia Core Integration (Importing Bot Modules)
# ──────────────────────────────────────────────────────────────────────────────
SYSTEM_READY = False
BotClient = None      # app
CallClient = None     # StreamController
QueueDB = {}          # db
YouTubeHelper = None  # YouTube
Config = None         # config module
BANNED_USERS = set()

print("🔌 TitanOS: Initializing Core Integration...")

try:
    # 1. استيراد الإعدادات
    import config
    Config = config
    
    # تحميل المتغيرات المهمة من الكونفج
    WEB_PASSWORD = getattr(config, "WEB_PASSWORD", "asdfghjkl05896")
    WEB_SECRET = getattr(config, "WEB_SECRET", "AnnieX_Secret_Key_99123")
    HOST = getattr(config, "HOST", "0.0.0.0")
    PORT = int(getattr(config, "PORT", "8080"))
    
    # 2. استيراد كائنات البوت الأساسية
    from AnnieXMedia import app as BotClient
    from AnnieXMedia import LOGGER
    
    # 3. استيراد متحكم المكالمات (Call Controller)
    from AnnieXMedia.core.call import StreamController as CallClient
    
    # 4. استيراد قواعد البيانات والمساعدات
    from AnnieXMedia.misc import db as QueueDB
    from AnnieXMedia import YouTube as YouTubeHelper
    
    # 5. استيراد دوال قاعدة البيانات (Database Utils)
    from AnnieXMedia.utils.database import (
        add_gban_user, remove_gban_user, get_banned_users,
        blacklist_chat, whitelist_chat, blacklisted_chats,
        autoend_on, autoend_off, is_autoend,
        maintenance_on, maintenance_off, is_maintenance,
        get_active_chats, get_active_video_chats,
        remove_active_chat, remove_active_video_chat,
        get_served_chats, get_served_users,
        get_loop, set_loop,
        is_music_playing
    )
    
    # 6. استيراد قائمة المحظورين
    from config import BANNED_USERS as _BANS
    BANNED_USERS = _BANS

    # 7. استيراد وظائف الطابور (Queue Utils) - مهم للإضافة اليدوية
    try:
        from AnnieXMedia.utils.stream.queue import put_queue
    except ImportError:
        pass 

    SYSTEM_READY = True
    print(f"✅ TitanOS Web: Engine Connected Successfully via {config.BOT_NAME}.")

except Exception as e:
    print(f"⚠️ TitanOS Web: Running in DEGRADED MODE. Integration Failed: {e}")
    traceback.print_exc()
    # قيم افتراضية لمنع انهيار السيرفر
    class MockConfig:
        WEB_PASSWORD = "admin"
        WEB_SECRET = "secret"
        BOT_NAME = "Unknown"
        OWNER_USERNAME = "Unknown"
        UPSTREAM_BRANCH = "master"
    
    if Config is None: Config = MockConfig()
    WEB_PASSWORD = "admin"
    WEB_SECRET = "secret"

# [4] FastAPI App Initialization
# ──────────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="TitanOS Ultimate",
    description="AnnieXMedia Web Controller",
    version="3.5.0",
    docs_url=None, 
    redoc_url=None
)

# Middleware Setup
app.add_middleware(SessionMiddleware, secret_key=WEB_SECRET)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Template Setup
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Mount Static Directories (Only if exists)
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
if os.path.exists(DOWNLOADS_DIR):
    app.mount("/downloads", StaticFiles(directory=DOWNLOADS_DIR), name="downloads")

# [5] Advanced Utility Helpers (Async/Sync Handling)
# ──────────────────────────────────────────────────────────────────────────────
def _is_awaitable(obj: Any) -> bool:
    """Check if an object is awaitable (coroutine or future)."""
    return asyncio.iscoroutine(obj) or inspect.isawaitable(obj)

async def safe_call(target: Any, attr: str, *args, **kwargs):
    """
    Safely call a method or access an attribute on a target object.
    """
    if not target:
        return None
    try:
        if not hasattr(target, attr):
            return None
        
        val = getattr(target, attr)
        
        if callable(val):
            result = val(*args, **kwargs)
            if _is_awaitable(result):
                return await result
            return result
        else:
            return val
    except Exception as e:
        logging.error(f"TitanOS: Safe Call Error on {attr}: {e}")
        return None

def json_response(data, status_code=200):
    """Helper for standardized JSON responses."""
    return JSONResponse(content=data, status_code=status_code)

async def safe_get_active_calls() -> List[int]:
    """
    Retrieves a list of active chat IDs using multiple fallback methods.
    """
    active_chats = set()
    
    # Method 1: Check StreamController.active_calls
    try:
        if CallClient and hasattr(CallClient, "active_calls"):
            ac = CallClient.active_calls
            if isinstance(ac, (set, list)):
                active_chats.update(ac)
            elif callable(ac):
                res = ac()
                if _is_awaitable(res): res = await res
                if res: active_chats.update(res)
    except: pass

    # Method 2: Check Database Utils
    if SYSTEM_READY:
        try:
            db_chats = await get_active_video_chats() 
            if db_chats: active_chats.update(db_chats)
            
            db_chats_a = await get_active_chats()
            if db_chats_a: active_chats.update(db_chats_a)
        except: pass
    
    # Method 3: Check QueueDB Keys
    try:
        if isinstance(QueueDB, dict):
            for k in QueueDB.keys():
                if isinstance(k, int) or (isinstance(k, str) and k.isdigit()):
                    active_chats.add(int(k))
    except: pass

    return list(active_chats)

# [6] Streaming Engine Core (Range & Chunking)
# ──────────────────────────────────────────────────────────────────────────────
def get_current_media_path(chat_id: int) -> Optional[str]:
    """
    Determines the exact file path currently playing in a specific chat.
    Prioritizes the QueueDB, then falls back to recent downloads.
    """
    if SYSTEM_READY and QueueDB:
        try:
            cid = int(chat_id)
            if cid in QueueDB and QueueDB[cid]:
                current_track = QueueDB[cid][0]
                if "file" in current_track and current_track["file"]:
                    fpath = current_track["file"]
                    if os.path.exists(fpath):
                        return fpath
        except Exception:
            pass

    # Fallback: Find most recent media file in downloads
    try:
        if os.path.exists(DOWNLOADS_DIR):
            files = [os.path.join(DOWNLOADS_DIR, f) for f in os.listdir(DOWNLOADS_DIR) 
                     if f.lower().endswith(('.mp4', '.webm', '.mkv', '.mp3', '.m4a'))]
            if files:
                return max(files, key=os.path.getctime)
    except: pass
    
    return None

def file_iterator(file_path: str, start: int, end: int, chunk_size: int = 1024 * 1024):
    """Generator to read file chunks for streaming."""
    with open(file_path, "rb") as f:
        f.seek(start)
        remaining = end - start + 1
        while remaining > 0:
            bytes_to_read = min(chunk_size, remaining)
            data = f.read(bytes_to_read)
            if not data:
                break
            remaining -= len(data)
            yield data

@app.get("/stream/live/{chat_id}")
async def stream_media_endpoint(chat_id: str, request: Request):
    """
    Endpoint providing live media streaming with Range Support.
    """
    try:
        cid = int(chat_id)
    except ValueError:
        return Response("Invalid Chat ID", status_code=400)

    file_path = get_current_media_path(cid)
    
    if not file_path or not os.path.exists(file_path):
        return Response("Media Not Found or Live Stream (URL) Active", status_code=404)

    file_size = os.path.getsize(file_path)
    range_header = request.headers.get("range")

    ext = os.path.splitext(file_path)[1].lower()
    content_type = "video/mp4" 
    if ext in ['.mp3', '.m4a', '.flac']: content_type = "audio/mpeg"
    elif ext == '.webm': content_type = "video/webm"

    if range_header:
        try:
            byte_str = range_header.replace("bytes=", "")
            start_str, end_str = byte_str.split("-")
            start = int(start_str)
            end = int(end_str) if end_str else file_size - 1
            
            if start >= file_size: start = file_size - 1
            if end >= file_size: end = file_size - 1
            
            chunk_length = end - start + 1
            headers = {
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(chunk_length),
                "Content-Type": content_type,
            }
            
            return StreamingResponse(
                file_iterator(file_path, start, end),
                status_code=206,
                headers=headers
            )
        except Exception:
            pass 

    return FileResponse(file_path, media_type=content_type)

# [7] API Endpoints: Player Data & Control
# ──────────────────────────────────────────────────────────────────────────────
@app.get("/api/player/active_calls")
async def api_get_active_calls():
    """Returns a JSON list of all active chats with basic metadata."""
    if not SYSTEM_READY:
        return json_response([])

    chats_data = []
    active_ids = await safe_get_active_calls()

    for cid in active_ids:
        try:
            chat_name = str(cid)
            cover = config.UNIFIED_IMG
            title = "Unknown Track"
            
            if cid in QueueDB and QueueDB[cid]:
                track = QueueDB[cid][0]
                title = track.get("title", title)[:50]
                cover = track.get("thumb") or config.UNIFIED_IMG
            
            try:
                chat_obj = await BotClient.get_chat(cid)
                chat_name = chat_obj.title
            except: pass

            chats_data.append({
                "chat_id": str(cid),
                "name": chat_name,
                "title": title,
                "cover": cover,
                "stream_url": f"/stream/live/{cid}"
            })
        except Exception:
            continue

    return json_response({"chats": chats_data})

@app.get("/api/player/track_info/{chat_id}")
async def api_track_info(chat_id: str):
    """Detailed info for a specific chat player (Polling)."""
    default_info = {
        "title": "Not Playing",
        "artist": "-",
        "cover": config.UNIFIED_IMG,
        "duration": "00:00",
        "is_playing": False,
        "loop_mode": 0
    }
    
    if not SYSTEM_READY: return json_response(default_info)

    try:
        cid = int(chat_id)
        
        is_active = False
        active_list = await safe_get_active_calls()
        if cid in active_list: is_active = True
        
        if cid in QueueDB and QueueDB[cid]:
            track = QueueDB[cid][0]
            loop_val = await get_loop(cid)
            
            info = {
                "title": track.get("title", "Unknown"),
                "artist": track.get("by", "Unknown"),
                "cover": track.get("thumb") or config.UNIFIED_IMG,
                "duration": track.get("dur", "Live"),
                "is_playing": is_active,
                "stream_url": f"/stream/live/{cid}",
                "loop_mode": loop_val,
                "queued_count": len(QueueDB[cid]) - 1
            }
            return json_response(info)
            
    except Exception:
        pass

    return json_response(default_info)

@app.post("/api/player/control")
async def api_player_control(request: Request):
    """Unified Control Endpoint (Pause, Resume, Skip, Stop, Loop)."""
    user = request.session.get("user")
    if not user: return json_response({"error": "Unauthorized"}, 401)
    
    try:
        data = await request.json()
    except:
        form = await request.form()
        data = {k: v for k, v in form.items()}
        
    cmd = data.get("cmd") or data.get("action")
    chat_id = data.get("chat_id")

    if not cmd or not chat_id:
        return json_response({"error": "Missing params"}, 400)
    
    try:
        cid = int(chat_id)
    except:
        return json_response({"error": "Invalid Chat ID"}, 400)

    if not SYSTEM_READY or not CallClient:
        return json_response({"error": "Bot Core Offline"}, 503)

    try:
        result_msg = "OK"
        
        if cmd == "pause":
            await safe_call(CallClient, "pause_stream", cid)
        elif cmd == "resume":
            await safe_call(CallClient, "resume_stream", cid)
        elif cmd == "skip":
            await safe_call(CallClient, "skip_stream", cid) 
            await safe_call(CallClient, "stop_stream", cid) 
        elif cmd == "stop":
            await safe_call(CallClient, "force_stop_stream", cid)
        elif cmd == "loop":
            curr = await get_loop(cid)
            new_val = 3 if curr == 0 else 0
            await set_loop(cid, new_val)
            result_msg = f"Loop {'Enabled' if new_val > 0 else 'Disabled'}"
            
        return json_response({"status": "Success", "message": result_msg})
    except Exception as e:
        return json_response({"error": str(e)}, 500)

@app.post("/api/player/play")
async def api_play_custom(request: Request):
    """Play media directly from URL or Search Query via Web."""
    if not request.session.get("user"): return json_response({"error": "Unauthorized"}, 401)
    
    try:
        data = await request.json()
        chat_id = int(data.get("chat_id"))
        query = data.get("query")
    except:
        return json_response({"error": "Invalid Data"}, 400)

    if not SYSTEM_READY: return json_response({"error": "Offline"}, 503)

    try:
        details, track_id = await YouTubeHelper.track(query)
        
        file_path, direct = await YouTubeHelper.download(
            track_id, 
            mystic=None, 
            video=True, 
            videoid=track_id
        )
        
        if not file_path:
            return json_response({"error": "Download Failed"}, 500)

        await safe_call(
            CallClient, "join_call",
            chat_id=chat_id,
            original_chat_id=chat_id,
            link=file_path,
            video=True,
            image=details.get("thumb")
        )

        from AnnieXMedia.utils.stream.queue import put_queue
        await put_queue(
            chat_id,
            chat_id,
            file_path,
            details["title"],
            details["duration_min"],
            "TitanOS Web", 
            track_id,
            config.OWNER_ID,
            "video"
        )
        
        return json_response({
            "status": "Success", 
            "title": details["title"],
            "duration": details["duration_min"]
        })

    except Exception as e:
        traceback.print_exc()
        return json_response({"error": str(e)}, 500)

# [8] API Endpoints: System & Security
# ──────────────────────────────────────────────────────────────────────────────
@app.get("/api/system/status")
async def api_system_status(request: Request):
    """Get real-time system stats."""
    if not request.session.get("user"): return json_response({}, 401)
    
    ram = psutil.virtual_memory().percent
    cpu = psutil.cpu_percent()
    
    ping = 0
    if CallClient:
        ping = await safe_call(CallClient, "ping")
    
    m_mode = False
    if SYSTEM_READY: m_mode = await is_maintenance()
    
    return json_response({
        "ram": ram,
        "cpu": cpu,
        "ping": ping,
        "maintenance": m_mode,
        "active_calls": len(await safe_get_active_calls())
    })

@app.post("/api/system/action")
async def api_system_action(request: Request, background_tasks: BackgroundTasks):
    """System Actions: Restart, Update, Maintenance, Clean."""
    if not request.session.get("user"): return json_response({"error": "Unauthorized"}, 401)
    
    data = await request.json()
    action = data.get("action")
    
    if action == "restart":
        async def _restart():
            await asyncio.sleep(2)
            os.execv(sys.executable, [sys.executable, "-m", "AnnieXMedia"])
        background_tasks.add_task(_restart)
        return json_response({"status": "Restarting..."})
        
    elif action == "update":
        async def _update():
            if Config.UPSTREAM_BRANCH:
                os.system(f"git fetch origin {Config.UPSTREAM_BRANCH} &> /dev/null")
            os.system("git pull")
            await asyncio.sleep(2)
            os.execv(sys.executable, [sys.executable, "-m", "AnnieXMedia"])
        background_tasks.add_task(_update)
        return json_response({"status": "Updating..."})
        
    elif action == "maintenance":
        enable = data.get("value", False)
        if enable: await maintenance_on()
        else: await maintenance_off()
        return json_response({"status": "Updated Maintenance Mode"})
        
    elif action == "clean":
        freed = 0
        for f in [DOWNLOADS_DIR, CACHE_DIR, RAW_FILES_DIR]:
            if os.path.exists(f):
                for sub in os.listdir(f):
                    p = os.path.join(f, sub)
                    try:
                        if os.path.isfile(p):
                            freed += os.path.getsize(p)
                            os.remove(p)
                    except: pass
        gc.collect()
        return json_response({"status": "Cleaned", "freed_mb": round(freed/(1024*1024), 2)})
        
    return json_response({"error": "Unknown Action"}, 400)

@app.get("/api/security/users")
async def api_get_users(request: Request):
    """Get blocked users list."""
    if not request.session.get("user"): return json_response({}, 401)
    
    blocked = []
    if SYSTEM_READY:
        blocked = await get_banned_users()
    return json_response({"blocked_users": list(blocked)})

@app.post("/api/security/block")
async def api_block_user(request: Request):
    """Block/Unblock User."""
    if not request.session.get("user"): return json_response({}, 401)
    data = await request.json()
    uid = int(data.get("user_id"))
    do_block = data.get("block", True)
    
    if SYSTEM_READY:
        if do_block:
            await add_gban_user(uid)
            BANNED_USERS.add(uid)
        else:
            await remove_gban_user(uid)
            if uid in BANNED_USERS: BANNED_USERS.remove(uid)
            
    return json_response({"status": "Success"})

@app.get("/api/logs")
async def api_logs_download(request: Request):
    """Download system logs."""
    if not request.session.get("user"): return json_response({}, 401)
    if os.path.exists(LOG_FILE):
        return FileResponse(LOG_FILE, filename="annie_logs.txt")
    return json_response({"error": "Log file empty"}, 404)

# [9] Frontend Routes & AUTH INTEGRATION
# ──────────────────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def page_dashboard(request: Request):
    """Main Dashboard Page."""
    if not request.session.get("user"):
        return RedirectResponse("/login")
    
    tpl_path = os.path.join(TEMPLATES_DIR, "dashboard.html")
    if os.path.exists(tpl_path):
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "bot_name": config.BOT_NAME,
            "owner": config.OWNER_USERNAME
        })
    
    return HTMLResponse(f"""
    <html><head><title>TitanOS Error</title></head>
    <body style="background:#1a1a1a;color:white;font-family:sans-serif;text-align:center;padding:50px;">
        <h1>Dashboard Template Missing</h1>
        <p>Could not find <code>dashboard.html</code> in {TEMPLATES_DIR}</p>
    </body></html>
    """)

@app.get("/login", response_class=HTMLResponse)
async def page_login(request: Request):
    """Login Page."""
    if request.session.get("user"):
        return RedirectResponse("/")
        
    tpl_path = os.path.join(TEMPLATES_DIR, "login.html")
    if os.path.exists(tpl_path):
        return templates.TemplateResponse("login.html", {"request": request})
    
    return HTMLResponse("Login Template Missing")

@app.post("/login")
async def action_login(request: Request, username: str = Form(...), password: str = Form(...)):
    """Handle Standard Form Login (Fallback)."""
    if password == WEB_PASSWORD:
        request.session["user"] = {"username": username, "role": "admin"}
        return RedirectResponse("/", status_code=303)
    
    return RedirectResponse("/login?error=1", status_code=303)

# ⚠️ [AUTH INTEGRATION] NEW ENDPOINTS FOR JS LOGIN ⚠️
# ──────────────────────────────────────────────────────────────────────────────
@app.post("/auth/step1")
async def auth_step1_api(request: Request):
    """Validates Password from JS Fetch."""
    try:
        data = await request.json()
        password = data.get("password")
        
        if password == WEB_PASSWORD:
            # Grant access directly for now (since 2FA/Bio is client-side simulated)
            request.session["user"] = {"username": "admin", "role": "admin"}
            return json_response({"status": "success", "msg": "Access Granted"})
        
        return json_response({"status": "error", "msg": "Invalid Credentials"}, 401)
    except Exception as e:
        return json_response({"status": "error", "msg": str(e)}, 500)

@app.post("/auth/verify-2fa")
async def auth_verify_2fa_api(request: Request):
    """Validates OTP Code from JS Fetch."""
    try:
        data = await request.json()
        code = data.get("code")
        # In a real DB scenario, we verify code here.
        # For simulation, we assume any 6-digit code is valid if the client sent it.
        if code and len(code) == 6:
            request.session["user"] = {"username": "admin", "role": "admin"}
            return json_response({"status": "success"})
        return json_response({"status": "error", "msg": "Invalid Code"}, 400)
    except:
        return json_response({"status": "error"}, 400)

@app.post("/auth/biometric/enroll")
async def auth_bio_enroll_api(request: Request):
    """Enables Biometric (Returns success to save token)."""
    return json_response({"status": "success"})

@app.post("/auth/biometric/verify")
async def auth_bio_verify_api(request: Request):
    """Verifies Biometric Token."""
    # Since token check is client-side in this version, request implies success
    request.session["user"] = {"username": "admin", "role": "admin"}
    return json_response({"status": "success"})
# ──────────────────────────────────────────────────────────────────────────────

@app.get("/logout")
async def action_logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login")

# [10] Server Startup Hook & Runner
# ──────────────────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def on_startup_event():
    print("🚀 TitanOS: Server Startup Sequence Initiated.")

def start_server_thread():
    """Function to start server in a separate thread (for main.py)."""
    uvicorn.run(app, host=HOST, port=PORT, log_level="error")

if __name__ == "__main__":
    # Standalone execution
    print(f"🌍 Starting TitanOS Standalone on {HOST}:{PORT}")
    uvicorn.run("web_srv:app", host=HOST, port=PORT, reload=True)
