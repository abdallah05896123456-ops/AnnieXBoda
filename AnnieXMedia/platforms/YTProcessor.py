# file: AnnieXMedia/platforms/YTProcessor.py
# Processor: safe downloads, direct-link fast-path, aria2c background cache, thumbnails & metadata
# Compatible return: download_file(...) -> (path_or_url_or_None, direct_flag_bool)

import asyncio
import os
import time
import glob
import shutil
import yt_dlp
import subprocess
import logging
from concurrent.futures import ThreadPoolExecutor

from pyrogram.types import InputMediaAudio, InputMediaVideo, InlineKeyboardButton
from pyrogram.errors import MessageIdInvalid, MessageNotModified

# استيراد المتغيرات الهامة
from config import LOGGER_ID, OWNER_ID
from AnnieXMedia import LOGGER
from AnnieXMedia.utils.formatters import convert_bytes  # optional helper if used

logger = logging.getLogger("AnnieXMedia.YTProcessor")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)

class Config:
    if os.path.exists("/dev/shm"):
        DOWNLOAD_PATH = "/dev/shm/AnnieDownloads"
    else:
        DOWNLOAD_PATH = os.path.abspath("downloads")
    MAX_WORKERS = 16
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"

if not os.path.exists(Config.DOWNLOAD_PATH):
    os.makedirs(Config.DOWNLOAD_PATH, exist_ok=True)

class YTProcessorAPI:
    def __init__(self):
        self.pool = ThreadPoolExecutor(max_workers=Config.MAX_WORKERS)
        self._clean_cache()

    def _clean_cache(self):
        try:
            for filename in os.listdir(Config.DOWNLOAD_PATH):
                file_path = os.path.join(Config.DOWNLOAD_PATH, filename)
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
        except Exception:
            pass

    def get_cookie_file(self):
        possible_paths = [
            "cookies.txt", "AnnieXMedia/cookies.txt",
            "assets/cookies.txt", "AnnieXMedia/assets/cookies.txt",
            "platforms/cookies.txt", "/app/cookies.txt"
        ]
        for path in possible_paths:
            if os.path.exists(path) and os.path.getsize(path) > 0:
                return path
        return None

    async def get_quality_buttons(self, vidid, stype):
        yturl = f"https://www.youtube.com/watch?v={vidid}"
        cookie_file = self.get_cookie_file()

        ydl_opts = {
            "quiet": True,
            "cookiefile": cookie_file,
            "no_warnings": True,
            "ignoreerrors": True,
            "nocheckcertificate": True,
        }

        loop = asyncio.get_running_loop()

        def _fetch_info():
            try:
                opts = ydl_opts.copy()
                opts['extractor_args'] = {'youtube': {'player_client': ['web']}}
                with yt_dlp.YoutubeDL(opts) as ydl:
                    return ydl.extract_info(yturl, download=False)
            except Exception:
                return None

        formats = []
        try:
            info = await loop.run_in_executor(self.pool, _fetch_info)
            if info:
                formats = info.get("formats", [])
        except Exception:
            pass

        keyboard = []
        if stype == "audio":
            keyboard.append([InlineKeyboardButton(text="💎 جـودة الـمـالـك (320)", callback_data=f"song_download audio|high|{vidid}")])
            keyboard.append([InlineKeyboardButton(text="جـودة مـتـوسـطـة (128)", callback_data=f"song_download audio|mid|{vidid}")])
            keyboard.append([InlineKeyboardButton(text="جـودة مـنـخـفـضـة", callback_data=f"song_download audio|low|{vidid}")])
        else:
            has_high = False
            if formats:
                for x in formats:
                    h = x.get("height")
                    if h and h >= 1080:
                        has_high = True
                        break
            if has_high:
                keyboard.append([InlineKeyboardButton(text="💎 جـودة الـمـالـك (4K/1080)", callback_data=f"song_download video|high|{vidid}")])
            keyboard.append([InlineKeyboardButton(text="جـودة مـتـوسـطـة (720/480)", callback_data=f"song_download video|mid|{vidid}")])
            keyboard.append([InlineKeyboardButton(text="جـودة مـنـخـفـضـة (360/144)", callback_data=f"song_download video|low|{vidid}")])

        keyboard.append([InlineKeyboardButton(text="إغـلاق", callback_data="close")])
        return keyboard

    async def download_file(self, url, quality_arg, is_video, title, vidid=None, is_owner=False):
        """
        Return: (path_or_url_or_None, direct_flag_bool)
        - tries to return a direct URL (True) if available fast,
          while scheduling background cache.
        - otherwise performs download and returns local path (False).
        """
        vid_id_str = vidid if vidid else str(int(time.time()))
        output_template = os.path.join(Config.DOWNLOAD_PATH, f"{vid_id_str}.%(ext)s")
        cookie_file = self.get_cookie_file()
        if not url.startswith("http") and vidid:
            url = f"https://www.youtube.com/watch?v={vidid}"

        aria2_args = [
            "-x", "16", "-s", "16", "-j", "16", "-k", "1M",
            "--file-allocation=none", "--disable-ipv6=true",
            "--max-connection-per-server=16"
        ]

        is_hls = "m3u8" in url or url.endswith(".m3u8")  # simple HLS detect

        base_opts = {
            "outtmpl": output_template,
            "cookiefile": cookie_file,
            "geo_bypass": True,
            "nocheckcertificate": True,
            "quiet": True,
            "noplaylist": True,
            "writethumbnail": True,
            "addmetadata": True,
            # parse-metadata mapping (yt-dlp 2026+)
            "parse_metadata": {
                "title": "%(artist)s - %(title)s",
                "artist": "%(uploader)s",
                "album": "%(channel)s",
            },
            "socket_timeout": 60,
            "retries": 10,
            "extractor_args": {'youtube': {'player_client': ['web', 'android']}},
        }

        # choose format depending on request
        if is_video:
            if is_owner and quality_arg == "high":
                fmt = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best"
            else:
                fmt = "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]"
            base_opts["format"] = fmt
            base_opts["postprocessors"] = [{'key': 'FFmpegMetadata', 'add_metadata': True}]
        else:
            # audio path
            base_opts["format"] = "bestaudio[ext=m4a]/bestaudio"
            q_rate = '320' if is_owner and quality_arg == "high" else '128'
            base_opts["postprocessors"] = [
                {'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': q_rate},
                {'key': 'FFmpegMetadata', 'add_metadata': True},
                {'key': 'EmbedThumbnail'}
            ]

        # disable external_download for HLS
        if not is_hls:
            base_opts["external_downloader"] = "aria2c"
            base_opts["external_downloader_args"] = aria2_args

        loop = asyncio.get_running_loop()

        # 1) Try to get a direct URL from formats (fast-path)
        def _try_direct():
            try:
                opts = base_opts.copy()
                opts["skip_download"] = True
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                fmts = info.get("formats", []) if info else []
                # prefer non-dash formats that contain 'url'
                for f in reversed(fmts):
                    u = f.get("url")
                    if not u:
                        continue
                    fmt_name = str(f.get("format", "")).lower()
                    if "dash" in fmt_name:
                        continue
                    # found candidate direct URL
                    return u
            except Exception:
                return None

        try:
            direct_candidate = await loop.run_in_executor(self.pool, _try_direct)
            if direct_candidate:
                # schedule background cache to fill RAM disk
                final_path = os.path.join(Config.DOWNLOAD_PATH, f"{vid_id_str}.{ 'mp4' if is_video else 'm4a'}")
                self.pool.submit(self._background_download, url, final_path, bool(is_video))
                return direct_candidate, True
        except Exception:
            logger.debug("Direct candidate attempt failed", exc_info=True)

        # 2) Fallback to full download (blocking in threadpool)
        def _sync_download():
            try:
                opts = base_opts.copy()
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    # prepare filename and probe for actual ext
                    filename = ydl.prepare_filename(info)
                    base = os.path.splitext(filename)[0]
                    # look for existing extension alternatives
                    for ext in (".mp4", ".m4a", ".mp3", ".webm", ".mkv", ".ts"):
                        candidate = base + ext
                        if os.path.exists(candidate):
                            return candidate
                    # if not found, return filename if exists
                    return filename if os.path.exists(filename) else None
            except Exception as e:
                logger.exception("download_file error", exc_info=True)
                return None

        downloaded = await loop.run_in_executor(self.pool, _sync_download)
        if downloaded:
            return downloaded, False

        return None, False

    def _background_download(self, link: str, final_path: str, is_video: bool):
        """
        Background cache using yt-dlp+aria2c (runs in threadpool).
        It's best-effort: failures logged but ignored.
        """
        try:
            fmt = "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]" if is_video else "bestaudio[ext=m4a]/bestaudio/best"
            aria2_args = ["-x", "16", "-s", "16", "-j", "16", "-k", "1M", "--file-allocation=none", "--disable-ipv6=true"]
            opts = {
                "format": fmt,
                "outtmpl": final_path,
                "cookiefile": self.get_cookie_file(),
                "quiet": True,
                "no_warnings": True,
                "external_downloader": "aria2c",
                "external_downloader_args": aria2_args,
                "prefer_ffmpeg": True,
                "writethumbnail": True,
                "addmetadata": True,
            }
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([link])
        except Exception:
            logger.debug("background download failed", exc_info=True)
            return

    async def upload_alexa_style(self, client, mystic_msg, file_path_or_url, is_video, title, duration, user_name, vidid=None):
        """
        file_path_or_url may be:
          - local path (file exists)
          - remote direct URL (starts with http)
        """
        if not file_path_or_url:
            return False

        # If it's a remote URL, Pyrogram can sometimes stream it directly.
        is_remote = isinstance(file_path_or_url, str) and file_path_or_url.startswith("http")
        caption = f"**الـعـنـوان:** {title}\n**طـلـب:** {user_name}"
        chat_id = mystic_msg.chat.id

        thumb_path = None
        # try find local thumbnail near file
        if not is_remote and os.path.exists(file_path_or_url):
            base = os.path.splitext(file_path_or_url)[0]
            for ext in (".webp", ".jpg", ".jpeg", ".png"):
                if os.path.exists(base + ext):
                    thumb_path = base + ext
                    break
            file_to_send = file_path_or_url
        else:
            file_to_send = file_path_or_url  # URL or non-existent path

        try:
            if is_video:
                media = InputMediaVideo(media=file_to_send, thumb=thumb_path, caption=caption, duration=duration, supports_streaming=True)
            else:
                media = InputMediaAudio(media=file_to_send, thumb=thumb_path, caption=caption, duration=duration, title=title, performer=user_name)

            await mystic_msg.edit_media(media=media)
        except (MessageIdInvalid, MessageNotModified):
            try:
                try:
                    await mystic_msg.delete()
                except Exception:
                    pass
                if is_video:
                    if is_remote:
                        await client.send_video(chat_id, video=file_to_send, caption=caption, duration=duration, thumb=thumb_path, supports_streaming=True)
                    else:
                        await client.send_video(chat_id, video=file_to_send, caption=caption, duration=duration, thumb=thumb_path, supports_streaming=True)
                else:
                    if is_remote:
                        await client.send_audio(chat_id, audio=file_to_send, caption=caption, duration=duration, title=title, performer=user_name, thumb=thumb_path)
                    else:
                        await client.send_audio(chat_id, audio=file_to_send, caption=caption, duration=duration, title=title, performer=user_name, thumb=thumb_path)
            except Exception:
                return False
        except Exception:
            try:
                if is_video:
                    await client.send_video(chat_id, video=file_to_send, caption=caption, duration=duration)
                else:
                    await client.send_audio(chat_id, audio=file_to_send, caption=caption, duration=duration, title=title, performer=user_name)
            except Exception:
                return False

        return True

    async def download_playlist(self, client, mystic_msg, playlist_url, is_video, user_name, limit=30):
        cookie_file = self.get_cookie_file()
        loop = asyncio.get_running_loop()

        ydl_opts = {
            "extract_flat": True,
            "playlistend": limit,
            "quiet": True,
            "cookiefile": cookie_file,
            "user_agent": Config.USER_AGENT,
            "no_warnings": True,
            "ignoreerrors": True,
            "extractor_args": {'youtube': {'player_client': ['web', 'android']}}
        }

        def _fetch_playlist():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(playlist_url, download=False)

        await mystic_msg.edit_text("**جـارٍ جـلـب الـقـائـمـة...**")

        try:
            info = await loop.run_in_executor(self.pool, _fetch_playlist)
        except Exception:
            return await mystic_msg.edit_text("**❌ فـشـل الـجـلـب.**")

        if not info or 'entries' not in info:
            return await mystic_msg.edit_text("**❌ لا يـوجـد مـحـتـوى.**")

        entries = info['entries']
        total = len(entries)
        await mystic_msg.edit_text(f"**✅ تـم كـشـف {total} مـلـف.\nجـارٍ الـبـدء...**")

        count = 0
        for entry in entries:
            count += 1
            vid_id = entry.get('id')
            title = entry.get('title', f"Track {count}")
            url = f"https://www.youtube.com/watch?v={vid_id}"

            if count % 2 == 0:
                try:
                    await mystic_msg.edit_text(f"**📥 تـحـمـيـل: {count}/{total}**\n**🎵 {title}**")
                except Exception:
                    pass

            file_path_or_url, direct = await self.download_file(url, "mid" if is_video else "high", is_video, title, vidid=vid_id, is_owner=True)
            if file_path_or_url:
                temp_msg = await client.send_message(mystic_msg.chat.id, "**⬆️ رفـع...**")
                await self.upload_alexa_style(client, temp_msg, file_path_or_url, is_video, title, 0, user_name, vidid=vid_id)
                # remove local file if it's local
                try:
                    if not (isinstance(file_path_or_url, str) and file_path_or_url.startswith("http")):
                        os.remove(file_path_or_url)
                        base = os.path.splitext(file_path_or_url)[0]
                        for ext in [".jpg", ".webp", ".png"]:
                            if os.path.exists(base + ext):
                                os.remove(base + ext)
                except Exception:
                    pass

            await asyncio.sleep(1)

        await mystic_msg.edit_text(f"**✅ تـم الانـتـهـاء!**")

Processor = YTProcessorAPI()
