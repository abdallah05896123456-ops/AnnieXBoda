#!/bin/bash

# 1. إنشاء المجلد
mkdir -p /root/.ollama

# 2. إجبار السيرفر يشتغل على العنوان الرقمي ويفضل صاحي 24 ساعة
export OLLAMA_HOST=127.0.0.1:11434
export OLLAMA_KEEP_ALIVE=-1

# 3. الرام ديسك (45 جيجا)
echo "🚀 Creating 45GB RAM Disk..."
mount -t tmpfs -o size=45g tmpfs /root/.ollama

# 4. تشغيل الذكاء
echo "🧠 Starting AI Engine..."
ollama serve &

# 5. انتظار الخدمة
echo "⏳ Waiting for AI..."
while ! curl -s http://127.0.0.1:11434 > /dev/null; do sleep 1; done

# 6. تحميل الموديل (لو مش موجود)
if ! ollama list | grep -q "qwen2.5:32b"; then
    echo "⬇️ Downloading Qwen 2.5 (32B) directly into RAM..."
    ollama pull qwen2.5:32b
fi

echo "✅ AI Ready! Launching Bot..."
python3 run.py
