import os
import sys
import glob
import json
import time
import shutil
import psutil
import socket
import signal
import asyncio
import logging
import zipfile
import platform
import subprocess
import traceback
from io import BytesIO
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for, send_file, Response, make_response
from werkzeug.utils import secure_filename
from pyrogram import Client, filters, enums
from pyrogram.types import Message
from AnnieXMedia import app, userbot
from AnnieXMedia.core.call import StreamController
from AnnieXMedia.utils.database import get_served_chats, get_served_users, add_gban_user, remove_gban_user, is_gbanned_user, get_sudoers, add_sudo, remove_sudo, get_active_chats, remove_active_chat, blacklist_chat, whitelist_chat
from config import WEB_PASSWORD, OWNER_ID, MONGO_DB_URI

web_bp = Blueprint('web', __name__)
CORE_START_TIME = time.time()
AUDIT_LOGS = []
PRIORITY_CHAT = None
MAX_LOGS = 500

def run_async(coroutine):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            return asyncio.run_coroutine_threadsafe(coroutine, loop)
        else:
            return loop.run_until_complete(coroutine)
    except Exception:
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)
        return new_loop.run_until_complete(coroutine)

def check_auth():
    return session.get('authenticated', False)

def audit(action, details, ip):
    global AUDIT_LOGS
    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "action": action.upper(),
        "details": str(details),
        "ip": ip
    }
    AUDIT_LOGS.insert(0, entry)
    if len(AUDIT_LOGS) > MAX_LOGS:
        AUDIT_LOGS.pop()

def get_readable_time(seconds: int) -> str:
    count = 0
    ping_time = ""
    time_list = []
    time_suffix_list = ["s", "m", "h", "days"]
    while count < 4:
        count += 1
        remainder, result = divmod(seconds, 60) if count < 3 else divmod(seconds, 24)
        if seconds == 0 and remainder == 0:
            break
        time_list.append(int(result))
        seconds = int(remainder)
    for x in range(len(time_list)):
        time_list[x] = str(time_list[x]) + time_suffix_list[x]
    if len(time_list) == 4:
        ping_time += time_list.pop() + ", "
    time_list.reverse()
    ping_time += ":".join(time_list)
    return ping_time

def get_system_stats():
    cpu_freq = psutil.cpu_freq()
    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()
    disk = psutil.disk_usage('/')
    net_io = psutil.net_io_counters()
    try:
        temps = psutil.sensors_temperatures()
        cpu_temp = temps['cpu_thermal'][0].current if 'cpu_thermal' in temps else 0
    except:
        cpu_temp = 0
    return {
        "cpu": {
            "percent": psutil.cpu_percent(interval=None),
            "cores": psutil.cpu_count(logical=False),
            "threads": psutil.cpu_count(logical=True),
            "freq_current": f"{cpu_freq.current:.2f}Mhz" if cpu_freq else "N/A",
            "temp": cpu_temp
        },
        "memory": {
            "total": f"{mem.total / (1024**3):.2f}GB",
            "available": f"{mem.available / (1024**3):.2f}GB",
            "percent": mem.percent,
            "used": f"{mem.used / (1024**3):.2f}GB"
        },
        "swap": {
            "total": f"{swap.total / (1024**3):.2f}GB",
            "used": f"{swap.used / (1024**3):.2f}GB",
            "percent": swap.percent
        },
        "disk": {
            "total": f"{disk.total / (1024**3):.2f}GB",
            "used": f"{disk.used / (1024**3):.2f}GB",
            "percent": disk.percent
        },
        "network": {
            "sent": f"{net_io.bytes_sent / (1024**2):.2f}MB",
            "recv": f"{net_io.bytes_recv / (1024**2):.2f}MB"
        },
        "os": {
            "system": platform.system(),
            "release": platform.release(),
            "uptime": get_readable_time(int(time.time() - psutil.boot_time()))
        },
        "bot_uptime": get_readable_time(int(time.time() - CORE_START_TIME))
    }

@web_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('password') == WEB_PASSWORD:
            session['authenticated'] = True
            audit("LOGIN", "Success", request.remote_addr)
            return redirect(url_for('web.dashboard'))
        audit("LOGIN", "Failed Attempt", request.remote_addr)
        return render_template('index.html', error="INVALID CREDENTIALS", login_page=True)
    return render_template('index.html', login_page=True)

@web_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('web.login'))

@web_bp.route('/')
def dashboard():
    if not check_auth(): return redirect(url_for('web.login'))
    return render_template('index.html', login_page=False)

@web_bp.route('/api/system_monitor', methods=['GET'])
def api_system_monitor():
    if not check_auth(): return jsonify({"error": "Unauthorized"}), 401
    return jsonify(get_system_stats())

@web_bp.route('/api/processes', methods=['GET'])
def api_processes():
    if not check_auth(): return jsonify({"error": "Unauthorized"}), 401
    procs = []
    for p in psutil.process_iter(['pid', 'name', 'username', 'cpu_percent', 'memory_percent']):
        try:
            procs.append(p.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    procs.sort(key=lambda x: x['memory_percent'] or 0, reverse=True)
    return jsonify({"data": procs[:50]})

@web_bp.route('/api/kill_process', methods=['POST'])
def api_kill_process():
    if not check_auth(): return jsonify({"error": "Unauthorized"}), 401
    try:
        pid = int(request.json.get('pid'))
        os.kill(pid, signal.SIGKILL)
        audit("PROCESS_KILL", f"PID: {pid}", request.remote_addr)
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@web_bp.route('/api/terminal/exec', methods=['POST'])
def api_terminal_exec():
    if not check_auth(): return jsonify({"error": "Unauthorized"}), 401
    cmd = request.json.get('cmd')
    if not cmd: return jsonify({"output": "No command provided"})
    try:
        process = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            shell=True, 
            text=True
        )
        stdout, stderr = process.communicate(timeout=10)
        output = stdout + stderr
    except subprocess.TimeoutExpired:
        process.kill()
        output = "Command Timed Out"
    except Exception as e:
        output = str(e)
    audit("TERMINAL", cmd, request.remote_addr)
    return jsonify({"output": output})

@web_bp.route('/api/files/list', methods=['GET'])
def api_files_list():
    if not check_auth(): return jsonify({"error": "Unauthorized"}), 401
    path = request.args.get('path', os.getcwd())
    if not os.path.isdir(path):
        path = os.getcwd()
    items = []
    try:
        with os.scandir(path) as it:
            for entry in it:
                stats = entry.stat()
                items.append({
                    "name": entry.name,
                    "is_dir": entry.is_dir(),
                    "size": stats.st_size,
                    "mtime": datetime.fromtimestamp(stats.st_mtime).strftime('%Y-%m-%d %H:%M'),
                    "path": entry.path
                })
    except Exception as e:
        return jsonify({"error": str(e)})
    items.sort(key=lambda x: (not x['is_dir'], x['name'].lower()))
    return jsonify({"path": path, "items": items})

@web_bp.route('/api/files/action', methods=['POST'])
def api_files_action():
    if not check_auth(): return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    action = data.get('action')
    path = data.get('path')
    
    try:
        if action == 'delete':
            if os.path.isfile(path): os.remove(path)
            elif os.path.isdir(path): shutil.rmtree(path)
        elif action == 'rename':
            new_name = data.get('new_name')
            os.rename(path, os.path.join(os.path.dirname(path), new_name))
        elif action == 'create_folder':
            os.makedirs(os.path.join(path, data.get('name')), exist_ok=True)
        elif action == 'zip':
            shutil.make_archive(path, 'zip', path)
        elif action == 'read':
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                return jsonify({"status": "success", "content": f.read()})
        elif action == 'write':
            with open(path, 'w', encoding='utf-8') as f:
                f.write(data.get('content'))
        
        audit("FILES", f"{action} on {path}", request.remote_addr)
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@web_bp.route('/api/files/upload', methods=['POST'])
def api_files_upload():
    if not check_auth(): return jsonify({"error": "Unauthorized"}), 401
    if 'file' not in request.files: return jsonify({"error": "No file"})
    file = request.files['file']
    path = request.form.get('path', os.getcwd())
    filename = secure_filename(file.filename)
    save_path = os.path.join(path, filename)
    file.save(save_path)
    audit("UPLOAD", save_path, request.remote_addr)
    return jsonify({"status": "success"})

@web_bp.route('/api/files/download')
def api_files_download():
    if not check_auth(): return jsonify({"error": "Unauthorized"}), 401
    path = request.args.get('path')
    return send_file(path, as_attachment=True)

@web_bp.route('/api/bot/stats', methods=['GET'])
def api_bot_stats():
    if not check_auth(): return jsonify({"error": "Unauthorized"}), 401
    async def get_stats():
        users = await get_served_users()
        chats = await get_served_chats()
        active = await get_active_chats()
        return len(users), len(chats), len(active)
    
    users, chats, active = run_async(get_stats())
    return jsonify({
        "users": users,
        "chats": chats,
        "active_streams": active,
        "priority_mode": PRIORITY_CHAT is not None
    })

@web_bp.route('/api/mixer/control', methods=['POST'])
def api_mixer_control():
    if not check_auth(): return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    chat_id = int(data.get('chat_id'))
    action = data.get('action')
    val = data.get('val')
    
    try:
        if action == 'pause': run_async(StreamController.pause_stream(chat_id))
        elif action == 'resume': run_async(StreamController.resume_stream(chat_id))
        elif action == 'skip': run_async(StreamController.skip_stream(chat_id, userbot.one.me.id))
        elif action == 'stop': 
            run_async(StreamController.force_stop_stream(chat_id))
            try: remove_active_chat(chat_id)
            except: pass
        elif action == 'volume':
             pass 
        elif action == 'seek':
             pass 
        
        audit("MIXER", f"{action} in {chat_id}", request.remote_addr)
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@web_bp.route('/api/queue/fetch', methods=['GET'])
def api_queue_fetch():
    if not check_auth(): return jsonify({"error": "Unauthorized"}), 401
    chat_id = request.args.get('chat_id')
    try:
        from AnnieXMedia.core.call import queues
        if int(chat_id) in queues:
            return jsonify({"queue": queues[int(chat_id)]})
        return jsonify({"queue": []})
    except:
        return jsonify({"queue": []})

@web_bp.route('/api/priority/toggle', methods=['POST'])
def api_priority_toggle():
    global PRIORITY_CHAT
    if not check_auth(): return jsonify({"error": "Unauthorized"}), 401
    target = request.json.get('chat_id')
    
    if target == 'OFF':
        PRIORITY_CHAT = None
        audit("PRIORITY", "Disabled", request.remote_addr)
        return jsonify({"status": "success", "mode": "Balanced"})
    
    try:
        PRIORITY_CHAT = int(target)
        async def enforce_priority():
            active = await get_active_chats()
            killed = 0
            for chat in active:
                cid = chat['chat_id'] if isinstance(chat, dict) else chat
                if int(cid) != PRIORITY_CHAT:
                    await StreamController.force_stop_stream(int(cid))
                    killed += 1
            return killed
        
        killed = run_async(enforce_priority())
        audit("PRIORITY", f"Enabled for {target}, Killed {killed}", request.remote_addr)
        return jsonify({"status": "success", "killed": killed})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@web_bp.route('/api/database/action', methods=['POST'])
def api_db_action():
    if not check_auth(): return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    action = data.get('action')
    target = int(data.get('target'))
    
    async def exec_db():
        if action == 'add_sudo': await add_sudo(target)
        elif action == 'del_sudo': await remove_sudo(target)
        elif action == 'gban': await add_gban_user(target)
        elif action == 'ungban': await remove_gban_user(target)
        elif action == 'blacklist': await blacklist_chat(target)
        elif action == 'whitelist': await whitelist_chat(target)
    
    try:
        run_async(exec_db())
        audit("DATABASE", f"{action} on {target}", request.remote_addr)
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@web_bp.route('/api/userbot/action', methods=['POST'])
def api_userbot_action():
    if not check_auth(): return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    action = data.get('action')
    client_id = data.get('client_id', 0)
    
    clients = [userbot.one, userbot.two, userbot.three, userbot.four, userbot.five]
    if client_id >= len(clients): return jsonify({"error": "Invalid Client"})
    client = clients[client_id]
    
    async def exec_ub():
        if action == 'join':
            await client.join_chat(data.get('link'))
        elif action == 'leave':
            await client.leave_chat(int(data.get('chat_id')))
        elif action == 'send':
            await client.send_message(int(data.get('chat_id')), data.get('msg'))
        elif action == 'update_profile':
            if data.get('name'): await client.update_profile(first_name=data.get('name'))
            if data.get('bio'): await client.update_profile(bio=data.get('bio'))
            
    try:
        run_async(exec_ub())
        audit("USERBOT", f"{action} by Client {client_id}", request.remote_addr)
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@web_bp.route('/api/broadcast', methods=['POST'])
def api_broadcast():
    if not check_auth(): return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    msg = data.get('msg')
    pin = data.get('pin', False)
    target = data.get('target', 'all')
    
    async def broadcast_process():
        targets = []
        if target in ['all', 'chats']:
            chats = await get_served_chats()
            targets.extend([c['chat_id'] if isinstance(c, dict) else c for c in chats])
        if target in ['all', 'users']:
            users = await get_served_users()
            targets.extend([u['user_id'] if isinstance(u, dict) else u for u in users])
            
        sent = 0
        failed = 0
        for t in targets:
            try:
                m = await app.send_message(int(t), msg)
                if pin: await m.pin(disable_notification=False)
                sent += 1
                await asyncio.sleep(0.05)
            except:
                failed += 1
        return sent, failed
        
    run_async(broadcast_process()) 
    audit("BROADCAST", f"Target: {target}", request.remote_addr)
    return jsonify({"status": "queued"})

@web_bp.route('/api/config/io', methods=['GET', 'POST'])
def api_config_io():
    if not check_auth(): return jsonify({"error": "Unauthorized"}), 401
    config_file = 'config.py' if os.path.exists('config.py') else '.env'
    
    if request.method == 'GET':
        try:
            with open(config_file, 'r') as f:
                return jsonify({"content": f.read(), "file": config_file})
        except: return jsonify({"error": "Read Failed"})
        
    if request.method == 'POST':
        content = request.json.get('content')
        try:
            shutil.copy(config_file, config_file + ".bak")
            with open(config_file, 'w') as f:
                f.write(content)
            audit("CONFIG", "Modified", request.remote_addr)
            return jsonify({"status": "success"})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)})

@web_bp.route('/api/logs/view', methods=['GET'])
def api_logs_view():
    if not check_auth(): return jsonify({"error": "Unauthorized"}), 401
    return jsonify({"audit": AUDIT_LOGS})

@web_bp.route('/api/maintenance', methods=['POST'])
def api_maintenance():
    if not check_auth(): return jsonify({"error": "Unauthorized"}), 401
    action = request.json.get('action')
    
    if action == 'restart':
        audit("SYSTEM", "Restart", request.remote_addr)
        os.execl(sys.executable, sys.executable, "-m", "AnnieXMedia")
    elif action == 'update':
        audit("SYSTEM", "Git Pull", request.remote_addr)
        try:
            out = subprocess.check_output(["git", "pull"], text=True)
            return jsonify({"status": "success", "output": out})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)})
    elif action == 'clean_cache':
        shutil.rmtree('downloads', ignore_errors=True)
        shutil.rmtree('cache', ignore_errors=True)
        os.makedirs('downloads', exist_ok=True)
        os.makedirs('cache', exist_ok=True)
        audit("SYSTEM", "Clean Cache", request.remote_addr)
        return jsonify({"status": "success"})
        
    return jsonify({"status": "unknown"})

@web_bp.route('/api/speedtest', methods=['GET'])
def api_speedtest():
    if not check_auth(): return jsonify({"error": "Unauthorized"}), 401
    try:
        import speedtest
        st = speedtest.Speedtest()
        st.get_best_server()
        dl = st.download() / 1_000_000
        ul = st.upload() / 1_000_000
        ping = st.results.ping
        return jsonify({"dl": dl, "ul": ul, "ping": ping})
    except:
        return jsonify({"error": "Failed"})

@web_bp.route('/api/proxy/request', methods=['POST'])
def api_proxy_request():
    if not check_auth(): return jsonify({"error": "Unauthorized"}), 401
    url = request.json.get('url')
    method = request.json.get('method', 'GET')
    headers = request.json.get('headers', {})
    import requests
    try:
        if method == 'GET':
            r = requests.get(url, headers=headers, timeout=10)
        else:
            r = requests.post(url, headers=headers, json=request.json.get('data'), timeout=10)
        return jsonify({"status": r.status_code, "text": r.text[:2000]})
    except Exception as e:
        return jsonify({"error": str(e)})

@web_bp.before_request
def before_req():
    if request.endpoint and 'static' not in request.endpoint and not session.get('authenticated') and request.endpoint != 'web.login':
        pass 
