import os
import sqlite3
import asyncio
import datetime
from fastapi import FastAPI, WebSocket, Request, Form, Depends, UploadFile, File
from fastapi.responses import RedirectResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.sessions import SessionMiddleware
import psutil

# Base directory of this file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = FastAPI()
# Session secret (change in production)
app.add_middleware(SessionMiddleware, secret_key="CHANGE_THIS_SECRET")

# Mount static directory and templates
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# Setup SQLite DB for activity logs and banned groups
db_path = os.path.join(BASE_DIR, "db.sqlite3")
conn = sqlite3.connect(db_path, check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS activity_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    action TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS banned_groups (
    group_id INTEGER PRIMARY KEY
)
""")
conn.commit()

def log_action(username: str, action: str):
    cursor.execute("INSERT INTO activity_log (username, action) VALUES (?, ?)", (username, action))
    conn.commit()

# === Authentication Routes ===
@app.get("/")
async def root(request: Request):
    if request.session.get("user") != "Abdallah":
        return RedirectResponse("/login")
    return RedirectResponse("/dashboard")

@app.get("/login")
async def login_get(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})

@app.post("/login")
async def login_post(request: Request, username: str = Form(...), password: str = Form(...)):
    if username == "Abdallah" and password == "asdfghjkl05896":
        request.session["user"] = username
        return RedirectResponse("/dashboard", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request, "error": "اسم المستخدم أو كلمة المرور غير صحيحة"})

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login")

# === لوحة التحكم الرئيسية ===
@app.get("/dashboard")
async def dashboard(request: Request):
    if request.session.get("user") != "Abdallah":
        return RedirectResponse("/login")
    return templates.TemplateResponse("dashboard.html", {"request": request, "user": request.session.get("user")})

# === سجل أنشطة المدير ===
@app.get("/admin/logs")
async def admin_logs(request: Request):
    if request.session.get("user") != "Abdallah":
        return RedirectResponse("/login")
    cursor.execute("SELECT username, action, timestamp FROM activity_log ORDER BY timestamp DESC")
    logs = cursor.fetchall()
    return templates.TemplateResponse("logs.html", {"request": request, "logs": logs})

# === التحكم الأساسي بالميديا (Core Media) ===
@app.post("/api/play/{group_id}")
async def api_play(request: Request, group_id: int):
    log_action(request.session.get("user"), f"Play resumed in group {group_id}")
    return {"status": "playing"}

@app.post("/api/pause/{group_id}")
async def api_pause(request: Request, group_id: int):
    log_action(request.session.get("user"), f"Playback paused in group {group_id}")
    return {"status": "paused"}

@app.post("/api/skip/{group_id}")
async def api_skip(request: Request, group_id: int):
    log_action(request.session.get("user"), f"Song skipped in group {group_id}")
    return {"status": "skipped"}

@app.post("/api/replay/{group_id}")
async def api_replay(request: Request, group_id: int):
    log_action(request.session.get("user"), f"Song replayed in group {group_id}")
    return {"status": "replaying"}

@app.post("/api/seek/{group_id}")
async def api_seek(request: Request, group_id: int, position: int = Form(...)):
    log_action(request.session.get("user"), f"Seeked to {position}s in group {group_id}")
    return {"status": "seeked", "position": position}

@app.post("/api/volume/{group_id}")
async def api_volume(request: Request, group_id: int, level: int = Form(...)):
    log_action(request.session.get("user"), f"Volume set to {level}% in group {group_id}")
    return {"status": "volume set", "level": level}

@app.post("/api/loop/{group_id}")
async def api_loop(request: Request, group_id: int):
    log_action(request.session.get("user"), f"Loop toggled in group {group_id}")
    return {"status": "loop toggled"}

@app.post("/api/shuffle/{group_id}")
async def api_shuffle(request: Request, group_id: int):
    log_action(request.session.get("user"), f"Shuffle toggled in group {group_id}")
    return {"status": "shuffle toggled"}

@app.post("/api/switch_media/{group_id}")
async def api_switch_media(request: Request, group_id: int):
    log_action(request.session.get("user"), f"Media mode switched in group {group_id}")
    return {"status": "media mode switched"}

@app.get("/api/download/{group_id}")
async def api_download(request: Request, group_id: int):
    filepath = os.path.join(BASE_DIR, "static", "sample.mp3")
    if os.path.exists(filepath):
        return FileResponse(filepath, media_type='audio/mpeg', filename="song.mp3")
    return {"status": "no file"}

@app.get("/api/lyrics/{group_id}")
async def api_lyrics(request: Request, group_id: int):
    lyrics = "كلمات الأغنية غير متوفرة حالياً."
    return {"lyrics": lyrics}

# === معاينة الفيديو المباشرة ===
@app.get("/api/thumbnail/{group_id}")
async def api_thumbnail(request: Request, group_id: int):
    img_path = os.path.join(BASE_DIR, "static", "thumbnail.jpg")
    if os.path.exists(img_path):
        return FileResponse(img_path, media_type="image/jpeg", filename="thumbnail.jpg")
    return {"status": "no thumbnail"}

# === التحكم العميق (Deep Control) ===
@app.post("/api/ban_group/{group_id}")
async def api_ban_group(request: Request, group_id: int):
    cursor.execute("INSERT OR IGNORE INTO banned_groups (group_id) VALUES (?)", (group_id,))
    conn.commit()
    log_action(request.session.get("user"), f"Group {group_id} banned")
    return {"status": f"group {group_id} banned"}

@app.post("/api/force_end/{group_id}")
async def api_force_end(request: Request, group_id: int):
    log_action(request.session.get("user"), f"Force ended stream in group {group_id}")
    return {"status": f"stream force-ended in group {group_id}"}

@app.post("/api/kick/{group_id}")
async def api_kick(request: Request, group_id: int, user_id: int = Form(...)):
    log_action(request.session.get("user"), f"User {user_id} kicked from group {group_id}")
    return {"status": f"user {user_id} kicked"}

@app.post("/api/mute/{group_id}")
async def api_mute(request: Request, group_id: int, user_id: int = Form(...)):
    log_action(request.session.get("user"), f"User {user_id} muted in group {group_id}")
    return {"status": f"user {user_id} muted"}

@app.get("/api/queue/{group_id}")
async def api_get_queue(request: Request, group_id: int):
    queue = ["Song A", "Song B", "Song C"]  # Example placeholder
    return {"queue": queue}

@app.post("/api/queue/{group_id}")
async def api_update_queue(request: Request, group_id: int, songs: str = Form(...)):
    queue = songs.split(',')
    log_action(request.session.get("user"), f"Queue updated in group {group_id}: {queue}")
    return {"status": "queue updated", "queue": queue}

# === نظام الملفات والكاش ===
@app.get("/api/cache")
async def api_cache(request: Request):
    downloads = []
    cache = []
    download_dir = os.path.join(BASE_DIR, "downloads")
    cache_dir = os.path.join(BASE_DIR, "cache")
    if os.path.isdir(download_dir):
        downloads = os.listdir(download_dir)
    if os.path.isdir(cache_dir):
        cache = os.listdir(cache_dir)
    return {"downloads": downloads, "cache": cache}

@app.post("/api/upload")
async def api_upload(request: Request, file: UploadFile = File(...)):
    content = await file.read()
    cache_dir = os.path.join(BASE_DIR, "cache")
    os.makedirs(cache_dir, exist_ok=True)
    file_path = os.path.join(cache_dir, file.filename)
    with open(file_path, "wb") as f:
        f.write(content)
    log_action(request.session.get("user"), f"File {file.filename} uploaded")
    return {"status": "uploaded", "filename": file.filename}

@app.post("/api/clean_cache")
async def api_clean_cache(request: Request):
    now = datetime.datetime.now().timestamp()
    for d in ["downloads", "cache"]:
        dirpath = os.path.join(BASE_DIR, d)
        if os.path.isdir(dirpath):
            for fname in os.listdir(dirpath):
                fpath = os.path.join(dirpath, fname)
                if os.path.isfile(fpath) and (now - os.path.getmtime(fpath) > 7*24*3600):
                    os.remove(fpath)
    log_action(request.session.get("user"), "Old cache files cleaned")
    return {"status": "cache cleaned"}

@app.post("/api/play_local/{group_id}")
async def api_play_local(request: Request, group_id: int, filename: str = Form(...)):
    log_action(request.session.get("user"), f"Local file {filename} played in group {group_id}")
    return {"status": f"playing {filename}"}

# === المساعدين والسيرفر ===
@app.get("/api/assistants_status")
async def api_assistants_status(request: Request):
    assistants = {
        "assistant1": "online",
        "assistant2": "offline",
        "assistant3": "online",
        "assistant4": "offline",
        "assistant5": "online"
    }
    return assistants

@app.post("/api/assistant/join")
async def assistant_join(request: Request, link: str = Form(...)):
    log_action(request.session.get("user"), f"Assistant join requested for {link}")
    return {"status": f"assistant join {link}"}

@app.post("/api/assistant/leave")
async def assistant_leave(request: Request, link: str = Form(...)):
    log_action(request.session.get("user"), f"Assistant leave requested for {link}")
    return {"status": f"assistant leave {link}"}

@app.post("/api/edit_profile")
async def api_edit_profile(request: Request, name: str = Form(...), bio: str = Form(...)):
    log_action(request.session.get("user"), f"Profile changed Name={name}, Bio={bio}")
    return {"status": "profile updated"}

# === مراقبة السيرفر الحية ===
@app.websocket("/ws/monitor")
async def ws_monitor(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = {
                "cpu": psutil.cpu_percent(),
                "ram": psutil.virtual_memory().percent,
                "disk": psutil.disk_usage('/').percent,
                "net_sent": psutil.net_io_counters().bytes_sent,
                "net_recv": psutil.net_io_counters().bytes_recv
            }
            await websocket.send_json(data)
            await asyncio.sleep(1)
    except:
        await websocket.close()

# === الترمينال الحي (Logs) ===
@app.websocket("/ws/logs")
async def ws_logs(websocket: WebSocket):
    await websocket.accept()
    log_file = os.path.join(BASE_DIR, "bot.log")
    if not os.path.exists(log_file):
        await websocket.send_text("Log file not found.")
        await websocket.close()
        return
    with open(log_file, "r") as f:
        f.seek(0, os.SEEK_END)
        while True:
            line = f.readline()
            if line:
                await websocket.send_text(line.strip())
            else:
                await asyncio.sleep(0.5)

# === إعادة تشغيل البوت تلقائياً ===
@app.post("/api/restart")
async def api_restart(request: Request):
    log_action(request.session.get("user"), "Bot restart triggered")
    # Exit process; use external manager to restart
    os._exit(0)

# === Broadcaster ===
@app.post("/api/broadcast")
async def api_broadcast(request: Request, message: str = Form(...)):
    log_action(request.session.get("user"), "Broadcast message sent")
    return {"status": "broadcast sent"}
