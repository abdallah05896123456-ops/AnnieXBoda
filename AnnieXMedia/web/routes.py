# ==============================================================================
# ☢️ ANNIE-X ULTIMATE CORE - WEB CONTROLLER
# Authored By Certified Coders © 2025
# Integrated Features: Mixer, Files, Terminal, Userbot, DB, Security, AI Logic
# ==============================================================================

import asyncio
import os
import sys
import shutil
import psutil
import logging
import subprocess
import time
import signal
import platform
import socket
import zipfile
import speedtest
from datetime import datetime
from io import StringIO
from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for, send_file, Response
from werkzeug.utils import secure_filename

# --- Core Bot Imports ---
from AnnieXMedia import app as bot_app
from AnnieXMedia import userbot as ub_instance
from AnnieXMedia.core.call import StreamController
from config import WEB_PASSWORD, OWNER_ID

# --- Database Imports (The Power Source) ---
try:
    from AnnieXMedia.utils.database import (
        get_active_chats, remove_active_chat, get_served_chats, get_served_users,
        add_gban_user, remove_gban_user, is_gbanned_user, get_gbanned,
        add_sudo, remove_sudo, get_sudoers,
        blacklist_chat, whitelist_chat, blacklisted_chats,
        get_client # لجلب كلاس اليوزربوت المحدد من الداتابيز
    )
except ImportError:
    # Fallback to prevent crash if DB module varies
    logging.error("CRITICAL: Database functions import failed. Web dashboard capabilities reduced.")

# --- System Configuration ---
web_bp = Blueprint('web', __name__)
UPLOAD_FOLDER = 'downloads'
CACHE_FOLDER = 'cache'
if not os.path.exists(UPLOAD_FOLDER): os.makedirs(UPLOAD_FOLDER)

# --- Global State Variables ---
AUDIT_LOGS = [] # سجل العمليات في الرام
PRIORITY_CHAT_ID = None # متغير وضع التركيز

# ==============================================================================
# 🛠️ HELPER FUNCTIONS
# ==============================================================================

def run_async(coro):
    """Bridge between Flask (Sync) and Pyrogram (Async)"""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            return asyncio.run_coroutine_threadsafe(coro, loop)
    except:
        pass
    return None

def is_auth():
    """Check session authentication"""
    return session.get('authenticated', False)

def log_action(action, details, user="Admin"):
    """Save actions to Audit Log"""
    entry = {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "user": user,
        "action": action,
        "details": details
    }
    AUDIT_LOGS.insert(0, entry)
    if len(AUDIT_LOGS) > 100: AUDIT_LOGS.pop() # Keep last 100

async def send_cmd_via_userbot(chat_id, command):
    """Magic Trick: Use Userbot to control the bot via chat commands"""
    client = ub_instance.one # Use Assistant 1
    try:
        await client.send_message(int(chat_id), command)
        return True
    except Exception as e:
        return str(e)

# ==============================================================================
# 🔐 AUTHENTICATION ROUTES
# ==============================================================================

@web_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('password') == WEB_PASSWORD:
            session['authenticated'] = True
            log_action("LOGIN", "Session started")
            return redirect(url_for('web.dashboard'))
        return render_template('index.html', error="ACCESS DENIED", login_page=True)
    return render_template('index.html', login_page=True)

@web_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('web.login'))

@web_bp.route('/')
def dashboard():
    if not is_auth(): return redirect(url_for('web.login'))
    return render_template('index.html', login_page=False)

# ==============================================================================
# 📊 API: SYSTEM & STATS (The Dashboard Brain)
# ==============================================================================

@web_bp.route('/api/stats_full')
def api_stats_full():
    if not is_auth(): return jsonify({}), 403
    
    # 1. Hardware Stats
    cpu = psutil.cpu_percent()
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    net = psutil.net_io_counters()
    boot_time = datetime.fromtimestamp(psutil.boot_time()).strftime("%Y-%m-%d %H:%M:%S")
    
    # 2. Bot Logic (Async Wrapper)
    async def _get_bot_stats():
        users = len(await get_served_users())
        chats = len(await get_served_chats())
        gbans = len(await get_gbanned())
        sudos = len(await get_sudoers())
        active = len(await get_active_chats())
        return users, chats, gbans, sudos, active

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    u, c, g, s, a = loop.run_until_complete(_get_bot_stats())
    loop.close()

    return jsonify({
        "hardware": {
            "cpu": cpu,
            "ram_percent": ram.percent,
            "ram_used": f"{ram.used / (1024**3):.2f} GB",
            "disk": disk.percent,
            "net_sent": f"{net.bytes_sent / (1024**2):.2f} MB",
            "net_recv": f"{net.bytes_recv / (1024**2):.2f} MB",
            "uptime": boot_time
        },
        "bot": {
            "users": u, "chats": c, "gbanned": g, "sudoers": s, "active_calls": a,
            "priority_mode": PRIORITY_CHAT_ID
        }
    })

# ==============================================================================
# 🎛️ API: MIXER & STREAM CONTROL (The Studio)
# ==============================================================================

@web_bp.route('/api/mixer', methods=['POST'])
def mixer_control():
    if not is_auth(): return jsonify({}), 403
    data = request.json
    chat_id = data.get('chat_id')
    cmd = data.get('cmd') # pause, resume, skip, stop, shuffle
    val = data.get('val') # volume

    if not chat_id: return jsonify({"error": "No Chat ID"})

    # تنفيذ الأوامر بطريقتين: إما مباشرة بالكود أو عبر اليوزربوت (لضمان التفاعل)
    text_cmd = ""
    if cmd == 'volume': text_cmd = f"/volume {val}"
    elif cmd == 'pause': text_cmd = "/pause"
    elif cmd == 'resume': text_cmd = "/resume"
    elif cmd == 'skip': text_cmd = "/skip"
    elif cmd == 'shuffle': text_cmd = "/shuffle"
    elif cmd == 'stop': text_cmd = "/stop"
    
    # إرسال الأمر عبر اليوزربوت ليراه الجميع في الجروب
    run_async(send_cmd_via_userbot(chat_id, text_cmd))
    
    # تنفيذ إجباري من الكود (Double Kill)
    try:
        if cmd == 'stop': run_async(StreamController.force_stop_stream(int(chat_id)))
        if cmd == 'pause': run_async(StreamController.pause_stream(int(chat_id)))
        if cmd == 'resume': run_async(StreamController.resume_stream(int(chat_id)))
    except: pass

    log_action("MIXER", f"Executed {cmd} in {chat_id}")
    return jsonify({"status": "ok", "msg": f"Command {cmd} sent!"})

# ==============================================================================
# ☢️ API: PRIORITY MODE (Server Focus)
# ==============================================================================

@web_bp.route('/api/priority', methods=['POST'])
def set_priority():
    global PRIORITY_CHAT_ID
    if not is_auth(): return jsonify({}), 403
    chat_id = request.json.get('chat_id')

    if chat_id == "OFF":
        PRIORITY_CHAT_ID = None
        log_action("PRIORITY", "Disabled Focus Mode")
        return jsonify({"status": "ok", "msg": "Focus Mode Disabled. Resources Balanced."})
    
    try:
        target = int(chat_id)
        PRIORITY_CHAT_ID = target
        
        async def _nuke_others():
            active = await get_active_chats()
            killed = 0
            for chat in active:
                cid = chat['chat_id'] if isinstance(chat, dict) else chat
                if int(cid) != target:
                    await StreamController.force_stop_stream(cid)
                    killed += 1
            return killed
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        killed_count = loop.run_until_complete(_nuke_others())
        
        log_action("PRIORITY", f"Focused on {target}, Killed {killed_count} streams")
        return jsonify({"status": "ok", "msg": f"Server Focused on {target}. Terminated {killed_count} other streams."})
    except Exception as e:
        return jsonify({"error": str(e)})

# ==============================================================================
# 🤖 API: USERBOT MANAGEMENT (Clone Control)
# ==============================================================================

@web_bp.route('/api/assistant/update', methods=['POST'])
def assistant_update():
    if not is_auth(): return jsonify({}), 403
    data = request.json
    num = data.get('num') # 1,2,3,4,5
    name = data.get('name')
    bio = data.get('bio')
    
    async def _update_bot():
        # نفترض أن ub_instance يحتوي على الكلاينتس كـ lists أو attributes
        clients = [ub_instance.one, ub_instance.two, ub_instance.three, ub_instance.four, ub_instance.five]
        cli = clients[int(num)-1]
        if name: await cli.update_profile(first_name=name)
        if bio: await cli.update_profile(bio=bio)
    
    run_async(_update_bot())
    log_action("USERBOT", f"Updated Assistant {num}")
    return jsonify({"status": "ok", "msg": f"Assistant {num} Profile Updated"})

@web_bp.route('/api/assistant/join', methods=['POST'])
def assistant_join():
    if not is_auth(): return jsonify({}), 403
    link = request.json.get('link')
    
    async def _join_all():
        clients = [ub_instance.one, ub_instance.two, ub_instance.three, ub_instance.four, ub_instance.five]
        success = 0
        for cli in clients:
            try:
                await cli.join_chat(link)
                success += 1
            except: pass
        return success
    
    count = run_async(_join_all()) # Note: This needs proper async handling in prod
    log_action("USERBOT", f"Joined {link}")
    return jsonify({"status": "ok", "msg": f"Assistants joining..."})

# ==============================================================================
# 💻 API: TERMINAL & PROCESSES (God Mode)
# ==============================================================================

@web_bp.route('/api/terminal', methods=['POST'])
def term_exec():
    if not is_auth(): return jsonify({}), 403
    cmd = request.json.get('cmd')
    
    try:
        res = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT)
        output = res.decode('utf-8')
    except subprocess.CalledProcessError as e:
        output = e.output.decode('utf-8')
    except Exception as e:
        output = str(e)
        
    log_action("TERMINAL", f"Executed: {cmd}")
    return jsonify({"output": output})

@web_bp.route('/api/processes', methods=['GET'])
def get_procs():
    if not is_auth(): return jsonify({}), 403
    procs = []
    for p in psutil.process_iter(['pid', 'name', 'memory_percent', 'cpu_percent']):
        try:
            procs.append(p.info)
        except: pass
    procs.sort(key=lambda x: x['memory_percent'] or 0, reverse=True)
    return jsonify({"processes": procs[:20]}) # Top 20

@web_bp.route('/api/kill_proc', methods=['POST'])
def kill_proc():
    if not is_auth(): return jsonify({}), 403
    pid = int(request.json.get('pid'))
    try:
        os.kill(pid, signal.SIGKILL)
        log_action("PROCESS", f"Killed PID {pid}")
        return jsonify({"status": "ok"})
    except Exception as e: return jsonify({"error": str(e)})

# ==============================================================================
# 📁 API: FILE MANAGER & CONFIG (The Vault)
# ==============================================================================

@web_bp.route('/api/files')
def list_files():
    if not is_auth(): return jsonify({}), 403
    path = request.args.get('path', '.')
    files = []
    try:
        with os.scandir(path) as entries:
            for entry in entries:
                files.append({
                    "name": entry.name,
                    "is_dir": entry.is_dir(),
                    "size": entry.stat().st_size if not entry.is_dir() else 0,
                    "path": entry.path
                })
    except Exception as e: return jsonify({"error": str(e)})
    return jsonify({"files": files, "current": os.path.abspath(path)})

@web_bp.route('/api/upload', methods=['POST'])
def upload_file():
    if not is_auth(): return jsonify({}), 403
    if 'file' not in request.files: return jsonify({"error": "No file"})
    file = request.files['file']
    if file:
        filename = secure_filename(file.filename)
        path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(path)
        log_action("FILES", f"Uploaded {filename}")
        return jsonify({"status": "ok", "path": path})

@web_bp.route('/api/config', methods=['GET', 'POST'])
def config_editor():
    if not is_auth(): return jsonify({}), 403
    config_file = "config.py" if os.path.exists("config.py") else ".env"
    
    if request.method == 'GET':
        with open(config_file, 'r') as f: content = f.read()
        return jsonify({"content": content, "filename": config_file})
    
    if request.method == 'POST':
        content = request.json.get('content')
        # إنشاء نسخة احتياطية قبل الحفظ
        shutil.copy(config_file, config_file + ".bak")
        with open(config_file, 'w') as f: f.write(content)
        log_action("CONFIG", "Modified Configuration")
        return jsonify({"status": "ok", "msg": "Config Saved! Restart Recommended."})

@web_bp.route('/api/backup')
def download_backup():
    if not is_auth(): return jsonify({}), 403
    zip_name = f"backup_{datetime.now().strftime('%Y%m%d')}.zip"
    with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk('.'):
            if 'venv' in root or '.git' in root: continue # Skip junk
            for file in files:
                zipf.write(os.path.join(root, file))
    return send_file(zip_name, as_attachment=True)

# ==============================================================================
# 🛡️ API: SECURITY & BROADCAST (The Shield)
# ==============================================================================

@web_bp.route('/api/security', methods=['POST'])
def security_action():
    if not is_auth(): return jsonify({}), 403
    cmd = request.json.get('cmd')
    target_id = int(request.json.get('id'))
    
    async def _exec_sec():
        if cmd == 'add_sudo': await add_sudo(target_id)
        elif cmd == 'rem_sudo': await remove_sudo(target_id)
        elif cmd == 'gban': await add_gban_user(target_id)
        elif cmd == 'ungban': await remove_gban_user(target_id)
        elif cmd == 'ban_chat': await blacklist_chat(target_id)
        elif cmd == 'unban_chat': await whitelist_chat(target_id)

    run_async(_exec_sec())
    log_action("SECURITY", f"{cmd} on {target_id}")
    return jsonify({"status": "ok"})

@web_bp.route('/api/broadcast', methods=['POST'])
def broadcast():
    if not is_auth(): return jsonify({}), 403
    msg = request.json.get('msg')
    pin = request.json.get('pin', False)
    
    async def _bc():
        chats = await get_served_chats()
        count = 0
        for c in chats:
            try:
                cid = c['chat_id'] if isinstance(c, dict) else c
                m = await bot_app.send_message(cid, msg)
                if pin: await m.pin()
                count += 1
                await asyncio.sleep(0.1)
            except: pass
        return count
    
    run_async(_bc())
    log_action("BROADCAST", "Started Global Broadcast")
    return jsonify({"status": "ok", "msg": "Broadcast Queued"})

@web_bp.route('/api/logs')
def get_logs():
    if not is_auth(): return jsonify({}), 403
    return jsonify({"logs": AUDIT_LOGS})

@web_bp.route('/api/action', methods=['POST'])
def sys_action():
    if not is_auth(): return jsonify({}), 403
    cmd = request.json.get('cmd')
    
    if cmd == 'restart':
        log_action("SYSTEM", "Restart Initiated")
        os.execl(sys.executable, sys.executable, "-m", "AnnieXMedia")
    elif cmd == 'git_pull':
        os.system("git pull")
        log_action("SYSTEM", "Git Pull Executed")
        
    return jsonify({"status": "ok"})

@web_bp.route('/api/speedtest')
def network_speed():
    if not is_auth(): return jsonify({}), 403
    try:
        st = speedtest.Speedtest()
        st.get_best_server()
        dl = st.download() / 1_000_000
        ul = st.upload() / 1_000_000
        ping = st.results.ping
        return jsonify({"dl": f"{dl:.2f}", "ul": f"{ul:.2f}", "ping": ping})
    except: return jsonify({"error": "Speedtest failed"})

# ==============================================================================
# END OF ROUTES
# ==============================================================================
