#!/bin/bash
echo "🧠 Starting AI Engine (40GB Mode)..."
ollama serve &

echo "⏳ Waiting for AI..."
while ! curl -s http://localhost:11434 > /dev/null; do sleep 1; done

# التأكد من تحميل النسخة الـ 70b
if ! ollama list | grep -q "70b"; then
    echo "⚠️ Model not found, pulling llama3:70b..."
    ollama pull llama3:70b
fi

echo "✅ AI Ready! Launching Bot..."
python3 run.py
