# System: Processor | PRO COVER EDITION | Fix Thumbnails | 16-Core Speed

import asyncio
import os
import time
import glob
import shutil
import yt_dlp
from concurrent.futures import ThreadPoolExecutor
from pyrogram.types import InputMediaAudio, InputMediaVideo, InlineKeyboardButton
from pyrogram.errors import MessageIdInvalid, MessageNotModified, FloodWait
from config import LOGGER_ID
from AnnieXMedia import LOGGER
from AnnieXMedia.utils.formatters import convert_bytes

class Config:
    # استخدام الرامات (RAM Disk)
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
            "platforms/cookies.txt"
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
            "remote_components": ["ejs:github"],
        }
        
        loop = asyncio.get_running_loop()
        
        def _fetch_info():
            try:
                opts = ydl_opts.copy()
                opts['extractor_args'] = {'youtube': {'player_client': ['web']}}
                with yt_dlp.YoutubeDL(opts) as ydl:
                    return ydl.extract_info(yturl, download=False)
            except:
                return None

        formats = []
        try:
            info = await loop.run_in_executor(self.pool, _fetch_info)
            if info: formats = info.get("formats", [])
        except:
            pass 

        keyboard = []
        if stype == "audio":
            keyboard.append([InlineKeyboardButton(text="جـودة فـائـقـة (320)", callback_data=f"song_download audio|high|{vidid}")])
            keyboard.append([InlineKeyboardButton(text="جـودة مـتـوسـطـة (128)", callback_data=f"song_download audio|mid|{vidid}")])
            keyboard.append([InlineKeyboardButton(text="جـودة مـنـخـفـضـة", callback_data=f"song_download audio|low|{vidid}")])
        else:
            has_high = False
            if formats:
                for x in formats:
                    h = x.get("height")
                    if h and h >= 1080: has_high = True

            if has_high:
                keyboard.append([InlineKeyboardButton(text="جـودة فـائـقـة (4K/1080)", callback_data=f"song_download video|high|{vidid}")])
            keyboard.append([InlineKeyboardButton(text="جـودة مـتـوسـطـة (720/480)", callback_data=f"song_download video|mid|{vidid}")])
            keyboard.append([InlineKeyboardButton(text="جـودة مـنـخـفـضـة (360/144)", callback_data=f"song_download video|low|{vidid}")])
        
        keyboard.append([InlineKeyboardButton(text="إغـلاق", callback_data="close")])
        return keyboard

    async def download_file(self, url, quality_arg, is_video, title, vidid=None, is_owner=False):
        vid_id_str = vidid if vidid else str(int(time.time()))
        ext = "mp4" if is_video else "m4a" 
        final_file = os.path.join(Config.DOWNLOAD_PATH, f"{vid_id_str}.{ext}")
        
        if os.path.exists(final_file) and os.path.getsize(final_file) > 1024:
            return final_file

        cookie_file = self.get_cookie_file()
        if not url.startswith("http"): url = f"https://www.youtube.com/watch?v={vidid}"

        # إعدادات Aria2c
        aria2_args = [
            "-x", "16", "-s", "16", "-j", "16", "-k", "1M",
            "--file-allocation=none", "--disable-ipv6=true",
            "--max-connection-per-server=16"
        ]

        base_opts = {
            "outtmpl": os.path.join(Config.DOWNLOAD_PATH, f"{vid_id_str}.%(ext)s"),
            "cookiefile": cookie_file,
            "geo_bypass": True,
            "nocheckcertificate": True,
            "quiet": True,
            "noplaylist": True,
            "external_downloader": "aria2c",
            "external_downloader_args": aria2_args,
            "writethumbnail": True, # تحميل الغلاف أساسي
            "socket_timeout": 60,
            "retries": 10,
            "remote_components": ["ejs:github"],
        }
        
        if is_video:
            # --- إعدادات الفيديو ---
            # المالك
            if is_owner:
                if quality_arg == "high":
                    fmt = "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
                elif quality_arg == "mid":
                    fmt = "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best"
                else:
                    fmt = "bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/best[height<=360][ext=mp4]/best"
            # الأعضاء
            else:
                if quality_arg == "low":
                    fmt = "bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/best[height<=360][ext=mp4]/best"
                else:
                    fmt = "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best"

            # تحويل الغلاف لـ JPG عشان تليجرام يقبله كغلاف للفيديو
            base_opts["postprocessors"] = [
                {'key': 'FFmpegMetadata', 'add_metadata': True},
                {'key': 'FFmpegThumbnailsConvertor', 'format': 'jpg'}
            ]
        else:
            # --- إعدادات الصوت ---
            if is_owner and quality_arg == "high":
                fmt = "bestaudio[ext=m4a]/bestaudio/best"
                q_rate = '320'
            else:
                fmt = "bestaudio[ext=m4a]/bestaudio/best"
                q_rate = '128'

            # دمج الغلاف للصوت
            base_opts["postprocessors"] = [
                {'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': q_rate},
                {'key': 'FFmpegMetadata', 'add_metadata': True},
                {'key': 'EmbedThumbnail'},
                {'key': 'FFmpegThumbnailsConvertor', 'format': 'jpg'}
            ]

        if not is_video:
            final_file = final_file.replace(".m4a", ".mp3")

        base_opts['format'] = fmt

        loop = asyncio.get_running_loop()

        def _run_download():
            try:
                opts = base_opts.copy()
                opts['extractor_args'] = {'youtube': {'player_client': ['web']}}
                
                with yt_dlp.YoutubeDL(opts) as ydl:
                    ydl.download([url])
                
                # التحقق النهائي
                base_name = os.path.join(Config.DOWNLOAD_PATH, vid_id_str)
                if os.path.exists(final_file): return final_file
                if os.path.exists(f"{base_name}.mp4"): return f"{base_name}.mp4"
                if os.path.exists(f"{base_name}.mp3"): return f"{base_name}.mp3"

            except Exception as e:
                print(f"Download Error: {e}")
                pass
            return None

        return await loop.run_in_executor(self.pool, _run_download)

    async def upload_alexa_style(self, client, mystic_msg, file_path, is_video, title, duration, user_name, vidid=None):
        if not file_path or not os.path.exists(file_path):
            return False

        caption = f"**الـعـنـوان:** {title}\n**طـلـب:** {user_name}"
        chat_id = mystic_msg.chat.id
        
        # --- تجهيز الغلاف ---
        thumb_path = None
        base_name = os.path.splitext(file_path)[0]
        
        # التأكد من وجود صورة بصيغة JPG (التيليجرام يفضلها كغلاف فيديو)
        if os.path.exists(f"{base_name}.jpg"):
            thumb_path = f"{base_name}.jpg"
        elif os.path.exists(f"{base_name}.webp"):
            # لو موجودة WebP ممكن نحولها سريعاً لو لزم الأمر، لكن غالباً jpg ستكون موجودة
            thumb_path = f"{base_name}.webp"
        
        # لو مفيش، ندور بأي طريقة
        if not thumb_path and vidid:
             possible_files = glob.glob(os.path.join(Config.DOWNLOAD_PATH, f"*{vidid}*"))
             for f in possible_files:
                if f.endswith((".jpg", ".jpeg", ".png")) and not f.endswith((".mp3", ".mp4", ".m4a")):
                    thumb_path = f
                    break

        try:
            if is_video:
                # هنا النقطة: thumb=thumb_path بيخلي الفيديو يتبعت وعليه الغلاف بتاعه
                # مش بيبعت رسالة تانية، لا، بيبعت فيديو واحد شكله احترافي
                media = InputMediaVideo(
                    media=file_path,
                    thumb=thumb_path, 
                    caption=caption, 
                    duration=duration, 
                    supports_streaming=True
                )
            else:
                media = InputMediaAudio(
                    media=file_path, 
                    thumb=thumb_path, 
                    caption=caption, 
                    duration=duration, 
                    title=title, 
                    performer=user_name
                )
            
            await mystic_msg.edit_media(media=media)
            
        except (MessageIdInvalid, MessageNotModified):
            # لو الرسالة القديمة اتمسحت، ابعت واحدة جديدة نضيفة
            try:
                try: await mystic_msg.delete()
                except: pass
                
                if is_video:
                    await client.send_video(
                        chat_id, 
                        video=file_path, 
                        caption=caption, 
                        duration=duration, 
                        thumb=thumb_path, # الغلاف هنا
                        supports_streaming=True
                    )
                else:
                    await client.send_audio(
                        chat_id, 
                        audio=file_path, 
                        caption=caption, 
                        duration=duration, 
                        title=title, 
                        performer=user_name, 
                        thumb=thumb_path
                    )
            except:
                return False
        except Exception:
            # لو فشل كل حاجة، ابعت الملف من غير غلاف (نادراً ما يحصل)
            try:
                if is_video:
                    await client.send_video(chat_id, video=file_path, caption=caption, duration=duration)
                else:
                    await client.send_audio(chat_id, audio=file_path, caption=caption, duration=duration, title=title, performer=user_name)
            except:
                return False
        
        return True

    # --- تحميل البلاي ليست ---
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
            "remote_components": ["ejs:github"],
        }

        def _fetch_playlist():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(playlist_url, download=False)

        await mystic_msg.edit_text("**جـارٍ جـلـب الـقـائـمـة...**")
        
        try:
            info = await loop.run_in_executor(self.pool, _fetch_playlist)
        except:
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
                try: await mystic_msg.edit_text(f"**📥 تـحـمـيـل: {count}/{total}**\n**🎵 {title}**")
                except: pass

            file_path = await self.download_file(
                url, "mid", is_video, title, vidid=vid_id
            )
            
            if file_path:
                temp_msg = await client.send_message(mystic_msg.chat.id, "**⬆️ رفـع...**")
                await self
