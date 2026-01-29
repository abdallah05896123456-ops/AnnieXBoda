#!/bin/bash
set -e

echo "Booting AnnieXMedia AI Environment..."

# ===============================
# 1) Paths
# ===============================
export OLLAMA_HOME="/root/.ollama"
mkdir -p "$OLLAMA_HOME"

# ===============================
# 2) Ollama Core Settings (FIXED)
# ===============================
# لازم http:// وإلا aiohttp هيقع
export OLLAMA_HOST="http://127.0.0.1:11434"

# التحكم في الذاكرة والعمر
export OLLAMA_KEEP_ALIVE="30m"

# تحكم في الضغط
export OLLAMA_MAX_QUEUE=4
export OLLAMA_NUM_THREADS=12

# ===============================
# 3) RAM Disk (آمن)
# ===============================
echo "Mounting 40GB RAM Disk..."
if ! mountpoint -q "$OLLAMA_HOME"; then
  mount -t tmpfs -o size=40g tmpfs "$OLLAMA_HOME"
fi

# ===============================
# 4) Start Ollama (Low Priority)
# ===============================
echo "Starting Ollama..."
nice -n 10 ollama serve > ollama.log 2>&1 &

# ===============================
# 5) Wait for HTTP API
# ===============================
echo "Waiting for Ollama HTTP API..."
until curl -sf http://127.0.0.1:11434/api/tags >/dev/null; do
  sleep 1
done

echo "Ollama is ready."

# ===============================
# 6) Pull Models (Light + Heavy)
# ===============================
MODELS=(
  "qwen2.5:7b"
  "qwen2.5:32b"
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
export AI_MODEL_DEFAULT="qwen2.5:7b"

# للتوافق لو أي كود قديم بيستخدمه
export OLLAMA_HTTP_URL="http://127.0.0.1:11434/api/chat"

echo "Default AI Model set to: $AI_MODEL_DEFAULT"

# ===============================
# 8) Start Bot (High Priority)
# ===============================
echo "Starting AnnieXMedia Bot..."
exec nice -n -5 python3 run.py
