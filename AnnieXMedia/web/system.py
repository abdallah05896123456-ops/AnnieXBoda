import os
import sys
import time
import platform
import psutil
import subprocess
import socket
import gc
import json
from datetime import datetime
from flask import jsonify, request, session, Response
from . import web_bp
from .utils import (
    Config, 
    sudo_required, 
    get_readable_size, 
    log_activity, 
    logger, 
    APIResponse,
    CacheManager
)

# الثوابت
BOOT_TIME = psutil.boot_time()
PROCESS_FILTER = ['python', 'java', 'ffmpeg', 'node', 'bash']

# =========================================================
# 1. كلاس مراقبة النظام (System Monitor Class)
# =========================================================
class SystemMonitor:
    """
    فئة مسؤولة عن تجميع كافة إحصائيات النظام.
    """
    
    @staticmethod
    def get_cpu_info():
        """تفاصيل دقيقة للمعالج"""
        try:
            return {
                "percent": psutil.cpu_percent(interval=0.1),
                "cores_logical": psutil.cpu_count(logical=True),
                "cores_physical": psutil.cpu_count(logical=False),
                "frequency": psutil.cpu_freq()._asdict() if psutil.cpu_freq() else {},
                "load_avg": [x / psutil.cpu_count() * 100 for x in psutil.getloadavg()] if hasattr(psutil, "getloadavg") else []
            }
        except Exception as e:
            logger.error("CPU Info Error", e)
            return {"percent": 0}

    @staticmethod
    def get_memory_info():
        """تفاصيل الذاكرة والـ Swap"""
        vm = psutil.virtual_memory()
        sw = psutil.swap_memory()
        return {
            "ram": {
                "total": get_readable_size(vm.total),
                "available": get_readable_size(vm.available),
                "used": get_readable_size(vm.used),
                "percent": vm.percent
            },
            "swap": {
                "total": get_readable_size(sw.total),
                "used": get_readable_size(sw.used),
                "percent": sw.percent
            }
        }

    @staticmethod
    def get_disk_info():
        """تفاصيل جميع الأقراص المتصلة"""
        partitions_data = []
        try:
            for part in psutil.disk_partitions(all=False):
                if 'snap' in part.mountpoint: continue # تجاهل ملفات snap في لينكس
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    partitions_data.append({
                        "device": part.device,
                        "mount": part.mountpoint,
                        "fstype": part.fstype,
                        "total": get_readable_size(usage.total),
                        "used": get_readable_size(usage.used),
                        "free": get_readable_size(usage.free),
                        "percent": usage.percent
                    })
                except PermissionError:
                    continue
        except Exception as e:
            logger.error("Disk Info Error", e)

        # الإجمالي (للبارتيشن الرئيسي فقط /)
        root_usage = psutil.disk_usage('/')
        return {
            "root": {
                "total": get_readable_size(root_usage.total),
                "used": get_readable_size(root_usage.used),
                "percent": root_usage.percent
            },
            "partitions": partitions_data
        }

    @staticmethod
    def get_network_info():
        """مراقبة تدفق البيانات"""
        io = psutil.net_io_counters()
        return {
            "bytes_sent": get_readable_size(io.bytes_sent),
            "bytes_recv": get_readable_size(io.bytes_recv),
            "packets_sent": io.packets_sent,
            "packets_recv": io.packets_recv,
            "errin": io.errin,
            "errout": io.errout
        }

    @staticmethod
    def get_system_details():
        """معلومات نظام التشغيل الثابتة"""
        return {
            "os": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "arch": platform.machine(),
            "hostname": socket.gethostname(),
            "python_version": platform.python_version(),
            "uptime_sec": int(time.time() - BOOT_TIME),
            "uptime_str": str(timedelta(seconds=int(time.time() - BOOT_TIME)))
        }

# =========================================================
# 2. واجهات API المراقبة (Monitor Endpoints)
# =========================================================

@web_bp.route('/api/system/stats')
@sudo_required
def api_system_stats():
    """الراوت المجمع لكل الإحصائيات"""
    try:
        # استخدام الكاش لتخفيف الضغط لو الطلبات سريعة
        cached = CacheManager.get("sys_stats")
        if cached: return jsonify(cached)

        data = {
            "cpu": SystemMonitor.get_cpu_info(),
            "memory": SystemMonitor.get_memory_info(),
            "disk": SystemMonitor.get_disk_info(),
            "network": SystemMonitor.get_network_info(),
            "system": SystemMonitor.get_system_details(),
            "timestamp": time.time()
        }
        
        CacheManager.set("sys_stats", data, ttl=1) # كاش لمدة ثانية واحدة
        return jsonify(data)
    except Exception as e:
        return APIResponse.error("Failed to fetch system stats", details=e)

# =========================================================
# 3. مدير العمليات (Process Manager)
# =========================================================

@web_bp.route('/api/system/processes')
@sudo_required
def api_processes():
    """عرض العمليات النشطة مع الفلترة"""
    procs = []
    try:
        for p in psutil.process_iter(['pid', 'name', 'username', 'cpu_percent', 'memory_percent', 'status']):
            try:
                # تصفية العمليات حسب الاسم أو الاستهلاك العالي
                p_info = p.info
                if (p_info['cpu_percent'] > 0.1 or 
                    p_info['name'] in PROCESS_FILTER or 
                    'python' in p_info['name']):
                    
                    procs.append({
                        "pid": p_info['pid'],
                        "name": p_info['name'],
                        "user": p_info['username'],
                        "cpu": round(p_info['cpu_percent'], 1),
                        "mem": round(p_info['memory_percent'], 1),
                        "status": p_info['status']
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except Exception as e:
        logger.error("Process Iteration Error", e)

    # ترتيب حسب استهلاك المعالج
    procs.sort(key=lambda x: x['cpu'], reverse=True)
    return jsonify({"count": len(procs), "processes": procs[:50]})

@web_bp.route('/api/system/kill_process', methods=['POST'])
@sudo_required
def kill_process():
    """إنهاء عملية معينة (Kill PID)"""
    pid = request.json.get('pid')
    if not pid: return APIResponse.error("PID required")
    
    try:
        p = psutil.Process(int(pid))
        p.terminate()
        log_activity("KILL_PROCESS", f"PID: {pid}")
        return APIResponse.success(message=f"Process {pid} terminated")
    except psutil.NoSuchProcess:
        return APIResponse.error("Process not found", 404)
    except psutil.AccessDenied:
        return APIResponse.error("Access denied", 403)
    except Exception as e:
        return APIResponse.error("Kill failed", details=e)

# =========================================================
# 4. الطرفية التفاعلية (Web Terminal)
# =========================================================
@web_bp.route('/api/system/terminal', methods=['POST'])
@sudo_required
def execute_terminal():
    """
    محاكي طرفية (Shell Executor).
    يحتوي على نظام حماية من الأوامر الكارثية.
    """
    command = request.json.get('command', '').strip()
    if not command: return jsonify({"output": ""})

    # 1. نظام الحماية (Safety Net)
    FORBIDDEN_COMMANDS = [
        'rm -rf /', ':(){ :|:& };:', 'mkfs', 'dd if=/dev/zero', 
        'shutdown', 'reboot', 'init 0', '> /dev/sda'
    ]
    
    for ban in FORBIDDEN_COMMANDS:
        if ban in command:
            log_activity("SECURITY_ALERT", f"Blocked Command: {command}")
            return jsonify({
                "output": f"\033[1;31m[SECURITY BLOCK] Command '{command}' is blacklisted.\033[0m",
                "cwd": os.getcwd()
            })

    # 2. تنفيذ الأمر
    log_activity("TERMINAL_EXEC", command)
    
    # التعامل مع أوامر تغيير المسار cd
    if command.startswith('cd '):
        try:
            target_dir = command[3:].strip()
            os.chdir(os.path.expanduser(target_dir))
            return jsonify({"output": "", "cwd": os.getcwd()})
        except FileNotFoundError:
            return jsonify({"output": f"cd: {target_dir}: No such file or directory", "cwd": os.getcwd()})

    try:
        # تشغيل الأمر والتقاط المخرجات
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=os.getcwd()
        )
        stdout, stderr = process.communicate(timeout=15) # مهلة 15 ثانية
        
        output = stdout + stderr
        if not output: output = "Done."
        
    except subprocess.TimeoutExpired:
        process.kill()
        output = "\033[1;33m[TIMEOUT] Command execution timed out > 15s.\033[0m"
    except Exception as e:
        output = str(e)

    return jsonify({"output": output, "cwd": os.getcwd()})

# =========================================================
# 5. إدارة ملفات اللوج (Log Management)
# =========================================================
@web_bp.route('/api/system/logs')
@sudo_required
def stream_logs():
    """قراءة ملف اللوج وعرض آخر السطور"""
    log_path = Config.LOG_FILE
    lines_count = request.args.get('lines', 100, type=int)
    
    if not os.path.exists(log_path):
        return jsonify({"logs": ["Log file not found."]})

    try:
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            # قراءة ذكية (Seek to end)
            f.seek(0, os.SEEK_END)
            file_size = f.tell()
            
            # قراءة آخر 50 كيلوبايت لو الملف كبير
            read_size = min(file_size, 50000) 
            f.seek(file_size - read_size)
            content = f.read()
            
            lines = content.splitlines()
            return jsonify({"logs": lines[-lines_count:]})
    except Exception as e:
        return jsonify({"logs": [f"Error reading logs: {e}"]})

@web_bp.route('/api/system/logs/action', methods=['POST'])
@sudo_required
def log_actions():
    action = request.json.get('action')
    if action == 'clear':
        open(Config.LOG_FILE, 'w').close()
        return APIResponse.success(message="Logs cleared")
    return APIResponse.error("Unknown action")
