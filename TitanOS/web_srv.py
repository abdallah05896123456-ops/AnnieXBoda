# -*- coding: utf-8 -*-
# ==============================================================================
# TITAN OS | BRIDGE SERVER (API & STREAMING)
# ==============================================================================

import os
import sys
import logging
import asyncio
from aiohttp import web
import aiohttp_cors

# --- ربط السورس (AnnieXMedia Integration) ---
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

# ------------------------------------------------------------------------------
# 1. تقديم الصفحات (Frontend Serving)
# ------------------------------------------------------------------------------

@routes.get("/")
async def serve_dashboard(request):
    """يقرأ ملف dashboard.html ويعرضه"""
    if os.path.exists("dashboard.html"):
        return web.FileResponse("dashboard.html")
    return web.Response(text="<h1>Error: dashboard.html not found!</h1>", content_type="text/html")

@routes.get("/logs")
async def serve_logs(request):
    """يقرأ ملف اللوجات"""
    # غير اسم الملف هنا لو اسم ملف اللوج عندك مختلف
    log_files = ["log.txt", "AnnieXMedia.log", "logs.txt"]
    for f in log_files:
        if os.path.exists(f):
            return web.FileResponse(f)
    return web.Response(text="No logs found.")

# ------------------------------------------------------------------------------
# 2. الفيديو ستريمنج (Video Streaming Bridge)
# ------------------------------------------------------------------------------

@routes.get("/stream/{chat_id}")
async def stream_handler(request):
    """مسار خاص لتشغيل الفيديو داخل الموقع"""
    chat_id = int(request.match_info['chat_id'])
    
    # محاولة العثور على الملف المحلي المشغل حالياً
    if chat_id in db and db[chat_id]:
        track = db[chat_id][0]
        file_path = track.get("file")
        
        if file_path and os.path.exists(file_path):
            # يقوم بتقديم الملف للمتصفح كـ فيديو
            return web.FileResponse(file_path)
            
    return web.Response(status=404, text="No active stream file found locally.")

# ------------------------------------------------------------------------------
# 3. الـ API (البيانات والتحكم)
# ------------------------------------------------------------------------------

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
    """جلب معلومات الأغنية + رابط الفيديو"""
    try:
        chat_id = int(request.match_info['chat_id'])
        default = {"title": "System Idle", "artist": "Waiting...", "cover": "", "has_video": False}
        
        if chat_id in db:
            data = db[chat_id]
            if data:
                track = data[0]
                vidid = track.get("vidid")
                # جلب صورة الغلاف
                cover = f"https://img.youtube.com/vi/{vidid}/hqdefault.jpg" if vidid else "https://telegra.ph/file/default_music.png"
                
                return web.json_response({
                    "title": track.get("title", "Unknown Track"),
                    "artist": track.get("by", "Unknown Artist"),
                    "cover": cover,
                    # هذا الرابط هو اللي هيشغل الفيديو في الموقع
                    "stream_url": f"/stream/{chat_id}" 
                })
        return web.json_response(default)
    except:
        return web.json_response({})

@routes.post("/api/{cmd}/{chat_id}")
async def api_control(request):
    """التحكم (Play, Pause, Skip, Stop)"""
    cmd = request.match_info['cmd']
    try:
        chat_id = int(request.match_info['chat_id'])
        if cmd == "pause": await StreamController.pause_stream(chat_id)
        elif cmd == "resume": await StreamController.resume_stream(chat_id)
        elif cmd == "stop": await StreamController.stop_stream(chat_id)
        elif cmd == "skip": 
             # محاولة تخطي بسيطة (يمكن تحسينها حسب السورس)
             await StreamController.stop_stream(chat_id) 
        return web.json_response({"ok": True})
    except Exception as e:
        return web.json_response({"ok": False, "error": str(e)})

# ------------------------------------------------------------------------------
# 4. أوامر النظام (Turbo & Cache)
# ------------------------------------------------------------------------------

@routes.post("/api/system/turbo")
async def api_turbo(request):
    """تنظيف الرامات"""
    try:
        import gc
        gc.collect()
        return web.json_response({"ok": True})
    except:
        return web.json_response({"ok": False})

@routes.post("/api/system/cleancache")
async def api_clean(request):
    """حذف الكاش"""
    try:
        # أوامر تنظيف لينكس
        os.system("rm -rf downloads/")
        os.system("rm -rf cache/")
        return web.json_response({"ok": True})
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
