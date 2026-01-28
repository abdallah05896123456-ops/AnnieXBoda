#!/bin/bash

# 1. تشغيل "مخ" الذكاء (Ollama) في الخلفية داخل السيرفر
# (ده داخلي فقط ومش محتاج بورتات خارجية)
echo "🧠 Starting AI Engine..."
ollama serve &

# 2. أمر الانتظار: بنقول للبوت "نام شوية لحد ما المخ يصحى"
# بيفضل يجرب يتصل داخلياً كل ثانية لحد ما ينجح
echo "⏳ Waiting for AI to wake up..."
while ! curl -s http://localhost:11434 > /dev/null; do
    sleep 1
done

echo "✅ AI is Ready! Starting the Bot..."

# 3. دلوقتي بس نشغل البوت بأمان
python3 run.py
