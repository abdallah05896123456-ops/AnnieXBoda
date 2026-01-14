import os
import sys
import shutil
import psutil
import time
import subprocess
import platform
import json
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from AnnieXMedia import app 
from config import WEB_PASSWORD

# تعريف البلوبرنت (تأكد أن ملف index.html داخل مجلد templates)
web_bp = Blueprint('web', __name__, template_folder='templates')

def get_log_time():
    return datetime.now().strftime("%d-%b-%y %H:%M:%S")

# --- دوال المساعدة ---
def check_auth():
    return session.get('authenticated', False)

def get_system_stats():
    try:
        mem = psutil.virtual_memory()
        net = psutil.net_io_counters()
        cpu_freq = psutil.cpu_freq()
        
        # تحويل القيم لـ JSON
        return {
            "cpu": {
                "percent": psutil.cpu_percent(interval=None),
                "cores": psutil.cpu_count(),
                "freq_current": f"{cpu_freq.current:.0f}MHz" if cpu_freq else "N/A"
            },
            "memory": {
                "percent": mem.percent,
                "total": f"{mem.total/1024**3:.1f}GB",
                "used": f"{mem.used/1024**3:.1f}GB"
            },
            "network": {
                "sent": f"{net.bytes_sent/1024**2:.1f}MB",
                "recv": f"{net.bytes_recv/1024**2:.1f}MB"
            }
        }
    except Exception as e:
        return {"error": str(e)}

# --- الصفحات (Routes) ---

@web_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # استقبال الباسورد سواء من Form أو JSON
        password = request.form.get('password') or request.json.get('password')
        
        if password == WEB_PASSWORD:
            session['authenticated'] = True
            print(f"[{get_log_time()} - AUTH] - Web Login Successful from {request.remote_addr}")
            # لو الطلب جاي من Ajax (JS) نرد بـ JSON
            if request.is_json:
                return jsonify({"status": "success", "redirect": url_for('web.dashboard')})
            return redirect(url_for('web.dashboard'))
            
        if request.is_json:
            return jsonify({"error": "Invalid Password"}), 401
        return render_template('index.html', login_page=True, error="Invalid Password")

    if check_auth():
        return redirect(url_for('web.dashboard'))
        
    return render_template('index.html', authenticated=False)

@web_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('web.login'))

@web_bp.route('/')
def dashboard():
    if not check_auth(): return redirect(url_for('web.login'))
    return render_template('index.html', authenticated=True)

# --- APIs (عشان الداشبورد تشتغل) ---

@web_bp.route('/api/system_monitor')
def api_system_monitor():
    if not check_auth(): return jsonify({"error": "Auth Required"}), 401
    return jsonify(get_system_stats())

@web_bp.route('/api/bot/stats')
def api_bot_stats():
    if not check_auth(): return jsonify({"error": "Auth Required"}), 401
    # هنا تقدر تربط مع داتابيز البوت الحقيقية
    return jsonify({"users": 0, "chats": 0, "priority_mode": False})

@web_bp.route('/api/terminal/exec', methods=['POST'])
def api_terminal():
    if not check_auth(): return jsonify({"error": "Auth Required"}), 401
    cmd = request.json.get('cmd')
    try:
        out = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT, text=True, timeout=5)
        return jsonify({"output": out})
    except subprocess.CalledProcessError as e:
        return jsonify({"output": e.output})
    except Exception as e:
        return jsonify({"output": str(e)})

@web_bp.route('/api/files/list')
def api_files_list():
    if not check_auth(): return jsonify({"error": "Auth Required"}), 401
    path = request.args.get('path', '.')
    items = []
    try:
        if not os.path.exists(path): path = '.'
        for entry in os.scandir(path):
            items.append({
                "name": entry.name, 
                "is_dir": entry.is_dir(), 
                "size": entry.stat().st_size, 
                "path": entry.path
            })
    except Exception as e:
        return jsonify({"error": str(e)})
    return jsonify({"path": path, "items": items})

@web_bp.route('/api/maintenance', methods=['POST'])
def api_maint():
    if not check_auth(): return jsonify({"error": "Auth Required"}), 401
    action = request.json.get('action')
    if action == 'restart':
        # أمر إعادة تشغيل البوت (يختلف حسب السيرفر)
        os.kill(os.getpid(), 9)
    return jsonify({"status": "ok"})

# --- طباعة اللوجز عند التشغيل ---
print(f"[{get_log_time()} - INFO] - AnnieX OS • Titan Class - Loaded Successfully")
print(f"[{get_log_time()} - INFO] - DASHBOARD URL: https://anniexboda-ongrzg.fly.dev")
