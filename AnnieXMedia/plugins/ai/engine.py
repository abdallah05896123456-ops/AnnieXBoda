# plugins/ai/engine.py
# Ollama AI Engine (Streaming)
# Authored By Certified Coders © 2026

import aiohttp
import asyncio
import json
import os

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
MODEL_NAME = os.getenv("OLLAMA_MODEL", "qwen2.5:32b")


async def ask_ollama_stream(prompt: str):
    """
    Stream response from Ollama model
    """
    url = f"{OLLAMA_HOST}/api/generate"

    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": True,
    }

    timeout = aiohttp.ClientTimeout(total=None)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(url, json=payload) as resp:
            async for line in resp.content:
                if not line:
                    continue
                try:
                    data = json.loads(line.decode("utf-8"))
                    if "response" in data:
                        yield data["response"]
                except Exception:
                    continue
