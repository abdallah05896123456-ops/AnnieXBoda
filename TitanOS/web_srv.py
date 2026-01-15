# -*- coding: utf-8 -*-
# ==============================================================================
# TITAN OS | BRIDGE SERVER (API ONLY)
# ==============================================================================

import os
import sys
import time
import psutil
import logging
import asyncio
from aiohttp import web
import aiohttp_cors

# --- ربط السورس (AnnieXMedia) ---
try:
    from AnnieXMedia import app
    from AnnieXMedia.core.call import StreamController
    from AnnieXMedia.misc import db
    from config import API_ID, API_HASH
except ImportError:
    print("CRITICAL: AnnieXMedia module not found.")
    sys.exit(1)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TitanBridge")

routes = web.RouteTableDef()

# --- 1. تقديم ملف الواجهة (Dashboard) ---
@routes.get("/")
async def serve_dashboard(request):
    """يقرأ ملف dashboard.html ويعرضه"""
    if os.path.exists("dashboard.html"):
        return web.FileResponse("dashboard.html")
    return web.Response(text="<h1>Error: dashboard.html not found!</h1>", content_type="text/html")

# --- 2. تقديم ملف السجلات ---
@routes.get("/logs")
async def serve_logs(request):
    """يقرأ ملف اللوجات"""
    log_file = "log.txt" # تأكد من اسم ملف اللوج في بوتك
    if os.path.exists(log_file):
        return web.FileResponse(log_file)
    return web.Response(text="No logs found yet.")

# --- 3. الـ API (المحرك) ---

@routes.get("/api/active_calls")
async def api_get_calls(request):
    """جلب قائمة المكالمات النشطة"""
    active_chats = []
    try:
        active_ids = list(StreamController.active_calls)
        for chat_id in active_ids:
            chat_name = f"Chat {chat_id}"
            try:
                chat = await app.get_chat(chat_id)
                chat_name = chat.title
            except: pass
            
            active_chats.append({
                "id": chat_id,
                "name": chat_name
            })
    except Exception as e:
        logger.error(f"Scan Error: {e}")
    return web.json_response({"chats": active_chats})

@routes.get("/api/track_info/{chat_id}")
async def api_track_info(request):
    """جلب معلومات الأغنية الحالية"""
    chat_id = int(request.match_info['chat_id'])
    default = {"title": "System Idle", "artist": "---", "cover": ""}
    
    if chat_id in db:
        data = db[chat_id]
        if data:
            track = data[0]
            vidid = track.get("vidid")
            cover = f"https://img.youtube.com/vi/{vidid}/hqdefault.jpg" if vidid else ""
            return web.json_response({
                "title": track.get("title", "Unknown"),
                "artist": track.get("by", "Unknown"),
                "cover": cover
            })
    return web.json_response(default)

@routes.post("/api/{cmd}/{chat_id}")
async def api_control(request):
    """التحكم (Play, Pause, Skip, Stop)"""
    cmd = request.match_info['cmd']
    try:
        chat_id = int(request.match_info['chat_id'])
        if cmd == "pause": await StreamController.pause_stream(chat_id)
        elif cmd == "resume": await StreamController.resume_stream(chat_id)
        elif cmd == "stop": await StreamController.stop_stream(chat_id)
        elif cmd == "skip": await StreamController.stop_stream(chat_id) # Skip via stop logic
        return web.json_response({"ok": True})
    except Exception as e:
        return web.json_response({"ok": False, "error": str(e)})

# --- 4. أوامر النظام (Turbo & Cache) ---
@routes.post("/api/system/turbo")
async def api_turbo(request):
    """تفريغ الرام"""
    try:
        import gc
        gc.collect()
        return web.json_response({"ok": True, "msg": "RAM Cleaned"})
    except:
        return web.json_response({"ok": False})

@routes.post("/api/system/cleancache")
async def api_clean(request):
    """حذف ملفات الكاش"""
    try:
        os.system("rm -rf downloads/")
        os.system("rm -rf cache/")
        return web.json_response({"ok": True, "msg": "Cache Cleared"})
    except:
        return web.json_response({"ok": False})

# --- تشغيل السيرفر ---
async def start_titan_web():
    app_web = web.Application()
    app_web.add_routes(routes)
    cors = aiohttp_cors.setup(app_web, defaults={"*": aiohttp_cors.ResourceOptions(allow_credentials=True, expose_headers="*", allow_headers="*")})
    for route in list(app_web.router.routes()): cors.add(route)
    runner = web.AppRunner(app_web)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8080)
    await site.start()
    print("✅ TITAN WEB SERVICE STARTED ON PORT 8080")
