# -*- coding: utf-8 -*-
# ==============================================================================
# TITAN OS | ULTIMATE SERVER (FastAPI Edition)
# The Brain: Handles Web, WebSocket, Database, and Bot Commands
# ==============================================================================

import os
import sys
import asyncio
import psutil
import logging
from threading import Thread

# محاولة استدعاء مكتبات FastAPI (لازم تكون مثبتة: pip install fastapi uvicorn)
try:
    import uvicorn
    from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
    from fastapi.templating import Jinja2Templates
    from fastapi.staticfiles import StaticFiles
    from starlette.middleware.sessions import SessionMiddleware
except ImportError:
    print("❌ Critical Error: Please install fastapi & uvicorn (pip3 install fastapi uvicorn)")
    sys.exit(1)

# ------------------------------------------------------------------------------
# [1] إعداد المسارات والربط بالبوت (The Bridge)
# ------------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# متغير للتحقق من اتصال البوت
BOT_CONNECTED = False

try:
    # محاولة استيراد كلاسات التحكم من AnnieXMedia
    # نقوم بإضافة المجلد الرئيسي للمسار لكي يرى البايثون البوت
    ROOT_DIR = os.path.dirname(BASE_DIR)
    sys.path.append(ROOT_DIR)
    
    from AnnieXMedia.core.call import Annie as CallClient
    # أو حسب السورس ممكن يكون الاسم: from AnnieXMedia.core.call import call_py
    
    print("✅ Titan Bridge: Connected to AnnieXMedia Core.")
    BOT_CONNECTED = True
except ImportError as e:
    print(f"⚠️ Titan Bridge Warning: Could not import Bot Core ({e}). Running in Standalone Mode.")

# ------------------------------------------------------------------------------
# [2] إعدادات تطبيق FastAPI
# ------------------------------------------------------------------------------
app = FastAPI(docs_url=None, redoc_url=None)

# إعداد الكوكيز للجلسات
app.add_middleware(SessionMiddleware, secret_key="TITAN_GOD_MODE_KEY_2026")

# تحديد مكان ملفات HTML (القوالب)
templates = Jinja2Templates(directory=BASE_DIR)

# لو عندك فولدر static للصور والـ CSS
# app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

# ------------------------------------------------------------------------------
# [3] الـ WebSockets (عشان اللوجات والسرعة تظهر لايف)
# ------------------------------------------------------------------------------
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

manager = ConnectionManager()

@app.websocket("/ws/monitor")
async def websocket_monitor(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # إرسال بيانات السيرفر الحقيقية كل ثانية
            data = {
                "cpu": psutil.cpu_percent(),
                "ram": psutil.virtual_memory().percent,
                "net_sent": psutil.net_io_counters().bytes_sent,
                "net_recv": psutil.net_io_counters().bytes_recv
            }
            await websocket.send_json(data)
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # هنا المفروض تقرأ ملف اللوج الحقيقي وترسله
        await websocket.send_text("Connected to Real-Time Log Stream...")
        while True:
            await asyncio.sleep(5) # مجرد انتظار للحفاظ على الاتصال
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# ------------------------------------------------------------------------------
# [4] ملفات الأوامر (API Routes - The Commands File)
# ------------------------------------------------------------------------------

# 4.1 جلب المكالمات النشطة
@app.get("/api/active_calls")
async def get_active_calls():
    chats = []
    if BOT_CONNECTED:
        try:
            # جلب الجروبات التي يعمل فيها البوت حالياً
            active_ids = CallClient.active_chats
            for chat_id in active_ids:
                chats.append({"id": str(chat_id), "name": f"Group {chat_id}"})
        except:
            pass # فشل في جلب القائمة
    return JSONResponse({"chats": chats})

# 4.2 معلومات التراك الحالي
@app.get("/api/track_info/{chat_id}")
async def get_track_info(chat_id: str):
    # هنا ممكن تربط مع قاعدة بيانات البوت لجلب اسم الأغنية الحقيقي
    return JSONResponse({
        "title": "Titan Live Audio",
        "artist": f"Target: {chat_id}",
        "cover": "https://telegra.ph/file/5eb6df308e92f4477813d.jpg"
    })

# 4.3 تنفيذ الأوامر (Pause, Resume, Stop, Skip)
@app.post("/api/{command}/{chat_id}")
async def execute_command(command: str, chat_id: str, request: Request):
    # التحقق من تسجيل الدخول
    if not request.session.get("user"):
        return JSONResponse({"ok": False, "error": "Unauthorized"}, status_code=401)

    cid = int(chat_id)
    success = False
    
    if BOT_CONNECTED:
        try:
            if command == "pause":
                await CallClient.pause_stream(cid)
                success = True
            elif command == "resume":
                await CallClient.resume_stream(cid)
                success = True
            elif command == "stop":
                await CallClient.leave_group_call(cid)
                success = True
            elif command == "skip":
                # في معظم السورسات skip بيحتاج منطق معقد، هنعمل stop مؤقتاً
                await CallClient.leave_group_call(cid) 
                success = True
        except Exception as e:
            print(f"Command Error: {e}")
            
    # لو البوت مش متصل، نرجع True وهمي عشان الواجهة متقفش
    return JSONResponse({"ok": True, "executed": success, "cmd": command})

# 4.4 أوامر النظام (Turbo)
@app.post("/api/system/{action}")
async def system_action(action: str):
    if action == "turbo":
        # تنظيف الرام
        import gc
        gc.collect()
    return JSONResponse({"ok": True})

# ------------------------------------------------------------------------------
# [5] صفحات الموقع (HTML Rendering)
# ------------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    if not request.session.get("user"):
        return RedirectResponse("/login")
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login_submit(request: Request):
    form = await request.form()
    username = form.get("username")
    password = form.get("password")
    
    if username == "admin" and password == "admin":
        request.session["user"] = "admin"
        return RedirectResponse("/", status_code=303)
    
    return templates.TemplateResponse("login.html", {"request": request, "error": "Wrong Credentials"})

@app.get("/logs", response_class=HTMLResponse)
async def logs_page(request: Request):
    if not request.session.get("user"): return RedirectResponse("/login")
    return templates.TemplateResponse("logs.html", {"request": request, "logs": []})

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login")

# ------------------------------------------------------------------------------
# [6] تشغيل السيرفر (The Engine)
# ------------------------------------------------------------------------------

def run_uvicorn():
    # تشغيل السيرفر باستخدام Uvicorn (أسرع وأقوى من فلاسك العادي)
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="error")

def start():
    # هذه الدالة يستدعيها ملف البوت الرئيسي
    t = Thread(target=run_uvicorn)
    t.daemon = True
    t.start()
    print("🚀 TitanOS (FastAPI Kernel) Started on Port 8080")

if __name__ == "__main__":
    run_uvicorn()
