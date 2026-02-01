# file: AnnieXMedia/platforms/YTProcessor.py
# Processor: streaming via FIFO, direct URL fast-path, background caching, upload, call play

import asyncio
import os
import time
import glob
import shutil
import yt_dlp
import logging
import subprocess
from concurrent.futures import ThreadPoolExecutor
from typing import Tuple

from pyrogram.types import InputMediaAudio, InputMediaVideo, InlineKeyboardButton
from pyrogram.errors import MessageIdInvalid, MessageNotModified

# optional: pytgcalls for voice chat streaming
try:
    from pytgcalls import PyTgCalls
    from pytgcalls.types.input_stream import InputAudioStream
    PYCALLS_AVAILABLE = True
except Exception:
    PYCALLS_AVAILABLE = False

logger = logging.getLogger("AnnieXMedia.YTProcessor")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)

# CONFIG (same approach as Youtube.py)
if os.path.exists("/dev/shm"):
    DOWNLOAD_PATH = "/dev/shm/AnnieDownloads"
else:
    DOWNLOAD_PATH = os.path.abspath("downloads")
os.makedirs(DOWNLOAD_PATH, exist_ok=True)

ARIA2_ARGS = ["-x", "16", "-s", "16", "-j", "16", "-k", "1M", "--file-allocation=none", "--disable-ipv6=true"]
POOL_MAX = 12

class YTProcessorAPI:
    def __init__(self, app=None, pytgcalls_instance=None):
        self.pool = ThreadPoolExecutor(max_workers=POOL_MAX)
        self.app = app  # pyrogram client (set later if needed)
        self.pytgcalls = pytgcalls_instance if PYCALLS_AVAILABLE and pytgcalls_instance else None

    def get_cookie_file(self):
        possible_paths = [
            "cookies.txt", "AnnieXMedia/cookies.txt",
            "assets/cookies.txt", "AnnieXMedia/assets/cookies.txt",
            "platforms/cookies.txt", "/app/cookies.txt"
        ]
        for p in possible_paths:
            if os.path.exists(p) and os.path.getsize(p) > 0:
                return p
        return None

    # helper: create fifo path
    def _make_fifo(self, vidid: str, ext: str) -> str:
        base = os.path.join(DOWNLOAD_PATH, f"{vidid}.{ext}.fifo")
        if os.path.exists(base):
            try:
                os.unlink(base)
            except Exception:
                pass
        try:
            os.mkfifo(base, 0o600)
            return base
        except Exception:
            # fallback to normal temp file
            fallback = os.path.join(DOWNLOAD_PATH, f"{vidid}.{ext}")
            return fallback

    # background cache using aria2/yt-dlp
    def _background_cache(self, url: str, outpath: str, is_video: bool):
        try:
            fmt = "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]" if is_video else "bestaudio[ext=m4a]/bestaudio/best"
            cookie = self.get_cookie_file()
            opts = {
                "format": fmt,
                "outtmpl": outpath,
                "cookiefile": cookie,
                "quiet": True,
                "no_warnings": True,
                "external_downloader": "aria2c",
                "external_downloader_args": ARIA2_ARGS,
                "prefer_ffmpeg": True,
                "writethumbnail": True,
                "addmetadata": True,
                "extractor_args": {'youtube': {'player_client': ['web']}},
                "remote_components": ["ejs:github"],
            }
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])
        except Exception:
            logger.exception("background cache failed")

    # primary interface: download_file -> returns (path_or_url, direct_flag)
    async def download_file(self, url: str, quality_arg: str, is_video: bool, title: str, vidid: str = None, is_owner: bool = False) -> Tuple[str, bool]:
        """
        Try direct URL fast-path, then stream-to-fifo for immediate upload,
        then fallback to full download.
        Returns (path_or_url, direct_flag)
        """
        vid = vidid or str(int(time.time()))
        cookie = self.get_cookie_file()
        loop = asyncio.get_running_loop()

        # 1) try direct link (fast)
        def _try_direct():
            try:
                opts = {"quiet": True, "cookiefile": cookie, "extractor_args": {'youtube': {'player_client': ['web']}}, "remote_components": ["ejs:github"]}
                if is_video:
                    opts["format"] = "best[height<=720]"
                else:
                    opts["format"] = "bestaudio[ext=m4a]/bestaudio"
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                fmts = info.get("formats", []) if info else []
                for f in reversed(fmts):
                    if not f.get("url"):
                        continue
                    fmt_name = str(f.get("format", "")).lower()
                    if "dash" in fmt_name:
                        continue
                    return f.get("url")
                return None
            except Exception:
                return None

        direct = await loop.run_in_executor(self.pool, _try_direct)
        if direct:
            # start background cache to fill an actual file for later
            outpath = os.path.join(DOWNLOAD_PATH, f"{vid}.fallback.{'mp4' if is_video else 'm4a'}")
            self.pool.submit(self._background_cache, url, outpath, is_video)
            return direct, True

        # 2) try streaming via FIFO -> ffmpeg pipeline, then return fifo path for immediate upload
        # fifo ext
        ext = "mp4" if is_video else "m4a"
        fifo = self._make_fifo(vid, ext)

        # build commands
        cookie_args = []
        if cookie:
            cookie_args = ["--cookies", cookie]

        # yt-dlp command outputs to stdout (-o -), prefer a suitable format to pipe cleanly
        ytdlp_fmt = "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]" if is_video else "bestaudio[ext=m4a]/bestaudio/best"
        ytdlp_cmd = ["yt-dlp", *cookie_args, "-f", ytdlp_fmt, "-o", "-", url]

        # ffmpeg will read stdin (-i -) and output container to fifo (stream copy if possible)
        if is_video:
            ffmpeg_cmd = [
                "ffmpeg", "-hide_banner", "-loglevel", "error",
                "-i", "pipe:0",
                "-c", "copy",
                "-f", "mp4",
                fifo
            ]
        else:
            # audio: convert to m4a/mp3 to be safe
            ffmpeg_cmd = [
                "ffmpeg", "-hide_banner", "-loglevel", "error",
                "-i", "pipe:0",
                "-c:a", "aac", "-b:a", "192k",
                "-f", "mp4",
                fifo
            ]

        # run pipeline in threadpool so it doesn't block loop
        def _run_pipe():
            try:
                # start yt-dlp process (stdout pipe)
                p1 = subprocess.Popen(ytdlp_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                # start ffmpeg, reading from p1.stdout
                p2 = subprocess.Popen(ffmpeg_cmd, stdin=p1.stdout, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                # close parent's reference to p1.stdout so ffmpeg gets EOF when done
                p1.stdout.close()
                # wait for pipeline completion (this will run until stream end or download completed)
                p2.wait()
                p1.wait()
            except Exception:
                logger.exception("stream pipeline failed")
            finally:
                # when pipeline ends, if fifo is a real fifo, it will close; if fallback file, ensure exists
                return

        # submit pipeline
        self.pool.submit(_run_pipe)

        # return fifo path for immediate upload (Pyrogram will read it)
        return fifo, False

    # upload helper: supports local path or remote url; if FIFO path is provided, Pyrogram streams it.
    async def upload_alexa_style(self, client, mystic_msg, path_or_url: str, is_video: bool, title: str, duration: int, user_name: str, vidid: str = None) -> bool:
        if not path_or_url:
            return False

        chat_id = mystic_msg.chat.id
        caption = f"**الـعـنـوان:** {title}\n**طـلـب:** {user_name}"

        # choose media
        try:
            if is_video:
                media = InputMediaVideo(media=path_or_url, caption=caption, duration=duration, supports_streaming=True)
            else:
                media = InputMediaAudio(media=path_or_url, caption=caption, duration=duration, title=title, performer=user_name)
            await mystic_msg.edit_media(media=media)
            return True
        except (MessageIdInvalid, MessageNotModified):
            try:
                try:
                    await mystic_msg.delete()
                except Exception:
                    pass
                if is_video:
                    await client.send_video(chat_id, video=path_or_url, caption=caption, duration=duration, supports_streaming=True)
                else:
                    await client.send_audio(chat_id, audio=path_or_url, caption=caption, duration=duration, title=title, performer=user_name)
                return True
            except Exception:
                logger.exception("fallback send failed")
                return False
        except Exception:
            logger.exception("edit_media/send failed")
            return False

    # optional: play in voice chat using pytgcalls (if available)
    async def play_in_call(self, chat_id: int, url: str):
        if not PYCALLS_AVAILABLE or not self.pytgcalls:
            raise RuntimeError("PyTgCalls not available/configured")
        # try to get direct stream url
        # pytgcalls expects local or raw stream input (telegram voice chat uses PCM/Opus)
        # simplest: pass direct url to InputAudioStream.url (depends on pytgcalls backend)
        try:
            await self.pytgcalls.join_group_call(chat_id, InputAudioStream(url))
            return True
        except Exception:
            logger.exception("play_in_call failed")
            return False

Processor = YTProcessorAPI()
