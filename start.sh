#!/bin/bash
set -e

echo "Booting AnnieXMedia AI Environment..."

# ===============================
# 1) Paths
# ===============================
export OLLAMA_HOME="/root/.ollama"
mkdir -p "$OLLAMA_HOME"

# ===============================
# 2) Ollama Core Settings
# ===============================
# مهم جداً: لازم http://
export OLLAMA_HOST="http://127.0.0.1:11434"

# عمر الموديل في الذاكرة
export OLLAMA_KEEP_ALIVE="1h"

# تنظيم الضغط
export OLLAMA_MAX_QUEUE=2
export OLLAMA_NUM_THREADS=16

# تسريع
export OLLAMA_FLASH_ATTENTION=1
export OLLAMA_KV_CACHE_TYPE="f16"

# ===============================
# 3) RAM Disk
# ===============================
# 80GB RAM Disk (آمن مع 128GB RAM)
echo "Mounting RAM Disk for Ollama..."
if ! mountpoint -q "$OLLAMA_HOME"; then
  mount -t tmpfs -o size=80g tmpfs "$OLLAMA_HOME"
fi

# ===============================
# 4) Start Ollama
# ===============================
echo "Starting Ollama service..."
nice -n 10 ollama serve > ollama.log 2>&1 &

# ===============================
# 5) Wait for HTTP API
# ===============================
echo "Waiting for Ollama HTTP API..."
until curl -sf http://127.0.0.1:11434/api/tags >/dev/null; do
  sleep 1
done

echo "Ollama HTTP API is ready."

# ===============================
# 6) Pull Models (Light + Heavy)
# ===============================
MODELS=(
  "llama3.1:8b"
  "llama3.1:70b"
)

for MODEL in "${MODELS[@]}"; do
  if ! ollama list | grep -q "$MODEL"; then
    echo "Pulling model: $MODEL"
    ollama pull "$MODEL"
  else
    echo "Model already exists: $MODEL"
  fi
done

# ===============================
# 7) Default Model
# ===============================
export OLLAMA_LIGHT_MODEL="llama3.1:8b"
export OLLAMA_HEAVY_MODEL="llama3.1:70b"
export AI_MODEL_DEFAULT="llama3.1:8b"

# للتوافق مع أي كود قديم
export OLLAMA_HTTP_URL="http://127.0.0.1:11434/api/chat"

echo "Default AI Model: $AI_MODEL_DEFAULT"

# ===============================
# 8) CPU / BLAS Acceleration
# ===============================
export OMP_NUM_THREADS=16
export MKL_NUM_THREADS=16
export NUMEXPR_NUM_THREADS=16

# ===============================
# 9) Start Bot
# ===============================
echo "Starting AnnieXMedia Bot..."
exec nice -n -5 python3 run.py
