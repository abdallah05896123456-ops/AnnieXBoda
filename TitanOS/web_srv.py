# -*- coding: utf-8 -*-
# ==============================================================================
# TITAN OS | ULTIMATE KERNEL (The Complete Backend Engine)
# Authored By Certified Coders © 2025
# ==============================================================================

import os
import sys
import asyncio
import psutil
import shutil
import socket
import logging
import gc
from datetime import datetime
from threading import Thread

# [1] Library Imports | استيراد المكتبات الأساسية
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
    pass

# ------------------------------------------------------------------------------
# [2] Paths & Config | إعداد المسارات
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
# [3] Bot Integration | دمج قلب البوت وقواعد البيانات
# ------------------------------------------------------------------------------
SYSTEM_READY = False
CallClient = None
BotClient = None
QueueDB = {}
YouTubeHelper = None
Config = None

try:
    # --- Core Imports ---
    import config
    Config = config
    from config import BANNED_USERS
    from AnnieXMedia import app as BotClient
    
    # --- Stream Controller ---
    from AnnieXMedia.core.call import StreamController as CallClient
    
    # --- Helpers ---
    from AnnieXMedia import YouTube as YouTubeHelper
    from AnnieXMedia.misc import db as QueueDB
    
    # --- Database Functions (Everything you sent) ---
    from AnnieXMedia.utils.database import (
        add_gban_user, remove_gban_user, get_banned_users, # Block System
        blacklist_chat, whitelist_chat, blacklisted_chats, # Blacklist System
        autoend_on, autoend_off, is_autoend,              # AutoEnd System
        maintenance_on, maintenance_off, is_maintenance,   # Maintenance System
        get_active_chats, get_active_video_chats,          # Active Chats
        remove_active_chat, remove_active_video_chat
    )
    
    SYSTEM_READY = True
    print("✅ TitanOS Web: Engine Connected (DB, Call, Config, Admin Systems).")

except ImportError as e:
    print(f"⚠️ TitanOS Web: Running Standalone Mode (Missing: {e})")

# ------------------------------------------------------------------------------
# [4] Server Initialization | إعداد السيرفر
# ------------------------------------------------------------------------------
app = FastAPI(title="TitanOS Ultimate", docs_url=None, redoc_url=None)

# Security & Middleware
app.add_middleware(SessionMiddleware, secret_key="TITAN_GOD_KEY_2026")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True, 
    allow_methods=["*"], allow_headers=["*"],
)

templates = Jinja2Templates(directory=BASE_DIR)

# Ensure Critical Folders Exist
for folder in [DOWNLOADS_DIR, CACHE_DIR, RAW_FILES_DIR]:
    if not os.path.exists(folder):
        try: os.makedirs(folder, exist_ok=True)
        except: pass

# Mount Static Files
if os.path.exists(DOWNLOADS_DIR):
    app.mount("/downloads", StaticFiles(directory=DOWNLOADS_DIR), name="downloads")

# ------------------------------------------------------------------------------
# [5] Streaming Engine | محرك الفيديو (Anti-Lag Chunking)
# ------------------------------------------------------------------------------
def get_current_media_path(chat_id):
    """Retrieves the file path playing in a specific chat"""
    if not SYSTEM_READY: return None
    try:
        cid = int(chat_id)
        if cid in QueueDB and QueueDB[cid]:
            return QueueDB[cid][0].get("file")
    except: pass
    
    # Fallback Mechanism: If DB is empty, try latest download
    try:
        files = [os.path.join(DOWNLOADS_DIR, f) for f in os.listdir(DOWNLOADS_DIR) if f.endswith(('.mp4', '.mp3', '.webm'))]
        if files: return max(files, key=os.path.getctime)
    except: pass
    
    return None

def chunk_generator(file_path, start, end):
    """Reads file in chunks for smooth streaming"""
    with open(file_path, "rb") as f:
        f.seek(start)
        while f.tell() <= end:
            read_size = min(1024*1024, end - f.tell() + 1) # 1MB Chunk
            data = f.read(read_size)
            if not data: break
            yield data

@app.get("/stream/live/{chat_id}")
async def stream_media(chat_id: str, request: Request):
    """Live Video Stream Endpoint"""
    file_path = get_current_media_path(chat_id)
    
    if not file_path or not os.path.exists(file_path):
        # محاولة البحث عن أي ملف في الداونلودز كبديل
        try:
            files = [os.path.join(DOWNLOADS_DIR, f) for f in os.listdir(DOWNLOADS_DIR) if f.endswith('.mp4')]
            if files: file_path = max(files, key=os.path.getctime)
        except: pass

    if not file_path or not os.path.exists(file_path):
        return Response("No Active Stream / File Not Found", status_code=404)

    file_size = os.path.getsize(file_path)
    range_header = request.headers.get("range")

    if range_header:
        byte1, byte2 = 0, None
        match = range_header.replace("bytes=", "").split("-")
        byte1 = int(match[0])
        if match[1]: byte2 = int(match[1])
        byte2 = byte2 if byte2 else file_size - 1
        length = byte2 - byte1 + 1
        headers = {
            "Content-Range": f"bytes {byte1}-{byte2}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(length),
            "Content-Type": "video/mp4",
        }
        return StreamingResponse(chunk_generator(file_path, byte1, byte2), status_code=206, headers=headers)
    return FileResponse(file_path)

# ==============================================================================
# [6] API SECTOR 1: Player Control & Info (تحكم المشغل)
# ==============================================================================

@app.get("/api/player/active_calls")
async def get_active_calls_api():
    """Returns list of active chats with metadata"""
    chats = []
    if SYSTEM_READY and CallClient:
        try:
            active_cids = CallClient.active_calls
            for cid in active_cids:
                name = str(cid)
                cover = "https://telegra.ph/file/5eb6df308e92f4477813d.jpg"
                try:
                    if cid in QueueDB and QueueDB[cid]:
                        data = QueueDB[cid][0]
                        name = data.get("title", str(cid))[:30]
                        cover = data.get("thumb", cover)
                    else:
                        chat = await BotClient.get_chat(cid)
                        name = chat.title
                except: pass
                chats.append({"id": str(cid), "name": name, "cover": cover})
        except: pass
    
    if not chats: chats = [{"id": "0", "name": "System Idle", "cover": ""}]
    return JSONResponse({"chats": chats})

@app.get("/api/player/track_info/{chat_id}")
async def get_track_info_api(chat_id: str):
    """Returns detailed info for UI Card"""
    info = {"title": "Titan OS", "artist": "Idle", "cover": "", "duration": "00:00", "is_playing": False, "stream_url": ""}
    if SYSTEM_READY:
        try:
            cid = int(chat_id)
            if cid in QueueDB and QueueDB[cid]:
                t = QueueDB[cid][0]
                info = {
                    "title": t.get("title", "Unknown")[:40],
                    "artist": t.get("by", "Artist")[:20],
                    "cover": t.get("thumb", ""),
                    "duration": t.get("dur", "Live"),
                    "is_playing": True,
                    "stream_url": f"/stream/live/{cid}"
                }
        except: pass
    return JSONResponse(info)

@app.post("/api/player/control")
async def player_control_api(cmd: str = Form(...), chat_id: str = Form(...), request: Request = None):
    """Controls: Pause, Resume, Skip, Stop"""
    if not request.session.get("user"): return JSONResponse({"error": "Auth Required"}, 401)
    if not SYSTEM_READY: return JSONResponse({"error": "Offline"}, 503)
    
    try:
        cid = int(chat_id)
        if cmd == "pause": await CallClient.pause_stream(cid)
        elif cmd == "resume": await CallClient.resume_stream(cid)
        elif cmd == "skip": await CallClient.stop_stream(cid)
        elif cmd == "stop": await CallClient.force_stop_stream(cid)
        elif cmd == "focus": CallClient.turbo_chat_id = cid # وضع التركيز
        return JSONResponse({"status": "Success", "command": cmd})
    except Exception as e:
        return JSONResponse({"error": str(e)}, 500)

@app.post("/api/player/play_custom")
async def play_custom_api(chat_id: str = Form(...), query: str = Form(...), request: Request = None):
    """Play a song by ID/Link directly"""
    if not request.session.get("user"): return JSONResponse({"error": "Auth Required"}, 401)
    if not SYSTEM_READY: return JSONResponse({"error": "System Offline"}, 503)
    try:
        cid = int(chat_id)
        # Search
        results = await YouTubeHelper.search(query, limit=1)
        if not results: return JSONResponse({"error": "No results found"}, 404)
        
        link = results[0]["link"]
        title = results[0]["title"]
        
        # Join & Play
        await CallClient.join_call(chat_id=cid, original_chat_id=cid, link=link, video=True)
        return JSONResponse({"status": "success", "msg": f"Playing: {title}", "chat_id": cid})
    except Exception as e: return JSONResponse({"error": str(e)}, 500)

# ==============================================================================
# [7] API SECTOR 2: Security (حظر المستخدمين & الجروبات)
# ==============================================================================

@app.post("/api/security/block_user")
async def block_user_api(user_id: str = Form(...), action: str = Form(...)): # action: enable/disable
    """Block/Unblock User (GBAN)"""
    if not SYSTEM_READY: return JSONResponse({"error": "Offline"}, 503)
    try:
        uid = int(user_id)
        if action == "enable":
            if uid not in BANNED_USERS:
                await add_gban_user(uid)
                BANNED_USERS.add(uid)
            return JSONResponse({"status": "User Blocked", "id": uid})
        elif action == "disable":
            if uid in BANNED_USERS:
                await remove_gban_user(uid)
                BANNED_USERS.remove(uid)
            return JSONResponse({"status": "User Unblocked", "id": uid})
    except Exception as e: return JSONResponse({"error": str(e)}, 500)

@app.get("/api/security/blocked_users")
async def list_blocked_users():
    """Get List of GBANNED Users"""
    if not SYSTEM_READY: return JSONResponse({"users": []})
    users = await get_banned_users()
    return JSONResponse({"users": list(users)}) # Ensure list format

@app.post("/api/security/blacklist_chat")
async def blacklist_chat_api(chat_id: str = Form(...), action: str = Form(...)): # action: enable/disable
    """Blacklist/Whitelist Chat"""
    if not SYSTEM_READY: return JSONResponse({"error": "Offline"}, 503)
    try:
        cid = int(chat_id)
        if action == "enable":
            await blacklist_chat(cid)
            try: await BotClient.leave_chat(cid)
            except: pass
            return JSONResponse({"status": "Chat Blacklisted", "id": cid})
        elif action == "disable":
            await whitelist_chat(cid)
            return JSONResponse({"status": "Chat Whitelisted", "id": cid})
    except Exception as e: return JSONResponse({"error": str(e)}, 500)

@app.get("/api/security/blacklisted_chats")
async def list_blacklisted_chats():
    """Get List of Blacklisted Chats"""
    if not SYSTEM_READY: return JSONResponse({"chats": []})
    chats = await blacklisted_chats()
    return JSONResponse({"chats": list(chats)})

# ==============================================================================
# [8] API SECTOR 3: System Settings (إعدادات النظام)
# ==============================================================================

@app.post("/api/settings/maintenance")
async def toggle_maintenance(action: str = Form(...)): # action: enable/disable
    """Toggle Maintenance Mode"""
    if not SYSTEM_READY: return JSONResponse({"error": "Offline"}, 503)
    try:
        if action == "enable":
            await maintenance_on()
            return JSONResponse({"status": "Maintenance Mode ON 🔴"})
        else:
            await maintenance_off()
            return JSONResponse({"status": "Maintenance Mode OFF 🟢"})
    except Exception as e: return JSONResponse({"error": str(e)}, 500)

@app.post("/api/settings/autoend")
async def toggle_autoend(action: str = Form(...)): # action: enable/disable
    """Toggle Auto-End Stream"""
    if not SYSTEM_READY: return JSONResponse({"error": "Offline"}, 503)
    try:
        if action == "enable":
            await autoend_on()
            return JSONResponse({"status": "AutoEnd ON 🟢"})
        else:
            await autoend_off()
            return JSONResponse({"status": "AutoEnd OFF 🔴"})
    except Exception as e: return JSONResponse({"error": str(e)}, 500)

@app.get("/api/settings/status")
async def get_system_status():
    """Get Current Status of Settings & Ping"""
    if not SYSTEM_READY: return JSONResponse({"maintenance": False, "autoend": False, "ping": 0})
    m_status = await is_maintenance()
    a_status = await is_autoend() if hasattr(sys.modules[__name__], 'is_autoend') else False
    
    # Ping Calculation
    pytgping = "0.0"
    if CallClient:
        try: pytgping = await CallClient.ping()
        except: pass
        
    return JSONResponse({
        "maintenance": m_status, 
        "autoend": a_status,
        "ping": pytgping,
        "ram": psutil.virtual_memory().percent,
        "cpu": psutil.cpu_percent()
    })

# ==============================================================================
# [9] API SECTOR 4: Utilities & Actions (أدوات النظام)
# ==============================================================================

@app.post("/api/utils/turbo")
async def turbo_clean(request: Request):
    """Turbo Mode: Clean RAM & Cache"""
    if not request.session.get("user"): return JSONResponse({"error": "Auth Required"}, 401)
    
    deleted_files = 0
    cleaned_size = 0
    
    # 1. Clean Disk
    folders = [DOWNLOADS_DIR, CACHE_DIR, RAW_FILES_DIR]
    for folder in folders:
        if os.path.exists(folder):
            for f in os.listdir(folder):
                file_path = os.path.join(folder, f)
                try:
                    cleaned_size += os.path.getsize(file_path)
                    os.remove(file_path)
                    deleted_files += 1
                except: pass
                
    # 2. Clean PyCache
    for root, dirs, files in os.walk(ROOT_DIR):
        for d in dirs:
            if d == "__pycache__":
                try: shutil.rmtree(os.path.join(root, d))
                except: pass

    # 3. Clean RAM
    gc.collect()
    
    return JSONResponse({
        "status": "Turbo Executed 🚀", 
        "files_removed": deleted_files,
        "space_freed_mb": f"{cleaned_size / (1024*1024):.2f} MB"
    })

@app.get("/api/utils/logs")
async def download_logs(request: Request):
    """Download System Logs"""
    if not request.session.get("user"): return JSONResponse({"error": "Auth Required"}, 401)
    if os.path.exists(LOG_FILE):
        return FileResponse(LOG_FILE, filename="log.txt")
    return JSONResponse({"error": "No Log File Found"}, 404)

async def restart_process():
    """Background Task: Restart Bot"""
    await asyncio.sleep(2)
    os.execv(sys.executable, [sys.executable, "-m", "AnnieXMedia"])

async def update_process():
    """Background Task: Git Pull & Restart"""
    try:
        os.system(f"git fetch origin {Config.UPSTREAM_BRANCH} &> /dev/null")
        os.system("git pull")
        await restart_process()
    except Exception as e:
        print(f"Update Failed: {e}")

@app.post("/api/utils/action")
async def system_action(action: str = Form(...), background_tasks: BackgroundTasks = None, request: Request = None):
    """Actions: Update, Restart"""
    if not request.session.get("user"): return JSONResponse({"error": "Auth Required"}, 401)
    
    if action == "restart":
        background_tasks.add_task(restart_process)
        return JSONResponse({"status": "Restarting System... Please wait 15s"})
    elif action == "update":
        background_tasks.add_task(update_process)
        return JSONResponse({"status": "Updating from Git & Restarting..."})
    
    return JSONResponse({"error": "Unknown Action"}, 400)

@app.get("/api/utils/cache_list")
async def list_cache_files(request: Request):
    """List Files in Cache/Downloads"""
    if not request.session.get("user"): return JSONResponse({"error": "Auth Required"}, 401)
    files_list = []
    total_size = 0
    
    if os.path.exists(DOWNLOADS_DIR):
        for f in os.listdir(DOWNLOADS_DIR):
            fp = os.path.join(DOWNLOADS_DIR, f)
            size = os.path.getsize(fp) / (1024 * 1024)
            total_size += size
            files_list.append({"name": f, "size": f"{size:.2f} MB"})
            
    return JSONResponse({
        "files": files_list,
        "total_count": len(files_list),
        "total_size_mb": f"{total_size:.2f} MB"
    })

# ==============================================================================
# [10] Frontend Routes (صفحات العرض)
# ==============================================================================

@app.get("/", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    if not request.session.get("user"): return RedirectResponse("/login")
    if os.path.exists(os.path.join(BASE_DIR, "dashboard.html")):
        return templates.TemplateResponse("dashboard.html", {"request": request})
    return HTMLResponse("<h1>TitanOS Kernel Active. Waiting for Design.</h1>", 200)

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if os.path.exists(os.path.join(BASE_DIR, "login.html")):
        return templates.TemplateResponse("login.html", {"request": request})
    return HTMLResponse("<h1>Login Required</h1>", 200)

@app.post("/login")
async def perform_login(request: Request, username: str = Form(...), password: str = Form(...)):
    # Credentials
    if username == "Abdallah" and password == "asdfghjkl05896":
        request.session["user"] = "Root"
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid Credentials"})

@app.get("/logout")
async def perform_logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login")

# ==============================================================================
# [11] Main Launcher (التشغيل)
# ==============================================================================
def start_server():
    """Starts the Uvicorn Server in a Thread"""
    t = Thread(target=uvicorn.run, args=(app,), kwargs={"host":"0.0.0.0", "port":8080, "log_level":"critical"})
    t.daemon = True
    t.start()
    print("🚀 TitanOS Ultimate Kernel: Web Server Started on Port 8080")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
