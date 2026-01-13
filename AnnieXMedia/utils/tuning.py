import asyncio
import os

# Fly.io aggressive mode
CPU = os.cpu_count() or 2

# ⚠️ أعلى قيمة مستقرة فعلًا
MAX_CONCURRENT = 12   # لا تزود عن كده على Fly

# 🚀 Chunk ضخم = أقل requests = سرعة نار
CHUNK_SIZE = 4 * 1024 * 1024   # 4 MB 🔥

YTDLP_TIMEOUT = 20

YOUTUBE_META_TTL = 300
YOUTUBE_META_MAX = 4096

SEM = asyncio.Semaphore(MAX_CONCURRENT)
