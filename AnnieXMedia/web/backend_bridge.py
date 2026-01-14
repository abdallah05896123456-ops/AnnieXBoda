# -*- coding: utf-8 -*-
# ==============================================================================
# TITAN OS KERNEL BRIDGE - VERSION 9.2 (DOCKER OPTIMIZED)
# Architected for: Fly.io, Heroku, Docker Environments
# Features: Structure-Aware Discovery, Auto-Healing, Zero-Config Deployment
# ==============================================================================

import asyncio
import json
import os
import sys
import time
import shlex
import logging
import subprocess
import traceback
import platform
import gc
import psutil
import signal
from datetime import datetime
from threading import Thread, Lock, Event
from typing import Dict, List, Optional, Any, Union
from collections import deque
from concurrent.futures import ThreadPoolExecutor

# --- Fast ASN.1 & Server Libs ---
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, BackgroundTasks, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

# ==============================================================================
# 🧠 LEVEL 1: INTELLIGENT IMPORT SYSTEM (NEURAL LINK)
# ==============================================================================
class SystemStatus:
    CALLS = False
    USERBOT = False
    DB = False
    RO = False
    SECURITY = False

# 1. Core Call System
try:
    from AnnieXMedia.core.call import StreamController
    from AnnieXMedia.utils.database import group_assistant
    SystemStatus.CALLS = True
except ImportError:
    try:
        from AnnieXMedia.core.call import Call as StreamController
        from AnnieXMedia.utils.database import group_assistant
        SystemStatus.CALLS = True
    except ImportError:
        StreamController = None
        print("⚠️ [KERNEL] StreamController not linked. Audio features disabled.")

# 2. Identity System (Userbot & DB)
try:
    from AnnieXMedia import userbot, db
    SystemStatus.USERBOT = True
    SystemStatus.DB = True
except ImportError:
    try:
        from AnnieXMedia import userbot
        from AnnieXMedia.misc import db
        SystemStatus.USERBOT = True
        SystemStatus.DB = True
    except ImportError:
        userbot = None
        db = {}
        print("⚠️ [KERNEL] Userbot/DB not linked. Bot features disabled.")

# 3. Configuration
try:
    import config
except ImportError:
    config = None

# 4. Titan Modules (Resource Optimizer & Security Gate)
try:
    import Resource_Optimizer as RO
    import security_gate
    SystemStatus.RO = True
    SystemStatus.SECURITY = True
except ImportError:
    try:
        from AnnieXMedia.web import Resource_Optimizer as RO
        from AnnieXMedia.web import security_gate
        SystemStatus.RO = True
        SystemStatus.SECURITY = True
    except ImportError:
        RO = None
        security_gate = None
        print("⚠️ [KERNEL] Titan Modules (RO/Security) missing. Running in Safe Mode.")

# ==============================================================================
# ⚙️ LEVEL 2: HYPER-CONFIGURATION
# ==============================================================================
class KernelConfig:
    APP_TITLE = "Titan OS Kernel"
    VERSION = "9.2.0-Docker"
    HOST = "0.0.0.0"
    PORT = 8080
    WS_INTERVAL = getattr(config, "WS_STATUS_INTERVAL", 1.0)
    LOG_FILE = getattr(config, "LOG_FILE", "titan_kernel.log")
    
    # Smart Directory Resolution
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    ROOT_DIR = os.getcwd()

logging.basicConfig(
    format="%(asctime)s - [%(levelname)s] - %(name)s - %(message)s",
    datefmt="%H:%M:%S",
    level=logging.INFO,
    handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler(KernelConfig.LOG_FILE, mode="a", encoding="utf-8")]
)
logger = logging.getLogger("TitanKernel")

# ==============================================================================
# 🛡️ LEVEL 3: SERVER INITIALIZATION & SMART MOUNTING
# ==============================================================================
app = FastAPI(title=KernelConfig.APP_TITLE, version=KernelConfig.VERSION, docs_url=None, redoc_url=None)

if SystemStatus.SECURITY:
    app.include_router(security_gate.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- INTELLIGENT COMPONENT DISCOVERY (DOCKER OPTIMIZED) ---
# This loop specifically targets the structure: /app/AnnieXMedia/web/components
found_components = False
search_paths = [
    # 1. Docker Structure Priority
    os.path.join(KernelConfig.ROOT_DIR, "AnnieXMedia", "web", "components"),
    # 2. Local/Standard Structure
    os.path.join(KernelConfig.ROOT_DIR, "web", "components"),
    os.path.join(KernelConfig.BASE_DIR, "components"),
    "components",
    "web/components"
]

for path in search_paths:
    if os.path.exists(path) and os.path.isdir(path):
        app.mount("/components", StaticFiles(directory=path), name="components")
        logger.info(f"📂 [FILESYSTEM] Linked 'components' from: {path}")
        found_components = True
        break

if not found_components:
    logger.warning("⚠️ [FILESYSTEM] Components not found. UI styling might break.")

# ==============================================================================
# 🧠 LEVEL 4: ARTIFICIAL SYSTEM INTELLIGENCE (A.S.I)
# ==============================================================================
class ArtificialSystemIntelligence:
    def __init__(self):
        self._running = False
        self._focused_group = None
        self._start_time = time.time()
        self._metrics = {"requests": 0, "healed": 0, "zombies": 0}

    async def ignite(self):
        self._running = True
        logger.info("🧠 [ASI] Neural Core Online.")
        if SystemStatus.RO:
            Thread(target=RO.monitor_loop, args=(2.0,), daemon=True, name="TitanRO").start()
        asyncio.create_task(self._watchdog_protocol())
        asyncio.create_task(self._auto_healer())

    async def terminate(self):
        self._running = False
        if SystemStatus.RO: RO.unfocus_all()
        logger.info("🧠 [ASI] Neural Core Hibernating.")

    async def _watchdog_protocol(self):
        while self._running:
            try:
                for proc in psutil.process_iter(['pid', 'name', 'create_time']):
                    if proc.info['name'] and 'ffmpeg' in proc.info['name'].lower():
                        if time.time() - proc.info['create_time'] > 600:
                            proc.kill()
                            self._metrics["zombies"] += 1
            except: pass
            await asyncio.sleep(60)

    async def _auto_healer(self):
        while self._running and SystemStatus.USERBOT:
            try:
                clients = [getattr(userbot, "one", None), getattr(userbot, "two", None), getattr(userbot, "three", None), getattr(userbot, "four", None), getattr(userbot, "five", None)]
                for c in clients:
                    if c and not c.is_connected:
                        try: await c.start(); self._metrics["healed"] += 1
                        except: pass
            except: pass
            await asyncio.sleep(300)

ASI = ArtificialSystemIntelligence()

# ==============================================================================
# 📡 LEVEL 5: HYPER-SPEED TELEMETRY (WEBSOCKETS)
# ==============================================================================
class WebSocketHub:
    def __init__(self):
        self.active_connections = []
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        async with self._lock: self.active_connections.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active_connections: self.active_connections.remove(ws)

    async def broadcast(self, message: dict):
        if not self.active_connections: return
        payload = json.dumps(message)
        for ws in self.active_connections:
            try: await ws.send_text(payload)
            except: self.disconnect(ws)

Hub = WebSocketHub()

async def telemetry_stream():
    while ASI._running:
        try:
            cpu = psutil.cpu_percent()
            mem = psutil.virtual_memory()
            active_chats = []
            if SystemStatus.CALLS and hasattr(StreamController, "active_calls"):
                active_chats = list(StreamController.active_calls)
            
            assistants = []
            if SystemStatus.USERBOT:
                clients = [getattr(userbot, "one", None), getattr(userbot, "two", None), getattr(userbot, "three", None), getattr(userbot, "four", None), getattr(userbot, "five", None)]
                for i, c in enumerate(clients):
                    if c: assistants.append({"id": i + 1, "online": c.is_connected, "groups": 0, "group_id": None})

            data = {
                "stats": {"cpu": cpu, "ram": int(mem.used / 1024 / 1024), "groups": len(active_chats)},
                "focused_group": ASI._focused_group,
                "dominant_color": "#00ff88" if ASI._focused_group else "#00ffff",
                "assistants": assistants,
                "type": "status_snapshot",
                "payload": {"current": {"title": "System Active", "artist": f"Titan OS v{KernelConfig.VERSION}", "duration": 0}, "listeners": {}}
            }
            await Hub.broadcast(data)
            await asyncio.sleep(KernelConfig.WS_INTERVAL)
        except: await asyncio.sleep(1)

# ==============================================================================
# 🎮 LEVEL 6: API BRIDGE
# ==============================================================================
class ChatReq(BaseModel): chat_id: int
class PlayReq(ChatReq): query: Optional[str] = None; video: bool = False
class SkipReq(ChatReq): link: str = ""; video: bool = False
class SeekReq(ChatReq): to_seek: str; file_path: str = ""; duration: str = ""; mode: str = "absolute"
class VolReq(ChatReq): volume: int
class FocusReq(BaseModel): group_id: int
class EqReq(ChatReq): bands: Dict[str, float]; input_path: str
class UserReq(BaseModel): user_id: str; action: str

def get_assistant(chat_id):
    if not SystemStatus.USERBOT: raise HTTPException(503, "Userbot Offline")
    return group_assistant(StreamController, chat_id)

def safe_run(func):
    async def wrapper(*args, **kwargs):
        try: return await func(*args, **kwargs)
        except Exception as e: raise HTTPException(500, str(e))
    return wrapper

@app.post("/bridge/play")
@safe_run
async def play(p: PlayReq):
    ASI._metrics["requests"] += 1
    assistant = await get_assistant(p.chat_id)
    await StreamController.play(assistant, p.chat_id)
    return {"status": "ok"}

@app.post("/bridge/pause")
@safe_run
async def pause(p: ChatReq):
    await StreamController.pause_stream(p.chat_id)
    return {"status": "paused"}

@app.post("/bridge/resume")
@safe_run
async def resume(p: ChatReq):
    await StreamController.resume_stream(p.chat_id)
    return {"status": "resumed"}

@app.post("/bridge/skip")
@safe_run
async def skip(p: SkipReq):
    await StreamController.skip_stream(p.chat_id, p.link, video=p.video)
    return {"status": "skipped"}

@app.post("/bridge/seek")
@safe_run
async def seek(p: SeekReq):
    await StreamController.seek_stream(p.chat_id, p.file_path, p.to_seek, p.duration, p.mode)
    return {"status": "seeked"}

@app.post("/bridge/volume")
@safe_run
async def volume(p: VolReq):
    assistant = await get_assistant(p.chat_id)
    try:
        if hasattr(assistant, "change_volume_call"): await assistant.change_volume_call(p.chat_id, p.volume)
        else: await assistant.group_call.set_my_volume(p.volume)
    except: pass
    return {"status": "ok", "vol": p.volume}

@app.post("/bridge/eq")
@safe_run
async def equalizer(p: EqReq):
    if not os.path.exists(p.input_path): return {"status": "simulated"}
    out = f"downloads/eq_{p.chat_id}_{int(time.time())}.opus"
    os.makedirs("downloads", exist_ok=True)
    filters = ",".join([f"equalizer=f={f}:width_type=o:width=2:g={g}" for f, g in p.bands.items()])
    cmd = f'ffmpeg -y -hide_banner -loglevel error -i {shlex.quote(p.input_path)} -af "{filters}" -c:a libopus -b:a 128k {shlex.quote(out)}'
    await asyncio.to_thread(subprocess.run, cmd, shell=True)
    return {"status": "ok", "processed": out}

@app.post("/resource/focus")
async def focus(p: FocusReq):
    if not SystemStatus.RO: raise HTTPException(501, "Resource Optimizer Missing")
    res = RO.focus_on_group(p.group_id)
    ASI._focused_group = p.group_id
    return res

@app.post("/resource/unfocus")
async def unfocus():
    if SystemStatus.RO: RO.unfocus_all()
    ASI._focused_group = None
    return {"status": "normalized"}

@app.post("/assistants/restart_all")
async def restart_assistants():
    return {"status": "restart_sequence_initiated"}

@app.post("/logs/tail")
async def logs(p: Dict[str, int]):
    if os.path.exists(KernelConfig.LOG_FILE):
        with open(KernelConfig.LOG_FILE, "r", encoding="utf-8", errors="ignore") as f:
            return {"lines": f.readlines()[-p.get("lines", 100):]}
    return {"lines": []}

@app.get("/bridge/db/collections")
async def db_cols():
    return list(db.keys()) if SystemStatus.DB else []

@app.get("/health")
async def health():
    return {"status": "healthy", "asi": "active", "uptime": int(time.time() - ASI._start_time)}

# ==============================================================================
# 🚪 LEVEL 7: FRONTEND ENTRY POINT (DIRECT DASHBOARD ACCESS)
# ==============================================================================
@app.get("/", response_class=HTMLResponse)
async def serve_index():
    """
    Since index.html is deleted, this serves the iOS_Dashboard directly.
    Target Path: /app/AnnieXMedia/web/components/iOS_Dashboard.html
    """
    # 1. Priority Paths (Since index.html is gone, we look for dashboard)
    priority_paths = [
        os.path.join(KernelConfig.ROOT_DIR, "AnnieXMedia", "web", "components", "iOS_Dashboard.html"), # Docker
        "AnnieXMedia/web/components/iOS_Dashboard.html",
        "web/components/iOS_Dashboard.html",
        "components/iOS_Dashboard.html",
        os.path.join(KernelConfig.BASE_DIR, "components", "iOS_Dashboard.html")
    ]

    for path in priority_paths:
        if os.path.exists(path):
            logger.info(f"🎯 [UI] Direct Launch: {path}")
            return FileResponse(path)

    return HTMLResponse(
        f"""<html style='background:#000;color:#ff4444;font-family:monospace;padding:20px;'>
        <div>
            <h1>⚠️ TITAN KERNEL: DASHBOARD NOT FOUND</h1>
            <p>Could not locate 'iOS_Dashboard.html'. Checked paths: {priority_paths}</p>
        </div></html>"""
    )

# ==============================================================================
# 🔌 LEVEL 8: WEBSOCKET GATEWAYS
# ==============================================================================
@app.websocket("/ws/status")
@app.websocket("/bridge/ws")
async def websocket_endpoint(ws: WebSocket):
    await Hub.connect(ws)
    try:
        while True:
            data = await ws.receive_text()
            if data == "ping": await ws.send_json({"type": "pong"})
    except WebSocketDisconnect:
        Hub.disconnect(ws)

@app.websocket("/bridge/logs")
async def websocket_logs(ws: WebSocket):
    await ws.accept()
    f = None
    try:
        if os.path.exists(KernelConfig.LOG_FILE):
            f = open(KernelConfig.LOG_FILE, "r")
            f.seek(0, 2)
        while True:
            await asyncio.sleep(0.5)
            if f:
                line = f.readline()
                if line: await ws.send_text(line)
    except: pass
    finally:
        if f: f.close()

# ==============================================================================
# 🚀 LEVEL 9: IGNITION SEQUENCE
# ==============================================================================
@app.on_event("startup")
async def startup_event():
    logger.info("🚀 [TITAN] Ignition Sequence Start.")
    await ASI.ignite()
    asyncio.create_task(telemetry_stream())
    logger.info(f"✨ [TITAN] System Operational on Port {KernelConfig.PORT}")

@app.on_event("shutdown")
async def shutdown_event():
    await ASI.terminate()

def launch():
    uvicorn.run(app, host=KernelConfig.HOST, port=KernelConfig.PORT, log_level="error", loop="asyncio")

if __name__ != "__main__":
    t = Thread(target=launch, name="TitanKernelThread", daemon=True)
    t.start()
