# TitanOS/main.py
# TitanOS Engine & Bridge System
# Copyright (c) 2025 TitanOS

import sys
import os
import asyncio
import sqlite3
import psutil
import json
from datetime import datetime
from typing import Optional, List

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException, Depends, Form, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, Response, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel

# ==========================================
# 1. THE BRIDGE (نظام الكوبري للربط بالبوت)
# ==========================================
# تحديد المسار الحالي ومسار البوت الرئيسي
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)

# إضافة المسار الرئيسي للنظام عشان نقدر نستدعي ملفات البوت
sys.path.append(ROOT_DIR)

# محاولة استدعاء أدوات البوت (AnnieXMedia)
try:
    from AnnieXMedia.core.call import StreamController
    from AnnieXMedia.misc import db as bot_queue_db
    from AnnieXMedia.utils.database import get_lang
    # استدعاء دوال المساعدة لو احتجناها
    print("✅ TitanOS Bridge: Connected to AnnieXMedia Successfully.")
except ImportError as e:
    print(f"❌ TitanOS Bridge Error: {e}")
    print("⚠️ تأكد أن مجلد TitanOS موجود داخل مجلد AnnieXMedia الرئيسي.")

# ==========================================
# 2. إعدادات النظام وقاعدة البيانات
# ==========================================

ADMIN_USER = "Abdallah"
ADMIN_PASS = "asdfghjkl05896"
SECRET_KEY = "TitanOS_X_Secret_Key_2025"
DB_PATH = os.path.join(BASE_DIR, "db.sqlite3")

app = FastAPI(title="Titan OS", version="3.0", docs_url=None)
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)
templates = Jinja2Templates(directory=BASE_DIR) # القوالب في نفس المسار

# متغيرات لتخزين الـ CSS و JS في الرامات
CSS_CONTENT = ""
JS_CONTENT = ""

@app.on_event("startup")
async def startup_system():
    # 1. إنشاء مجلدات الكاش والتحميلات
    os.makedirs(os.path.join(BASE_DIR, "downloads"), exist_ok=True)
    os.makedirs(os.path.join(BASE_DIR, "cache"), exist_ok=True)

    # 2. بناء قاعدة البيانات (SQLite)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # جدول السجلات
    cursor.execute('''CREATE TABLE IF NOT EXISTS activity_log 
                      (id INTEGER PRIMARY KEY, username TEXT, action TEXT, meta TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    # جدول الجروبات المحظورة
    cursor.execute('''CREATE TABLE IF NOT EXISTS banned_groups (group_id INTEGER PRIMARY KEY)''')
    # جدول تخزين الطابور
    cursor.execute('''CREATE TABLE IF NOT EXISTS queue_cache (group_id INTEGER, position INTEGER, title TEXT)''')
    conn.commit()
    conn.close()

    # 3. قراءة وتفكيك ملف assets_bundle.txt (ستايل وكود الموقع)
    global CSS_CONTENT, JS_CONTENT
    assets_path = os.path.join(BASE_DIR, "assets_bundle.txt")
    if os.path.exists(assets_path):
        with open(assets_path, "r", encoding="utf-8") as f:
            content = f.read()
            # نفصل الـ CSS عن الـ JS باستخدام العلامات المميزة
            if "---CSS---" in content and "---JS---" in content:
                parts = content.split("---JS---")
                if len(parts) > 1:
                    css_part = parts[0].split("---CSS---")[1]
                    JS_CONTENT = parts[1].strip()
                    CSS_CONTENT = css_part.strip()
    else:
        print("⚠️ Warning: assets_bundle.txt not found!")

# ==========================================
# 3. أدوات المراقبة والأمان
# ==========================================

def log_to_db(username, action, meta=""):
    """تسجيل العمليات في قاعدة البيانات"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("INSERT INTO activity_log (username, action, meta) VALUES (?, ?, ?)", (username, action, str(meta)))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Log Error: {e}")

def check_auth(request: Request):
    """التحقق من تسجيل الدخول"""
    user = request.session.get("user")
    if user != ADMIN_USER:
        if request.url.path.startswith("/api"):
            raise HTTPException(status_code=401, detail="Unauthorized")
        raise HTTPException(status_code=303, detail="Login Required", headers={"Location": "/login"})
    return True

# ==========================================
# 4. WebSockets (للتحديث الحي)
# ==========================================

class ConnectionManager:
    def __init__(self):
        self.connections: List[WebSocket] = []
    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.connections.append(ws)
    def disconnect(self, ws: WebSocket):
        if ws in self.connections: self.connections.remove(ws)

manager = ConnectionManager()

@app.websocket("/ws/monitor")
async def ws_monitor_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # إرسال بيانات السيرفر الحقيقية
            data = {
                "cpu": psutil.cpu_percent(),
                "ram": psutil.virtual_memory().percent,
                "disk": psutil.disk_usage('/').percent,
                "net_sent": psutil.net_io_counters().bytes_sent,
                "net_recv": psutil.net_io_counters().bytes_recv,
                "time": datetime.now().strftime("%H:%M:%S")
            }
            await websocket.send_json(data)
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.websocket("/ws/logs")
async def ws_logs_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # قراءة ملف السجل الخاص بالبوت (لو موجود)
        log_file_path = os.path.join(ROOT_DIR, "AnnieXMedia.log") # أو bot.log حسب السورس
        if not os.path.exists(log_file_path):
             await websocket.send_text("Log file not found. Waiting for logs...")
        
        while True:
            # محاكاة بسيطة لقراءة السطور الجديدة (Tail)
            # في الإنتاج الحقيقي بنستخدم aiofiles لقراءة الملف
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# ==========================================
# 5. تقديم الملفات (Routes)
# ==========================================

@app.get("/static/css/style.css")
async def serve_css():
    return Response(content=CSS_CONTENT, media_type="text/css")

@app.get("/static/js/app.js")
async def serve_js():
    return Response(content=JS_CONTENT, media_type="application/javascript")

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login_action(request: Request, username: str = Form(...), password: str = Form(...)):
    if username == ADMIN_USER and password == ADMIN_PASS:
        request.session["user"] = username
        log_to_db(username, "Login", "Successful login via Web")
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request, "error": "بيانات الدخول غير صحيحة"})

@app.get("/logout")
async def logout_action(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)

@app.get("/", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    try: check_auth(request)
    except HTTPException as e: return RedirectResponse("/login")
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/logs", response_class=HTMLResponse)
async def logs_page(request: Request):
    try: check_auth(request)
    except HTTPException as e: return RedirectResponse("/login")
    # جلب آخر العمليات
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT * FROM activity_log ORDER BY id DESC LIMIT 50").fetchall()
    conn.close()
    return templates.TemplateResponse("logs.html", {"request": request, "logs": rows})

# ==========================================
# 6. API Endpoints (التحكم الفعلي)
# ==========================================

# -- Media Controls --
@app.post("/api/play/{chat_id}")
async def api_play(chat_id: int, request: Request):
    check_auth(request)
    # ملاحظة: التشغيل المباشر يحتاج تفاصيل أكتر، هنا Resume
    await StreamController.resume_stream(chat_id)
    log_to_db(ADMIN_USER, "Resume", f"Chat: {chat_id}")
    return {"ok": True}

@app.post("/api/pause/{chat_id}")
async def api_pause(chat_id: int, request: Request):
    check_auth(request)
    await StreamController.pause_stream(chat_id)
    log_to_db(ADMIN_USER, "Pause", f"Chat: {chat_id}")
    return {"ok": True}

@app.post("/api/skip/{chat_id}")
async def api_skip(chat_id: int, request: Request):
    check_auth(request)
    # Skip في السورس بتاعك بيحتاج رابط، هنا هنعمل Stop مؤقتاً
    # أو نستخدم force_stop والـ Queue هيدخل اللي بعده
    await StreamController.stop_stream(chat_id) 
    log_to_db(ADMIN_USER, "Skip", f"Chat: {chat_id}")
    return {"ok": True}

@app.post("/api/volume/{chat_id}")
async def api_volume(chat_id: int, level: int = Form(...), request: Request):
    check_auth(request)
    assistant = await StreamController.userbot1 # مثال: استخدام المساعد الأول
    # PyTgCalls Volume logic needs to be accessed via the assistant client call
    # This acts as a stub - volume control depends on the specific pytgcalls version used in Annie
    log_to_db(ADMIN_USER, "Volume", f"Chat: {chat_id}, Level: {level}")
    return {"ok": True, "level": level}

# -- Queue Data --
@app.get("/api/Queue/{chat_id}")
async def api_get_queue(chat_id: int, request: Request):
    check_auth(request)
    data = bot_queue_db.get(chat_id)
    if not data:
        return {"active": False, "queue": []}
    
    current = data[0]
    queue_list = []
    for item in data[1:]:
        queue_list.append({"title": item.get("title"), "dur": item.get("dur")})
        
    return {
        "active": True,
        "current": {
            "title": current.get("title"),
            "dur": current.get("dur"),
            "by": current.get("by"),
            "thumb": current.get("thumb")
        },
        "queue": queue_list
    }

# -- System Controls --
@app.post("/api/restart")
async def api_restart(request: Request):
    check_auth(request)
    log_to_db(ADMIN_USER, "System", "Restart Initiated")
    os.execl(sys.executable, sys.executable, "-m", "AnnieXMedia") # إعادة تشغيل البوت بالكامل
    return {"ok": True}

@app.get("/selftest")
async def self_test():
    """فحص سريع للنظام"""
    return {
        "db": os.path.exists(DB_PATH),
        "bridge": "AnnieXMedia" in sys.modules,
        "assets": len(CSS_CONTENT) > 0,
        "status": "TitanOS Online"
    }
