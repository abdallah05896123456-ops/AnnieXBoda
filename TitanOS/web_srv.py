# -*- coding: utf-8 -*-
# ==============================================================================
# TITAN OS | ULTIMATE KERNEL (Stream & Control Edition)
# Features: Real-time Streaming, Bot Control, System Monitor, File Serving
# ==============================================================================

import os
import sys
import asyncio
import psutil
import logging
from threading import Thread

# محاولة استيراد المكتبات القوية (FastAPI)
try:
    import uvicorn
    from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, Response
    from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, FileResponse, StreamingResponse
    from fastapi.templating import Jinja2Templates
    from fastapi.staticfiles import StaticFiles
    from starlette.middleware.sessions import SessionMiddleware
    from starlette.middleware.cors import CORSMiddleware
except ImportError:
    print("❌ ERROR: Install requirements: pip3 install fastapi uvicorn aiofiles python-multipart")
    sys.exit(1)

# ------------------------------------------------------------------------------
# [1] إعداد البيئة والربط (Bridge System)
# ------------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
DOWNLOADS_DIR = os.path.join(ROOT_DIR, "downloads") # مجلد التحميلات الخاص بالبوت
CACHE_DIR = os.path.join(ROOT_DIR, "cache")

# إضافة مسار البوت الرئيسي
sys.path.append(ROOT_DIR)

# متغيرات للتحكم والربط
BOT_CORE = None
SYSTEM_READY = False

# محاولة الاتصال بقلب البوت (AnnieXMedia)
try:
    # نقوم باستيراد الكائنات الحيوية من السورس
    from AnnieXMedia import app as BotClient
    from AnnieXMedia.core.call import Annie as CallClient
    # استيراد قاعدة بيانات الطابور لمعرفة الملف الحالي
    try:
        from AnnieXMedia.misc import db as QueueDB
    except:
        QueueDB = {} # في حالة عدم العثور عليها
        
    SYSTEM_READY = True
    print("✅ TitanOS: Connected to AnnieXMedia Engine.")
except ImportError:
    print("⚠️ TitanOS: Running in Standalone Mode (Bot not found).")

# ------------------------------------------------------------------------------
# [2] إعداد سيرفر FastAPI
# ------------------------------------------------------------------------------
app = FastAPI(title="TitanOS", docs_url=None)

# إعداد الكوكيز والأمان
app.add_middleware(SessionMiddleware, secret_key="TITAN_ULTIMATE_KEY_2026")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# إعداد القوالب
templates = Jinja2Templates(directory=BASE_DIR)

# إتاحة مجلد التحميلات للموقع (عشان الفيديو يشتغل)
if os.path.exists(DOWNLOADS_DIR):
    app.mount("/downloads", StaticFiles(directory=DOWNLOADS_DIR), name="downloads")

# ------------------------------------------------------------------------------
# [3] تقنية البث المباشر للموقع (The Streaming Core)
# ------------------------------------------------------------------------------
def get_current_media_path(chat_id):
    """
    هذه الدالة الذكية تبحث عن ملف الميديا الحالي لتشغيله في الموقع.
    تبحث في الطابور (Queue) الخاص بالبوت.
    """
    if not SYSTEM_READY: return None
    
    # محاولة جلب الملف من قاعدة بيانات البوت
    # ملاحظة: هذا الكود يعتمد على هيكلة Annie القياسية
    try:
        chat_id = int(chat_id)
        if chat_id in QueueDB:
            # العنصر الأول هو اللي شغال دلوقتي
            current_track = QueueDB[chat_id][0] 
            file_path = current_track.get("file")
            
            # التأكد إن الملف موجود فعلاً
            if file_path and os.path.exists(file_path):
                return file_path
    except:
        pass
        
    # بحث يدوي في مجلد التحميلات كخيار أخير
    # بنشوف أحدث ملف نزل
    try:
        files = [os.path.join(DOWNLOADS_DIR, f) for f in os.listdir(DOWNLOADS_DIR) if f.endswith(('.mp4', '.mp3', '.m4a', '.webm'))]
        if files:
            newest_file = max(files, key=os.path.getctime)
            return newest_file
    except:
        pass
        
    return None

@app.get("/stream/live/{chat_id}")
async def stream_media(chat_id: str, request: Request):
    """
    الرابط السحري: يقوم ببث الفيديو أو الصوت للمتصفح مباشرة
    يدعم النطاقات (Ranges) عشان تقدر تقدم وترجع في الفيديو
    """
    file_path = get_current_media_path(chat_id)
    
    if not file_path:
        # لو مفيش ملف، نرجع فيديو انتظار
        return JSONResponse({"status": "No media playing"}, status_code=404)

    # تقديم الملف كـ Stream
    file_size = os.path.getsize(file_path)
    range_header = request.headers.get("range")

    # منطق الـ Byte Range (لتقديم وتأخير الفيديو)
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
        return Response(content=data, status_code=206, headers=headers, media_type=headers["Content-Type"])

    # لو مفيش Range، رجع الملف كله
    return FileResponse(file_path)

# ------------------------------------------------------------------------------
# [4] التحكم و API (The Command Center)
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
        except:
            pass
    
    # بيانات وهمية لو البوت مش متصل (للتجربة)
    if not chats and not SYSTEM_READY:
        chats = [{"id": "-100123", "name": "Demo Channel"}]
        
    return JSONResponse({"chats": chats})

@app.get("/api/track_info/{chat_id}")
async def track_info(chat_id: str):
    # معلومات التراك للعرض في الموقع
    title = "System Idle"
    artist = "Titan OS"
    cover = "https://telegra.ph/file/5eb6df308e92f4477813d.jpg"
    
    # محاولة جلب المعلومات الحقيقية من الطابور
    if SYSTEM_READY:
        try:
            cid = int(chat_id)
            if cid in QueueDB:
                track = QueueDB[cid][0]
                title = track.get("title", title)
                artist = track.get("dur", artist) # المدة كاسم الفنان
                cover = track.get("thumb", cover) # صورة الغلاف
        except:
            pass
            
    return JSONResponse({
        "title": title,
        "artist": artist,
        "cover": cover,
        "stream_url": f"/stream/live/{chat_id}" # هذا هو الرابط الذي سيشغله الموقع
    })

@app.post("/api/{cmd}/{chat_id}")
async def commands(cmd: str, chat_id: str, request: Request):
    if not request.session.get("user"): return JSONResponse({"error": "Auth"}, 401)
    
    cid = int(chat_id)
    if SYSTEM_READY:
        try:
            if cmd == "pause": await CallClient.pause_stream(cid)
            elif cmd == "resume": await CallClient.resume_stream(cid)
            elif cmd == "stop": await CallClient.leave_group_call(cid)
            elif cmd == "skip": await CallClient.stop_stream(cid) # Stop بيعمل Trigger للـ Next في السورس
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
# [5] صفحات الواجهة (HTML Routes)
# ------------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    if not request.session.get("user"): return RedirectResponse("/login")
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/login", response_class=HTMLResponse)
async def login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def do_login(request: Request):
    form = await request.form()
    # User: admin / Pass: admin (للسرعة)
    if form.get("username") == "admin" and form.get("password") == "admin":
        request.session["user"] = "Root"
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request, "error": "X"})

@app.get("/logs", response_class=HTMLResponse)
async def logs(request: Request):
    return templates.TemplateResponse("logs.html", {"request": request, "logs": []})

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login")

# ------------------------------------------------------------------------------
# [6] WebSockets (المراقبة الحية)
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
# [7] المشغل (Engine Starter)
# ------------------------------------------------------------------------------
def run_uvicorn():
    # تشغيل السيرفر
    # log_level="critical" لتقليل الضوضاء في التيرمينال
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="critical")

def start():
    t = Thread(target=run_uvicorn)
    t.daemon = True
    t.start()
    print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("🚀 TITAN OS ULTIMATE IS ONLINE")
    print("📺 WEB UI: http://YOUR-IP:8080")
    print("🎬 STREAMING: ACTIVE (Video & Audio)")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")

if __name__ == "__main__":
    run_uvicorn()
