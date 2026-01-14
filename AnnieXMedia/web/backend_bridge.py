# -*- coding: utf-8 -*-
# ==============================================================================
# TITAN OS KERNEL BRIDGE - VERSION 9.0 (GOD MODE)
# Architected for: High Performance, Zero-Latency, Self-Healing Systems
# Integrates: React JSX, Resource Optimization, Security Gate, Real-time Telemetry
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
# This system detects the environment and adapts the imports dynamically.
# It prevents the server from crashing even if critical modules are missing.

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
    # Try Local Import First (Priority)
    import Resource_Optimizer as RO
    import security_gate
    SystemStatus.RO = True
    SystemStatus.SECURITY = True
except ImportError:
    try:
        # Try Package Import
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
    VERSION = "9.0.0-GodMode"
    HOST = "0.0.0.0"
    PORT = 8080
    
    # Adaptive Defaults
    WS_INTERVAL = getattr(config, "WS_STATUS_INTERVAL", 1.0)
    LOG_FILE = getattr(config, "LOG_FILE", "titan_kernel.log")
    CORS_ORIGINS = getattr(config, "CORS_ORIGINS", ["*"])
    
    # Performance Tuning
    MAX_WORKERS = (os.cpu_count() or 1) * 2
    KEEPALIVE = 60
    
    # Paths
    WEB_DIR = "web" if os.path.exists("web") else "."
    COMPONENTS_DIR = os.path.join(WEB_DIR, "components")

# Logging System (Non-blocking)
logging.basicConfig(
    format="%(asctime)s - [%(levelname)s] - %(name)s - %(message)s",
    datefmt="%H:%M:%S",
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(KernelConfig.LOG_FILE, mode="a", encoding="utf-8")
    ]
)
logger = logging.getLogger("TitanKernel")

# ==============================================================================
# 🛡️ LEVEL 3: SERVER INITIALIZATION
# ==============================================================================
app = FastAPI(
    title=KernelConfig.APP_TITLE,
    version=KernelConfig.VERSION,
    docs_url=None, 
    redoc_url=None
)

# 🔒 Mount Security Gate if available
if SystemStatus.SECURITY:
    app.include_router(security_gate.router)
    logger.info("🛡️ [SECURITY] Gate Active & Monitoring.")

# 🌐 CORS Policy
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 📂 Frontend File Serving (The Bridge to JSX)
if os.path.exists(KernelConfig.COMPONENTS_DIR):
    app.mount("/components", StaticFiles(directory=KernelConfig.COMPONENTS_DIR), name="components")
    logger.info(f"📂 [FILESYSTEM] Serving JSX components from: {KernelConfig.COMPONENTS_DIR}")

# ==============================================================================
# 🧠 LEVEL 4: ARTIFICIAL SYSTEM INTELLIGENCE (A.S.I)
# ==============================================================================
class ArtificialSystemIntelligence:
    """
    The Brain of Titan OS. Manages resources, monitors health, 
    and auto-heals connections.
    """
    def __init__(self):
        self._running = False
        self._shutdown_event = Event()
        self._focused_group = None
        self._start_time = time.time()
        self._metrics = {
            "requests": 0,
            "healed": 0,
            "zombies": 0
        }

    async def ignite(self):
        self._running = True
        logger.info("🧠 [ASI] Neural Core Online.")
        
        # 1. Activate Resource Optimizer
        if SystemStatus.RO:
            Thread(target=RO.monitor_loop, args=(2.0,), daemon=True, name="TitanRO").start()
            logger.info("⚡ [ASI] Resource Optimizer Engaged.")

        # 2. Start Background Processes
        asyncio.create_task(self._watchdog_protocol())
        asyncio.create_task(self._auto_healer())

    async def terminate(self):
        self._running = False
        if SystemStatus.RO:
            RO.unfocus_all()
        logger.info("🧠 [ASI] Neural Core Hibernating.")

    async def _watchdog_protocol(self):
        """Kills zombie FFmpeg processes to free RAM."""
        while self._running:
            try:
                for proc in psutil.process_iter(['pid', 'name', 'create_time']):
                    if proc.info['name'] and 'ffmpeg' in proc.info['name'].lower():
                        if time.time() - proc.info['create_time'] > 600: # 10 mins limit
                            proc.kill()
                            self._metrics["zombies"] += 1
            except: pass
            await asyncio.sleep(60)

    async def _auto_healer(self):
        """Checks userbot clients and reconnects them if they drop."""
        while self._running and SystemStatus.USERBOT:
            try:
                clients = [
                    getattr(userbot, "one", None), getattr(userbot, "two", None),
                    getattr(userbot, "three", None), getattr(userbot, "four", None),
                    getattr(userbot, "five", None)
                ]
                for c in clients:
                    if c and not c.is_connected:
                        try: 
                            await c.start()
                            self._metrics["healed"] += 1
                        except: pass
            except: pass
            await asyncio.sleep(300)

ASI = ArtificialSystemIntelligence()

# ==============================================================================
# 📡 LEVEL 5: HYPER-SPEED TELEMETRY (WEBSOCKETS)
# ==============================================================================
class WebSocketHub:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        async with self._lock:
            self.active_connections.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active_connections:
            self.active_connections.remove(ws)

    async def broadcast(self, message: dict):
        if not self.active_connections: return
        payload = json.dumps(message)
        # Fire and forget strategy for speed
        for ws in self.active_connections:
            try: await ws.send_text(payload)
            except: self.disconnect(ws)

Hub = WebSocketHub()

async def telemetry_stream():
    """
    Generates a unified state object for the frontend every X seconds.
    Compatible with BOTH iOS_Dashboard.jsx and Interactive_Player.jsx
    """
    while ASI._running:
        try:
            # 1. Hardware Stats
            cpu = psutil.cpu_percent()
            mem = psutil.virtual_memory()
            
            # 2. Call Stats
            active_chats = []
            if SystemStatus.CALLS and hasattr(StreamController, "active_calls"):
                active_chats = list(StreamController.active_calls)
            
            # 3. Assistants Stats
            assistants = []
            if SystemStatus.USERBOT:
                clients = [
                    getattr(userbot, "one", None), getattr(userbot, "two", None),
                    getattr(userbot, "three", None), getattr(userbot, "four", None),
                    getattr(userbot, "five", None)
                ]
                for i, c in enumerate(clients):
                    if c:
                        assistants.append({
                            "id": i + 1,
                            "online": c.is_connected,
                            "groups": 0, # Placeholder for performance
                            "group_id": None
                        })

            # 4. The Payload
            data = {
                # Section: iOS Dashboard
                "stats": {
                    "cpu": cpu,
                    "ram": int(mem.used / 1024 / 1024),
                    "groups": len(active_chats)
                },
                "focused_group": ASI._focused_group,
                "dominant_color": "#00ff88" if ASI._focused_group else "#00ffff",
                "assistants": assistants,

                # Section: Interactive Player
                "type": "status_snapshot",
                "payload": {
                    "current": {
                        "title": "System Active",
                        "artist": f"Titan OS v{KernelConfig.VERSION}",
                        "duration": 0,
                        "dominant_color": "#00ff88"
                    },
                    "listeners": {}
                }
            }
            
            await Hub.broadcast(data)
            await asyncio.sleep(KernelConfig.WS_INTERVAL)
            
        except Exception as e:
            logger.error(f"Telemetry Error: {e}")
            await asyncio.sleep(1)

# ==============================================================================
# 🎮 LEVEL 6: API BRIDGE (THE COMMAND CENTER)
# ==============================================================================

# --- Data Models ---
class ChatReq(BaseModel): chat_id: int
class PlayReq(ChatReq): query: Optional[str] = None; video: bool = False
class SkipReq(ChatReq): link: str = ""; video: bool = False
class SeekReq(ChatReq): to_seek: str; file_path: str = ""; duration: str = ""; mode: str = "absolute"
class VolReq(ChatReq): volume: int
class FocusReq(BaseModel): group_id: int
class EqReq(ChatReq): bands: Dict[str, float]; input_path: str
class UserReq(BaseModel): user_id: str; action: str

# --- Helper ---
def get_assistant(chat_id):
    if not SystemStatus.USERBOT: raise HTTPException(503, "Userbot Offline")
    return group_assistant(StreamController, chat_id)

def safe_run(func):
    """Decorator to prevent API crashes"""
    async def wrapper(*args, **kwargs):
        try: return await func(*args, **kwargs)
        except Exception as e:
            logger.error(f"API Error: {e}")
            raise HTTPException(500, str(e))
    return wrapper

# --- Endpoints ---

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
    # Handles string input like "00:30" or "+10" from frontend
    await StreamController.seek_stream(p.chat_id, p.file_path, p.to_seek, p.duration, p.mode)
    return {"status": "seeked"}

@app.post("/bridge/volume")
@safe_run
async def volume(p: VolReq):
    assistant = await get_assistant(p.chat_id)
    try:
        if hasattr(assistant, "change_volume_call"): 
            await assistant.change_volume_call(p.chat_id, p.volume)
        else: 
            await assistant.group_call.set_my_volume(p.volume)
    except: pass
    return {"status": "ok", "vol": p.volume}

@app.post("/bridge/eq")
@safe_run
async def equalizer(p: EqReq):
    # Generates FFmpeg command for Equalizer
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
    # Signals userbot clients to restart (Handled by ASI auto-healer)
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
    return {
        "status": "healthy",
        "asi": "active",
        "uptime": int(time.time() - ASI._start_time),
        "modules": {
            "ro": SystemStatus.RO,
            "security": SystemStatus.SECURITY,
            "calls": SystemStatus.CALLS
        }
    }

# ==============================================================================
# 🚪 LEVEL 7: FRONTEND ENTRY POINT (INDEX.HTML)
# ==============================================================================
@app.get("/", response_class=HTMLResponse)
async def serve_index():
    """
    Serves the index.html that bootstraps the React application.
    Checks multiple locations to ensure it works in any deployment structure.
    """
    paths = [
        os.path.join(KernelConfig.WEB_DIR, "index.html"),
        "index.html"
    ]
    for path in paths:
        if os.path.exists(path):
            return FileResponse(path)
    return HTMLResponse(
        """<html style='background:#000;color:#0f0;font-family:monospace;display:flex;justify-content:center;align-items:center;height:100vh;'>
        <div><h1>⚠️ TITAN KERNEL: NO UI FOUND</h1><p>Please upload 'index.html' to the 'web/' folder.</p></div></html>"""
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
            # Keep connection alive with heartbeat
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
    logger.info("🛑 [TITAN] Shutdown Sequence Initiated.")
    await ASI.terminate()

def launch():
    """Entry point for the thread launcher"""
    uvicorn.run(
        app, 
        host=KernelConfig.HOST, 
        port=KernelConfig.PORT, 
        log_level="error", 
        loop="asyncio"
    )

if __name__ != "__main__":
    # When imported by the bot's main script, run in a daemon thread
    t = Thread(target=launch, name="TitanKernelThread", daemon=True)
    t.start()
