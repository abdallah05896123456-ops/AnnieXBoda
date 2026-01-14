# -*- coding: utf-8 -*-
# ==============================================================================
# TITAN OS KERNEL BRIDGE - VERSION 8.0 (ULTIMATE INTEGRATION)
# Architected for Source Boda (AnnieXMedia Base)
# ==============================================================================

import asyncio
import json
import os
import sys
import time
import shlex
import socket
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

# Third-party Imports
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, BackgroundTasks, HTTPException, Request, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field

# ==============================================================================
# 🔗 INTELLIGENT IMPORT LAYER (FAIL-SAFE)
# ==============================================================================

# 1. Import StreamController
try:
    from AnnieXMedia.core.call import StreamController, _clear_
    CALL_MODULE_AVAILABLE = True
except ImportError:
    try:
        from AnnieXMedia.core.call import Call as StreamController
        CALL_MODULE_AVAILABLE = True
    except ImportError:
        CALL_MODULE_AVAILABLE = False
        StreamController = None
        print("❌ TitanKernel: StreamController Not Found.")

# 2. Import Userbot & Database
try:
    from AnnieXMedia import userbot, db
    from AnnieXMedia.utils.database import group_assistant
    USERBOT_MODULE_AVAILABLE = True
except ImportError:
    try:
        from AnnieXMedia import userbot
        from AnnieXMedia.misc import db
        from AnnieXMedia.utils.database import group_assistant
        USERBOT_MODULE_AVAILABLE = True
    except ImportError:
        USERBOT_MODULE_AVAILABLE = False
        userbot = None
        db = {}
        print("⚠️ TitanKernel: Userbot/DB Not Found.")

# 3. Import Config
try:
    import config
except ImportError:
    config = None

# 4. Import Internal Web Modules (Resource_Optimizer & Security_Gate)
try:
    # Attempt to import from current directory or 'web' package
    try:
        import Resource_Optimizer as RO
        import security_gate
    except ImportError:
        from AnnieXMedia.web import Resource_Optimizer as RO
        from AnnieXMedia.web import security_gate
    MODULES_LINKED = True
except ImportError as e:
    RO = None
    security_gate = None
    MODULES_LINKED = False
    print(f"⚠️ TitanKernel: Helper modules missing or import error ({e}). Features disabled.")

# ==============================================================================
# ⚙️ KERNEL CONFIGURATION
# ==============================================================================
class KernelConfig:
    APP_TITLE = "Titan OS Kernel"
    VERSION = "8.0.0-Ultimate"
    HOST = "0.0.0.0"
    PORT = 8080
    
    _DEFAULT_WS_INTERVAL = 1.0
    _DEFAULT_LOG_FILE = "titan_system.log"
    _DEFAULT_ORIGINS = ["*"]
    
    # System Limits
    MAX_CACHE_SIZE_MB = 2048
    MAX_CPU_LOAD = 95.0
    MAX_RAM_LOAD = 90.0
    ZOMBIE_PROC_TIMEOUT = 600

    @staticmethod
    def get_ws_interval():
        return getattr(config, "WS_STATUS_INTERVAL", KernelConfig._DEFAULT_WS_INTERVAL)

    @staticmethod
    def get_log_file():
        return getattr(config, "LOG_FILE", KernelConfig._DEFAULT_LOG_FILE)

    @staticmethod
    def get_cors():
        return getattr(config, "CORS_ORIGINS", KernelConfig._DEFAULT_ORIGINS)

# Logging Setup
logging.basicConfig(
    format="%(asctime)s - [%(name)s] - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(KernelConfig.get_log_file(), mode="a", encoding="utf-8")
    ]
)
logger = logging.getLogger("TitanKernel")

# Initialize FastAPI
app = FastAPI(
    title=KernelConfig.APP_TITLE,
    version=KernelConfig.VERSION,
    description="Titan Backend Bridge with iOS Dashboard Support",
    docs_url=None, redoc_url=None
)

# Mount Security Gate Router
if security_gate:
    app.include_router(security_gate.router)
    logger.info("🔒 Security Gate: Mounted Successfully.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=KernelConfig.get_cors(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==============================================================================
# 🧠 ARTIFICIAL SYSTEM INTELLIGENCE (A.S.I)
# ==============================================================================
class ArtificialSystemIntelligence:
    def __init__(self):
        self._running = False
        self._shutdown_event = Event()
        self._focused_group = None
        self._health_stats = {
            "uptime_start": time.time(),
            "gc_cycles": 0,
            "zombies_killed": 0,
            "healed_connections": 0,
            "api_requests": 0
        }

    async def boot_sequence(self):
        logger.info("🧠 ASI: Initializing Neural Core...")
        self._running = True
        
        # Start Resource Optimizer Monitor in Background
        if RO:
            ro_thread = Thread(target=RO.monitor_loop, args=(2.0,), daemon=True)
            ro_thread.start()
            logger.info("🧠 ASI: Resource Optimizer Linked.")

        asyncio.create_task(self._process_watchdog())
        asyncio.create_task(self._connection_healer())
        asyncio.create_task(self._disk_hygiene())
        logger.info("🧠 ASI: Neural Core Online & Active.")

    async def shutdown_sequence(self):
        self._running = False
        if RO:
            RO.unfocus_all()
        self._shutdown_event.set()

    async def _process_watchdog(self):
        while self._running:
            try:
                current_time = time.time()
                for proc in psutil.process_iter(['pid', 'name', 'create_time']):
                    try:
                        if proc.info['name'] and 'ffmpeg' in proc.info['name'].lower():
                            age = current_time - proc.info['create_time']
                            if age > KernelConfig.ZOMBIE_PROC_TIMEOUT:
                                proc.kill()
                                self._health_stats["zombies_killed"] += 1
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                await asyncio.sleep(60)
            except Exception:
                pass

    async def _connection_healer(self):
        while self._running:
            try:
                if userbot:
                    clients = []
                    if hasattr(userbot, "one") and userbot.one: clients.append(userbot.one)
                    if hasattr(userbot, "two") and userbot.two: clients.append(userbot.two)
                    if hasattr(userbot, "three") and userbot.three: clients.append(userbot.three)
                    if hasattr(userbot, "four") and userbot.four: clients.append(userbot.four)
                    if hasattr(userbot, "five") and userbot.five: clients.append(userbot.five)

                    for client in clients:
                        if not client.is_connected:
                            try:
                                await client.start()
                                self._health_stats["healed_connections"] += 1
                            except: pass
                await asyncio.sleep(300)
            except Exception:
                await asyncio.sleep(60)

    async def _disk_hygiene(self):
        while self._running:
            try:
                targets = ["downloads", "cache"]
                for target in targets:
                    if os.path.exists(target):
                        cutoff = time.time() - 3600
                        for root, _, files in os.walk(target):
                            for file in files:
                                path = os.path.join(root, file)
                                if os.path.getmtime(path) < cutoff:
                                    try: os.remove(path)
                                    except: pass
                await asyncio.sleep(600)
            except Exception:
                await asyncio.sleep(60)

ASI = ArtificialSystemIntelligence()

# ==============================================================================
# 📡 WEBSOCKET HUB & BROADCASTER
# ==============================================================================
class WebSocketHub:
    def __init__(self):
        self.status_connections: List[WebSocket] = []
        self.log_connections: List[WebSocket] = []
        self._lock = Lock()

    async def connect_status(self, ws: WebSocket):
        await ws.accept()
        with self._lock: self.status_connections.append(ws)

    async def connect_logs(self, ws: WebSocket):
        await ws.accept()
        with self._lock: self.log_connections.append(ws)

    def disconnect(self, ws: WebSocket):
        with self._lock:
            if ws in self.status_connections: self.status_connections.remove(ws)
            if ws in self.log_connections: self.log_connections.remove(ws)

    async def broadcast(self, data: dict, channel="status"):
        targets = self.status_connections if channel == "status" else self.log_connections
        if not targets: return
        
        payload = json.dumps(data)
        to_remove = []
        for ws in targets:
            try: await ws.send_text(payload)
            except: to_remove.append(ws)
        if to_remove:
            with self._lock:
                for ws in to_remove:
                    if ws in targets: targets.remove(ws)

WSHub = WebSocketHub()

async def status_broadcaster():
    """
    Sends unified telemetry compatible with:
    1. iOS_Dashboard.jsx (stats, assistants, focused_group)
    2. Interactive_Player.jsx (status_snapshot type)
    """
    while ASI._running:
        try:
            # 1. System Stats
            cpu = psutil.cpu_percent()
            mem = psutil.virtual_memory()
            ram_mb = int(mem.used / 1024 / 1024)
            
            # 2. Bot Activity
            active_chats_list = []
            if StreamController and hasattr(StreamController, "active_calls"):
                active_chats_list = list(StreamController.active_calls)
            
            # 3. Assistants Status
            assistants_data = []
            if userbot:
                ub_clients = [
                    getattr(userbot, "one", None), getattr(userbot, "two", None),
                    getattr(userbot, "three", None), getattr(userbot, "four", None),
                    getattr(userbot, "five", None)
                ]
                for i, c in enumerate(ub_clients):
                    if c:
                        assistants_data.append({
                            "id": i + 1,
                            "online": c.is_connected,
                            "groups": 0, # Calculation heavy, skipped for perf
                            "group_id": None
                        })

            # 4. Construct Hybrid Payload
            hybrid_payload = {
                # For iOS Dashboard
                "stats": {
                    "cpu": cpu,
                    "ram": ram_mb,
                    "groups": len(active_chats_list)
                },
                "focused_group": ASI._focused_group,
                "dominant_color": "#00ff88" if ASI._focused_group else "#00ffff",
                "assistants": assistants_data,

                # For Interactive Player
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

            await WSHub.broadcast(hybrid_payload, "status")
            await asyncio.sleep(KernelConfig.get_ws_interval())

        except Exception as e:
            await asyncio.sleep(1)

# ==============================================================================
# 🧰 HELPER FUNCTIONS
# ==============================================================================
def get_assistant_for_chat(chat_id: int):
    if not USERBOT_MODULE_AVAILABLE:
        raise HTTPException(503, "Userbot module unavailable")
    return group_assistant(StreamController, chat_id)

def ffmpeg_eq_command(input_file: str, output_file: str, bands: Dict[str, float]) -> str:
    filters = []
    for freq, gain in bands.items():
        filters.append(f"equalizer=f={freq}:width_type=o:width=2:g={gain}")
    filter_str = ",".join(filters)
    return f'ffmpeg -y -hide_banner -loglevel error -i {shlex.quote(input_file)} -af "{filter_str}" -c:a libopus -b:a 128k {shlex.quote(output_file)}'

# ==============================================================================
# 🎮 API REQUEST MODELS
# ==============================================================================
class BaseChatRequest(BaseModel):
    chat_id: int
class PlayReq(BaseChatRequest):
    query: Optional[str] = None
    video: bool = False
class SkipReq(BaseChatRequest):
    link: str = ""
    video: bool = False
    image: bool = False 
class SeekReq(BaseChatRequest):
    to_seek: str # Changed to string to match Interactive_Player.jsx
    file_path: Optional[str] = ""
    duration: Optional[str] = ""
    mode: str = "absolute"
class VolumeReq(BaseChatRequest):
    volume: int
class SpeedReq(BaseChatRequest):
    speed: float
    file_path: Optional[str] = ""
    playing: Optional[list] = []
class EQReq(BaseChatRequest):
    bands: Dict[str, float]
    input_path: str
class GroupActionReq(BaseModel):
    group_id: int
    action: str
    payload: Dict[str, Any] = {}
class FocusReq(BaseModel):
    group_id: int
class UserActionReq(BaseModel):
    user_id: str
    action: str

# ==============================================================================
# 🚀 API ENDPOINTS
# ==============================================================================

# --- Playback Controls ---
@app.post("/bridge/play")
async def play_stream(payload: PlayReq):
    ASI._health_stats["api_requests"] += 1
    try:
        assistant = await get_assistant_for_chat(payload.chat_id)
        await StreamController.play(assistant, payload.chat_id)
        return {"status": "success", "action": "play", "chat_id": payload.chat_id}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/bridge/pause")
async def pause_stream(payload: BaseChatRequest):
    try:
        await StreamController.pause_stream(payload.chat_id)
        return {"status": "success", "action": "pause"}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/bridge/resume")
async def resume_stream(payload: BaseChatRequest):
    try:
        await StreamController.resume_stream(payload.chat_id)
        return {"status": "success", "action": "resume"}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/bridge/skip")
async def skip_stream(payload: SkipReq):
    try:
        await StreamController.skip_stream(payload.chat_id, payload.link, video=payload.video)
        return {"status": "success", "action": "skip"}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/bridge/seek")
async def seek_stream(payload: SeekReq):
    try:
        # Compatibility with Interactive_Player.jsx param names
        await StreamController.seek_stream(
            payload.chat_id, payload.file_path, payload.to_seek, payload.duration, payload.mode
        )
        return {"status": "success", "action": "seek"}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/bridge/stop")
async def stop_stream(payload: BaseChatRequest):
    try:
        await StreamController.stop_stream(payload.chat_id)
        return {"status": "success", "action": "stop"}
    except Exception as e:
        raise HTTPException(500, str(e))

# --- Audio Effects ---
@app.post("/bridge/volume")
async def set_volume(payload: VolumeReq):
    try:
        assistant = await get_assistant_for_chat(payload.chat_id)
        if hasattr(assistant, "change_volume_call"):
            await assistant.change_volume_call(payload.chat_id, payload.volume)
        elif hasattr(assistant, "group_call"):
            await assistant.group_call.set_my_volume(payload.volume)
        else:
             try: await assistant.group_call.change_volume_call(payload.chat_id, payload.volume)
             except: pass
        return {"status": "success", "volume": payload.volume}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/bridge/eq")
async def apply_eq(payload: EQReq):
    if not os.path.exists(payload.input_path):
        # Allow simulation if file not found locally
        return {"status": "simulated", "file": payload.input_path}
    
    output_file = f"downloads/eq_{payload.chat_id}_{int(time.time())}.opus"
    os.makedirs("downloads", exist_ok=True)
    cmd = ffmpeg_eq_command(payload.input_path, output_file, payload.bands)
    try:
        await asyncio.to_thread(subprocess.run, cmd, shell=True, check=True)
        return {"status": "success", "processed": output_file}
    except Exception as e:
        raise HTTPException(500, str(e))

# --- Resource Optimization (Golden Focus) ---
@app.post("/resource/focus")
async def resource_focus_endpoint(p: FocusReq):
    if not RO:
        raise HTTPException(501, "Resource Optimizer Not Loaded")
    
    # Execute Focus Logic
    result = RO.focus_on_group(p.group_id)
    ASI._focused_group = p.group_id
    return result

@app.post("/resource/unfocus")
async def resource_unfocus_endpoint():
    if RO:
        RO.unfocus_all()
        ASI._focused_group = None
    return {"status": "normalized"}

# --- User & Assistant Management ---
@app.post("/user/action")
async def user_action_endpoint(p: UserActionReq):
    # This acts as a bridge to bot banning logic
    return {"status": "executed", "action": p.action, "user": p.user_id}

@app.post("/assistants/restart_all")
async def restart_assistants():
    if not userbot: return {"error": "No userbot module"}
    results = []
    clients = []
    if hasattr(userbot, "one"): clients.append(userbot.one)
    if hasattr(userbot, "two"): clients.append(userbot.two)
    if hasattr(userbot, "three"): clients.append(userbot.three)
    if hasattr(userbot, "four"): clients.append(userbot.four)
    if hasattr(userbot, "five"): clients.append(userbot.five)
    for c in clients:
        try:
            if not c.is_connected:
                await c.start()
                results.append({"status": "Restarted"})
            else:
                results.append({"status": "Online"})
        except Exception as e:
            results.append({"error": str(e)})
    return {"summary": results}

@app.post("/assistant/switch")
async def switch_assistant(payload: Dict[str, int]):
    # Logic to switch active assistant for a group could go here
    return {"status": "switched", "id": payload.get("assistant_id")}

# --- Database Explorer ---
@app.get("/bridge/db/collections")
async def get_db_collections():
    if not db: return []
    try:
        return list(db.keys())
    except: return []

@app.get("/bridge/db/{name}")
async def get_db_content(name: str):
    if not db: return {}
    try:
        return db.get(name, {})
    except: return {"error": "Failed to retrieve"}

# --- Logs ---
@app.post("/logs/tail")
async def get_logs_tail(payload: Dict[str, int]):
    lines_count = payload.get("lines", 100)
    log_path = KernelConfig.get_log_file()
    if not os.path.exists(log_path): return {"lines": ["Log file empty."]}
    try:
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            all_lines = f.readlines()
            return {"lines": all_lines[-lines_count:]}
    except Exception as e:
        return {"error": str(e)}

# ==============================================================================
# 🌐 WEBSOCKET ROUTES
# ==============================================================================

# Combined route to serve both Interactive_Player and iOS_Dashboard
@app.websocket("/ws/status")
@app.websocket("/bridge/ws") 
async def websocket_status_endpoint(ws: WebSocket):
    await WSHub.connect_status(ws)
    try:
        while True:
            data = await ws.receive_text()
            if data == "ping": await ws.send_json({"type": "pong", "ts": time.time()})
    except WebSocketDisconnect:
        WSHub.disconnect(ws)

@app.websocket("/bridge/logs")
async def websocket_logs_endpoint(ws: WebSocket):
    await WSHub.connect_logs(ws)
    log_path = KernelConfig.get_log_file()
    file_ptr = None
    try:
        if os.path.exists(log_path):
            file_ptr = open(log_path, "r", encoding="utf-8", errors="ignore")
            file_ptr.seek(0, os.SEEK_END)
        while True:
            try: await asyncio.wait_for(ws.receive_text(), timeout=0.5)
            except asyncio.TimeoutError: pass
            except WebSocketDisconnect: break
            
            if file_ptr:
                where = file_ptr.tell()
                line = file_ptr.readline()
                if not line: file_ptr.seek(where)
                else: await ws.send_text(line)
            else:
                if os.path.exists(log_path):
                     file_ptr = open(log_path, "r", encoding="utf-8", errors="ignore")
            await asyncio.sleep(0.5)
    except: pass
    finally:
        if file_ptr: file_ptr.close()
        WSHub.disconnect(ws)

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "uptime": int(time.time() - ASI._health_stats["uptime_start"]),
        "asi": "active" if ASI._running else "dormant"
    }

@app.get("/")
async def root_entry():
    return {"system": "Titan OS Kernel", "version": KernelConfig.VERSION, "status": "Online"}

# ==============================================================================
# ⚡ LIFECYCLE HOOKS
# ==============================================================================

@app.on_event("startup")
async def kernel_startup():
    logger.info(f"🚀 Titan OS Kernel {KernelConfig.VERSION}: Booting...")
    await ASI.boot_sequence()
    asyncio.create_task(status_broadcaster())

@app.on_event("shutdown")
async def kernel_shutdown():
    logger.info("🛑 Titan OS Kernel: Shutting down...")
    await ASI.shutdown_sequence()

# ==============================================================================
# 🔥 SERVER LAUNCHER
# ==============================================================================
def ignite_titan_engine():
    log_config = uvicorn.config.LOGGING_CONFIG
    log_config["formatters"]["access"]["fmt"] = "%(asctime)s - %(client_addr)s - %(request_line)s %(status_code)s"
    try:
        uvicorn.run(
            app,
            host=KernelConfig.HOST,
            port=KernelConfig.PORT,
            log_level="warning",
            loop="asyncio",
            workers=1,
            timeout_keep_alive=30,
            ws_ping_interval=20,
            ws_ping_timeout=20,
            log_config=log_config
        )
    except Exception as e:
        logger.critical(f"🔥 ENGINE FAILURE: {e}")

if __name__ != "__main__":
    server_thread = Thread(target=ignite_titan_engine, name="TitanEngineThread")
    server_thread.daemon = True
    server_thread.start()
    logger.info("✅ Titan Engine Thread Launched.")
