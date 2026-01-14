# web/backend_bridge.py
import asyncio
import json
import os
import shlex
import subprocess
import time
from typing import Dict, List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Deep integration with AnnieXMedia
from AnnieXMedia.core.call import Annie, StreamController, _clear_
from AnnieXMedia.misc import db  # assume a dict-style store
from AnnieXMedia.utils.database import group_assistant

import config

app = FastAPI(title="Titan-Glass Backend Bridge", version="1.0.0")

# CORS (adjust in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=getattr(config, "CORS_ORIGINS", ["http://localhost:3000"]),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------
# WebSocket real-time broadcaster
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


manager = ConnectionManager()

# Background task state
_ws_broadcaster_task: Optional[asyncio.Task] = None
_broadcaster_stop = asyncio.Event()

async def _gather_status_snapshot() -> dict:
    """Collect status: current track progress, active listeners, CPU/RAM from Resource_Optimizer if available."""
    # try to probe StreamController internal state
    try:
        active_calls = list(getattr(StreamController, "active_calls", []))
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
        import Resource_Optimizer as RO  # local module
        health = {"cpu_percent": RO.sample_cpu_percent(), "ram_used_mb": RO.sample_ram_mb(), "temp_c": RO.sample_temp_c()}
    except Exception:
        # fallback
        health = {"cpu_percent": 0.0, "ram_used_mb": 0.0, "temp_c": None}
    # current playing info: attempt to read from db or StreamController
    current = {}
    try:
        # assume StreamController has get_current or similar
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
    """Broadcast status to all websockets every 100ms."""
    while not _broadcaster_stop.is_set():
        snapshot = await _gather_status_snapshot()
        await manager.broadcast({"type": "status_snapshot", "payload": snapshot})
        await asyncio.sleep(0.1)  # 100ms


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

# WebSocket endpoint clients will connect to
@app.websocket("/ws/status")
async def ws_status(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            # keep the socket open and react to pings
            msg = await ws.receive_text()
            # support client pings: respond with immediate snapshot
            if msg == "ping":
                snap = await _gather_status_snapshot()
                await ws.send_text(json.dumps({"type": "pong", "payload": snap}))
    except WebSocketDisconnect:
        manager.disconnect(ws)


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
async def api_eq(chat_id: int, input_path: str, bands: Dict[str, float]):
    """
    Apply 5-band EQ on server-side audio file and queue the result.
    Returns path to processed file.
    """
    if not os.path.exists(input_path):
        raise HTTPException(status_code=404, detail="input file not found")
    out = f"/tmp/titan_eq_{chat_id}_{int(time.time())}.opus"
    try:
        apply_5band_eq(input_path, out, bands)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    # Optionally add to queue
    q = db.get(chat_id, [])
    q.insert(0, {"file": out, "title": os.path.basename(out)})
    db[chat_id] = q
    return {"status": "ok", "processed": out}

# --------------------
# Group operations
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
        # store ban in db
        banned = db.get("group_bans", set())
        banned.add(g)
        db["group_bans"] = banned
        return {"status": "ok", "action": "group_banned", "group": g}
    if a == "unban":
        banned = db.get("group_bans", set())
        banned.discard(g)
        db["group_bans"] = banned
        return {"status": "ok", "action": "group_unbanned", "group": g}
    if a == "set_bio":
        bio = p.get("bio", "")
        # attempt to set assistant bio across Assistant clients
        for assistant_client in Annie.clients():  # assume Annie.clients() returns list
            try:
                await assistant_client.update_profile(bio=bio)
            except Exception:
                pass
        return {"status": "ok", "action": "bio_set", "bio": bio}
    if a == "change_photo":
        photo = p.get("photo_path")
        if not photo or not os.path.exists(photo):
            raise HTTPException(status_code=400, detail="photo missing")
        for assistant_client in Annie.clients():
            try:
                await assistant_client.set_profile_photo(photo=photo)
            except Exception:
                pass
        return {"status": "ok", "action": "photo_changed"}
    if a == "force_play":
        # attempt to start playing in group (use assistant with group)
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
        ub.add(u)
        db["user_bans"] = ub
        return {"status": "ok", "action": "user_banned", "user": u}
    if a == "mute":
        mp = db.get("muted_users", set())
        mp.add(u)
        db["muted_users"] = mp
        return {"status": "ok", "action": "user_muted", "user": u}
    if a == "promote":
        admins = db.get("bot_admins", set())
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
    # schedule background delivery to avoid blocking
    async def _deliver():
        for g in groups:
            try:
                for client in Annie.clients():
                    try:
                        await client.send_html(g, html)
                        break
                    except Exception:
                        continue
            except Exception:
                continue
            await asyncio.sleep(0.02)  # small throttle
    background_tasks.add_task(_deliver)
    return {"status": "scheduled", "target_count": len(groups)}
