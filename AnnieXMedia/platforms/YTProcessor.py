# Authored By Certified Coders © 2026
# System: Processor | REMOTE JS BYPASS | ANDROID AUTH | HYBRID ENGINE
# Features: Fixes "Sign in" & JS Challenges | Pipe < 200MB | Aria2c > 200MB

import asyncio
import os
import time
import glob
import shutil
import json
import logging
import aiohttp
import yt_dlp
from concurrent.futures import ThreadPoolExecutor
from pyrogram.types import InputMediaAudio, InputMediaVideo, InlineKeyboardButton
from pyrogram.errors import MessageIdInvalid, MessageNotModified, FloodWait

# استيراد المتغيرات الهامة
from config import LOGGER_ID, OWNER_ID 
from AnnieXMedia import LOGGER

class Config:
    # استخدام الرامات (RAM Disk) للتخزين المؤقت للسرعة القصوى
    if os.path.exists("/dev/shm"):
        DOWNLOAD_PATH = "/dev/shm/AnnieDownloads"
    else:
        DOWNLOAD_PATH = os.path.abspath("downloads")
        
    MAX_WORKERS = 16 
    
    # هوية الأندرويد لتخطي الحظر (السطر السحري 1)
    USER_AGENT = "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
    
    # حد التحويل لـ Aria2c (200 ميجا بايت)
    ARIA2_THRESHOLD = 200 * 1024 * 1024 

# إنشاء المجلد
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
        # البحث عن الكوكيز بمسارات متعددة وإرجاع المسار الكامل (Absolute)
        possible_paths = [
            "cookies.txt", 
            "AnnieXMedia/assets/cookies.txt",
            "assets/cookies.txt", 
            "AnnieXMedia/assets/cookies.txt",
            "/app/cookies.txt"
        ]
        for path in possible_paths:
            if os.path.exists(path) and os.path.getsize(path) > 0:
                return os.path.abspath(path)
        return None

    # دالة تحميل الصورة (بديل wget)
    async def _download_thumb_native(self, url, path):
        if not url: return False
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        with open(path, 'wb') as f:
                            f.write(await resp.read())
                        return True
        except: pass
        return False

    # 🧠 الدماغ: جلب المعلومات وتخطي الحماية (Sign in & JS Bypass)
    async def _get_video_info(self, url):
        cookie_file = self.get_cookie_file()
        
        cmd = [
            "yt-dlp", "-j", 
            "--no-warnings",
            "--user-agent", Config.USER_AGENT,
            # ✅ السطر السحري 1: استخدام عميل أندرويد لتخطي Sign in
            "--extractor-args", "youtube:player_client=android",
            # ✅ السطر السحري 2: تفعيل الريموت لتخطي الجافا سكريبت المعقدة
            "--remote-components", "ejs:github",
            url
        ]
        
        if cookie_file:
            cmd.insert(2, "--cookies")
            cmd.insert(3, cookie_file)

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if stdout:
                return json.loads(stdout.decode())
            else:
                # لو فشل، جرب محاولة أخيرة بدون cookies (أحياناً الكوكيز الفاسدة هي السبب)
                if cookie_file:
                    print("⚠️ Retrying without cookies due to failure...")
                    cmd.pop(2) # remove --cookies
                    cmd.pop(2) # remove path
                    process = await asyncio.create_subprocess_exec(
                        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                    )
                    stdout, _ = await process.communicate()
                    if stdout: return json.loads(stdout.decode())
                    
        except Exception as e:
            print(f"❌ Info Fetch Error: {e}")
        return None

    async def get_quality_buttons(self, vidid, stype):
        return []

    # ⚡ الدالة الذكية (Smart Download Switcher)
    async def download_file(self, url, quality_arg, is_video, title, vidid=None, is_owner=False):
        vid_id_str = vidid if vidid else str(int(time.time()))
        
        # 1. جلب المعلومات أولاً (لتحديد الحجم وتجاوز الحماية)
        info = await self._get_video_info(url)
        if not info: return None

        # 2. فحص الحجم
        filesize = info.get('filesize') or info.get('filesize_approx') or 0
        
        # 3. اتخاذ القرار: Piping ولا Aria2c؟
        if filesize > Config.ARIA2_THRESHOLD:
            # أكبر من 200 ميجا -> استخدم Aria2c (للاستقرار)
            return await self._download_aria2c(url, quality_arg, is_video, vid_id_str)
        else:
            # أصغر من 200 ميجا -> استخدم Piping (للسرعة القصوى - 0 ثانية)
            return await self._download_piping(info, is_video, vid_id_str)

    # --- المحرك 1: البث المباشر (Piping) للملفات الخفيفة ---
    async def _download_piping(self, info, is_video, vid_id_str):
        direct_url = info.get('url')
        if not direct_url: return None

        ext = "mp4" if is_video else "mp3"
        pipe_path = os.path.join(Config.DOWNLOAD_PATH, f"{vid_id_str}.{ext}")
        
        if os.path.exists(pipe_path):
            try: os.remove(pipe_path)
            except: pass
        
        try: os.mkfifo(pipe_path)
        except: pass 

        # تحميل الصورة
        thumb_url = info.get('thumbnail')
        thumb_path = os.path.join(Config.DOWNLOAD_PATH, f"{vid_id_str}.jpg")
        if thumb_url: await self._download_thumb_native(thumb_url, thumb_path)

        ua = Config.USER_AGENT
        
        # استخدام FFmpeg للقراءة المباشرة من الرابط والكتابة في الأنبوب
        if is_video:
            # نسخ مباشر للفيديو في حاوية MP4
            ffmpeg_cmd = (
                f'ffmpeg -hide_banner -loglevel error -y -user_agent "{ua}" '
                f'-i "{direct_url}" -i "{thumb_path}" '
                f'-map 0 -map 1 -c:v copy -c:a copy '
                f'-movflags frag_keyframe+empty_moov '
                f'-f mp4 "{pipe_path}"'
            )
        else:
            # تحويل سريع لـ MP3
            ffmpeg_cmd = (
                f'ffmpeg -hide_banner -loglevel error -y -user_agent "{ua}" '
                f'-i "{direct_url}" -i "{thumb_path}" '
                f'-map 0:a -map 1 '
                f'-c:a libmp3lame -q:a 2 -id3v2_version 3 '
                f'-metadata:s:v title="Album cover" -metadata:s:v comment="Cover (front)" '
                f'-f mp3 "{pipe_path}"'
            )

        # تشغيل FFmpeg في الخلفية
        asyncio.create_subprocess_shell(ffmpeg_cmd)
        
        # انتظار بسيط جداً لفتح الأنبوب
        await asyncio.sleep(0.5)
        return pipe_path

    # --- المحرك 2: التحميل الكامل (Aria2c) للملفات الثقيلة ---
    async def _download_aria2c(self, url, quality_arg, is_video, vid_id_str):
        output_template = os.path.join(Config.DOWNLOAD_PATH, f"{vid_id_str}.%(ext)s")
        cookie_file = self.get_cookie_file()
        
        aria2_args = [
            "-x", "16", "-s", "16", "-j", "16", "-k", "1M",
            "--file-allocation=none", "--disable-ipv6=true",
            "--max-connection-per-server=16"
        ]

        base_opts = {
            "outtmpl": output_template,
            "cookiefile": cookie_file,
            "geo_bypass": True,
            "nocheckcertificate": True,
            "quiet": True,
            "noplaylist": True,
            "external_downloader": "aria2c",
            "external_downloader_args": aria2_args,
            "writethumbnail": True, 
            # ✅ تطبيق نفس الحماية هنا لضمان عمل Aria2c
            "remote_components": ["ejs:github"],
            "extractor_args": {"youtube": {"player_client": ["android"]}},
        }
        
        if is_video:
            fmt = "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
            base_opts["postprocessors"] = [{'key': 'FFmpegMetadata', 'add_metadata': True}]
        else:
            fmt = "bestaudio[ext=m4a]/bestaudio/best"
            base_opts["postprocessors"] = [
                {'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'},
                {'key': 'FFmpegMetadata', 'add_metadata': True},
                {'key': 'EmbedThumbnail'}
            ]

        base_opts['format'] = fmt
        loop = asyncio.get_running_loop()

        def _run_download():
            try:
                with yt_dlp.YoutubeDL(base_opts) as ydl:
                    ydl.download([url])
                
                search_pattern = os.path.join(Config.DOWNLOAD_PATH, f"{vid_id_str}.*")
                found_files = glob.glob(search_pattern)
                best_file = None
                max_size = 0
                for f in found_files:
                    if f.endswith(('.mp3', '.mp4', '.m4a', '.webm')):
                        size = os.path.getsize(f)
                        if size > 1024 and size > max_size:
                            max_size = size
                            best_file = f
                return best_file
            except: return None

        return await loop.run_in_executor(self.pool, _run_download)

    # دالة الرفع (Alexa Style)
    async def upload_alexa_style(self, client, mystic_msg, file_path, is_video, title, duration, user_name, vidid=None):
        if not file_path: return False
        
        caption = f"**الـعـنـوان:** {title}\n**طـلـب:** {user_name}"
        
        # استراتيجية الغلاف (مهمة للـ Piping)
        thumb_path = None
        if vidid:
            possible_thumb = os.path.join(Config.DOWNLOAD_PATH, f"{vidid}.jpg")
            if os.path.exists(possible_thumb):
                thumb_path = possible_thumb
            else:
                # بحث احتياطي لـ Aria2c
                for ext in [".webp", ".jpg", ".png"]:
                    t = os.path.join(Config.DOWNLOAD_PATH, f"{vidid}{ext}")
                    if os.path.exists(t): 
                        thumb_path = t; break
        
        if not thumb_path and mystic_msg.photo:
            try: thumb_path = await mystic_msg.download()
            except: pass

        try:
            if is_video:
                media = InputMediaVideo(
                    media=file_path,
                    thumb=thumb_path,
                    caption=caption,
                    duration=int(duration) if duration else 0,
                    supports_streaming=True
                )
                action = "upload_video"
            else:
                media = InputMediaAudio(
                    media=file_path,
                    thumb=thumb_path,
                    caption=caption,
                    duration=int(duration) if duration else 0,
                    title=title,
                    performer=user_name
                )
                action = "upload_audio"
            
            await client.send_chat_action(mystic_msg.chat.id, action)
            await mystic_msg.edit_media(media=media)
            
        except (MessageIdInvalid, MessageNotModified):
            try:
                await mystic_msg.delete()
            except: pass
                
            try:
                if is_video:
                    await client.send_video(mystic_msg.chat.id, video=file_path, caption=caption, thumb=thumb_path, duration=int(duration) if duration else 0)
                else:
                    await client.send_audio(mystic_msg.chat.id, audio=file_path, caption=caption, thumb=thumb_path, duration=int(duration) if duration else 0, title=title, performer=user_name)
            except:
                return False
        except Exception:
            return False
        
        # تنظيف
        if file_path and os.path.exists(file_path): 
            try: os.remove(file_path)
            except: pass
        if thumb_path and os.path.exists(thumb_path):
            try: os.remove(thumb_path)
            except: pass
            
        return True

    # القوائم: تستخدم Aria2c مباشرة لضمان الاستقرار
    async def download_playlist(self, client, mystic_msg, playlist_url, is_video, user_name, limit=30):
        cookie_file = self.get_cookie_file()
        loop = asyncio.get_running_loop()
        ydl_opts = {
            "extract_flat": True, "playlistend": limit, "quiet": True,
            "cookiefile": cookie_file, "user_agent": Config.USER_AGENT,
            "no_warnings": True, "ignoreerrors": True,
            # ✅ الريموت والأندرويد للقوائم أيضاً
            "remote_components": ["ejs:github"],
            "extractor_args": {"youtube": {"player_client": ["android"]}},
        }

        def _fetch_playlist():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(playlist_url, download=False)

        await mystic_msg.edit_text("**جـارٍ جـلـب الـقـائـمـة...**")
        try: info = await loop.run_in_executor(self.pool, _fetch_playlist)
        except: return await mystic_msg.edit_text("**❌ فـشـل الـجـلـب.**")

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

            # استخدام Aria2c (High Quality) للقوائم
            file_path = await self.download_file(
                url, "high", is_video, title, vidid=vid_id, is_owner=True 
            )
            
            if file_path:
                temp_msg = await client.send_message(mystic_msg.chat.id, "**⬆️ رفـع...**")
                await self.upload_alexa_style(
                    client, temp_msg, file_path, is_video, title, 0, user_name, vidid=vid_id
                )
                try:
                    os.remove(file_path)
                    base = os.path.splitext(file_path)[0]
                    for ext in [".jpg", ".webp", ".png"]: 
                        if os.path.exists(base+ext): os.remove(base+ext)
                except: pass
            
            await asyncio.sleep(1)

        await mystic_msg.edit_text(f"**✅ تـم الانـتـهـاء!**")

Processor = YTProcessorAPI()
