# file: AnnieXMedia/platforms/YTProcessor.py
import asyncio
import os
import time
import glob
import shutil
import yt_dlp
import logging
import subprocess
import stat
import io
from concurrent.futures import ThreadPoolExecutor
from typing import Tuple

from pyrogram.types import InputMediaAudio, InputMediaVideo
from pyrogram.errors import MessageIdInvalid, MessageNotModified

logger = logging.getLogger("AnnieXMedia.YTProcessor")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)

if os.path.exists("/dev/shm"):
    DOWNLOAD_PATH = "/dev/shm/AnnieDownloads"
else:
    DOWNLOAD_PATH = os.path.abspath("downloads")
os.makedirs(DOWNLOAD_PATH, exist_ok=True)

ARIA2_ARGS = ["-x", "16", "-s", "16", "-j", "16", "-k", "1M", "--file-allocation=none", "--disable-ipv6=true"]
POOL_MAX = 12

class YTProcessorAPI:
    def __init__(self, app=None):
        self.pool = ThreadPoolExecutor(max_workers=POOL_MAX)
        self.app = app  # set the pyrogram client later if needed

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

    def _make_fifo(self, vidid: str, ext: str) -> str:
        base = os.path.join(DOWNLOAD_PATH, f"{vidid}.{ext}.fifo")
        try:
            if os.path.exists(base):
                os.unlink(base)
            os.mkfifo(base, 0o600)
            return base
        except Exception:
            # fallback file
            return os.path.join(DOWNLOAD_PATH, f"{vidid}.{ext}")

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

    async def download_file(self, url: str, quality_arg: str, is_video: bool, title: str, vidid: str = None, is_owner: bool = False) -> Tuple[str, bool]:
        vid = vidid or str(int(time.time()))
        cookie = self.get_cookie_file()
        loop = asyncio.get_event_loop()

        # try direct url fast-path
        def _try_direct():
            try:
                opts = {"quiet": True, "cookiefile": cookie, "extractor_args": {'youtube': {'player_client': ['web']}}, "remote_components": ["ejs:github"]}
                if is_video:
                    opts["format"] = "best[height<=720]/best"
                else:
                    opts["format"] = "bestaudio[ext=m4a]/bestaudio"
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                if not info:
                    return None
                fmts = info.get("formats", [])
                for f in reversed(fmts):
                    u = f.get("url")
                    if not u:
                        continue
                    fmt_name = str(f.get("format", "")).lower()
                    if "dash" in fmt_name:
                        continue
                    return u
                return None
            except Exception:
                return None

        direct = await loop.run_in_executor(self.pool, _try_direct)
        if direct:
            # schedule background cache
            outpath = os.path.join(DOWNLOAD_PATH, f"{vid}.fallback.{'mp4' if is_video else 'm4a'}")
            self.pool.submit(self._background_cache, url, outpath, is_video)
            return direct, True

        # try streaming pipeline via fifo
        ext = "mp4" if is_video else "m4a"
        fifo = self._make_fifo(vid, ext)

        cookie_args = []
        if cookie:
            cookie_args = ["--cookies", cookie]

        ytdlp_fmt = "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]" if is_video else "bestaudio[ext=m4a]/bestaudio/best"
        ytdlp_cmd = ["yt-dlp", *cookie_args, "-f", ytdlp_fmt, "-o", "-", url]

        if is_video:
            ffmpeg_cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", "pipe:0", "-c", "copy", "-f", "mp4", fifo]
        else:
            ffmpeg_cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", "pipe:0", "-c:a", "aac", "-b:a", "192k", "-f", "mp4", fifo]

        def _run_pipe():
            try:
                p1 = subprocess.Popen(ytdlp_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                p2 = subprocess.Popen(ffmpeg_cmd, stdin=p1.stdout, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                p1.stdout.close()
                p2.wait()
                p1.wait()
            except Exception:
                logger.exception("stream pipeline failed")
            finally:
                return

        # start pipeline in background
        self.pool.submit(_run_pipe)

        # return fifo path (or fallback file path) — direct_flag False because it's local stream
        return fifo, False

    async def upload_alexa_style(self, client, mystic_msg, path_or_url: str, is_video: bool, title: str, duration: int, user_name: str, vidid: str = None) -> bool:
        if not path_or_url:
            return False

        chat_id = mystic_msg.chat.id
        caption = f"**الـعـنـوان:** {title}\n**طـلـب:** {user_name}"

        try:
            # detect remote url
            if isinstance(path_or_url, str) and path_or_url.startswith("http"):
                # try editing message media if possible
                try:
                    if is_video:
                        media = InputMediaVideo(media=path_or_url, caption=caption, duration=duration, supports_streaming=True)
                    else:
                        media = InputMediaAudio(media=path_or_url, caption=caption, duration=duration, title=title, performer=user_name)
                    await mystic_msg.edit_media(media=media)
                    return True
                except Exception:
                    # fallback to send
                    try:
                        await mystic_msg.delete()
                    except:
                        pass
                    if is_video:
                        await client.send_video(chat_id, video=path_or_url, caption=caption, duration=duration, supports_streaming=True)
                    else:
                        await client.send_audio(chat_id, audio=path_or_url, caption=caption, duration=duration, title=title, performer=user_name)
                    return True

            # else local path / fifo
            if os.path.exists(path_or_url):
                st = os.stat(path_or_url)
                is_fifo = stat.S_ISFIFO(st.st_mode)
            else:
                is_fifo = False

            # If FIFO: open as binary stream and send as file-like (Pyrogram supports file-like in send_audio/send_video)
            if is_fifo:
                try:
                    f = open(path_or_url, "rb")  # will block until writer writes
                    try:
                        await mystic_msg.delete()
                    except:
                        pass
                    if is_video:
                        await client.send_video(chat_id, video=f, caption=caption, duration=duration, supports_streaming=True)
                    else:
                        await client.send_audio(chat_id, audio=f, caption=caption, duration=duration, title=title, performer=user_name)
                    try:
                        f.close()
                    except:
                        pass
                    return True
                except Exception:
                    logger.exception("sending fifo failed")
                    try:
                        if not f.closed:
                            f.close()
                    except:
                        pass
                    return False

            # Not FIFO: try edit_media first (fast replacement)
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
                    except:
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

        except Exception:
            logger.exception("upload_alexa_style failed outer")
            return False

Processor = YTProcessorAPI()
