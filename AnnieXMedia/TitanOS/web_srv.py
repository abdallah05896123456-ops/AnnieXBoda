# -*- coding: utf-8 -*-
# ── 𝚂ᴏᴜʀᴄᴇ ✘ 𝐁ᴏᴅᴀ © 2026 ──────────────────────────────────────────────────────
# TITAN OS | ULTIMATE KERNEL V6 (Production Grade)
# Architecture: FastAPI + Motor Async + PyTgCalls Integration
# Features: Real-Time Sync, Adaptive Streaming, User Proxy, Zero-Latency Control
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
import json
from typing import Any, Dict, List, Union, Optional, Generator
from datetime import datetime

# [1] Critical Dependencies & Intelligent Fallback
# ──────────────────────────────────────────────────────────────────────────────
print("\n[BOOT] TitanOS Kernel: checking dependencies...")

try:
    # Core Server Libraries
    import uvicorn
    import aiofiles
    
    # Try importing Ultra-Fast JSON, fall back to Standard JSON if missing
    try:
        import ujson
        JSON_ENGINE = ujson
    except ImportError:
        print("⚠️ Warning: 'ujson' not found. Falling back to standard 'json'.")
        JSON_ENGINE = json

    # Database & Web Framework
    from motor.motor_asyncio import AsyncIOMotorClient
    from fastapi import FastAPI, Request, Response, Form, BackgroundTasks, HTTPException, status, Header
    from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, FileResponse, StreamingResponse
    from fastapi.templating import Jinja2Templates
    from fastapi.staticfiles import StaticFiles
    from starlette.middleware.sessions import SessionMiddleware
    from starlette.middleware.cors import CORSMiddleware
    
    # Telegram & Bot Core
    from pyrogram import Client, enums
    # [FIX]: Removed specific type imports that cause issues in new versions
    from pytgcalls import PyTgCalls 
    
except ImportError as e:
    print(f"\n❌ CRITICAL ERROR: Missing System Dependencies!\n👉 Please Install: pip3 install fastapi uvicorn aiofiles ujson motor python-multipart jinja2\nError Detail: {e}\n")
    sys.exit(1)

# [2] System Configuration & Path Management
# ──────────────────────────────────────────────────────────────────────────────
class SystemConfig:
    CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
    ROOT_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
    TEMPLATES_DIR = CURRENT_DIR
    STATIC_DIR = os.path.join(CURRENT_DIR, "static")
    
    # Data Directories
    DOWNLOADS_DIR = os.path.join(ROOT_DIR, "downloads")
    CACHE_DIR = os.path.join(ROOT_DIR, "cache")
    RAW_FILES_DIR = os.path.join(ROOT_DIR, "raw_files")
    LOG_FILE = os.path.join(ROOT_DIR, "log.txt")

    @classmethod
    def init_paths(cls):
        """Ensures all necessary system directories exist."""
        for folder in [cls.DOWNLOADS_DIR, cls.CACHE_DIR, cls.RAW_FILES_DIR]:
            os.makedirs(folder, exist_ok=True)
        if cls.ROOT_DIR not in sys.path:
            sys.path.insert(0, cls.ROOT_DIR)

SystemConfig.init_paths()

# [3] Custom High-Performance Response Engine
# ──────────────────────────────────────────────────────────────────────────────
class UJSONResponse(JSONResponse):
    """
    Optimized JSON Response class using the selected JSON Engine.
    Provides faster serialization for large datasets (e.g. chat lists).
    """
    media_type = "application/json"
    def render(self, content: Any) -> bytes:
        return JSON_ENGINE.dumps(content).encode("utf-8")

# [4] Neural Core Integration (Bot Logic)
# ──────────────────────────────────────────────────────────────────────────────
SYSTEM_READY = False
BotClient = None
CallClient = None
QueueDB = {}
Config = None
YouTubeHelper = None
BANNED_USERS = set()

print("🔌 TitanOS V6: Initializing Neural Core & Real-Time Engines...")

try:
    import config
    Config = config
    
    # Secure Credentials Load
    WEB_PASSWORD = getattr(config, "WEB_PASSWORD", "admin")
    WEB_SECRET = getattr(config, "WEB_SECRET", "titan_super_secret_key")
    HOST = getattr(config, "HOST", "0.0.0.0")
    PORT = int(getattr(config, "PORT", "8080"))
    MONGO_DB_URI = getattr(config, "MONGO_DB_URI", None)

    # Import Application Components
    from AnnieXMedia import app as BotClient
    from AnnieXMedia.core.call import StreamController as CallClient
    from AnnieXMedia.misc import db as QueueDB
    from AnnieXMedia import YouTube as YouTubeHelper
    
    # Import Database Utilities
    from AnnieXMedia.utils.database import (
        add_gban_user, remove_gban_user, get_banned_users,
        maintenance_on, maintenance_off, is_maintenance,
        get_active_chats, get_active_video_chats,
        get_loop, set_loop
    )
    
    # Load Ban List
    try:
        from config import BANNED_USERS as _BANS
        BANNED_USERS = _BANS
    except ImportError:
        pass

    SYSTEM_READY = True
    print(f"✅ TitanOS: Successfully Connected to {getattr(config, 'BOT_NAME', 'Bot')} Core.")

except Exception as e:
    print(f"⚠️ TitanOS Warning: Running in Standalone/Safe Mode. Integration Error: {e}")
    # Mock Config for Fallback (Prevents Crash)
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
    """
    Initializes a separate, thread-safe DB connection for the Web Server.
    This prevents Event Loop clashes with Pyrogram's internal loop.
    """
    global mongo_client, web_db
    if MONGO_DB_URI:
        try:
            mongo_client = AsyncIOMotorClient(MONGO_DB_URI)
            web_db = mongo_client[getattr(Config, "BOT_NAME", "AnnieXMedia")]
            print("🗄️ TitanOS: Web Database Link Established.")
        except Exception as e:
            print(f"❌ TitanOS DB Error: {e}")

async def close_db():
    """Gracefully closes the database connection on shutdown."""
    if mongo_client:
        mongo_client.close()
        print("🗄️ TitanOS: Web Database Connection Closed.")

# [6] FastAPI App Definition & Middleware
# ──────────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="TitanOS Ultimate",
    description="High-Performance Media Controller V6",
    version="6.0.0",
    default_response_class=UJSONResponse,
    on_startup=[init_db],
    on_shutdown=[close_db]
)

# Session & Security Middleware
app.add_middleware(SessionMiddleware, secret_key=WEB_SECRET)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Template & Static Engines
templates = Jinja2Templates(directory=SystemConfig.TEMPLATES_DIR)
if os.path.exists(SystemConfig.STATIC_DIR):
    app.mount("/static", StaticFiles(directory=SystemConfig.STATIC_DIR), name="static")

# [7] Advanced Streaming Engine (Adaptive & Resumable)
# ──────────────────────────────────────────────────────────────────────────────
class StreamEngine:
    """
    Intelligent Media Streamer V2.
    - Supports HTTP 206 (Partial Content) for seeking.
    - Smart Chunking for low latency.
    - Auto-detection of file types.
    """
    
    @staticmethod
    def get_file_path(chat_id: int) -> Optional[str]:
        """Locates the media file for a specific chat."""
        # Strategy 1: Check Queue Database
        if SYSTEM_READY and chat_id in QueueDB and QueueDB[chat_id]:
            try:
                track = QueueDB[chat_id][0]
                if track.get("file") and os.path.exists(track["file"]):
                    return track["file"]
            except Exception:
                pass
        
        # Strategy 2: Scan Downloads Directory (Heuristic)
        # This is a fallback if DB sync is slightly delayed
        if os.path.exists(SystemConfig.DOWNLOADS_DIR):
            try:
                files = [
                    os.path.join(SystemConfig.DOWNLOADS_DIR, f) 
                    for f in os.listdir(SystemConfig.DOWNLOADS_DIR)
                    if f.lower().endswith(('.mp4', '.mkv', '.webm', '.mp3'))
                ]
                if files:
                    # Return the most recently modified file
                    return max(files, key=os.path.getctime)
            except Exception: 
                pass
        return None

    @staticmethod
    async def range_generator(file_path: str, start: int, end: int, chunk_size: int = 64 * 1024):
        """
        Async generator for streaming file chunks.
        Optimized for 64KB blocks to balance memory usage and network throughput.
        """
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
        except Exception as e:
            print(f"Stream Error: {e}")

@app.get("/stream/live/{chat_id}")
async def endpoint_stream_media(chat_id: int, request: Request):
    """
    The Core Streaming Endpoint.
    Handles 'Range' headers to allow video players to seek forward/backward.
    """
    file_path = StreamEngine.get_file_path(chat_id)
    
    if not file_path:
        # 404 Not Found if no media is playing
        return Response("Media Not Found / Stream Idle", status_code=404)

    file_size = os.path.getsize(file_path)
    range_header = request.headers.get("range")
    
    # Dynamic Mime Type Detection
    content_type, _ = mimetypes.guess_type(file_path)
    content_type = content_type or "application/octet-stream"

    start = 0
    end = file_size - 1
    status_code = 200

    # Handle Range Request (Seeking)
    if range_header:
        try:
            byte_str = range_header.replace("bytes=", "")
            range_start, range_end = byte_str.split("-")
            start = int(range_start)
            if range_end:
                end = int(range_end)
            
            # Boundary Checks
            if start >= file_size: start = file_size - 1
            if end >= file_size: end = file_size - 1
            
            status_code = 206 # Partial Content
        except ValueError:
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

# [8] Background Task Executor (The Worker)
# ──────────────────────────────────────────────────────────────────────────────
async def bg_executor(func_name: str, chat_id: int, **kwargs):
    """
    Executes bot commands in the background.
    This ensures the Web API responds instantly (Zero-Latency).
    """
    if not SYSTEM_READY or not CallClient: 
        print("⚠️ TitanOS: Command ignored (System Not Ready)")
        return

    try:
        # V6 Feature: Precision Seek
        if func_name == "seek":
            seek_time = kwargs.get("value")
            if seek_time is not None:
                # Call the Bot's Seek function
                if hasattr(CallClient, "seek_stream"):
                    await CallClient.seek_stream(chat_id, int(seek_time))
                else:
                    print("⚠️ TitanOS: 'seek_stream' method not found in CallClient.")

        # Standard Controls
        elif func_name == "pause": 
            await CallClient.pause_stream(chat_id)
        elif func_name == "resume": 
            await CallClient.resume_stream(chat_id)
        elif func_name == "skip": 
            await CallClient.skip_stream(chat_id)
        elif func_name == "stop": 
            await CallClient.force_stop_stream(chat_id)
        elif func_name == "loop":
            curr = await get_loop(chat_id)
            await set_loop(chat_id, 3 if curr == 0 else 0)
            
    except Exception as e:
        print(f"⚠️ BG Task Error ({func_name}): {e}")
        traceback.print_exc()

# [9] API Endpoints: Player Controls & Info
# ──────────────────────────────────────────────────────────────────────────────
@app.post("/api/player/control")
async def api_control(request: Request, bg_tasks: BackgroundTasks):
    """
    Unified Endpoint for all Player Commands (Play, Pause, Seek, etc.)
    """
    if not request.session.get("user"): 
        return UJSONResponse({"error": "Unauthorized"}, 401)
    
    try:
        data = await request.json()
        cmd = data.get("cmd")
        chat_id = int(data.get("chat_id"))
        value = data.get("value") # Used for seek timestamp
    except (ValueError, TypeError):
        return UJSONResponse({"error": "Bad Request Payload"}, 400)

    # Dispatch to Background Worker
    bg_tasks.add_task(bg_executor, cmd, chat_id, value=value)
    return UJSONResponse({"status": "queued", "cmd": cmd, "timestamp": time.time()})

@app.get("/api/player/active_calls")
async def api_active_calls():
    """
    Aggregates active calls from Voice Chats, Video Chats, and the Queue DB.
    Returns a unified list for the Dashboard.
    """
    if not SYSTEM_READY: 
        return UJSONResponse({"chats": []})
    
    results = []
    try:
        # Fetch data concurrently (optimized)
        vid_chats_task = get_active_video_chats()
        aud_chats_task = get_active_chats()
        
        # In case they are not awaitable in some versions, handle safely
        if inspect.iscoroutine(vid_chats_task): vid_chats = await vid_chats_task
        else: vid_chats = vid_chats_task or []
            
        if inspect.iscoroutine(aud_chats_task): aud_chats = await aud_chats_task
        else: aud_chats = aud_chats_task or []
        
        all_ids = set(vid_chats + aud_chats)
        
        # Merge with internal QueueDB to catch states where VC is active but playing hasn't started
        if QueueDB:
            all_ids.update([k for k in QueueDB.keys() if isinstance(k, int)])
        
        for cid in all_ids:
            try:
                title = "Unknown Track"
                cover = Config.UNIFIED_IMG
                
                # Extract Metadata from Queue
                if cid in QueueDB and QueueDB[cid]:
                    t = QueueDB[cid][0]
                    title = t.get("title", title)[:60] # Truncate long titles
                    cover = t.get("thumb") or cover
                
                results.append({
                    "chat_id": str(cid),
                    "name": f"Chat {cid}", 
                    "title": title,
                    "cover": cover,
                    "stream_url": f"/stream/live/{cid}"
                })
            except Exception: 
                continue
    except Exception as e: 
        print(f"Error fetching active calls: {e}")
    
    return UJSONResponse({"chats": results})

@app.get("/api/player/track_info/{chat_id}")
async def api_track_info(chat_id: int):
    """
    Returns detailed real-time telemetry for a specific chat.
    Includes: Title, Duration, Current Position (for Seek Bar).
    """
    default_state = {
        "title": "Not Playing", 
        "artist": "-", 
        "cover": getattr(Config, "UNIFIED_IMG", ""), 
        "is_playing": False, 
        "duration": "00:00", 
        "loop_mode": 0, 
        "position": 0
    }
    
    if not SYSTEM_READY: 
        return UJSONResponse(default_state)
    
    try:
        if chat_id in QueueDB and QueueDB[chat_id]:
            track = QueueDB[chat_id][0]
            loop_val = await get_loop(chat_id)
            
            # [V6 Logic: Real-Time Position Calculation]
            current_pos = 0
            try:
                # Access internal PyTgCalls status if available
                core_call = getattr(CallClient, "call", None) 
                # Or try referencing the client directly from global if needed
                if not core_call and hasattr(CallClient, "pytgcalls"):
                    core_call = CallClient.pytgcalls

                if core_call:
                    active = core_call.get_active_call(chat_id)
                    if active and hasattr(active, "status"):
                        # 'time_elapsed' is usually in seconds
                        current_pos = getattr(active.status, "time_elapsed", 0)
            except Exception:
                pass # Sync error, default to 0

            return UJSONResponse({
                "title": track.get("title", "Unknown"),
                "artist": track.get("by", "TitanOS"),
                "cover": track.get("thumb") or default_state["cover"],
                "duration": track.get("dur", "Live"),
                "is_playing": True,
                "stream_url": f"/stream/live/{chat_id}",
                "loop_mode": loop_val,
                "queued": max(0, len(QueueDB[chat_id]) - 1),
                "position": current_pos 
            })
    except Exception: 
        pass
    
    return UJSONResponse(default_state)

# [10] Advanced Features: Proxy & Operators
# ──────────────────────────────────────────────────────────────────────────────
@app.get("/api/proxy_avatar/{user_id}")
async def api_proxy_avatar(user_id: int):
    """
    Serves Telegram profile photos over HTTP.
    Includes an LRU Cache mechanism to prevent API Rate Limits.
    """
    if not SYSTEM_READY: 
        return RedirectResponse(Config.UNIFIED_IMG)
    
    cache_path = os.path.join(SystemConfig.CACHE_DIR, f"avatar_{user_id}.jpg")
    
    # 1. Check Local Cache (Valid for 1 Hour)
    if os.path.exists(cache_path):
        if (time.time() - os.path.getmtime(cache_path)) < 3600:
            return FileResponse(cache_path)

    # 2. Fetch from Telegram Cloud
    try:
        if BotClient:
            photo = await BotClient.download_media(
                message=user_id, 
                file_name=cache_path
            )
            if photo:
                return FileResponse(photo)
    except Exception:
        pass
        
    # 3. Fallback
    return RedirectResponse(Config.UNIFIED_IMG)

@app.get("/api/player/participants/{chat_id}")
async def api_participants(chat_id: int):
    """
    Fetches the list of Voice Chat participants (Operators).
    Prioritizes Admins/Owners.
    """
    if not SYSTEM_READY: 
        return UJSONResponse({"participants": []})
    
    participants = []
    
    try:
        # Use Pyrogram to fetch admins
        async for member in BotClient.get_chat_members(chat_id, filter=enums.ChatMembersFilter.ADMINISTRATORS):
            user = member.user
            if user.is_deleted: continue
            
            participants.append({
                "user_id": user.id,
                "name": f"{user.first_name} {user.last_name or ''}".strip(),
                "role": "Operator" if member.status in [enums.ChatMemberStatus.OWNER, enums.ChatMemberStatus.ADMINISTRATOR] else "Listener",
                "photo_url": f"/api/proxy_avatar/{user.id}" if user.photo else Config.UNIFIED_IMG
            })
    except Exception as e:
        print(f"Participant Fetch Error: {e}")
        
    return UJSONResponse({"participants": participants})

@app.post("/api/player/play")
async def api_play_request(request: Request, bg_tasks: BackgroundTasks):
    """
    Handles Play Requests from the Dashboard Modal.
    Downloads the track and joins the call.
    """
    if not request.session.get("user"): 
        return UJSONResponse({"error": "Unauthorized"}, 401)
    
    try:
        data = await request.json()
        chat_id = int(data.get("chat_id"))
        query = data.get("query")
    except:
        return UJSONResponse({"error": "Bad Request"}, 400)
    
    async def _play_task():
        """Background Worker for downloading and playing."""
        try:
            # 1. Resolve Track
            details, track_id = await YouTubeHelper.track(query)
            
            # 2. Download
            file_path, _ = await YouTubeHelper.download(track_id, mystic=None, video=True, videoid=track_id)
            
            # 3. Join Call
            await CallClient.join_call(
                chat_id=chat_id, 
                original_chat_id=chat_id,
                link=file_path, 
                video=True, 
                image=details.get("thumb")
            )
            
            # 4. Update Queue
            from AnnieXMedia.utils.stream.queue import put_queue
            await put_queue(
                chat_id, chat_id, file_path, details["title"],
                details["duration_min"], "WebUser", track_id,
                Config.OWNER_ID, "video"
            )
        except Exception as e:
            print(f"❌ Web Play Error: {e}")
            traceback.print_exc()

    bg_tasks.add_task(_play_task)
    return UJSONResponse({"status": "processing"})

# [11] System & Security Endpoints
# ──────────────────────────────────────────────────────────────────────────────
@app.get("/api/system/status")
async def api_sys_status(request: Request):
    """Returns Server Health Metrics (CPU, RAM, Threads)."""
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
    """Administrative Actions: Restart, Clean Cache, Git Pull."""
    if not request.session.get("user"): return UJSONResponse({"error": "Unauthorized"}, 401)
    
    data = await request.json()
    action = data.get("action")
    
    if action == "clean":
        freed = 0
        for f in [SystemConfig.DOWNLOADS_DIR, SystemConfig.CACHE_DIR, SystemConfig.RAW_FILES_DIR]:
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
            print("🔄 Rebooting TitanOS...")
            await asyncio.sleep(2)
            os.execv(sys.executable, [sys.executable, "-m", "AnnieXMedia"])
        bg_tasks.add_task(_restart)
        return UJSONResponse({"status": "Restarting..."})
    
    elif action == "update":
        async def _update():
            print("⬇️ Pulling Updates...")
            os.system("git pull")
            await asyncio.sleep(2)
            os.execv(sys.executable, [sys.executable, "-m", "AnnieXMedia"])
        bg_tasks.add_task(_update)
        return UJSONResponse({"status": "Updating..."})
        
    return UJSONResponse({"error": "Unknown Action"}, 400)

@app.get("/api/security/users")
async def api_get_users(request: Request):
    """View Global Banned Users."""
    if not request.session.get("user"): return UJSONResponse({}, 401)
    blocked = []
    if SYSTEM_READY: blocked = await get_banned_users()
    return UJSONResponse({"blocked_users": list(blocked)})

@app.post("/api/security/block")
async def api_block_user(request: Request):
    """GBAN / UNGBAN User."""
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
    """Download System Logs."""
    if not request.session.get("user"): return UJSONResponse({}, 401)
    if os.path.exists(SystemConfig.LOG_FILE):
        return FileResponse(SystemConfig.LOG_FILE, filename="titan_logs.txt")
    return UJSONResponse({"error": "No Logs Found"}, 404)

# [12] Frontend Routing (HTML Serving)
# ──────────────────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def page_dashboard(request: Request):
    """Main Dashboard Interface."""
    if not request.session.get("user"): return RedirectResponse("/login")
    
    tpl = "dashboard.html"
    if os.path.exists(os.path.join(SystemConfig.TEMPLATES_DIR, tpl)):
        return templates.TemplateResponse(tpl, {
            "request": request, 
            "bot_name": getattr(Config, "BOT_NAME", "Titan"),
            "owner": getattr(Config, "OWNER_USERNAME", "SysAdmin")
        })
    return HTMLResponse("<h1>Error: dashboard.html missing in TitanOS folder.</h1>")

@app.get("/login", response_class=HTMLResponse)
async def page_login(request: Request):
    """Login Interface."""
    if request.session.get("user"): return RedirectResponse("/")
    
    tpl = "login.html"
    if os.path.exists(os.path.join(SystemConfig.TEMPLATES_DIR, tpl)):
        return templates.TemplateResponse(tpl, {"request": request})
    return HTMLResponse("<h1>Error: login.html missing in TitanOS folder.</h1>")

@app.post("/login")
async def page_login_post(request: Request, username: str = Form(...), password: str = Form(...)):
    """Standard Form Login Handler."""
    if password == WEB_PASSWORD:
        request.session["user"] = {"role": "admin", "name": username}
        return RedirectResponse("/", status_code=303)
    return RedirectResponse("/login?error=1", status_code=303)

@app.post("/auth/step1")
async def auth_js_login(request: Request):
    """AJAX Login Handler."""
    data = await request.json()
    if data.get("password") == WEB_PASSWORD:
        request.session["user"] = {"role": "admin"}
        return UJSONResponse({"status": "success"})
    return UJSONResponse({"status": "error"}, 401)

@app.get("/logout")
async def page_logout(request: Request):
    """Session Cleanup."""
    request.session.clear()
    return RedirectResponse("/login")

# [13] Entry Points
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"🚀 TitanOS Ultimate V6: Starting Standalone on {HOST}:{PORT}")
    uvicorn.run("web_srv:app", host=HOST, port=PORT, reload=True)

def start_server_thread():
    """Integration hook for the main Bot process."""
    try:
        config = uvicorn.Config(app, host=HOST, port=PORT, log_level="warning")
        server = uvicorn.Server(config)
        # Using a threaded execution is common for side-loading with Pyrogram
        import threading
        t = threading.Thread(target=server.run)
        t.daemon = True
        t.start()
        print("✅ TitanOS Web Server: Background Thread Started.")
    except Exception as e:
        print(f"❌ Web Server Failed to Start: {e}")
