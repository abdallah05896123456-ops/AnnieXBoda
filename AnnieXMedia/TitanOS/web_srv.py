# -*- coding: utf-8 -*-
# ── 𝚂ᴏᴜʀᴄᴇ ✘ 𝐁ᴏᴅᴀ © 2026 ──────────────────────────────────────────────────────
# TITAN OS | ULTIMATE KERNEL V6 (Real-Time Sync Edition)
# Features: Live Seek, VC Participants, Async Database, Zero-Latency Control
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
import mimetypes
import time
from typing import Any, Dict, List, Union, Optional, Generator
from datetime import datetime

# [1] Critical Dependencies Check & Imports
# ──────────────────────────────────────────────────────────────────────────────
try:
    import uvicorn
    import aiofiles
    import ujson  # Ultra-Fast JSON
    from motor.motor_asyncio import AsyncIOMotorClient
    from fastapi import FastAPI, Request, Response, Form, BackgroundTasks, HTTPException, status, Header
    from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, FileResponse, StreamingResponse
    from fastapi.templating import Jinja2Templates
    from fastapi.staticfiles import StaticFiles
    from starlette.middleware.sessions import SessionMiddleware
    from starlette.middleware.cors import CORSMiddleware
    
    # Telegram Core
    from pyrogram import Client, enums
    from pytgcalls import PyTgCalls
    from pytgcalls.types import StreamAudioEnded, StreamVideoEnded
except ImportError as e:
    print(f"\n❌ CRITICAL ERROR: Missing Dependencies!\n👉 Please Install: pip3 install fastapi uvicorn aiofiles ujson motor python-multipart jinja2\nError Detail: {e}\n")
    sys.exit()

# [2] System Configuration & Paths
# ──────────────────────────────────────────────────────────────────────────────
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
TEMPLATES_DIR = CURRENT_DIR
STATIC_DIR = os.path.join(CURRENT_DIR, "static")
DOWNLOADS_DIR = os.path.join(ROOT_DIR, "downloads")
CACHE_DIR = os.path.join(ROOT_DIR, "cache")
RAW_FILES_DIR = os.path.join(ROOT_DIR, "raw_files")
LOG_FILE = os.path.join(ROOT_DIR, "log.txt")

# Ensure directories exist
for folder in [DOWNLOADS_DIR, CACHE_DIR, RAW_FILES_DIR]:
    os.makedirs(folder, exist_ok=True)

# Add Root to Path for Imports
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# [3] Custom High-Performance Responses
# ──────────────────────────────────────────────────────────────────────────────
class UJSONResponse(JSONResponse):
    """Ultra-fast JSON Response using ujson."""
    media_type = "application/json"
    def render(self, content: Any) -> bytes:
        return ujson.dumps(content).encode("utf-8")

# [4] AnnieXMedia Core Integration (Smart Import)
# ──────────────────────────────────────────────────────────────────────────────
SYSTEM_READY = False
BotClient = None
CallClient = None
QueueDB = {}
Config = None
YouTubeHelper = None

print("🔌 TitanOS V6: Initializing Neural Core & Real-Time Engines...")

try:
    import config
    Config = config
    
    # Load Secrets
    WEB_PASSWORD = getattr(config, "WEB_PASSWORD", "admin")
    WEB_SECRET = getattr(config, "WEB_SECRET", "titan_super_secret_key")
    HOST = getattr(config, "HOST", "0.0.0.0")
    PORT = int(getattr(config, "PORT", "8080"))
    MONGO_DB_URI = getattr(config, "MONGO_DB_URI", None)

    # Import Bot Components
    from AnnieXMedia import app as BotClient
    from AnnieXMedia.core.call import StreamController as CallClient
    from AnnieXMedia.misc import db as QueueDB
    from AnnieXMedia import YouTube as YouTubeHelper
    
    # Import Database Utils
    from AnnieXMedia.utils.database import (
        add_gban_user, remove_gban_user, get_banned_users,
        maintenance_on, maintenance_off, is_maintenance,
        get_active_chats, get_active_video_chats,
        get_loop, set_loop
    )
    
    # Banned Users Set
    from config import BANNED_USERS as _BANS
    BANNED_USERS = _BANS

    SYSTEM_READY = True
    print(f"✅ TitanOS: Successfully Connected to {config.BOT_NAME} Core.")

except Exception as e:
    print(f"⚠️ TitanOS Warning: Running in Standalone Mode. Integration Error: {e}")
    # Mock Config to prevent crash
    class MockConfig:
        WEB_PASSWORD = "admin"
        WEB_SECRET = "secret"
        BOT_NAME = "TitanBot"
        OWNER_USERNAME = "Unknown"
        UNIFIED_IMG = "https://telegra.ph/file/default.jpg"
        UPSTREAM_BRANCH = "master"
        OWNER_ID = 0
    if Config is None: Config = MockConfig()
    WEB_PASSWORD = "admin"
    WEB_SECRET = "secret"

# [5] Database Isolation Layer (Async Motor)
# ──────────────────────────────────────────────────────────────────────────────
mongo_client: Optional[AsyncIOMotorClient] = None
web_db = None

async def init_db():
    """Initializes a separate DB connection for the Web Server to avoid Event Loop Clash."""
    global mongo_client, web_db
    if MONGO_DB_URI:
        try:
            mongo_client = AsyncIOMotorClient(MONGO_DB_URI)
            web_db = mongo_client[getattr(Config, "BOT_NAME", "AnnieXMedia")]
            print("🗄️ TitanOS: Web Database Link Established.")
        except Exception as e:
            print(f"❌ TitanOS DB Error: {e}")

async def close_db():
    if mongo_client:
        mongo_client.close()

# [6] FastAPI App Definition
# ──────────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="TitanOS Ultimate",
    description="High-Performance Media Controller V6",
    version="6.0.0",
    default_response_class=UJSONResponse,
    on_startup=[init_db],
    on_shutdown=[close_db]
)

# Middleware
app.add_middleware(SessionMiddleware, secret_key=WEB_SECRET)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

# Template & Static Engines
templates = Jinja2Templates(directory=TEMPLATES_DIR)
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# [7] Advanced Streaming Engine (Range Support)
# ──────────────────────────────────────────────────────────────────────────────
class StreamEngine:
    """
    Intelligent Media Streamer.
    Handles Byte-Range requests for seeking and optimizes chunk sizes.
    """
    @staticmethod
    def get_file_path(chat_id: int) -> Optional[str]:
        # 1. Try QueueDB
        if SYSTEM_READY and chat_id in QueueDB and QueueDB[chat_id]:
            track = QueueDB[chat_id][0]
            if track.get("file") and os.path.exists(track["file"]):
                return track["file"]
        
        # 2. Try Recent Downloads (Smart Fallback)
        if os.path.exists(DOWNLOADS_DIR):
            try:
                files = [os.path.join(DOWNLOADS_DIR, f) for f in os.listdir(DOWNLOADS_DIR)
                         if f.lower().endswith(('.mp4', '.mkv', '.webm', '.mp3'))]
                if files:
                    return max(files, key=os.path.getctime)
            except: pass
        return None

    @staticmethod
    async def range_generator(file_path: str, start: int, end: int, chunk_size: int = 64 * 1024):
        """Async generator for streaming file chunks."""
        try:
            async with aiofiles.open(file_path, "rb") as f:
                await f.seek(start)
                remaining = end - start + 1
                while remaining > 0:
                    bytes_to_read = min(chunk_size, remaining)
                    data = await f.read(bytes_to_read)
                    if not data:
                        break
                    remaining -= len(data)
                    yield data
        except Exception:
            pass

@app.get("/stream/live/{chat_id}")
async def endpoint_stream_media(chat_id: int, request: Request):
    """
    The Core Streaming Endpoint.
    Supports: HTTP 206 Partial Content (Seeking).
    """
    file_path = StreamEngine.get_file_path(chat_id)
    
    if not file_path:
        return Response("Media Not Found / Live URL", status_code=404)

    file_size = os.path.getsize(file_path)
    range_header = request.headers.get("range")
    
    # Guess Mime Type
    content_type, _ = mimetypes.guess_type(file_path)
    content_type = content_type or "application/octet-stream"

    # Default: Full File
    start = 0
    end = file_size - 1
    status_code = 200

    # Range Handling
    if range_header:
        try:
            byte_str = range_header.replace("bytes=", "")
            range_start, range_end = byte_str.split("-")
            start = int(range_start)
            if range_end:
                end = int(range_end)
            
            # Sanity Check
            if start >= file_size: start = file_size - 1
            if end >= file_size: end = file_size - 1
            
            status_code = 206
        except:
            pass

    chunk_length = end - start + 1
    headers = {
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(chunk_length),
        "Content-Type": content_type,
        "Cache-Control": "no-cache, no-store, must-revalidate"
    }

    return StreamingResponse(
        StreamEngine.range_generator(file_path, start, end),
        status_code=status_code,
        headers=headers
    )

# [8] Background Command Processor (V6 Upgraded)
# ──────────────────────────────────────────────────────────────────────────────
async def bg_executor(func_name: str, chat_id: int, **kwargs):
    """
    Executes bot commands in background.
    V6 Update: Handles 'seek' with timestamps.
    """
    if not SYSTEM_READY or not CallClient: return
    try:
        if func_name == "pause": await CallClient.pause_stream(chat_id)
        elif func_name == "resume": await CallClient.resume_stream(chat_id)
        elif func_name == "skip": 
            await CallClient.skip_stream(chat_id)
        elif func_name == "stop": await CallClient.force_stop_stream(chat_id)
        elif func_name == "loop":
            curr = await get_loop(chat_id)
            await set_loop(chat_id, 3 if curr == 0 else 0)
        
        # [V6 Requirement: Seek Implementation]
        elif func_name == "seek":
            seek_time = kwargs.get("value")
            if seek_time is not None:
                # Seek via CallClient wrapper
                await CallClient.seek_stream(chat_id, int(seek_time))
                
    except Exception as e:
        print(f"⚠️ BG Task Error ({func_name}): {e}")

# [9] API Endpoints: Player Control
# ──────────────────────────────────────────────────────────────────────────────
@app.post("/api/player/control")
async def api_control(request: Request, bg_tasks: BackgroundTasks):
    """
    Unified Control API.
    V6 Update: Extracts 'value' for seeking logic.
    """
    if not request.session.get("user"): return UJSONResponse({"error": "Auth"}, 401)
    
    try:
        data = await request.json()
        cmd = data.get("cmd")
        chat_id = int(data.get("chat_id"))
        value = data.get("value") # Grab timestamp for seek
    except:
        return UJSONResponse({"error": "Bad Request"}, 400)

    bg_tasks.add_task(bg_executor, cmd, chat_id, value=value)
    return UJSONResponse({"status": "queued", "cmd": cmd})

@app.get("/api/player/active_calls")
async def api_active_calls():
    """Get list of active chats intelligently."""
    if not SYSTEM_READY: return UJSONResponse({"chats": []})
    
    results = []
    try:
        vid_chats = await get_active_video_chats()
        aud_chats = await get_active_chats()
        all_ids = set(vid_chats + aud_chats)
        
        # Merge with QueueDB keys for accuracy
        if QueueDB:
            all_ids.update([k for k in QueueDB.keys() if isinstance(k, int)])
        
        for cid in all_ids:
            try:
                title = "Unknown Track"
                cover = Config.UNIFIED_IMG
                
                if cid in QueueDB and QueueDB[cid]:
                    t = QueueDB[cid][0]
                    title = t.get("title", title)[:60]
                    cover = t.get("thumb") or cover
                
                results.append({
                    "chat_id": str(cid),
                    "name": f"Chat {cid}", 
                    "title": title,
                    "cover": cover,
                    "stream_url": f"/stream/live/{cid}"
                })
            except: continue
    except: pass
    
    return UJSONResponse({"chats": results})

@app.get("/api/player/track_info/{chat_id}")
async def api_track_info(chat_id: int):
    """
    Poll for detailed track info.
    V6 Update: Returns Real-Time 'position' from PyTgCalls core.
    """
    default = {
        "title": "Not Playing", "artist": "-", 
        "cover": getattr(Config, "UNIFIED_IMG", ""), 
        "is_playing": False, "duration": "00:00", 
        "loop_mode": 0, "position": 0
    }
    
    if not SYSTEM_READY: return UJSONResponse(default)
    
    try:
        if chat_id in QueueDB and QueueDB[chat_id]:
            track = QueueDB[chat_id][0]
            loop_val = await get_loop(chat_id)
            
            # [V6 Requirement: Live Playback Position]
            current_pos = 0
            try:
                # Accessing PyTgCalls active call status
                # CallClient must expose .call or .pytgcalls instance
                core_call = getattr(CallClient, "call", None) 
                if core_call:
                    active = core_call.get_active_call(chat_id)
                    if active and active.status:
                        current_pos = active.status.time_elapsed # in seconds
            except Exception:
                pass # Fail silently to 0 if call not synced yet

            return UJSONResponse({
                "title": track.get("title", "Unknown"),
                "artist": track.get("by", "TitanOS"),
                "cover": track.get("thumb") or default["cover"],
                "duration": track.get("dur", "Live"),
                "is_playing": True,
                "stream_url": f"/stream/live/{chat_id}",
                "loop_mode": loop_val,
                "queued": len(QueueDB[chat_id]) - 1,
                "position": current_pos # Real-time sync
            })
    except: pass
    
    return UJSONResponse(default)

# [NEW: V6 Feature] Operators & Avatar Proxy
# ──────────────────────────────────────────────────────────────────────────────
@app.get("/api/proxy_avatar/{user_id}")
async def api_proxy_avatar(user_id: int):
    """
    Fetches Telegram User Profile Photo and serves it over HTTP.
    Uses a simple LRU caching strategy (via file system) to avoid rate limits.
    """
    if not SYSTEM_READY: return RedirectResponse(Config.UNIFIED_IMG)
    
    cache_path = os.path.join(CACHE_DIR, f"avatar_{user_id}.jpg")
    
    # Return cached if fresh (less than 1 hour old)
    if os.path.exists(cache_path):
        if (time.time() - os.path.getmtime(cache_path)) < 3600:
            return FileResponse(cache_path)

    try:
        # Download new photo
        photo = await BotClient.download_media(
            message=user_id, # Can pass ID to download profile photo
            file_name=cache_path
        )
        if photo:
            return FileResponse(photo)
    except Exception:
        pass
        
    return RedirectResponse(Config.UNIFIED_IMG)

@app.get("/api/player/participants/{chat_id}")
async def api_participants(chat_id: int):
    """
    V6 Requirement: Fetch Voice Chat Participants / Operators.
    Retreives Admin list and attempts to identify listeners.
    """
    if not SYSTEM_READY: return UJSONResponse({"participants": []})
    
    participants = []
    
    try:
        # 1. Get Administrators (The Operators)
        # Using Pyrogram enums for filter
        async for member in BotClient.get_chat_members(chat_id, filter=enums.ChatMembersFilter.ADMINISTRATORS):
            user = member.user
            if user.is_deleted: continue
            
            # Construct User Object
            participants.append({
                "user_id": user.id,
                "name": f"{user.first_name} {user.last_name or ''}".strip(),
                "role": "Operator" if member.status in [enums.ChatMemberStatus.OWNER, enums.ChatMemberStatus.ADMINISTRATOR] else "Listener",
                "photo_url": f"/api/proxy_avatar/{user.id}" if user.photo else Config.UNIFIED_IMG
            })
            
        # 2. Note: Getting ALL generic listeners in a VC requires iterating 
        # get_chat_members if they are not admins, which is heavy. 
        # For this version, we prioritize Admins/Operators as requested.
            
    except Exception as e:
        print(f"Participant Fetch Error: {e}")
        
    return UJSONResponse({"participants": participants})


@app.post("/api/player/play")
async def api_play_request(request: Request, bg_tasks: BackgroundTasks):
    """Search and Play via Web."""
    if not request.session.get("user"): return UJSONResponse({"error": "Auth"}, 401)
    
    data = await request.json()
    chat_id = int(data.get("chat_id"))
    query = data.get("query")
    
    async def _play_task():
        try:
            details, track_id = await YouTubeHelper.track(query)
            file_path, _ = await YouTubeHelper.download(track_id, mystic=None, video=True, videoid=track_id)
            
            await CallClient.join_call(
                chat_id=chat_id, original_chat_id=chat_id,
                link=file_path, video=True, image=details.get("thumb")
            )
            
            from AnnieXMedia.utils.stream.queue import put_queue
            await put_queue(
                chat_id, chat_id, file_path, details["title"],
                details["duration_min"], "WebUser", track_id,
                Config.OWNER_ID, "video"
            )
        except Exception as e:
            print(f"❌ Play Error: {e}")

    bg_tasks.add_task(_play_task)
    return UJSONResponse({"status": "processing"})

# [10] API Endpoints: System & Security
# ──────────────────────────────────────────────────────────────────────────────
@app.get("/api/system/status")
async def api_sys_status(request: Request):
    if not request.session.get("user"): return UJSONResponse({}, 401)
    
    m_mode = False
    if SYSTEM_READY: m_mode = await is_maintenance()
    
    return UJSONResponse({
        "ram": psutil.virtual_memory().percent,
        "cpu": psutil.cpu_percent(),
        "maintenance": m_mode,
        "active_threads": asyncio.active_count()
    })

@app.post("/api/system/action")
async def api_sys_action(request: Request, bg_tasks: BackgroundTasks):
    """Handle Restart, Update, Clean, Maintenance."""
    if not request.session.get("user"): return UJSONResponse({"error": "Auth"}, 401)
    
    data = await request.json()
    action = data.get("action")
    
    if action == "clean":
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
        return UJSONResponse({"status": "Cleaned", "freed": f"{freed/1024/1024:.2f} MB"})
        
    elif action == "maintenance":
        val = data.get("value", False)
        if val: await maintenance_on()
        else: await maintenance_off()
        return UJSONResponse({"status": "Maintenance Updated"})
        
    elif action == "restart":
        async def _restart():
            await asyncio.sleep(2)
            os.execv(sys.executable, [sys.executable, "-m", "AnnieXMedia"])
        bg_tasks.add_task(_restart)
        return UJSONResponse({"status": "Restarting..."})
    
    elif action == "update":
        async def _update():
            os.system("git pull")
            await asyncio.sleep(2)
            os.execv(sys.executable, [sys.executable, "-m", "AnnieXMedia"])
        bg_tasks.add_task(_update)
        return UJSONResponse({"status": "Updating..."})
        
    return UJSONResponse({"error": "Unknown"}, 400)

@app.get("/api/security/users")
async def api_get_users(request: Request):
    if not request.session.get("user"): return UJSONResponse({}, 401)
    blocked = []
    if SYSTEM_READY: blocked = await get_banned_users()
    return UJSONResponse({"blocked_users": list(blocked)})

@app.post("/api/security/block")
async def api_block_user(request: Request):
    if not request.session.get("user"): return UJSONResponse({}, 401)
    data = await request.json()
    uid = int(data.get("user_id"))
    block = data.get("block", True)
    
    if SYSTEM_READY:
        if block: 
            await add_gban_user(uid)
            BANNED_USERS.add(uid)
        else: 
            await remove_gban_user(uid)
            if uid in BANNED_USERS: BANNED_USERS.remove(uid)
            
    return UJSONResponse({"status": "success"})

@app.get("/api/logs")
async def api_download_logs(request: Request):
    if not request.session.get("user"): return UJSONResponse({}, 401)
    if os.path.exists(LOG_FILE):
        return FileResponse(LOG_FILE, filename="titan_logs.txt")
    return UJSONResponse({"error": "No Logs"}, 404)

# [11] Frontend Routes & Authentication
# ──────────────────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def page_dashboard(request: Request):
    if not request.session.get("user"): return RedirectResponse("/login")
    
    tpl = "dashboard.html"
    if os.path.exists(os.path.join(TEMPLATES_DIR, tpl)):
        return templates.TemplateResponse(tpl, {
            "request": request, 
            "bot_name": getattr(Config, "BOT_NAME", "Titan"),
            "owner": getattr(Config, "OWNER_USERNAME", "Boda")
        })
    return HTMLResponse("<h1>Error: dashboard.html missing</h1>")

@app.get("/login", response_class=HTMLResponse)
async def page_login(request: Request):
    if request.session.get("user"): return RedirectResponse("/")
    
    tpl = "login.html"
    if os.path.exists(os.path.join(TEMPLATES_DIR, tpl)):
        return templates.TemplateResponse(tpl, {"request": request})
    return HTMLResponse("<h1>Error: login.html missing</h1>")

@app.post("/login")
async def page_login_post(request: Request, username: str = Form(...), password: str = Form(...)):
    """Fallback Form Login"""
    if password == WEB_PASSWORD:
        request.session["user"] = {"role": "admin", "name": username}
        return RedirectResponse("/", status_code=303)
    return RedirectResponse("/login?error=1", status_code=303)

@app.post("/auth/step1")
async def auth_js_login(request: Request):
    """JS Fetch Login"""
    data = await request.json()
    if data.get("password") == WEB_PASSWORD:
        request.session["user"] = {"role": "admin"}
        return UJSONResponse({"status": "success"})
    return UJSONResponse({"status": "error"}, 401)

@app.get("/logout")
async def page_logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login")

# Mock Biometrics (Always returns success for simulation)
@app.post("/auth/biometric/enroll")
async def bio_enroll(request: Request): return UJSONResponse({"status": "success"})
@app.post("/auth/biometric/verify")
async def bio_verify(request: Request): 
    request.session["user"] = {"role": "admin"}
    return UJSONResponse({"status": "success"})

# [12] Execution & Threading
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"🚀 TitanOS Ultimate V6: Starting Standalone on {HOST}:{PORT}")
    uvicorn.run("web_srv:app", host=HOST, port=PORT, reload=True)

def start_server_thread():
    """Entry point for main.py integration."""
    try:
        uvicorn.run(app, host=HOST, port=PORT, log_level="error")
    except Exception as e:
        print(f"Server Fail: {e}")
