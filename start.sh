#!/bin/bash

# 1. إنشاء المجلد
mkdir -p /root/.ollama

# 2. 🔥 تحديد 45 جيجا رام ديسك (كما طلبت) 🔥
# التحميل هيبقى طيارة لأنه بيكتب في الرامات
echo "🚀 Creating 45GB RAM Disk..."
mount -t tmpfs -o size=45g tmpfs /root/.ollama

# 3. تشغيل الذكاء في الخلفية
echo "🧠 Starting AI Engine..."
ollama serve &

# 4. انتظار الخدمة
echo "⏳ Waiting for AI..."
while ! curl -s http://localhost:11434 > /dev/null; do sleep 1; done

# 5. تحميل الموديل (بيعتمد على سرعة نت السيرفر مش جهازك)
if ! ollama list | grep -q "qwen2.5:32b"; then
    echo "⬇️ Downloading Qwen 2.5 (32B) directly into RAM..."
    ollama pull qwen2.5:32b
fi

echo "✅ AI Ready! Launching Bot..."
python3 run.py
