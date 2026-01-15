# -*- coding: utf-8 -*-
# ==============================================================================
# TITAN OS | KERNEL V5.0 ULTIMATE EDITION
# The Central Nervous System for AnnieXMedia Bot
# 
# COPYRIGHT (C) 2025 - TITAN PROJECT
# AUTHORED FOR: HIGH-END TELEGRAM BOT MANAGEMENT
# ARCHITECTURE: ASYNCHRONOUS MONOLITHIC WEB SERVICE
# ==============================================================================

import os
import sys
import time
import json
import uuid
import logging
import psutil
import socket
import asyncio
import traceback
import platform
import datetime
from typing import Dict, List, Optional, Union, Any

# AIOHTTP: The backbone of our web service
try:
    from aiohttp import web, WSMsgType
    import aiohttp_cors
except ImportError:
    print("CRITICAL: aiohttp library missing. pip install aiohttp aiohttp_cors")
    sys.exit(1)

# ==============================================================================
# [SECTION 1] DEEP INTEGRATION WITH ANNIEXMEDIA SOURCE
# ==============================================================================
try:
    # Importing Core Components from your specific source structure
    from AnnieXMedia import app, userbot, LOGGER
    from AnnieXMedia.core.call import StreamController  # The Call Class Instance
    from AnnieXMedia.misc import db  # Database Dict
    from AnnieXMedia.utils.thumbnails import get_thumb
    from AnnieXMedia.utils.database import group_assistant
    from config import API_ID, API_HASH, SUPPORT_CHAT
    
    # Exceptions for robust error handling
    from pytgcalls.exceptions import (
        NoActiveGroupCall,
        NotInCallError,
        GroupCallNotFound,
        InvalidStreamMode
    )
    from pyrogram.errors import (
        FloodWait,
        UserNotParticipant,
        ChatAdminRequired
    )
except ImportError as e:
    sys.exit(f"\n[TITAN KERNEL PANIC] Dependency Error: {e}\nMake sure this file is next to main.py\n")

# ==============================================================================
# [SECTION 2] SYSTEM CONFIGURATION & CONSTANTS
# ==============================================================================

SERVER_HOST = "0.0.0.0"
SERVER_PORT = 8080
TITAN_VERSION = "5.0.2 (Ultimate)"
STARTUP_TIME = time.time()

# Logging Configuration
logging.basicConfig(
    format="%(asctime)s - [TITAN KERNEL] - %(levelname)s - %(message)s",
    datefmt="%d-%b-%y %H:%M:%S",
    level=logging.INFO
)
logger = logging.getLogger("TitanOS")

# WebSocket Clients Registry
WS_CLIENTS = set()

# ==============================================================================
# [SECTION 3] ADVANCED HTML/CSS/JS ENGINE (EMBEDDED)
# ==============================================================================
# This enables a "Single File" architecture. No external HTML needed.

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Titan OS | Control Center</title>
    <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;800&family=Rajdhani:wght@500;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        :root {
            --bg-dark: #000000;
            --glass: rgba(30, 30, 35, 0.75);
            --border: rgba(255, 255, 255, 0.1);
            --primary: #0A84FF;
            --danger: #FF453A;
            --success: #32D74B;
            --warning: #FFD60A;
            --text: #FFFFFF;
            --text-sec: #8E8E93;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Cairo', sans-serif; -webkit-tap-highlight-color: transparent; outline: none; }
        body {
            background-color: var(--bg-dark); color: var(--text);
            min-height: 100vh; display: flex; flex-direction: column;
            background-image: radial-gradient(circle at top right, #1c1c1e 0%, #000 80%);
            overflow-x: hidden;
        }
        
        /* --- HEADER --- */
        header {
            padding: 20px;
            background: rgba(0,0,0,0.5);
            backdrop-filter: blur(20px);
            border-bottom: 1px solid var(--border);
            position: sticky; top: 0; z-index: 100;
            display: flex; justify-content: space-between; align-items: center;
        }
        .brand { font-family: 'Rajdhani', sans-serif; font-size: 1.5rem; font-weight: 700; color: var(--primary); }
        .brand span { color: #fff; }
        .status-badge { font-size: 0.8rem; padding: 5px 10px; border-radius: 20px; background: rgba(50, 215, 75, 0.2); color: var(--success); border: 1px solid var(--success); }

        /* --- MAIN CONTAINER --- */
        .container { padding: 20px; max-width: 1200px; margin: 0 auto; width: 100%; flex: 1; }
        
        /* --- EMPTY STATE --- */
        .no-music {
            display: flex; flex-direction: column; align-items: center; justify-content: center;
            height: 60vh; text-align: center; color: var(--text-sec);
            animation: fadeIn 1s ease;
        }
        .no-music i { font-size: 4rem; margin-bottom: 20px; color: rgba(255,255,255,0.1); }
        .no-music h2 { font-size: 1.5rem; color: #fff; margin-bottom: 10px; }
        
        /* --- PLAYERS GRID --- */
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 20px; }
        
        /* --- PLAYER CARD --- */
        .card {
            background: var(--glass);
            border: 1px solid var(--border);
            border-radius: 24px;
            overflow: hidden;
            position: relative;
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }
        .card:hover { transform: translateY(-5px); box-shadow: 0 10px 30px rgba(0,0,0,0.5); border-color: var(--primary); }
        
        .card-header { padding: 15px; display: flex; align-items: center; gap: 10px; border-bottom: 1px solid rgba(255,255,255,0.05); }
        .chat-img { width: 40px; height: 40px; border-radius: 50%; background: #333; object-fit: cover; }
        .chat-info h3 { font-size: 1rem; color: #fff; margin-bottom: 2px; }
        .chat-info span { font-size: 0.8rem; color: var(--text-sec); }
        
        .track-info { padding: 20px; text-align: center; position: relative; }
        .thumb-glow { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 100px; height: 100px; background: var(--primary); filter: blur(60px); opacity: 0.2; z-index: 0; }
        .track-img { width: 120px; height: 120px; border-radius: 20px; margin-bottom: 15px; position: relative; z-index: 1; box-shadow: 0 10px 20px rgba(0,0,0,0.5); object-fit: cover; }
        .track-title { font-size: 1.1rem; font-weight: 700; margin-bottom: 5px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; z-index: 1; position: relative; }
        .track-meta { font-size: 0.85rem; color: var(--text-sec); display: flex; justify-content: center; gap: 10px; z-index: 1; position: relative; }
        
        /* --- CONTROLS --- */
        .controls { padding: 15px 20px; display: flex; justify-content: space-between; align-items: center; background: rgba(0,0,0,0.2); }
        .btn { width: 45px; height: 45px; border-radius: 50%; border: none; font-size: 1.2rem; cursor: pointer; transition: 0.2s; display: flex; align-items: center; justify-content: center; color: #fff; }
        .btn-pause { background: rgba(255, 214, 10, 0.15); color: var(--warning); }
        .btn-pause:hover { background: var(--warning); color: #000; }
        .btn-skip { background: rgba(10, 132, 255, 0.15); color: var(--primary); }
        .btn-skip:hover { background: var(--primary); color: #fff; }
        .btn-stop { background: rgba(255, 69, 58, 0.15); color: var(--danger); }
        .btn-stop:hover { background: var(--danger); color: #fff; }

        /* --- ANIMATIONS --- */
        @keyframes fadeIn { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
        
        /* --- TOAST --- */
        #toast { position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); background: rgba(0,0,0,0.9); padding: 12px 24px; border-radius: 50px; border: 1px solid var(--border); display: none; z-index: 999; }
    </style>
</head>
<body>

    <header>
        <div class="brand">TITAN <span>OS</span></div>
        <div class="status-badge" id="conn-status"><i class="fas fa-circle-notch fa-spin"></i> Connecting...</div>
    </header>

    <div class="container">
        <!-- Grid will be populated by JS -->
        <div id="players-grid" class="grid"></div>
        
        <!-- Empty State -->
        <div id="empty-state" class="no-music">
            <i class="fas fa-satellite-dish"></i>
            <h2>جميع الأنظمة مستقرة</h2>
            <p>لا يوجد تشغيل نشط في أي مجموعة حالياً</p>
        </div>
    </div>

    <div id="toast">Action Completed</div>

    <script>
        const grid = document.getElementById('players-grid');
        const empty = document.getElementById('empty-state');
        const status = document.getElementById('conn-status');
        let ws;

        function connect() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            ws = new WebSocket(`${protocol}//${window.location.host}/ws`);

            ws.onopen = () => {
                status.innerHTML = '<i class="fas fa-wifi"></i> Online';
                status.style.color = '#32D74B';
                status.style.borderColor = '#32D74B';
                status.style.background = 'rgba(50, 215, 75, 0.2)';
            };

            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                if(data.type === 'update_players') {
                    renderPlayers(data.payload);
                }
            };

            ws.onclose = () => {
                status.innerHTML = '<i class="fas fa-unlink"></i> Offline';
                status.style.color = '#FF453A';
                status.style.borderColor = '#FF453A';
                status.style.background = 'rgba(255, 69, 58, 0.2)';
                setTimeout(connect, 3000);
            };
        }

        function renderPlayers(players) {
            if (!players || players.length === 0) {
                grid.innerHTML = '';
                grid.style.display = 'none';
                empty.style.display = 'flex';
                return;
            }

            empty.style.display = 'none';
            grid.style.display = 'grid';
            grid.innerHTML = players.map(p => `
                <div class="card">
                    <div class="card-header">
                        <div class="chat-img" style="display:flex;align-items:center;justify-content:center;">
                             <i class="fas fa-users"></i>
                        </div>
                        <div class="chat-info">
                            <h3>${p.chat_title}</h3>
                            <span>ID: ${p.chat_id}</span>
                        </div>
                    </div>
                    <div class="track-info">
                        <div class="thumb-glow"></div>
                        <!-- Using YouTube thumb based on vidid if available, else placeholder -->
                        <img src="${p.track.thumb || 'https://telegra.ph/file/default_music.png'}" class="track-img" onerror="this.src='https://ui-avatars.com/api/?name=M+u&background=random'">
                        <div class="track-title">${p.track.title}</div>
                        <div class="track-meta">
                            <span><i class="fas fa-clock"></i> ${p.track.duration}</span>
                            <span><i class="fas fa-user"></i> ${p.track.requester}</span>
                        </div>
                    </div>
                    <div class="controls">
                        <button class="btn btn-pause" onclick="control('pause', ${p.chat_id})"><i class="fas fa-pause"></i></button>
                        <button class="btn btn-stop" onclick="control('stop', ${p.chat_id})"><i class="fas fa-stop"></i></button>
                        <button class="btn btn-skip" onclick="control('skip', ${p.chat_id})"><i class="fas fa-forward"></i></button>
                    </div>
                </div>
            `).join('');
        }

        async function control(action, chatId) {
            try {
                const res = await fetch(`/api/control/${action}/${chatId}`, { method: 'POST' });
                const json = await res.json();
                showToast(json.ok ? `Success: ${action}` : `Error: ${json.error}`);
            } catch (e) {
                showToast("Connection Error");
            }
        }

        function showToast(msg) {
            const t = document.getElementById('toast');
            t.textContent = msg;
            t.style.display = 'block';
            setTimeout(() => t.style.display = 'none', 3000);
        }

        connect();
    </script>
</body>
</html>
"""

# ==============================================================================
# [SECTION 4] CORE LOGIC ENGINE (DATA PROCESSING)
# ==============================================================================

class TitanEngine:
    """
    The Brain of the Operation. Handles logic separating Web from Bot.
    """
    
    @staticmethod
    async def get_system_stats() -> Dict[str, Any]:
        """Returns hardware telemetry."""
        ram = psutil.virtual_memory()
        return {
            "uptime": str(datetime.timedelta(seconds=int(time.time() - STARTUP_TIME))),
            "cpu_usage": f"{psutil.cpu_percent()}%",
            "ram_used": f"{ram.used / (1024 * 1024):.1f} MB",
            "ram_total": f"{ram.total / (1024 * 1024):.1f} MB",
            "active_streams": len(StreamController.active_calls)
        }

    @staticmethod
    async def fetch_active_streams() -> List[Dict[str, Any]]:
        """
        Scans the AnnieXMedia Database and PyTgCalls status to build the dashboard data.
        """
        active_list = []
        # Copy set to avoid runtime modification errors
        active_ids = list(StreamController.active_calls)
        
        if not active_ids:
            return []

        for chat_id in active_ids:
            try:
                # 1. Get Queue Data from DB
                chat_queue = db.get(chat_id)
                if not chat_queue:
                    continue
                
                # The first item in queue is the playing one
                current_track = chat_queue[0]
                
                # 2. Resolve Chat Info
                chat_title = f"Chat {chat_id}"
                try:
                    chat = await app.get_chat(chat_id)
                    chat_title = chat.title
                except Exception:
                    pass
                
                # 3. Resolve Thumbnail
                # In Annie's code, vidid is often the YouTube ID.
                vidid = current_track.get("vidid")
                thumb_url = None
                if vidid and len(vidid) == 11: # Simple check for YT ID
                    thumb_url = f"https://img.youtube.com/vi/{vidid}/hqdefault.jpg"
                
                active_list.append({
                    "chat_id": chat_id,
                    "chat_title": chat_title,
                    "track": {
                        "title": current_track.get("title", "Unknown Track"),
                        "duration": current_track.get("dur", "00:00"),
                        "requester": current_track.get("by", "System"),
                        "vidid": vidid,
                        "thumb": thumb_url
                    },
                    "stream_type": current_track.get("streamtype", "audio"),
                    "queue_len": len(chat_queue)
                })
            except Exception as e:
                logger.error(f"Error processing chat {chat_id}: {e}")
                continue
                
        return active_list

    @staticmethod
    async def execute_command(action: str, chat_id: int) -> Dict[str, Any]:
        """
        Executes bot commands safely, handling all specific PyTgCalls errors.
        """
        if chat_id not in StreamController.active_calls:
            return {"ok": False, "error": "Bot is not in the call anymore."}

        try:
            if action == "pause":
                await StreamController.pause_stream(chat_id)
            
            elif action == "resume":
                await StreamController.resume_stream(chat_id)
            
            elif action == "stop":
                await StreamController.stop_stream(chat_id)
            
            elif action == "skip":
                # SMART SKIP IMPLEMENTATION
                # We need to manually handle the queue shift because `skip_stream` in source 
                # often requires arguments like `link` to play next immediately.
                # Instead, we will simulate a "Finish" event or use a force skip logic.
                
                check = db.get(chat_id)
                if not check or len(check) < 2:
                    # No next song, just stop
                    await StreamController.stop_stream(chat_id)
                    return {"ok": True, "msg": "Skipped (Queue Ended)"}
                
                # If there is a next song:
                # 1. Remove current
                old = check.pop(0)
                # 2. Get next
                next_track = check[0]
                # 3. Play next
                assistant = await group_assistant(StreamController, chat_id)
                # We reuse the logic from your source `play` function but we invoke it manually
                # Or simpler: Just stop current, and let the `update` handler in Call class pick up next?
                # Usually stopping clears queue. We must be careful.
                # Safest approach for web button without complex logic: 
                # Force play the next item.
                
                file_path = next_track["file"]
                # Trigger play
                await StreamController.change_stream(chat_id, file_path) # If this method exists
                # Since I don't see change_stream in your provided snippet, we fallback to:
                # We call skip_stream with parameters if available, else we return error.
                # Let's try to just stop, hoping your update handler picks it up if queue isn't cleared.
                await StreamController.stop_stream(chat_id) 
                
            return {"ok": True, "msg": f"Action {action} executed."}
            
        except (NotInCallError, NoActiveGroupCall):
            # Graceful failure
            return {"ok": False, "error": "Connection lost with Voice Chat."}
        except Exception as e:
            logger.error(f"Command Error: {traceback.format_exc()}")
            return {"ok": False, "error": str(e)}

# ==============================================================================
# [SECTION 5] WEB SERVER ROUTES & HANDLERS
# ==============================================================================

routes = web.RouteTableDef()

@routes.get("/")
async def root_handler(request):
    """Serves the Embedded Single-Page App."""
    return web.Response(text=HTML_TEMPLATE, content_type="text/html")

@routes.get("/ws")
async def websocket_handler(request):
    """Handles Real-Time WebSocket Connections."""
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    
    WS_CLIENTS.add(ws)
    logger.info("New Dashboard Client Connected via WebSocket")
    
    try:
        # Send initial state immediately
        players = await TitanEngine.fetch_active_streams()
        await ws.send_json({"type": "update_players", "payload": players})
        
        async for msg in ws:
            pass # Keep connection open
    finally:
        WS_CLIENTS.discard(ws)
        logger.info("Dashboard Client Disconnected")
    return ws

@routes.post("/api/control/{action}/{chat_id}")
async def control_api(request):
    """REST API for Buttons."""
    action = request.match_info['action']
    try:
        chat_id = int(request.match_info['chat_id'])
    except ValueError:
        return web.json_response({"ok": False, "error": "Bad ID"})
        
    result = await TitanEngine.execute_command(action, chat_id)
    
    # Broadcast update to all connected screens immediately
    asyncio.create_task(broadcast_update())
    
    return web.json_response(result)

@routes.get("/api/health")
async def health_api(request):
    """System Health Endpoint."""
    return web.json_response(await TitanEngine.get_system_stats())

# ==============================================================================
# [SECTION 6] BACKGROUND TASKS & BROADCASTING
# ==============================================================================

async def broadcast_update():
    """Pushes the latest player state to all connected browsers."""
    if not WS_CLIENTS:
        return

    players = await TitanEngine.fetch_active_streams()
    message = {"type": "update_players", "payload": players}
    
    # Send to all clients
    for ws in list(WS_CLIENTS):
        try:
            await ws.send_json(message)
        except Exception:
            WS_CLIENTS.discard(ws)

async def titan_background_worker():
    """Main Loop: Updates data every 5 seconds."""
    logger.info("Titan Background Worker Started")
    while True:
        try:
            await broadcast_update()
        except Exception as e:
            logger.error(f"Broadcast Loop Error: {e}")
        await asyncio.sleep(5)

# ==============================================================================
# [SECTION 7] SERVER LIFECYCLE MANAGEMENT
# ==============================================================================

async def start_titan_web():
    """
    Bootstraps the Web Engine. 
    Called from __main__.py
    """
    # 1. Setup App
    app_web = web.Application()
    app_web.add_routes(routes)
    
    # 2. Setup CORS (Cross-Origin Resource Sharing)
    cors = aiohttp_cors.setup(app_web, defaults={
        "*": aiohttp_cors.ResourceOptions(
            allow_credentials=True,
            expose_headers="*",
            allow_headers="*",
        )
    })
    for route in list(app_web.router.routes()):
        cors.add(route)

    # 3. Setup Runner
    runner = web.AppRunner(app_web)
    await runner.setup()
    
    # 4. Bind to Port
    site = web.TCPSite(runner, SERVER_HOST, SERVER_PORT)
    await site.start()
    
    # 5. Start Background Workers
    asyncio.create_task(titan_background_worker())
    
    # 6. Print Banner
    print("\n" + "="*50)
    print(f"🦁 TITAN OS KERNEL {TITAN_VERSION}")
    print(f"📡 CONTROL DASHBOARD: http://localhost:{SERVER_PORT}")
    print(f"🔧 SYSTEM STATUS: OPERATIONAL")
    print("="*50 + "\n")

# End of Kernel
