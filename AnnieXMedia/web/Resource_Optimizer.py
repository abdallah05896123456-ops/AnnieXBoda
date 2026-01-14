# web/Resource_Optimizer.py
import gc
import os
import psutil
import shutil
import subprocess
import time
from typing import Optional

# Configurable
FOCUS_NICE = -20  # highest priority
NORMAL_NICE = 0

# Helper samples
def sample_cpu_percent(interval: float = 0.1) -> float:
    return psutil.cpu_percent(interval=interval)

def sample_ram_mb() -> float:
    mem = psutil.virtual_memory()
    return (mem.used / 1024.0 / 1024.0)

def sample_temp_c() -> Optional[float]:
    try:
        temps = psutil.sensors_temperatures()
        if not temps:
            return None
        for name, entries in temps.items():
            if entries:
                return entries[0].current
    except Exception:
        return None
    return None

def _set_priority(pid: int, nice_value: int):
    try:
        p = psutil.Process(pid)
        p.nice(nice_value)
        return True
    except Exception:
        try:
            os.setpriority(os.PRIO_PROCESS, pid, nice_value)
            return True
        except Exception:
            return False

def _drop_caches():
    """Attempt to free OS pagecache - requires root."""
    try:
        if os.path.exists("/proc/sys/vm/drop_caches"):
            with open("/proc/sys/vm/drop_caches", "w") as f:
                f.write("3\n")
            return True
    except Exception:
        pass
    # fallback: call sync; echo 3 | sudo tee ...
    try:
        subprocess.run(["sync"])
        return False
    except Exception:
        return False

def focus_on_group(group_id: int):
    """
    Bring full resources to the group: raise process priority of the stream worker,
    clear caches of other groups, and attempt to prioritize network (best effort).
    """
    # find processes belonging to Annie/StreamController - heuristic: name or listening port
    for p in psutil.process_iter(attrs=["pid", "name", "cmdline"]):
        try:
            cmd = " ".join(p.info.get("cmdline") or [])
            if "pytgcalls" in cmd or "annie" in cmd.lower() or "stream" in cmd.info.get("name", "").lower():
                # bump this process
                _set_priority(p.info["pid"], FOCUS_NICE)
        except Exception:
            continue
    # drop caches to free RAM
    _drop_caches()
    # clear other groups' in-memory caches (app-specific)
    try:
        import AnnieXMedia.misc as misc
        # attempt to clear cached buffers
        if hasattr(misc, "clear_other_groups_cache"):
            misc.clear_other_groups_cache(except_group=group_id)
        else:
            # best-effort: delete buffers from db
            for k in list(misc.db.keys()):
                if isinstance(k, int) and k != group_id:
                    del misc.db[k]
    except Exception:
        pass
    # network priority by executing `tc` or `iptables` prioritization - best effort and requires root
    try:
        # use tc to add priority (example: prioritize UDP to port range 5200-5300)
        subprocess.run(["/sbin/tc", "qdisc", "show"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # Not attempting to change if tc not available; admin may run custom script
    except Exception:
        pass
    return {"status": "focused", "group": group_id}

def unfocus_all():
    """Reset priorities for processes we bumped earlier."""
    for p in psutil.process_iter(attrs=["pid", "name"]):
        try:
            if "pytgcalls" in " ".join(p.info.get("name") or []) or "annie" in p.info.get("name", "").lower():
                _set_priority(p.info["pid"], NORMAL_NICE)
        except Exception:
            continue
    return {"status": "unfocused"}

# Self-monitor coroutine
def monitor_loop(interval: float = 1.0):
    while True:
        cpu = sample_cpu_percent()
        ram = sample_ram_mb()
        temp = sample_temp_c()
        # Could log to file or push to websocket via backend
        time.sleep(interval)
