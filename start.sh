#!/bin/bash
set -e

echo "🚀 Booting AnnieXMedia AI Environment..."

# ===============================
# 1) مسارات أساسية
# ===============================
mkdir -p /root/.ollama

# ===============================
# 2) إعدادات Ollama (مهم جداً)
# ===============================
export OLLAMA_HOST=127.0.0.1:11434

# ⚠️ متخليش الذكاء ماسك الرام للأبد
export OLLAMA_KEEP_ALIVE=30m

# ⛔ منع الضغط الزائد
export OLLAMA_MAX_QUEUE=4
export OLLAMA_NUM_THREADS=12

# ===============================
# 3) RAM Disk (آمن)
# ===============================
echo "🧠 Mounting 40GB RAM Disk for Ollama..."
mountpoint -q /root/.ollama || mount -t tmpfs -o size=40g tmpfs /root/.ollama

# ===============================
# 4) تشغيل Ollama بأولوية أقل
# ===============================
echo "🤖 Starting Ollama (low priority)..."
nice -n 10 ollama serve > ollama.log 2>&1 &

# ===============================
# 5) انتظار الخدمة
# ===============================
echo "⏳ Waiting for Ollama..."
until curl -sf http://127.0.0.1:11434/api/tags >/dev/null; do
  sleep 1
done

# ===============================
# 6) تحميل الموديل لو مش موجود
# ===============================
if ! ollama list | grep -q "qwen2.5:32b"; then
    echo "⬇️ Pulling Qwen 2.5 32B into RAM..."
    ollama pull qwen2.5:32b
fi

# ===============================
# 7) تشغيل البوت (أولوية أعلى)
# ===============================
echo "🎵 Starting Bot (HIGH priority)..."
exec nice -n -5 python3 run.py
