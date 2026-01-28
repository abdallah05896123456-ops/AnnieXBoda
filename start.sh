#!/bin/bash

echo "🧠 Starting AI Engine (Qwen 2.5 32B - The Coding Monster)..."
# تشغيل المحرك
ollama serve &

echo "⏳ Waiting for AI..."
while ! curl -s http://localhost:11434 > /dev/null; do sleep 1; done

# التأكد من وجود الموديل
if ! ollama list | grep -q "qwen2.5:32b"; then
    echo "⚠️ Model not found, pulling qwen2.5:32b..."
    ollama pull qwen2.5:32b
fi

echo "✅ AI Ready! Launching Bot..."
python3 run.py
