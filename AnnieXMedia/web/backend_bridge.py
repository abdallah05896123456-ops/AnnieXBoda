# web/backend_bridge.py
import asyncio
import json
import os
import shlex
import subprocess
import time
from typing import Dict, List, Optional, Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, BackgroundTasks, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Deep integration with AnnieXMedia (project-specific)
from AnnieXMedia.core.call import Annie, StreamController, _clear_
from AnnieXMedia.misc import db  # assume a dict-style store
from AnnieXMedia.utils.database import group_assistant

# local modules
import config

# optional imports for resource optimizer / security gate
try:
    import Resource_Optimizer as RO
except Exception:
    RO = None

try:
    import security_gate
except Exception:
    security_gate = None

app = FastAPI(title="Titan-Glass Backend Bridge", version="1.1.0")

# CORS (adjust in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=getattr(config, "CORS_ORIGINS", ["http://localhost:3000"]),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------
# WebSocket broadcasters (status + logs)
# --------------------
class ConnectionManager:
    def __init__(self):
        self.active: List[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, message: dict):
        data = json.dumps(message)
        to_remove = []
        for ws in list(self.active):
            try:
                await ws.send_text(data)
            except Exception:
                to_remove.append(ws)
        for ws in to_remove:
            self.disconnect(ws)

status_manager = ConnectionManager()
logs_manager = ConnectionManager()

# Background task state
_ws_broadcaster_task: Optional[asyncio.Task] = None
_broadcaster_stop = asyncio.Event()

# --------------------
# Helpers: system snapshot
# --------------------
async def _gather_status_snapshot() -> dict:
    """Collect status: current track progress, active listeners, CPU/RAM from Resource_Optimizer if available."""
    # try to probe StreamController internal state
    try:
        active_calls = list(getattr(StreamController, "active_calls", []) or [])
    except Exception:
        active_calls = []

    # sample listeners per call if possible
    listeners = {}
    for chat_id in active_calls:
        try:
            listeners[chat_id] = getattr(StreamController, "listeners", {}).get(chat_id, 0)
        except Exception:
            listeners[chat_id] = 0

    # server health from Resource_Optimizer (if present)
    health = {}
    try:
        if RO is not None:
            health = {
                "cpu_percent": RO.sample_cpu_percent(),
                "ram_used_mb": RO.sample_ram_mb(),
                "temp_c": RO.sample_temp_c(),
            }
        else:
            health = {"cpu_percent": 0.0, "ram_used_mb": 0.0, "temp_c": None}
    except Exception:
        health = {"cpu_percent": 0.0, "ram_used_mb": 0.0, "temp_c": None}

    # current playing info: attempt to read from db or StreamController
    current = {}
    try:
        current = getattr(StreamController, "current_track", {}) or {}
    except Exception:
        current = {}

    return {
        "timestamp": int(time.time() * 1000),
        "active_calls": active_calls,
        "listeners": listeners,
        "health": health,
        "current": current,
    }

async def _broadcaster_loop():
    """Broadcast status to all websockets periodically."""
    # interval: configurable in config (seconds). default 0.1 (100ms)
    interval = float(getattr(config, "WS_STATUS_INTERVAL", 0.1))
    while not _broadcaster_stop.is_set():
        snapshot = await _gather_status_snapshot()
        await status_manager.broadcast({"type": "status_snapshot", "payload": snapshot})
        await asyncio.sleep(interval)

@app.on_event("startup")
async def startup_event():
    global _ws_broadcaster_task
    _broadcaster_stop.clear()
    if _ws_broadcaster_task is None or _ws_broadcaster_task.done():
        _ws_broadcaster_task = asyncio.create_task(_broadcaster_loop())

@app.on_event("shutdown")
async def shutdown_event():
    global _ws_broadcaster_task
    _broadcaster_stop.set()
    if _ws_broadcaster_task:
        await _ws_broadcaster_task
        _ws_broadcaster_task = None

# WebSocket endpoint clients will connect to for status updates
@app.websocket("/ws/status")
async def ws_status(ws: WebSocket):
    await status_manager.connect(ws)
    try:
        while True:
            # keep connection alive; respond to "ping"
            try:
                msg = await ws.receive_text()
            except WebSocketDisconnect:
                break
            except Exception:
                # if client doesn't send anything, continue (some clients just listen)
                await asyncio.sleep(0.1)
                continue
            if msg == "ping":
                snap = await _gather_status_snapshot()
                await ws.send_text(json.dumps({"type": "pong", "payload": snap}))
    except WebSocketDisconnect:
        status_manager.disconnect(ws)
    finally:
        status_manager.disconnect(ws)

# WebSocket endpoint for tailing logs (clients: iOS_Dashboard)
@app.websocket("/bridge/logs")
async def ws_logs(ws: WebSocket):
    """
    Streams new lines from log file to connected clients.
    Expects config.LOG_FILE set; otherwise streams nothing.
    """
    await logs_manager.connect(ws)
    log_path = getattr(config, "LOG_FILE", "/var/log/titan.log")
    try:
        # attempt to open and seek to end; then stream new lines
        # we'll implement a simple polling tail
        position = 0
        if os.path.exists(log_path):
            position = os.path.getsize(log_path)
        while True:
            try:
                # non-blocking receive to allow client pings or close
                try:
                    _ = await asyncio.wait_for(ws.receive_text(), timeout=0.2)
                    # ignore content; loop continues
                except asyncio.TimeoutError:
                    pass
                if os.path.exists(log_path):
                    size = os.path.getsize(log_path)
                    if size > position:
                        with open(log_path, "r", errors="ignore") as f:
                            f.seek(position)
                            chunk = f.read()
                            position = f.tell()
                            if chunk:
                                # send chunk (split into lines)
                                for line in chunk.splitlines():
                                    try:
                                        await ws.send_text(line)
                                    except Exception:
                                        pass
                await asyncio.sleep(0.2)
            except WebSocketDisconnect:
                break
    except WebSocketDisconnect:
        pass
    finally:
        logs_manager.disconnect(ws)

# --------------------
# Playback and control API models
# --------------------
class PlayModel(BaseModel):
    chat_id: int

class SkipModel(BaseModel):
    chat_id: int
    link: str = ""
    video: bool = False
    image: bool = False

class SeekModel(BaseModel):
    chat_id: int
    file_path: str = ""
    to_seek: str  # seconds or timestamp
    duration: str = ""
    mode: str = "absolute"

class VolumeModel(BaseModel):
    chat_id: int
    volume: int  # 0 - 200

class SpeedModel(BaseModel):
    chat_id: int
    speed: float
    file_path: Optional[str] = ""
    playing: Optional[list] = []

class EqModel(BaseModel):
    chat_id: int
    input_path: str
    bands: Dict[str, float]

# --------------------
# Utility: run ffmpeg filter command to apply EQ and return local file path
# --------------------
def apply_5band_eq(input_file: str, output_file: str, bands: Dict[str, float]):
    """
    bands: dict with keys '60','230','910','3600','14000' representing gain in dB (positive/negative)
    Produces output_file using ffmpeg with equalizer filters chained.
    """
    eq_filters = []
    for freq, gain in bands.items():
        # center frequency, q-factor generic
        filt = f"equalizer=f={freq}:width_type=o:width=2:g={gain}"
        eq_filters.append(filt)
    filter_chain = ",".join(eq_filters)
    cmd = f'ffmpeg -y -hide_banner -loglevel error -i {shlex.quote(input_file)} -af "{filter_chain}" -c:a libopus -b:a 128k {shlex.quote(output_file)}'
    proc = subprocess.run(cmd, shell=True)
    if proc.returncode != 0:
        raise RuntimeError("ffmpeg eq application failed")
    return output_file

# --------------------
# Playback endpoints
# --------------------
@app.post("/bridge/play")
async def api_play(payload: PlayModel):
    assistant = await group_assistant(StreamController, payload.chat_id)
    await StreamController.play(assistant, payload.chat_id)
    return {"status": "ok", "action": "play", "chat_id": payload.chat_id}

@app.post("/bridge/pause")
async def api_pause(payload: PlayModel):
    await StreamController.pause_stream(payload.chat_id)
    return {"status": "ok", "action": "pause", "chat_id": payload.chat_id}

@app.post("/bridge/resume")
async def api_resume(payload: PlayModel):
    await StreamController.resume_stream(payload.chat_id)
    return {"status": "ok", "action": "resume", "chat_id": payload.chat_id}

@app.post("/bridge/skip")
async def api_skip(payload: SkipModel):
    await StreamController.skip_stream(payload.chat_id, payload.link, payload.video, payload.image)
    return {"status": "ok", "action": "skip", "chat_id": payload.chat_id}

@app.post("/bridge/seek")
async def api_seek(payload: SeekModel):
    await StreamController.seek_stream(payload.chat_id, payload.file_path, payload.to_seek, payload.duration, payload.mode)
    return {"status": "ok", "action": "seek", "chat_id": payload.chat_id}

@app.post("/bridge/volume")
async def api_volume(payload: VolumeModel):
    assistant = await group_assistant(StreamController, payload.chat_id)
    # prefer change_volume_call if available, else call group_call interface
    try:
        if hasattr(assistant, "change_volume_call"):
            await assistant.change_volume_call(payload.chat_id, payload.volume)
        elif hasattr(assistant, "group_call") and hasattr(assistant.group_call, "set_my_volume"):
            await assistant.group_call.set_my_volume(payload.volume)
        else:
            raise RuntimeError("Assistant does not expose volume control")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"status": "ok", "action": "volume", "chat_id": payload.chat_id, "volume": payload.volume}

@app.post("/bridge/speed")
async def api_speed(payload: SpeedModel):
    await StreamController.speedup_stream(payload.chat_id, payload.file_path or "", payload.speed, payload.playing or [])
    return {"status": "ok", "action": "speed", "chat_id": payload.chat_id, "speed": payload.speed}

@app.post("/bridge/eq")
async def api_eq(payload: EqModel):
    """
    Apply 5-band EQ on server-side audio file and queue the result.
    Returns path to processed file.
    """
    chat_id = payload.chat_id
    input_path = payload.input_path
    bands = payload.bands or {}
    if not os.path.exists(input_path):
        raise HTTPException(status_code=404, detail="input file not found")
    out = f"/tmp/titan_eq_{chat_id}_{int(time.time())}.opus"
    try:
        apply_5band_eq(input_path, out, bands)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    # Optionally add to queue
    try:
        q = db.get(chat_id, [])
        q.insert(0, {"file": out, "title": os.path.basename(out)})
        db[chat_id] = q
    except Exception:
        pass
    return {"status": "ok", "processed": out}

# --------------------
# Resource optimizer endpoint (focus)
# --------------------
@app.post("/resource/focus")
async def api_resource_focus(body: dict):
    group_id = body.get("group_id") or body.get("group") or body.get("chat_id")
    if group_id is None:
        raise HTTPException(status_code=400, detail="group_id required")
    try:
        if RO is None:
            raise RuntimeError("Resource_Optimizer not available")
        res = RO.focus_on_group(int(group_id))
        return {"status": "ok", "result": res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --------------------
# Assistants operations
# --------------------
@app.post("/assistants/restart_all")
async def assistants_restart_all():
    """
    Attempt to restart all assistant clients. Non-blocking best-effort.
    """
    try:
        clients = []
        try:
            clients = Annie.clients()
        except Exception:
            clients = []
        results = []
        for client in clients:
            try:
                # prefer async restart if available
                fn = getattr(client, "restart", None) or getattr(client, "reconnect", None)
                if fn:
                    if asyncio.iscoroutinefunction(fn):
                        await fn()
                    else:
                        try:
                            fn()
                        except Exception:
                            pass
                    results.append({"client": getattr(client, "id", None), "restarted": True})
                else:
                    results.append({"client": getattr(client, "id", None), "restarted": False, "reason": "no restart method"})
            except Exception as e:
                results.append({"client": getattr(client, "id", None), "restarted": False, "error": str(e)})
        return {"status": "ok", "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --------------------
# Logs endpoints
# --------------------
@app.post("/logs/tail")
async def logs_tail(body: dict):
    lines = int(body.get("lines", 200))
    log_path = getattr(config, "LOG_FILE", "/var/log/titan.log")
    if not os.path.exists(log_path):
        return {"status": "ok", "lines": []}
    # efficient tail implementation
    try:
        with open(log_path, "rb") as f:
            f.seek(0, os.SEEK_END)
            filesize = f.tell()
            block = 1024
            data = b""
            while filesize > 0 and data.count(b"\n") <= lines:
                read_size = min(block, filesize)
                f.seek(filesize - read_size)
                data = f.read(read_size) + data
                filesize -= read_size
            text = data.decode(errors="ignore").splitlines()[-lines:]
        return {"status": "ok", "lines": text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --------------------
# Database explorer endpoints
# --------------------
@app.get("/bridge/db/collections")
async def db_collections():
    try:
        # if db exposes collections method, use it; else return keys
        if hasattr(db, "collections") and callable(db.collections):
            cols = db.collections()
            # if it's awaitable
            if asyncio.iscoroutine(cols):
                cols = await cols
            return list(cols)
        # fallback: treat db as dict-like
        return list(db.keys())
    except Exception:
        return []

@app.get("/bridge/db/{name}")
async def db_read_collection(name: str):
    try:
        val = db.get(name, [])
        return val
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --------------------
# Group operations (extended)
# --------------------
class GroupActionModel(BaseModel):
    group_id: int
    action: str
    payload: Optional[dict] = {}

@app.post("/group/action")
async def group_action(model: GroupActionModel):
    g = model.group_id
    a = model.action.lower()
    p = model.payload or {}
    # BAN/UNBAN by restricting bot?
    if a == "ban":
        banned = db.get("group_bans", set())
        if not isinstance(banned, set):
            banned = set(banned)
        banned.add(g)
        db["group_bans"] = banned
        return {"status": "ok", "action": "group_banned", "group": g}
    if a == "unban":
        banned = db.get("group_bans", set())
        if not isinstance(banned, set):
            banned = set(banned)
        banned.discard(g)
        db["group_bans"] = banned
        return {"status": "ok", "action": "group_unbanned", "group": g}
    if a == "set_bio":
        bio = p.get("bio", "")
        for assistant_client in Annie.clients():
            try:
                if asyncio.iscoroutinefunction(assistant_client.update_profile):
                    await assistant_client.update_profile(bio=bio)
                else:
                    try:
                        assistant_client.update_profile(bio=bio)
                    except Exception:
                        pass
            except Exception:
                pass
        return {"status": "ok", "action": "bio_set", "bio": bio}
    if a == "change_photo":
        photo = p.get("photo_path")
        if not photo or not os.path.exists(photo):
            raise HTTPException(status_code=400, detail="photo missing")
        for assistant_client in Annie.clients():
            try:
                fn = getattr(assistant_client, "set_profile_photo", None)
                if fn:
                    if asyncio.iscoroutinefunction(fn):
                        await fn(photo=photo)
                    else:
                        try:
                            fn(photo=photo)
                        except Exception:
                            pass
            except Exception:
                pass
        return {"status": "ok", "action": "photo_changed"}
    if a == "force_play":
        try:
            assistant = await group_assistant(StreamController, g)
            await StreamController.play(assistant, g)
            return {"status": "ok", "action": "force_play", "group": g}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    raise HTTPException(status_code=400, detail="unknown group action")

# --------------------
# User operations
# --------------------
class UserActionModel(BaseModel):
    user_id: int
    action: str
    payload: Optional[dict] = {}

@app.post("/user/action")
async def user_action(model: UserActionModel):
    u = model.user_id
    a = model.action.lower()
    p = model.payload or {}
    if a == "ban":
        ub = db.get("user_bans", set())
        if not isinstance(ub, set):
            ub = set(ub)
        ub.add(u)
        db["user_bans"] = ub
        return {"status": "ok", "action": "user_banned", "user": u}
    if a == "mute":
        mp = db.get("muted_users", set())
        if not isinstance(mp, set):
            mp = set(mp)
        mp.add(u)
        db["muted_users"] = mp
        return {"status": "ok", "action": "user_muted", "user": u}
    if a == "promote":
        admins = db.get("bot_admins", set())
        if not isinstance(admins, set):
            admins = set(admins)
        admins.add(u)
        db["bot_admins"] = admins
        return {"status": "ok", "action": "user_promoted", "user": u}
    raise HTTPException(status_code=400, detail="unknown user action")

# --------------------
# Broadcast HTML messages to all groups (careful)
# --------------------
class BroadcastModel(BaseModel):
    html: str
    groups: Optional[List[int]] = None  # if not provided, broadcast to all tracked groups (capped)

@app.post("/broadcast")
async def broadcast(model: BroadcastModel, background_tasks: BackgroundTasks):
    html = model.html
    groups = model.groups or list(db.get("groups_list", []) or [])[:10000]
    async def _deliver():
        for g in groups:
            try:
                for client in Annie.clients():
                    try:
                        # prefer coroutine send_html
                        if asyncio.iscoroutinefunction(getattr(client, "send_html", None)):
                            await client.send_html(g, html)
                        else:
                            try:
                                client.send_html(g, html)
                            except Exception:
                                pass
                        break
                    except Exception:
                        continue
            except Exception:
                continue
            await asyncio.sleep(0.02)  # small throttle
    background_tasks.add_task(_deliver)
    return {"status": "scheduled", "target_count": len(groups)}

# --------------------
# Optional: expose security router if available
# --------------------
if security_gate is not None:
    try:
        app.include_router(security_gate.get_router())
    except Exception:
        pass

# --------------------
# Simple health endpoint
# --------------------
@app.get("/health")
async def health():
    return {"status": "ok", "uptime": int(time.time())}

# --------------------
# End of file
# --------------------
# ==========================================
# 🔥 CRITICAL: SERVER STARTER FOR FLY.IO 🔥
# ==========================================
def start_titan_server():
    import uvicorn
    # تشغيل السيرفر على البورت 8080 عشان Fly.io يشوفه
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8080,
        log_level="info",
        ws_ping_interval=20,  # مهم عشان الـ WebSockets تفضل شغالة
        ws_ping_timeout=20
    )

# تشغيل السيرفر في Thread منفصل أول ما الملف ده يتعمل له Import
if __name__ != "__main__":
    from threading import Thread
    server_thread = Thread(target=start_titan_server)
    server_thread.daemon = True
    server_thread.start()
