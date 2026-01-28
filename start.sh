#!/bin/bash

echo "🧠 Starting AI Engine (Standard 4GB Mode)..."
ollama serve &

echo "⏳ Waiting for AI..."
while ! curl -s http://localhost:11434 > /dev/null; do sleep 1; done

# التأكد من تحميل llama3
if ! ollama list | grep -q "llama3:latest"; then
    echo "⚠️ Model not found, pulling llama3..."
    ollama pull llama3
fi

echo "✅ AI Ready! Launching Bot..."
python3 run.py
