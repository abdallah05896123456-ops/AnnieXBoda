#!/bin/bash
set -e

echo "🚀 Booting AnnieXMedia AI Environment (MAX PERFORMANCE)..."

# ===============================
# 0) Limits & Kernel Boost
# ===============================
ulimit -n 1048576 || true
ulimit -u unlimited || true

sysctl -w vm.swappiness=1 >/dev/null 2>&1 || true
sysctl -w net.core.somaxconn=65535 >/dev/null 2>&1 || true
sysctl -w net.ipv4.tcp_tw_reuse=1 >/dev/null 2>&1 || true
sysctl -w net.ipv4.tcp_fin_timeout=15 >/dev/null 2>&1 || true

# ===============================
# 1) Paths
# ===============================
mkdir -p /root/.ollama

# ===============================
# 2) Ollama ENV (CRITICAL)
# ===============================
export OLLAMA_HOST="http://127.0.0.1:11434"

# RAM & lifecycle
export OLLAMA_KEEP_ALIVE="45m"

# Concurrency control (تحت ضغط عالي)
export OLLAMA_MAX_QUEUE=2
export OLLAMA_NUM_THREADS=16
export OLLAMA_MAX_LOADED_MODELS=1

# ===============================
# 3) RAM Disk (Ultra Fast)
# ===============================
echo "🧠 Mounting 48GB RAM Disk for Ollama..."
if ! mountpoint -q /root/.ollama; then
    mount -t tmpfs -o size=48g,nr_inodes=10k tmpfs /root/.ollama
fi

# ===============================
# 4) Start Ollama (Pinned to CPU)
# ===============================
echo "🤖 Starting Ollama (isolated cores)..."

# شغل Ollama على أنوية محددة (0-11)
taskset -c 0-11 nice -n 10 ollama serve \
  > /root/ollama.log 2>&1 &

OLLAMA_PID=$!

# ===============================
# 5) Health Check
# ===============================
echo "⏳ Waiting for Ollama API..."
for i in {1..60}; do
    if curl -sf http://127.0.0.1:11434/api/tags >/dev/null; then
        echo "✅ Ollama is ready."
        break
    fi
    sleep 0.5
done

# ===============================
# 6) Pull Model (Once)
# ===============================
if ! ollama list | grep -q "qwen2.5:32b"; then
    echo "⬇️ Pulling Qwen 2.5 32B (RAM cached)..."
    ollama pull qwen2.5:32b
fi

# ===============================
# 7) Start Bot (MAX PRIORITY)
# ===============================
echo "🎵 Starting Bot (MAX PRIORITY / FAST RESPONSE)..."

# خلي البوت على أنوية مختلفة (12-15)
exec taskset -c 12-15 nice -n -10 python3 run.py
