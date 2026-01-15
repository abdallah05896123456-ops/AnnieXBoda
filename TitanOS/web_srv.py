# -*- coding: utf-8 -*-
# ==============================================================================
# TITAN OS | ULTIMATE KERNEL (FastAPI Engine)
# ==============================================================================

import os
import sys
import asyncio
import psutil
import logging
from threading import Thread

# [1] استيراد مكتبات السيرفر
try:
    import uvicorn
    from fastapi import FastAPI, Request, WebSocket, Response, Form
    from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, FileResponse
    from fastapi.templating import Jinja2Templates
    from fastapi.staticfiles import StaticFiles
    from starlette.middleware.sessions import SessionMiddleware
    from starlette.middleware.cors import CORSMiddleware
except ImportError:
    print("\n❌ ERROR: Missing Libraries! Please run: pip3 install fastapi uvicorn aiofiles python-multipart jinja2\n")
    pass

# ------------------------------------------------------------------------------
# [2] إعداد المسارات
# ------------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
DOWNLOADS_DIR = os.path.join(ROOT_DIR, "downloads")

if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# ------------------------------------------------------------------------------
# [3] الربط مع البوت (Bot Bridge)
# ------------------------------------------------------------------------------
SYSTEM_READY = False
CallClient = None
BotClient = None
QueueDB = {}

try:
    from AnnieXMedia import app as BotClient
    
    # ✅ التعديل هنا: استيراد StreamController مباشرة لأنه معرف مسبقاً في سورسك
    from AnnieXMedia.core.call import StreamController as CallClient
    
    # استيراد قاعدة البيانات
    try: from AnnieXMedia.misc import db as QueueDB
    except: pass
        
    SYSTEM_READY = True
    print("✅ TitanOS Web: Connected to StreamController.")
except ImportError as e:
    print(f"⚠️ TitanOS Web: Running Standalone. Error: {e}")

# ------------------------------------------------------------------------------
# [4] إعداد السيرفر
# ------------------------------------------------------------------------------
app = FastAPI(title="TitanOS", docs_url=None)

app.add_middleware(SessionMiddleware, secret_key="TITAN_GOD_KEY_2026")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True, 
    allow_methods=["*"], allow_headers=["*"],
)

templates = Jinja2Templates(directory=BASE_DIR)

if not os.path.exists(DOWNLOADS_DIR):
    try: os.makedirs(DOWNLOADS_DIR, exist_ok=True)
    except: pass
if os.path.exists(DOWNLOADS_DIR):
    app.mount("/downloads", StaticFiles(directory=DOWNLOADS_DIR), name="downloads")

# ------------------------------------------------------------------------------
# [5] Streaming Core
# ------------------------------------------------------------------------------
def get_current_media_path(chat_id):
    if not SYSTEM_READY: return None
    try:
        cid = int(chat_id)
        if cid in QueueDB and QueueDB[cid]:
            return QueueDB[cid][0].get("file")
    except: pass
    
    # Fallback to downloads
    try:
        files = [os.path.join(DOWNLOADS_DIR, f) for f in os.listdir(DOWNLOADS_DIR) if f.endswith(('mp4','mp3'))]
        if files: return max(files, key=os.path.getctime)
    except: pass
    return None

@app.get("/stream/live/{chat_id}")
async def stream_media(chat_id: str, request: Request):
    file_path = get_current_media_path(chat_id)
    if not file_path or not os.path.exists(file_path): 
        return Response("No Active Stream", status_code=404)

    file_size = os.path.getsize(file_path)
    range_header = request.headers.get("range")

    if range_header:
        byte1, byte2 = 0, None
        match = range_header.replace("bytes=", "").split("-")
        byte1 = int(match[0])
        if match[1]: byte2 = int(match[1])
        byte2 = byte2 if byte2 else file_size - 1
        length = byte2 - byte1 + 1

        with open(file_path, "rb") as f:
            f.seek(byte1)
            data = f.read(length)

        headers = {
            "Content-Range": f"bytes {byte1}-{byte2}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(length),
            "Content-Type": "video/mp4",
        }
        return Response(content=data, status_code=206, headers=headers)
    return FileResponse(file_path)

# ------------------------------------------------------------------------------
# [6] API Endpoints
# ------------------------------------------------------------------------------
@app.get("/api/active_calls")
async def get_calls():
    chats = []
    if SYSTEM_READY and CallClient:
        try:
            # استخدام active_calls من الكنترولر بتاعك
            for cid in CallClient.active_calls:
                try:
                    chat = await BotClient.get_chat(cid)
                    name = chat.title
                except: name = f"Chat: {cid}"
                chats.append({"id": str(cid), "name": name})
        except: pass
    
    if not chats: chats = [{"id": "0", "name": "No Signal"}]
    return JSONResponse({"chats": chats})

@app.get("/api/track_info/{chat_id}")
async def track_info(chat_id: str):
    info = {"title": "Idle", "artist": "System Ready", "cover": "", "stream_url": ""}
    if SYSTEM_READY:
        try:
            cid = int(chat_id)
            if cid in QueueDB and QueueDB[cid]:
                t = QueueDB[cid][0]
                info = {
                    "title": t.get("title", "Unknown"),
                    "artist": t.get("dur", "Live"),
                    "cover": t.get("thumb", ""),
                    "stream_url": f"/stream/live/{chat_id}"
                }
        except: pass
    return JSONResponse(info)

@app.post("/api/{cmd}/{chat_id}")
async def commands(cmd: str, chat_id: str, request: Request):
    if not request.session.get("user"): return JSONResponse({"error": "Auth"}, 401)
    if SYSTEM_READY and CallClient:
        try:
            cid = int(chat_id)
            if cmd == "pause": await CallClient.pause_stream(cid)
            elif cmd == "resume": await CallClient.resume_stream(cid)
            elif cmd in ["stop", "skip"]: await CallClient.stop_stream(cid)
        except: pass
    return JSONResponse({"ok": True})

@app.post("/api/system/{action}")
async def sys_action(action: str):
    if action == "turbo":
        import gc; gc.collect()
    return JSONResponse({"ok": True})

# ------------------------------------------------------------------------------
# [7] HTML Pages
# ------------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    if not request.session.get("user"): return RedirectResponse("/login")
    if os.path.exists(os.path.join(BASE_DIR, "dashboard.html")):
        return templates.TemplateResponse("dashboard.html", {"request": request})
    return HTMLResponse("Dashboard Not Found", 500)

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if os.path.exists(os.path.join(BASE_DIR, "login.html")):
        return templates.TemplateResponse("login.html", {"request": request})
    return HTMLResponse("Login Page Not Found", 500)

@app.post("/login")
async def do_login(request: Request, username: str = Form(...), password: str = Form(...)):
    if username == "Abdallah" and password == "asdfghjkl05896":
        request.session["user"] = "Root"
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request, "error": "Access Denied"})

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login")

# ------------------------------------------------------------------------------
# [8] Launcher
# ------------------------------------------------------------------------------
def start_server():
    t = Thread(target=uvicorn.run, args=(app,), kwargs={"host":"0.0.0.0", "port":8080, "log_level":"critical"})
    t.daemon = True
    t.start()
    print("🚀 TitanOS Web (FastAPI) Started on Port 8080")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
