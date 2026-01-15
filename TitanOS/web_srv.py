# -*- coding: utf-8 -*-
# ==============================================================================
# TITAN OS | ULTIMATE KERNEL (FastAPI Edition)
# Features: Real-time Streaming, Bot Control, System Monitor, File Serving
# ==============================================================================

import os
import sys
import asyncio
import psutil
import logging
from threading import Thread

# [1] استيراد مكتبات السيرفر القوية
try:
    import uvicorn
    # تم إضافة Form هنا عشان تسجيل الدخول يشتغل صح
    from fastapi import FastAPI, Request, WebSocket, Response, Form
    from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, FileResponse
    from fastapi.templating import Jinja2Templates
    from fastapi.staticfiles import StaticFiles
    from starlette.middleware.sessions import SessionMiddleware
    from starlette.middleware.cors import CORSMiddleware
except ImportError:
    print("\n❌ ERROR: Missing Libraries! Please run:")
    print("pip3 install fastapi uvicorn aiofiles python-multipart jinja2\n")
    sys.exit(1)

# ------------------------------------------------------------------------------
# [2] إعداد المسارات (Path Configuration) - أهم جزء للإصلاح
# ------------------------------------------------------------------------------
# تحديد مكان الملف الحالي (داخل TitanOS)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# تحديد المجلد الرئيسي للبوت (عشان نجيب منه AnnieXMedia)
ROOT_DIR = os.path.dirname(BASE_DIR)
DOWNLOADS_DIR = os.path.join(ROOT_DIR, "downloads")
CACHE_DIR = os.path.join(ROOT_DIR, "cache")

# إضافة المسار الرئيسي لـ sys.path عشان نقدر نستورد البوت
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

print(f"📂 TitanOS Web Directory: {BASE_DIR}")
print(f"📂 Downloads Directory: {DOWNLOADS_DIR}")

# ------------------------------------------------------------------------------
# [3] الربط مع البوت (Bot Bridge)
# ------------------------------------------------------------------------------
SYSTEM_READY = False
try:
    # محاولة استيراد الكائنات الحيوية من السورس
    from AnnieXMedia import app as BotClient
    from AnnieXMedia.core.call import Annie as CallClient
    # استيراد قاعدة بيانات الطابور لمعرفة الملف الحالي
    try:
        from AnnieXMedia.misc import db as QueueDB
    except ImportError:
        QueueDB = {} 
        
    SYSTEM_READY = True
    print("✅ TitanOS: Connected to AnnieXMedia Core.")
except ImportError as e:
    print(f"⚠️ TitanOS: Running in Standalone Mode (Bot modules not found: {e})")
    QueueDB = {}

# ------------------------------------------------------------------------------
# [4] إعداد سيرفر FastAPI
# ------------------------------------------------------------------------------
app = FastAPI(title="TitanOS", docs_url=None)

# إعداد الكوكيز والأمان
app.add_middleware(SessionMiddleware, secret_key="TITAN_GOD_KEY_2026")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# إعداد القوالب (Templates) - يقرأ من نفس الفولدر (TitanOS)
templates = Jinja2Templates(directory=BASE_DIR)

# إتاحة مجلد التحميلات للموقع (عشان الفيديو يشتغل)
if not os.path.exists(DOWNLOADS_DIR):
    try:
        os.makedirs(DOWNLOADS_DIR, exist_ok=True)
    except: pass

if os.path.exists(DOWNLOADS_DIR):
    app.mount("/downloads", StaticFiles(directory=DOWNLOADS_DIR), name="downloads")

# ------------------------------------------------------------------------------
# [5] تقنية البث المباشر (The Streaming Core)
# ------------------------------------------------------------------------------
def get_current_media_path(chat_id):
    """البحث عن ملف الميديا الحالي"""
    if not SYSTEM_READY: return None
    
    # 1. البحث في قاعدة بيانات البوت
    try:
        cid = int(chat_id)
        if cid in QueueDB and QueueDB[cid]:
            current_track = QueueDB[cid][0] 
            file_path = current_track.get("file")
            if file_path and os.path.exists(file_path):
                return file_path
    except: pass
        
    # 2. البحث في مجلد التحميلات (أحدث ملف)
    try:
        files = [os.path.join(DOWNLOADS_DIR, f) for f in os.listdir(DOWNLOADS_DIR) 
                 if f.endswith(('.mp4', '.mp3', '.webm', '.m4a'))]
        if files:
            return max(files, key=os.path.getctime)
    except: pass
        
    return None

@app.get("/stream/live/{chat_id}")
async def stream_media(chat_id: str, request: Request):
    """بث الفيديو مع دعم Range Requests (تقديم وتأخير)"""
    file_path = get_current_media_path(chat_id)
    
    if not file_path:
        return Response("No Active Stream", status_code=404)

    file_size = os.path.getsize(file_path)
    range_header = request.headers.get("range")

    if range_header:
        byte1, byte2 = 0, None
        match = range_header.replace("bytes=", "").split("-")
        byte1 = int(match[0])
        if match[1]:
            byte2 = int(match[1])
        
        byte2 = byte2 if byte2 else file_size - 1
        length = byte2 - byte1 + 1

        with open(file_path, "rb") as f:
            f.seek(byte1)
            data = f.read(length)

        headers = {
            "Content-Range": f"bytes {byte1}-{byte2}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(length),
            "Content-Type": "video/mp4" if file_path.endswith(".mp4") else "audio/mpeg",
        }
        return Response(content=data, status_code=206, headers=headers)

    # لو مفيش Range، رجع الملف كله
    return FileResponse(file_path)

# ------------------------------------------------------------------------------
# [6] واجهة التحكم (API Routes)
# ------------------------------------------------------------------------------

@app.get("/api/active_calls")
async def get_calls():
    # جلب قائمة الجروبات النشطة
    chats = []
    if SYSTEM_READY:
        try:
            for cid in CallClient.active_chats:
                try:
                    chat = await BotClient.get_chat(cid)
                    name = chat.title
                except:
                    name = f"Chat: {cid}"
                chats.append({"id": str(cid), "name": name})
        except: pass
    
    # داتا وهمية للتجربة لو البوت مش شغال
    if not chats:
        chats = [{"id": "0", "name": "System Waiting..."}]
        
    return JSONResponse({"chats": chats})

@app.get("/api/track_info/{chat_id}")
async def track_info(chat_id: str):
    # معلومات التراك للعرض في الموقع
    info = {
        "title": "System Idle",
        "artist": "Titan OS",
        "cover": "https://telegra.ph/file/5eb6df308e92f4477813d.jpg",
        "stream_url": ""
    }
    
    # محاولة جلب المعلومات الحقيقية من الطابور
    if SYSTEM_READY:
        try:
            cid = int(chat_id)
            if cid in QueueDB and QueueDB[cid]:
                track = QueueDB[cid][0]
                info["title"] = track.get("title", "Unknown")
                info["artist"] = track.get("dur", "Live")
                info["cover"] = track.get("thumb", info["cover"])
                info["stream_url"] = f"/stream/live/{chat_id}"
        except: pass
            
    return JSONResponse(info)

@app.post("/api/{cmd}/{chat_id}")
async def commands(cmd: str, chat_id: str, request: Request):
    if not request.session.get("user"): return JSONResponse({"error": "Auth"}, 401)
    
    cid = int(chat_id)
    if SYSTEM_READY:
        try:
            if cmd == "pause": await CallClient.pause_stream(cid)
            elif cmd == "resume": await CallClient.resume_stream(cid)
            elif cmd in ["stop", "skip"]: await CallClient.stop_stream(cid)
        except Exception as e:
            print(f"CMD Error: {e}")
            
    return JSONResponse({"ok": True, "cmd": cmd})

@app.post("/api/system/{action}")
async def sys_action(action: str):
    if action == "turbo":
        import gc
        gc.collect() # تنظيف الرام
        # تنظيف ملفات التحميل القديمة
        try:
            for f in os.listdir(DOWNLOADS_DIR):
                os.remove(os.path.join(DOWNLOADS_DIR, f))
        except: pass
        
    return JSONResponse({"ok": True})

# ------------------------------------------------------------------------------
# [7] صفحات الواجهة (HTML Pages)
# ------------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    if not request.session.get("user"): return RedirectResponse("/login")
    
    # التحقق من وجود الملف
    if os.path.exists(os.path.join(BASE_DIR, "dashboard.html")):
        return templates.TemplateResponse("dashboard.html", {"request": request})
    return HTMLResponse("<h1>Error: dashboard.html not found!</h1>", status_code=500)

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if os.path.exists(os.path.join(BASE_DIR, "login.html")):
        return templates.TemplateResponse("login.html", {"request": request, "error": None})
    return HTMLResponse("<h1>Error: login.html not found!</h1>", status_code=500)

@app.post("/login")
async def do_login(request: Request, username: str = Form(...), password: str = Form(...)):
    # بيانات الدخول: admin / admin
    if username == "admin" and password == "admin":
        request.session["user"] = "Root"
        return RedirectResponse("/", status_code=303)
    
    return templates.TemplateResponse("login.html", {"request": request, "error": "Wrong Password"})

@app.get("/logs")
async def logs(request: Request):
    if not request.session.get("user"): return RedirectResponse("/login")
    log_file = os.path.join(ROOT_DIR, "log.txt")
    if os.path.exists(log_file):
        return FileResponse(log_file)
    return HTMLResponse("No logs found.")

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login")

# ------------------------------------------------------------------------------
# [8] WebSockets (المراقبة الحية)
# ------------------------------------------------------------------------------
@app.websocket("/ws/monitor")
async def ws_monitor(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            await websocket.send_json({
                "cpu": psutil.cpu_percent(),
                "ram": psutil.virtual_memory().percent
            })
            await asyncio.sleep(2)
    except: pass

# ------------------------------------------------------------------------------
# [9] المشغل (Engine Starter)
# ------------------------------------------------------------------------------
def run_uvicorn():
    # تشغيل السيرفر
    # log_level="error" لتقليل الضوضاء
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="error")

def start_server():
    t = Thread(target=run_uvicorn)
    t.daemon = True
    t.start()
    print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("🚀 TITAN OS WEB SERVER IS ONLINE")
    print("🌐 URL: http://0.0.0.0:8080")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")

if __name__ == "__main__":
    run_uvicorn()
