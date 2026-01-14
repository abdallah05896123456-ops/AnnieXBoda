import os
import sys
import time
import platform
import psutil
import subprocess
import socket
import gc
from datetime import datetime
from flask import jsonify, request, session
from . import web_bp
from .utils import (
    LOG_FILE, 
    sudo_required, 
    get_readable_size, 
    log_activity,
    Config,
    db
)

# بداية تشغيل البوت لحساب الـ Uptime
BOOT_TIME = time.time()

# =========================================================
# 1. لوحة المراقبة الشاملة (Full System Monitor)
# =========================================================

@web_bp.route('/api/system/stats')
@sudo_required
def system_monitor():
    """
    جلب إحصائيات دقيقة جداً عن السيرفر.
    يغطي المعالج (أنوية)، الرام، السواب، الشبكة، والهارد.
    """
    # 1. المعالج (CPU)
    cpu_percent = psutil.cpu_percent(interval=None)
    cpu_cores = psutil.cpu_percent(interval=None, percpu=True) # استهلاك كل نواة
    cpu_freq = psutil.cpu_freq()
    
    # 2. الذاكرة (Memory)
    vm = psutil.virtual_memory()
    swap = psutil.swap_memory()
    
    # 3. التخزين (Disk)
    disk = psutil.disk_usage('/')
    # جلب كل الأقراص المتصلة
    partitions = []
    try:
        for part in psutil.disk_partitions():
            usage = psutil.disk_usage(part.mountpoint)
            partitions.append({
                "device": part.device,
                "mount": part.mountpoint,
                "total": get_readable_size(usage.total),
                "used": get_readable_size(usage.used),
                "percent": usage.percent
            })
    except: pass

    # 4. الشبكة (Network I/O)
    net_io = psutil.net_io_counters()
    
    # 5. وقت التشغيل (Uptime)
    uptime_sec = int(time.time() - BOOT_TIME)
    uptime_str = str(datetime.utcfromtimestamp(uptime_sec).strftime('%H:%M:%S'))
    
    # 6. معلومات النظام (OS Info)
    sys_info = {
        "os": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "hostname": socket.gethostname(),
        "python": platform.python_version(),
        "cores_count": psutil.cpu_count(logical=True)
    }

    return jsonify({
        "cpu": {
            "total": cpu_percent,
            "cores": cpu_cores,
            "freq": f"{cpu_freq.current:.0f}Mhz" if cpu_freq else "N/A"
        },
        "memory": {
            "percent": vm.percent,
            "used": get_readable_size(vm.used),
            "total": get_readable_size(vm.total),
            "free": get_readable_size(vm.available),
            "swap_percent": swap.percent
        },
        "disk": {
            "percent": disk.percent,
            "used": get_readable_size(disk.used),
            "total": get_readable_size(disk.total),
            "partitions": partitions
        },
        "network": {
            "sent": get_readable_size(net_io.bytes_sent),
            "recv": get_readable_size(net_io.bytes_recv),
            "packets_sent": net_io.packets_sent,
            "packets_recv": net_io.packets_recv
        },
        "uptime": uptime_str,
        "system": sys_info
    })

# =========================================================
# 2. مدير العمليات (Process Manager / Task Manager)
# =========================================================

@web_bp.route('/api/system/processes')
@sudo_required
def process_manager():
    """
    عرض العمليات الحالية (مثل Top في لينكس).
    يركز على بايثون و ffmpeg.
    """
    procs = []
    for proc in psutil.process_iter(['pid', 'name', 'username', 'cpu_percent', 'memory_percent']):
        try:
            # فلترة العمليات المهمة بس عشان منغرقش الواجهة
            if proc.info['name'] in ['python', 'python3', 'ffmpeg', 'mpv', 'bash']:
                procs.append(proc.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
            
    # ترتيب حسب استهلاك المعالج
    procs = sorted(procs, key=lambda p: p['cpu_percent'], reverse=True)
    return jsonify({"processes": procs[:20]}) # رجع اعلى 20 عملية بس

# =========================================================
# 3. الطرفية (Web Terminal / Shell) ☢️
# =========================================================

@web_bp.route('/api/system/terminal', methods=['POST'])
@sudo_required
def web_terminal():
    """
    تنفيذ أوامر النظام مباشرة (Root Access Simulation).
    """
    command = request.json.get('command')
    if not command: return jsonify({"output": ""})
    
    # قائمة سوداء للأوامر المدمرة (حماية)
    BLACKLIST = [
        'rm -rf /', ':(){ :|:& };:', 'mkfs', 'dd if=/dev/zero', 
        'shutdown', 'reboot', 'init 0'
    ]
    
    if any(cmd in command for cmd in BLACKLIST):
        log_activity("DANGEROUS_CMD_BLOCKED", f"Command: {command}")
        return jsonify({"output": "⛔ SECURITY PROTOCOL: Command Blocked for safety."})

    log_activity("TERMINAL_EXEC", f"Command: {command}")

    try:
        # تنفيذ الأمر والتقاط المخرجات
        result = subprocess.check_output(
            command, 
            shell=True, 
            stderr=subprocess.STDOUT,
            timeout=10 # مهلة 10 ثواني عشان السيرفر ميعلقش
        )
        output = result.decode('utf-8')
    except subprocess.CalledProcessError as e:
        output = e.output.decode('utf-8')
    except subprocess.TimeoutExpired:
        output = "⏱️ Error: Command timed out (took > 10s)."
    except Exception as e:
        output = str(e)

    return jsonify({"output": output, "cwd": os.getcwd()})

# =========================================================
# 4. قارئ السجلات الحي (Live Log Streamer)
# =========================================================

@web_bp.route('/api/system/logs')
@sudo_required
def get_logs():
    """
    قراءة آخر 100 سطر من ملف اللوج.
    """
    if not os.path.exists(LOG_FILE):
        return jsonify({"logs": [f"❌ Log file '{LOG_FILE}' not found."]})

    try:
        # قراءة الملف من الآخر (Tail)
        with open(LOG_FILE, 'r', encoding='utf-8', errors='ignore') as f:
            # طريقة سريعة لقراءة آخر السطور بدون تحميل الملف كله في الرام
            lines = f.readlines()
            last_lines = lines[-100:] # هات آخر 100 سطر
            
            # تنظيف السطور
            clean_lines = [l.strip() for l in last_lines if l.strip()]
            return jsonify({"logs": clean_lines})
    except Exception as e:
        return jsonify({"logs": [f"Error reading logs: {e}"]})

@web_bp.route('/api/system/logs/clear', methods=['POST'])
@sudo_required
def clear_logs():
    """مسح ملف اللوج"""
    try:
        open(LOG_FILE, 'w').close()
        log_activity("LOGS_CLEARED", "System logs wiped by admin")
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# =========================================================
# 5. محرر البيئة (.env Editor) ⚠️
# =========================================================

@web_bp.route('/api/system/env', methods=['GET', 'POST'])
@sudo_required
def manage_env():
    """
    قراءة وتعديل متغيرات البوت (.env).
    خطير جداً ومحتاج صلاحيات Sudo.
    """
    env_path = ".env"
    
    # أ) قراءة المتغيرات
    if request.method == 'GET':
        if not os.path.exists(env_path):
            return jsonify({"content": "# No .env file found"})
        with open(env_path, 'r') as f:
            return jsonify({"content": f.read()})
    
    # ب) حفظ التعديلات
    elif request.method == 'POST':
        new_content = request.json.get('content')
        try:
            with open(env_path, 'w') as f:
                f.write(new_content)
            log_activity("ENV_UPDATE", "Environment variables updated")
            return jsonify({"success": True, "message": "File saved! Restart bot to apply."})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)})

# =========================================================
# 6. أدوات الصيانة (Maintenance Tools)
# =========================================================

@web_bp.route('/api/system/maintenance', methods=['POST'])
@sudo_required
def system_maintenance():
    action = request.json.get('action')
    
    if action == 'gc':
        # تنظيف الرام (Garbage Collection)
        gc.collect()
        return jsonify({"success": True, "message": "Python Garbage Collector Ran."})
    
    elif action == 'clear_cache':
        # تنظيف مجلد التحميلات
        try:
            deleted_count = 0
            folder = Config.DOWNLOADS_DIR
            for filename in os.listdir(folder):
                file_path = os.path.join(folder, filename)
                try:
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.unlink(file_path)
                        deleted_count += 1
                except Exception as e:
                    pass
            return jsonify({"success": True, "message": f"Deleted {deleted_count} files from cache."})
        except Exception as e:
             return jsonify({"success": False, "error": str(e)})
             
    elif action == 'restart_bot':
        # إعادة تشغيل البوت (لو شغال بـ Heroku أو Service)
        # دي مجرد محاكاة، التنفيذ الحقيقي بيعتمد على الاستضافة
        return jsonify({"success": True, "message": "Restart signal sent (Manual restart required if local)."})

    return jsonify({"success": False, "error": "Unknown action"})
