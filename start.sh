#!/bin/bash
set -e

echo "🚀 Booting AnnieXMedia AI Environment..."

# ===============================
# 1) Paths
# ===============================
export OLLAMA_HOME="/root/.ollama"
mkdir -p "$OLLAMA_HOME"

# ===============================
# 2) Ollama Core Settings
# ===============================
export OLLAMA_HOST="127.0.0.1:11434"

# مايمسكش الرام للأبد
export OLLAMA_KEEP_ALIVE="30m"

# تحكم في الضغط
export OLLAMA_MAX_QUEUE=4
export OLLAMA_NUM_THREADS=12

# ===============================
# 3) RAM Disk (آمن)
# ===============================
echo "🧠 Mounting 40GB RAM Disk..."
mountpoint -q "$OLLAMA_HOME" || mount -t tmpfs -o size=40g tmpfs "$OLLAMA_HOME"

# ===============================
# 4) Start Ollama (Low Priority)
# ===============================
echo "🤖 Starting Ollama..."
nice -n 10 ollama serve > ollama.log 2>&1 &

# ===============================
# 5) Wait for HTTP API
# ===============================
echo "⏳ Waiting for Ollama HTTP..."
until curl -sf http://127.0.0.1:11434/api/tags >/dev/null; do
  sleep 1
done

echo "✅ Ollama is ready!"

# ===============================
# 6) Pull Models (Light + Heavy)
# ===============================
MODELS=(
  "qwen2.5:7b"
  "qwen2.5:32b"
)

for MODEL in "${MODELS[@]}"; do
  if ! ollama list | grep -q "$MODEL"; then
    echo "⬇️ Pulling $MODEL ..."
    ollama pull "$MODEL"
  else
    echo "✔️ $MODEL already exists"
  fi
done

# ===============================
# 7) Default Model (Light)
# ===============================
export AI_MODEL_DEFAULT="qwen2.5:7b"
export OLLAMA_HTTP_URL="http://127.0.0.1:11434/api/generate"

echo "🎯 Default AI Model: $AI_MODEL_DEFAULT"

# ===============================
# 8) Start Bot (High Priority)
# ===============================
echo "🎵 Starting Bot..."
exec nice -n -5 python3 run.py
