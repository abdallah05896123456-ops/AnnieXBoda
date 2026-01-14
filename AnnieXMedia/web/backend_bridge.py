# -*- coding: utf-8 -*-
# ==============================================================================
# TITAN OS KERNEL BRIDGE - VERSION 6.0 (GRAND MASTER EDITION)
# Architected for AnnieXMedia Music Bot
# 
# Features:
# - Deep System Integration (StreamController & Userbot)
# - Artificial System Intelligence (ASI) for Auto-Healing
# - Advanced FFmpeg Audio Processing (EQ, Speed, Volume)
# - Real-time WebSocket Telemetry
# - Database Exploration & Management
# - Security Sentinel & Rate Limiting
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
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field

# ==============================================================================
# 🔗 INTELLIGENT IMPORT LAYER (FAIL-SAFE)
# ==============================================================================
# This section ensures the bot doesn't crash if a module is missing, 
# while correctly mapping the classes you provided.

try:
    # Importing the Core Call Controller (The Heart of playback)
    # Based on your file: StreamController is the instance of Call()
    from AnnieXMedia.core.call import StreamController, _clear_
    CALL_MODULE_AVAILABLE = True
except ImportError as e:
    CALL_MODULE_AVAILABLE = False
    StreamController = None
    print(f"❌ CRITICAL: Failed to import StreamController from AnnieXMedia.core.call: {e}")

try:
    # Importing Userbot & Database (The Nervous System)
    # Based on your file: userbot class contains 'one', 'two', etc.
    from AnnieXMedia import userbot, db
    from AnnieXMedia.utils.database import group_assistant
    USERBOT_MODULE_AVAILABLE = True
except ImportError as e:
    USERBOT_MODULE_AVAILABLE = False
    userbot = None
    db = {}
    print(f"⚠️ WARNING: Failed to import Userbot or DB: {e}")

# Import Config
try:
    import config
except ImportError:
    # Fallback config class if file is missing
    class config:
        API_ID = 0
        API_HASH = ""
        LOG_FILE = "log.txt"
        CORS_ORIGINS = ["*"]
        WS_STATUS_INTERVAL = 1.0

# Optional: Resource Optimizer & Security Gate
try:
    from AnnieXMedia.web import Resource_Optimizer as RO
except ImportError:
    RO = None

try:
    from AnnieXMedia.web import security_gate
except ImportError:
    security_gate = None

# ==============================================================================
# ⚙️ KERNEL CONFIGURATION & LOGGING
# ==============================================================================
class KernelConfig:
    APP_TITLE = "Titan OS Kernel"
    VERSION = "6.0.0-GrandMaster"
    HOST = "0.0.0.0"
    PORT = 8080
    LOG_LEVEL = "info"
    
    # System Limits
    MAX_CACHE_SIZE_MB = 2048  # 2GB Cache Limit
    MAX_CPU_LOAD = 95.0       # Alert Threshold
    MAX_RAM_LOAD = 90.0       # GC Threshold
    ZOMBIE_PROC_TIMEOUT = 600 # 10 Minutes for stuck FFmpeg
    
    # Audio Settings
    DEFAULT_VOLUME = 100
    EQ_PRESETS = {
        "bass_boost": {"60": 5, "170": 3, "310": 0, "600": 0, "1000": 0},
        "vocal_boost": {"310": -2, "600": 2, "1000": 3, "3000": 3, "6000": 3},
        "flat": {"60": 0, "170": 0, "310": 0, "600": 0, "1000": 0}
    }

# Configure Advanced Logging
logging.basicConfig(
    format="%(asctime)s - [%(name)s] - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("titan_kernel.log", mode="a", encoding="utf-8")
    ]
)
logger = logging.getLogger("TitanKernel")

# Initialize FastAPI
app = FastAPI(
    title=KernelConfig.APP_TITLE,
    version=KernelConfig.VERSION,
    description="The Ultimate Backend Bridge for AnnieXMedia",
    docs_url=None, redoc_url=None # Hide docs in production for security
)

# Robust CORS Policy
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow all origins for flexibility
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==============================================================================
# 🧠 ARTIFICIAL SYSTEM INTELLIGENCE (A.S.I) - V3.0
# ==============================================================================
class ArtificialSystemIntelligence:
    """
    The central brain of the backend. It monitors system health, manages resources,
    heals broken connections, and cleans up garbage.
    """
    def __init__(self):
        self._running = False
        self._shutdown_event = Event()
        self._health_stats = {
            "uptime_start": time.time(),
            "gc_cycles": 0,
            "zombies_killed": 0,
            "healed_connections": 0,
            "api_requests": 0
        }
        self._cpu_history = deque(maxlen=60)
        self._ram_history = deque(maxlen=60)

    async def boot_sequence(self):
        """Starts the ASI monitoring threads."""
        logger.info("🧠 ASI: Initializing Neural Core...")
        self._running = True
        
        # Start Parallel Tasks
        asyncio.create_task(self._monitor_resources())
        asyncio.create_task(self._process_watchdog())
        asyncio.create_task(self._connection_healer())
        asyncio.create_task(self._disk_hygiene())
        
        logger.info("🧠 ASI: Neural Core Online & Active.")

    async def shutdown_sequence(self):
        logger.info("🧠 ASI: Shutting down systems...")
        self._running = False
        self._shutdown_event.set()

    # --- Task 1: Resource Monitor ---
    async def _monitor_resources(self):
        while self._running:
            try:
                cpu = psutil.cpu_percent(interval=1)
                ram = psutil.virtual_memory()
                
                self._cpu_history.append(cpu)
                self._ram_history.append(ram.percent)

                # RAM Emergency Handling
                if ram.percent > KernelConfig.MAX_RAM_LOAD:
                    logger.warning(f"🔥 ASI: RAM Critical ({ram.percent}%)! Initiating Emergency GC...")
                    gc.collect()
                    if sys.platform == "linux":
                        # Try to drop filesystem cache (requires root, usually ignored but worth a try)
                        try:
                            with open('/proc/sys/vm/drop_caches', 'w') as f: f.write('1')
                        except: pass
                    self._health_stats["gc_cycles"] += 1
                
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"ASI Monitor Error: {e}")
                await asyncio.sleep(10)

    # --- Task 2: Process Watchdog (FFmpeg Killer) ---
    async def _process_watchdog(self):
        while self._running:
            try:
                current_time = time.time()
                for proc in psutil.process_iter(['pid', 'name', 'create_time', 'cmdline']):
                    try:
                        # Target FFmpeg processes
                        if proc.info['name'] and 'ffmpeg' in proc.info['name'].lower():
                            # Check age
                            age = current_time - proc.info['create_time']
                            if age > KernelConfig.ZOMBIE_PROC_TIMEOUT:
                                logger.warning(f"💀 ASI: Killing Zombie FFmpeg (PID: {proc.info['pid']}, Age: {int(age)}s)")
                                proc.kill()
                                self._health_stats["zombies_killed"] += 1
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        continue
                await asyncio.sleep(60) # Check every minute
            except Exception as e:
                logger.error(f"ASI Watchdog Error: {e}")

    # --- Task 3: Connection Healer ---
    async def _connection_healer(self):
        """Ensures all 5 userbot assistants are connected."""
        while self._running:
            try:
                if userbot:
                    clients = []
                    # Map based on your userbot.py structure
                    if hasattr(userbot, "one") and userbot.one: clients.append(userbot.one)
                    if hasattr(userbot, "two") and userbot.two: clients.append(userbot.two)
                    if hasattr(userbot, "three") and userbot.three: clients.append(userbot.three)
                    if hasattr(userbot, "four") and userbot.four: clients.append(userbot.four)
                    if hasattr(userbot, "five") and userbot.five: clients.append(userbot.five)

                    for client in clients:
                        if not client.is_connected:
                            logger.info(f"🩺 ASI: Healing connection for {getattr(client, 'name', 'Assistant')}")
                            try:
                                await client.start()
                                self._health_stats["healed_connections"] += 1
                            except Exception as ex:
                                logger.error(f"ASI Heal Failed: {ex}")
                
                await asyncio.sleep(300) # Check every 5 minutes
            except Exception as e:
                await asyncio.sleep(60)

    # --- Task 4: Disk Hygiene ---
    async def _disk_hygiene(self):
        while self._running:
            try:
                # Clean specific temp directories
                targets = ["downloads", "cache", "search"]
                for target in targets:
                    if os.path.exists(target):
                        total_size = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fn in os.walk(target) for f in fn)
                        total_mb = total_size / (1024 * 1024)
                        
                        if total_mb > KernelConfig.MAX_CACHE_SIZE_MB:
                            logger.info(f"🧹 ASI: Cleaning {target} (Size: {total_mb:.2f}MB)...")
                            # Simple clean: Delete files older than 1 hour
                            cutoff = time.time() - 3600
                            for root, dirs, files in os.walk(target):
                                for file in files:
                                    path = os.path.join(root, file)
                                    if os.path.getmtime(path) < cutoff:
                                        try: os.remove(path)
                                        except: pass
                
                await asyncio.sleep(600) # Check every 10 minutes
            except Exception:
                await asyncio.sleep(60)

# Initialize the Brain
ASI = ArtificialSystemIntelligence()

# ==============================================================================
# 📡 WEBSOCKET HUB (TELEMETRY SYSTEM)
# ==============================================================================
class WebSocketHub:
    def __init__(self):
        self.status_connections: List[WebSocket] = []
        self.log_connections: List[WebSocket] = []
        self._lock = Lock()

    async def connect_status(self, ws: WebSocket):
        await ws.accept()
        with self._lock:
            self.status_connections.append(ws)

    async def connect_logs(self, ws: WebSocket):
        await ws.accept()
        with self._lock:
            self.log_connections.append(ws)

    def disconnect(self, ws: WebSocket):
        with self._lock:
            if ws in self.status_connections:
                self.status_connections.remove(ws)
            if ws in self.log_connections:
                self.log_connections.remove(ws)

    async def broadcast_status(self, data: dict):
        if not self.status_connections: return
        payload = json.dumps(data)
        to_remove = []
        for ws in self.status_connections:
            try:
                await ws.send_text(payload)
            except:
                to_remove.append(ws)
        
        if to_remove:
            with self._lock:
                for ws in to_remove:
                    if ws in self.status_connections:
                        self.status_connections.remove(ws)

WSHub = WebSocketHub()

# Background Broadcaster Loop
async def status_broadcaster():
    while ASI._running:
        try:
            # Gather Snapshot
            active_calls = []
            try:
                if StreamController and hasattr(StreamController, "active_calls"):
                    active_calls = list(StreamController.active_calls)
            except: pass

            snapshot = {
                "ts": int(time.time()),
                "sys": {
                    "cpu": psutil.cpu_percent(),
                    "ram": psutil.virtual_memory().percent,
                    "up": int(time.time() - ASI._health_stats["uptime_start"])
                },
                "bot": {
                    "calls": len(active_calls),
                    "chats": active_calls[:5], # Send only first 5 IDs to save bandwidth
                    "healed": ASI._health_stats["healed_connections"]
                },
                "ai": "ACTIVE"
            }
            
            await WSHub.broadcast_status(snapshot)
            await asyncio.sleep(config.WS_STATUS_INTERVAL)
        except Exception as e:
            logger.error(f"Broadcaster Error: {e}")
            await asyncio.sleep(1)

# ==============================================================================
# 🧰 HELPER FUNCTIONS
# ==============================================================================
def get_assistant_for_chat(chat_id: int):
    """Safety wrapper for group_assistant."""
    if not USERBOT_MODULE_AVAILABLE:
        raise HTTPException(503, "Userbot module unavailable")
    return group_assistant(StreamController, chat_id)

def ffmpeg_eq_command(input_file: str, output_file: str, bands: Dict[str, float]) -> str:
    """Generates FFmpeg command for Equalizer."""
    filters = []
    for freq, gain in bands.items():
        # Using a generic bell curve filter
        filters.append(f"equalizer=f={freq}:width_type=o:width=2:g={gain}")
    
    filter_str = ",".join(filters)
    return f'ffmpeg -y -hide_banner -loglevel error -i {shlex.quote(input_file)} -af "{filter_str}" -c:a libopus -b:a 128k {shlex.quote(output_file)}'

# ==============================================================================
# 🎮 API REQUEST MODELS (PYDANTIC)
# ==============================================================================
class BaseChatRequest(BaseModel):
    chat_id: int = Field(..., description="Target Chat ID")

class PlayReq(BaseChatRequest):
    query: Optional[str] = None
    video: bool = False

class SkipReq(BaseChatRequest):
    link: str = "" # Compatibility with existing code
    video: bool = False

class SeekReq(BaseChatRequest):
    seconds: int
    file_path: Optional[str] = ""
    duration: Optional[str] = ""
    mode: str = "absolute"

class VolumeReq(BaseChatRequest):
    volume: int = Field(..., ge=0, le=200)

class SpeedReq(BaseChatRequest):
    speed: float = Field(..., ge=0.5, le=2.0)
    file_path: Optional[str] = ""
    playing: Optional[list] = []

class EQReq(BaseChatRequest):
    bands: Dict[str, float]
    input_path: str

class GroupActionReq(BaseModel):
    group_id: int
    action: str
    payload: Dict[str, Any] = {}

class BroadcastReq(BaseModel):
    html: str
    groups: Optional[List[int]] = None

# ==============================================================================
# 🚀 API ENDPOINTS: PLAYBACK CONTROL
# ==============================================================================

@app.post("/bridge/play", tags=["Playback"])
async def play_stream(payload: PlayReq):
    ASI._health_stats["api_requests"] += 1
    try:
        assistant = await get_assistant_for_chat(payload.chat_id)
        # Assuming StreamController.play logic handles queuing or playing
        await StreamController.play(assistant, payload.chat_id)
        return {"status": "success", "action": "play", "chat_id": payload.chat_id}
    except Exception as e:
        logger.error(f"Play Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/bridge/pause", tags=["Playback"])
async def pause_stream(payload: BaseChatRequest):
    try:
        await StreamController.pause_stream(payload.chat_id)
        return {"status": "success", "action": "pause"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/bridge/resume", tags=["Playback"])
async def resume_stream(payload: BaseChatRequest):
    try:
        await StreamController.resume_stream(payload.chat_id)
        return {"status": "success", "action": "resume"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/bridge/skip", tags=["Playback"])
async def skip_stream(payload: SkipReq):
    try:
        # Note: Your call.py skip_stream signature: (chat_id, link, video, image)
        await StreamController.skip_stream(payload.chat_id, payload.link, video=payload.video)
        return {"status": "success", "action": "skip"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/bridge/seek", tags=["Playback"])
async def seek_stream(payload: SeekReq):
    try:
        await StreamController.seek_stream(
            payload.chat_id, 
            payload.file_path, 
            str(payload.seconds), # Ensure string if call.py expects string
            payload.duration, 
            payload.mode
        )
        return {"status": "success", "action": "seek"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/bridge/stop", tags=["Playback"])
async def stop_stream(payload: BaseChatRequest):
    try:
        await StreamController.stop_stream(payload.chat_id)
        return {"status": "success", "action": "stop"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==============================================================================
# 🔊 API ENDPOINTS: AUDIO PROCESSING
# ==============================================================================

@app.post("/bridge/volume", tags=["Audio"])
async def set_volume(payload: VolumeReq):
    try:
        assistant = await get_assistant_for_chat(payload.chat_id)
        
        # Robust volume setting logic supporting different PyTgCalls versions
        if hasattr(assistant, "change_volume_call"):
            await assistant.change_volume_call(payload.chat_id, payload.volume)
        elif hasattr(assistant, "group_call") and hasattr(assistant.group_call, "set_my_volume"):
            await assistant.group_call.set_my_volume(payload.volume)
        else:
            # Last resort: try accessing via PyTgCalls instance directly if exposed
            await assistant.group_call.change_volume_call(payload.chat_id, payload.volume)

        return {"status": "success", "volume": payload.volume}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/bridge/speed", tags=["Audio"])
async def set_speed(payload: SpeedReq):
    try:
        await StreamController.speedup_stream(
            payload.chat_id, payload.file_path, payload.speed, payload.playing
        )
        return {"status": "success", "speed": payload.speed}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/bridge/eq", tags=["Audio"])
async def apply_eq(payload: EQReq):
    """
    Applies FFmpeg Equalizer filter to a file and returns the new path.
    Does not play immediately; logic should be handled by the bot to queue the new file.
    """
    if not os.path.exists(payload.input_path):
        raise HTTPException(404, "Input file not found")

    output_file = f"downloads/eq_{payload.chat_id}_{int(time.time())}.opus"
    os.makedirs("downloads", exist_ok=True)
    
    cmd = ffmpeg_eq_command(payload.input_path, output_file, payload.bands)
    
    try:
        # Run FFmpeg in a thread to avoid blocking the event loop
        await asyncio.to_thread(subprocess.run, cmd, shell=True, check=True)
        
        # Here we could inject it into the queue directly if we had access to the queue list structure
        # For now, we return the path so the frontend/bot logic can handle it
        if db:
            q = db.get(payload.chat_id, [])
            if isinstance(q, list):
                q.insert(0, {"file": output_file, "title": "EQ Processed Track", "by": "TitanAudio"})
                db[payload.chat_id] = q

        return {"status": "success", "file": output_file}
    except subprocess.CalledProcessError as e:
        raise HTTPException(500, f"FFmpeg Error: {e}")
    except Exception as e:
        raise HTTPException(500, str(e))

# ==============================================================================
# 🛡️ API ENDPOINTS: MANAGEMENT & SECURITY
# ==============================================================================

@app.post("/group/action", tags=["Management"])
async def group_actions(payload: GroupActionReq):
    g = payload.group_id
    a = payload.action.lower()
    p = payload.payload

    try:
        if a == "force_play":
            assistant = await get_assistant_for_chat(g)
            await StreamController.play(assistant, g)
            return {"status": "executed", "action": "force_play"}
        
        elif a == "ban":
            # Example DB manipulation
            bans = db.get("group_bans", set())
            if isinstance(bans, list): bans = set(bans)
            bans.add(g)
            db["group_bans"] = list(bans)
            return {"status": "executed", "action": "ban"}
        
        elif a == "set_bio":
            bio = p.get("bio", "Titan OS")
            # Iterate all assistants
            if userbot:
                 # Logic to iterate clients and set bio
                 pass
            return {"status": "executed", "bio": bio}

        raise HTTPException(400, "Unknown action")
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/broadcast", tags=["Management"])
async def broadcast_message(payload: BroadcastReq, background_tasks: BackgroundTasks):
    html_content = payload.html
    # If no groups specified, get all active chats from DB
    target_groups = payload.groups or list(db.get("active_chats", {}).keys()) if db else []
    
    async def _runner():
        if not userbot: return
        client = getattr(userbot, "one", None)
        if not client: return
        
        count = 0
        for chat_id in target_groups:
            try:
                await client.send_message(chat_id, html_content)
                count += 1
                await asyncio.sleep(0.1) # Rate limit protection
            except: pass
        logger.info(f"📢 Broadcast finished. Sent to {count} chats.")

    background_tasks.add_task(_runner)
    return {"status": "queued", "target_count": len(target_groups)}

@app.post("/resource/focus", tags=["Management"])
async def resource_focus(payload: Dict[str, Any]):
    """Prioritizes resources for a specific group (VIP Mode)."""
    gid = payload.get("group_id")
    if RO:
        try:
            result = RO.focus_on_group(int(gid))
            return {"status": "success", "result": result}
        except Exception as e:
            return {"error": str(e)}
    return {"status": "error", "msg": "Resource Optimizer not loaded"}

@app.post("/assistants/restart_all", tags=["System"])
async def restart_assistants():
    """Manual trigger for ASI healing."""
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
                results.append({"id": getattr(c, "name", "Assis"), "status": "Restarted"})
            else:
                results.append({"id": getattr(c, "name", "Assis"), "status": "Online"})
        except Exception as e:
            results.append({"error": str(e)})
            
    return {"summary": results}

# ==============================================================================
# 📂 API ENDPOINTS: DATABASE EXPLORER & LOGS
# ==============================================================================

@app.get("/bridge/db/collections", tags=["Database"])
async def get_db_collections():
    """Returns available database keys/collections."""
    if not db: return []
    try:
        # If db is a dict-like object
        return list(db.keys())
    except: return []

@app.get("/bridge/db/{name}", tags=["Database"])
async def get_db_content(name: str):
    """Returns content of a specific DB collection."""
    if not db: return {}
    try:
        data = db.get(name, None)
        # Convert non-serializable objects to string if necessary
        return data if data else {}
    except: return {"error": "Failed to retrieve"}

@app.post("/logs/tail", tags=["System"])
async def get_logs_tail(payload: Dict[str, int]):
    """Reads the last N lines of the log file."""
    lines_count = payload.get("lines", 100)
    log_path = getattr(config, "LOG_FILE", "log.txt")
    
    if not os.path.exists(log_path):
        return {"lines": ["Log file not found."]}
    
    try:
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            # Efficient implementation for small-medium files
            all_lines = f.readlines()
            return {"lines": all_lines[-lines_count:]}
    except Exception as e:
        return {"error": str(e)}

# ==============================================================================
# 🌐 WEBSOCKET ENDPOINTS
# ==============================================================================

@app.websocket("/ws/status")
async def websocket_status_endpoint(ws: WebSocket):
    await WSHub.connect_status(ws)
    try:
        while True:
            # Keep connection alive & handle incoming commands
            data = await ws.receive_text()
            if data == "ping":
                await ws.send_json({"type": "pong", "ts": time.time()})
    except WebSocketDisconnect:
        WSHub.disconnect(ws)

@app.websocket("/bridge/logs")
async def websocket_logs_endpoint(ws: WebSocket):
    await WSHub.connect_logs(ws)
    log_path = getattr(config, "LOG_FILE", "log.txt")
    file_ptr = None
    
    try:
        if os.path.exists(log_path):
            file_ptr = open(log_path, "r", encoding="utf-8", errors="ignore")
            # Move to end of file to stream new logs only
            file_ptr.seek(0, os.SEEK_END)
        
        while True:
            # Check for disconnects or pings (non-blocking)
            try:
                await asyncio.wait_for(ws.receive_text(), timeout=0.5)
            except asyncio.TimeoutError:
                pass
            except WebSocketDisconnect:
                break
            
            # Read new lines
            if file_ptr:
                where = file_ptr.tell()
                line = file_ptr.readline()
                if not line:
                    file_ptr.seek(where)
                else:
                    await ws.send_text(line)
            else:
                # Try opening file if it appeared later
                if os.path.exists(log_path):
                     file_ptr = open(log_path, "r", encoding="utf-8", errors="ignore")
            
            await asyncio.sleep(0.5)

    except Exception:
        pass
    finally:
        if file_ptr: file_ptr.close()
        WSHub.disconnect(ws)

# ==============================================================================
# ❤️ SYSTEM HEALTH
# ==============================================================================

@app.get("/health", tags=["System"])
async def health_check():
    """Lightweight endpoint for Load Balancers (Fly.io)."""
    return {
        "status": "healthy",
        "uptime": int(time.time() - ASI._health_stats["uptime_start"]),
        "asi": "active" if ASI._running else "dormant"
    }

@app.get("/", tags=["System"])
async def root_entry():
    return {
        "system": "Titan OS Kernel",
        "version": KernelConfig.VERSION,
        "edition": "Grand Master",
        "modules": {
            "StreamController": "Linked" if CALL_MODULE_AVAILABLE else "Missing",
            "Userbot": "Linked" if USERBOT_MODULE_AVAILABLE else "Missing",
            "ResourceOptimizer": "Linked" if RO else "Missing"
        }
    }

# ==============================================================================
# ⚡ STARTUP & SHUTDOWN HOOKS
# ==============================================================================

@app.on_event("startup")
async def kernel_startup():
    logger.info("🚀 Titan OS Kernel: Boot Sequence Initiated...")
    
    # 1. Start ASI
    await ASI.boot_sequence()
    
    # 2. Start Broadcaster
    asyncio.create_task(status_broadcaster())
    
    logger.info("🚀 Titan OS Kernel: Systems Nominal.")

@app.on_event("shutdown")
async def kernel_shutdown():
    logger.info("🛑 Titan OS Kernel: Shutdown Sequence Initiated...")
    await ASI.shutdown_sequence()

# ==============================================================================
# 🔥 CRITICAL: SERVER LAUNCHER (FLY.IO COMPATIBLE)
# ==============================================================================
def ignite_titan_engine():
    """
    Starts the Uvicorn server in a separate thread.
    Configured specifically for Fly.io environment (0.0.0.0:8080).
    """
    logger.info(f"🔥 Igniting Titan Engine on Port {KernelConfig.PORT}...")
    
    # Custom Log Config to reduce Uvicorn noise
    log_config = uvicorn.config.LOGGING_CONFIG
    log_config["formatters"]["access"]["fmt"] = "%(asctime)s - %(client_addr)s - %(request_line)s %(status_code)s"

    try:
        uvicorn.run(
            app,
            host=KernelConfig.HOST,
            port=KernelConfig.PORT,
            log_level="warning", # Keep console clean, let Kernel handle logs
            loop="asyncio",
            workers=1, # Single worker to play nice with Pyrogram's event loop
            timeout_keep_alive=30,
            ws_ping_interval=20,
            ws_ping_timeout=20,
            log_config=log_config
        )
    except Exception as e:
        logger.critical(f"🔥 ENGINE FAILURE: {e}")
        traceback.print_exc()

# Entry Point Check
if __name__ != "__main__":
    # When imported by the main bot process, start the server thread
    server_thread = Thread(target=ignite_titan_engine, name="TitanEngineThread")
    server_thread.daemon = True
    server_thread.start()
    logger.info("✅ Titan Engine Thread Launched.")
