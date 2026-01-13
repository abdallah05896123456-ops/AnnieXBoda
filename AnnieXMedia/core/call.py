# Authored By Certified Coders © 2025
"""
نسخة محسّنة من call.py
- إزالة flags التي تبطئ ffmpeg مثل -re و -fflags nobuffer عند استخدامها كـ ffmpeg_parameters مع PyTgCalls.
- ضمان ستيريو (-ac 2) ومعدل عينة 48kHz (-ar 48000).
- تحسين خيارات yt-dlp لسرعة أكبر (أجزاء متزامنة وحجم chunk أكبر).
- محاولة copy streams أولاً ثم recode عند الضرورة لتسريع التحويل.
- تنفيذ كل عمليات الحظر (yt-dlp، requests، ffmpeg convert) في executor لعدم حجب الـ event loop.
- محاولات fallback ذكية عند NoVideoSourceFound.
"""

import asyncio
import os
import shlex
import subprocess
import tempfile
import time
from datetime import datetime, timedelta
from typing import Union, Optional

from ntgcalls import TelegramServerError, ConnectionNotFound
from pyrogram import Client
from pyrogram.errors import FloodWait, ChatAdminRequired
from pyrogram.types import InlineKeyboardMarkup
from pytgcalls import PyTgCalls
# ✅ تم إزالة AlreadyJoinedError لأنه غير موجود في نسختك
from pytgcalls.exceptions import NoActiveGroupCall, NoAudioSourceFound, NoVideoSourceFound
from pytgcalls.types import AudioQuality, ChatUpdate, MediaStream, StreamEnded, Update, VideoQuality

import yt_dlp

import config
from strings import get_string
from AnnieXMedia import LOGGER, YouTube, app
from AnnieXMedia.misc import db
from AnnieXMedia.utils.database import (
    add_active_chat,
    add_active_video_chat,
    get_lang,
    get_loop,
    group_assistant,
    is_autoend,
    music_on,
    remove_active_chat,
    remove_active_video_chat,
    set_loop,
)
from AnnieXMedia.utils.exceptions import AssistantErr
from AnnieXMedia.utils.formatters import check_duration, seconds_to_min, speed_converter
from AnnieXMedia.utils.inline.play import stream_markup
from AnnieXMedia.utils.stream.autoclear import auto_clean
from AnnieXMedia.utils.thumbnails import get_thumb
from AnnieXMedia.utils.errors import capture_internal_err

# ---------- إعدادات تحويل/تحميل عامة ----------
DOWNLOAD_DIR = os.path.join(os.getcwd(), "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# ---------- التغيير الرئيسي: افتراض ffmpeg params خفيف وفعال ----------
# ملاحظة: **لا تضع -re هنا** لأن ذلك سيجبر ffmpeg على قراءة المصدر بسرعة الزمن الحقيقي (يعرقل السرعة).
# اجعل ffmpeg يحافظ على ستيريو ومعدل عينة مناسب فقط.
DEFAULT_FFMPEG_PARAMS = "-ac 2 -ar 48000 -threads 0"

# timeout للـ ffmpeg convert (بالثواني)
FFMPEG_CONVERT_TIMEOUT = 300

# ---------- مساعدة لوجي (اختيارية) ----------
def _log(msg: str):
    try:
        LOGGER(__name__).debug(msg)
    except Exception:
        print(msg)

autoend = {}
counter = {}

# ---------- مساعدات داخلية لتحضير الوسائط ----------

def _is_url(path: str) -> bool:
    return isinstance(path, str) and path.startswith(("http://", "https://"))

def _is_m3u8(path: str) -> bool:
    return isinstance(path, str) and (path.lower().endswith(".m3u8") or ("m3u8" in path and "manifest" in path))

def _safe_tmpfile(suffix: str = ".mp4") -> str:
    fd, p = tempfile.mkstemp(suffix=suffix, prefix="annie_")
    os.close(fd)
    return p

def _run_subprocess(cmd: str, timeout: Optional[int] = None) -> bool:
    """
    Run shell command blocking. Returns True on success.
    """
    try:
        proc = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
        if proc.returncode == 0:
            return True
        # سجل الخطأ للتشخيص
        try:
            _log(f"Subprocess failed ({cmd}) rc={proc.returncode} stderr={proc.stderr.decode('utf-8', 'ignore')}")
        except Exception:
            print("Subprocess failed:", proc.returncode)
            print(proc.stderr.decode('utf-8', 'ignore'))
        return False
    except subprocess.TimeoutExpired:
        try:
            _log(f"Subprocess timeout: {cmd}")
        except Exception:
            print("Subprocess timeout:", cmd)
        return False
    except Exception as e:
        try:
            _log(f"Subprocess exception: {e}")
        except Exception:
            print("Subprocess exception:", e)
        return False

def _ffmpeg_convert_to_mp4(source: str, dest: str) -> bool:
    """
    Attempt stream copy first (fast). If fails, fallback to fast recode.
    Ensures audio is stereo and 48kHz.
    """
    # Attempt: copy video stream, re-encode audio to aac stereo (fast)
    cmd_copy_audio = (
        f'ffmpeg -y -hide_banner -loglevel error -i {shlex.quote(source)} '
        f'-c:v copy -c:a aac -b:a 128k -ac 2 -ar 48000 {shlex.quote(dest)}'
    )
    if _run_subprocess(cmd_copy_audio, timeout=FFMPEG_CONVERT_TIMEOUT):
        return True

    # Fallback: re-encode video (slower but reliable)
    cmd_recode = (
        f'ffmpeg -y -hide_banner -loglevel error -i {shlex.quote(source)} '
        f'-c:v libx264 -preset veryfast -c:a aac -b:a 128k -ac 2 -ar 48000 {shlex.quote(dest)}'
    )
    return _run_subprocess(cmd_recode, timeout=FFMPEG_CONVERT_TIMEOUT)

def _download_via_requests(url: str, dest: str, chunk_size: int = 4 << 20) -> bool:
    """
    تنزيل مباشر بوساطة requests (يُشغّل في executor).
    نستخدم chunk_size أكبر لتحسين السرعة (4 MiB).
    """
    try:
        import requests
        with requests.get(url, stream=True, timeout=(10, 600)) as r:
            r.raise_for_status()
            with open(dest, "wb") as fh:
                for chunk in r.iter_content(chunk_size=chunk_size):
                    if chunk:
                        fh.write(chunk)
        return os.path.exists(dest)
    except Exception as e:
        _log(f"requests download failed: {e}")
        return False

def _yt_dlp_download_blocking(url: str, prefer_mp4: bool = True, video: bool = True) -> Optional[str]:
    """
    Blocking yt-dlp call executed in executor.
    Enhanced options for speed: increase concurrent_fragment_downloads and http_chunk_size.
    """
    ydl_opts = {
        "outtmpl": os.path.join(DOWNLOAD_DIR, "%(id)s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "continuedl": True,
        "overwrites": False,
        "retries": 3,
        "fragment_retries": 3,
        "concurrent_fragment_downloads": 16,  # زيادة للحصول على سرعة أعلى من الحزم
        "http_chunk_size": 4 << 20,  # 4 MiB chunk
        "socket_timeout": 30,
        "cachedir": str(os.path.join(os.getcwd(), "cache")),
        "merge_output_format": "mp4",
    }
    # cookie support if available
    try:
        from AnnieXMedia.utils.cookie_handler import COOKIE_PATH as _COOKIES_FILE
        if _COOKIES_FILE and os.path.exists(_COOKIES_FILE):
            ydl_opts["cookiefile"] = _COOKIES_FILE
    except Exception:
        pass

    if prefer_mp4:
        if video:
            ydl_opts["format"] = "bestvideo[ext=mp4]+bestaudio/best[ext=m4a]/best"
        else:
            ydl_opts["format"] = "bestaudio[ext=m4a]/bestaudio/best"
    else:
        ydl_opts["format"] = "best"

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            # determine resulting file
            if isinstance(info, dict):
                vid = info.get("id")
                ext = info.get("ext")
                if vid and ext:
                    path = os.path.join(DOWNLOAD_DIR, f"{vid}.{ext}")
                    if os.path.exists(path):
                        return path
                # fallback search
                if vid:
                    for ext in ("mp4", "mkv", "webm", "m4a", "mp3"):
                        p = os.path.join(DOWNLOAD_DIR, f"{vid}.{ext}")
                        if os.path.exists(p):
                            return p
    except Exception as e:
        _log(f"yt-dlp exception for {url}: {e}")
    return None

async def prepare_media(path: str, video: bool = False, prefer_mp4: bool = True) -> Optional[str]:
    """
    Ensure path is local file ready for PyTgCalls.
    If URL: try yt-dlp download (fast). If yt-dlp returns m3u8, convert via ffmpeg.
    """
    # if local exists
    try:
        if os.path.exists(path) and os.path.isfile(path):
            return path
    except Exception:
        pass

    if not _is_url(path):
        return None

    loop = asyncio.get_running_loop()
    # 1) try download with yt-dlp (fast, fragments)
    try:
        result = await loop.run_in_executor(None, _yt_dlp_download_blocking, path, prefer_mp4, video)
        if result:
            return result
    except Exception as e:
        _log(f"prepare_media yt-dlp exception: {e}")

    # 2) get direct url from yt-dlp (no download) to detect m3u8 or direct file
    try:
        ydl_opts = {"quiet": True, "no_warnings": True, "noplaylist": True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(path, download=False)
            url = None
            if isinstance(info, dict):
                url = info.get("url")
                if not url and info.get("entries"):
                    entry = info["entries"][0] if info["entries"] else {}
                    if isinstance(entry, dict):
                        url = entry.get("url")
    except Exception:
        url = None

    if url:
        # if m3u8 -> ffmpeg convert (in executor)
        if _is_m3u8(url):
            out = _safe_tmpfile(".mp4")
            ok = await asyncio.get_running_loop().run_in_executor(None, _ffmpeg_convert_to_mp4, url, out)
            if ok:
                return out
        # if direct file extension is recognizable -> download via requests
        ext_guess = url.split("?")[0].split(".")[-1].lower()
        if ext_guess in ("mp4", "mkv", "webm", "m4a", "mp3"):
            out = _safe_tmpfile("." + ext_guess)
            ok = await asyncio.get_running_loop().run_in_executor(None, _download_via_requests, url, out)
            if ok:
                # if video required and not mp4 -> convert (executor)
                if video and ext_guess != "mp4":
                    dest = out + ".mp4"
                    ok2 = await asyncio.get_running_loop().run_in_executor(None, _ffmpeg_convert_to_mp4, out, dest)
                    if ok2:
                        try:
                            os.remove(out)
                        except Exception:
                            pass
                        return dest
                return out

    # last resort -> return None
    return None

# -------------------- dynamic_media_stream و Call (مع تحسينات) --------------------

def dynamic_media_stream(path: str, video: bool = False, ffmpeg_params: Optional[str] = None) -> MediaStream:
    """
    Build ffmpeg params smartly: base + any provided.
    Note: DO NOT include '-re' here.
    """
    base = DEFAULT_FFMPEG_PARAMS
    if ffmpeg_params:
        ff = f"{base} {ffmpeg_params}"
    else:
        ff = base

    if video:
        return MediaStream(
            media_path=path,
            audio_parameters=AudioQuality.HIGH,
            video_parameters=VideoQuality.HD_720p,
            audio_flags=MediaStream.Flags.REQUIRED,
            video_flags=MediaStream.Flags.REQUIRED,
            ffmpeg_parameters=ff,
        )
    else:
        return MediaStream(
            media_path=path,
            audio_parameters=AudioQuality.HIGH,
            audio_flags=MediaStream.Flags.REQUIRED,
            video_flags=MediaStream.Flags.IGNORE,
            ffmpeg_parameters=ff,
        )

async def _clear_(chat_id: int) -> None:
    popped = db.pop(chat_id, None)
    if popped:
        await auto_clean(popped)
    db[chat_id] = []
    await remove_active_video_chat(chat_id)
    await remove_active_chat(chat_id)
    await set_loop(chat_id, 0)

class Call:
    def __init__(self):
        self.userbot1 = Client(
            "AnnieXAssis1", config.API_ID, config.API_HASH, session_string=config.STRING1
        ) if config.STRING1 else None
        self.one = PyTgCalls(self.userbot1) if self.userbot1 else None

        self.userbot2 = Client(
            "AnnieXAssis2", config.API_ID, config.API_HASH, session_string=config.STRING2
        ) if config.STRING2 else None
        self.two = PyTgCalls(self.userbot2) if self.userbot2 else None

        self.userbot3 = Client(
            "AnnieXAssis3", config.API_ID, config.API_HASH, session_string=config.STRING3
        ) if config.STRING3 else None
        self.three = PyTgCalls(self.userbot3) if self.userbot3 else None

        self.userbot4 = Client(
            "AnnieXAssis4", config.API_ID, config.API_HASH, session_string=config.STRING4
        ) if config.STRING4 else None
        self.four = PyTgCalls(self.userbot4) if self.userbot4 else None

        self.userbot5 = Client(
            "AnnieXAssis5", config.API_ID, config.API_HASH, session_string=config.STRING5
        ) if config.STRING5 else None
        self.five = PyTgCalls(self.userbot5) if self.userbot5 else None

        self.active_calls: set[int] = set()


    @capture_internal_err
    async def pause_stream(self, chat_id: int) -> None:
        assistant = await group_assistant(self, chat_id)
        await assistant.pause(chat_id)

    @capture_internal_err
    async def resume_stream(self, chat_id: int) -> None:
        assistant = await group_assistant(self, chat_id)
        await assistant.resume(chat_id)

    @capture_internal_err
    async def mute_stream(self, chat_id: int) -> None:
        assistant = await group_assistant(self, chat_id)
        await assistant.mute(chat_id)

    @capture_internal_err
    async def unmute_stream(self, chat_id: int) -> None:
        assistant = await group_assistant(self, chat_id)
        await assistant.unmute(chat_id)

    @capture_internal_err
    async def stop_stream(self, chat_id: int) -> None:
        assistant = await group_assistant(self, chat_id)
        await _clear_(chat_id)
        if chat_id not in self.active_calls:
            return
        try:
            await assistant.leave_call(chat_id)
        except Exception:
            pass
        finally:
            self.active_calls.discard(chat_id)


    @capture_internal_err
    async def force_stop_stream(self, chat_id: int) -> None:
        assistant = await group_assistant(self, chat_id)
        try:
            check = db.get(chat_id)
            if check:
                check.pop(0)
        except (IndexError, KeyError):
            pass
        await remove_active_video_chat(chat_id)
        await remove_active_chat(chat_id)
        await _clear_(chat_id)
        if chat_id not in self.active_calls:
            return
        try:
            await assistant.leave_call(chat_id)
        except Exception:
            pass
        finally:
            self.active_calls.discard(chat_id)


    @capture_internal_err
    async def skip_stream(self, chat_id: int, link: str, video: Union[bool, str] = None, image: Union[bool, str] = None) -> None:
        assistant = await group_assistant(self, chat_id)
        # ensure local media if needed
        local = await prepare_media(link, video=bool(video))
        if not local:
            # fall back to raw link (best effort), but PyTgCalls likely fails for m3u8
            stream = dynamic_media_stream(path=link, video=bool(video))
        else:
            stream = dynamic_media_stream(path=local, video=bool(video))
        await assistant.play(chat_id, stream)

    @capture_internal_err
    async def vc_users(self, chat_id: int) -> list:
        assistant = await group_assistant(self, chat_id)
        participants = await assistant.get_participants(chat_id)
        return [p.user_id for p in participants if not p.is_muted]

    @capture_internal_err
    async def seek_stream(self, chat_id: int, file_path: str, to_seek: str, duration: str, mode: str) -> None:
        assistant = await group_assistant(self, chat_id)
        ffmpeg_params = f"-ss {to_seek} -to {duration}"
        is_video = mode == "video"
        # ensure local if it's a URL
        local = await prepare_media(file_path, video=is_video)
        if not local:
            raise AssistantErr("Unable to prepare media for seek.")
        stream = dynamic_media_stream(path=local, video=is_video, ffmpeg_params=ffmpeg_params)
        await assistant.play(chat_id, stream)

    @capture_internal_err
    async def speedup_stream(self, chat_id: int, file_path: str, speed: float, playing: list) -> None:
        if not isinstance(playing, list) or not playing or not isinstance(playing[0], dict):
            raise AssistantErr("Invalid stream info for speedup.")

        assistant = await group_assistant(self, chat_id)
        base = os.path.basename(file_path)
        chatdir = os.path.join("playback", str(speed))
        os.makedirs(chatdir, exist_ok=True)
        out = os.path.join(chatdir, base)

        if not os.path.exists(out):
            vs = str(2.0 / float(speed))
            cmd = f'ffmpeg -hide_banner -loglevel error -i "{file_path}" -filter:v "setpts={vs}*PTS" -filter:a atempo={speed} -y "{out}"'
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdin=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()

        dur = int(await asyncio.get_event_loop().run_in_executor(None, check_duration, out))
        played, con_seconds = speed_converter(playing[0]["played"], speed)
        duration_min = seconds_to_min(dur)
        is_video = playing[0]["streamtype"] == "video"
        ffmpeg_params = f"-ss {played} -to {duration_min}"
        stream = dynamic_media_stream(path=out, video=is_video, ffmpeg_params=ffmpeg_params)

        if chat_id in db and db[chat_id] and db[chat_id][0].get("file") == file_path:
            await assistant.play(chat_id, stream)
            db[chat_id][0].update({
                "played": con_seconds,
                "dur": duration_min,
                "seconds": dur,
                "speed_path": out,
                "speed": speed,
                "old_dur": db[chat_id][0].get("dur"),
                "old_second": db[chat_id][0].get("seconds"),
            })
        else:
            raise AssistantErr("Stream mismatch during speedup.")


    @capture_internal_err
    async def stream_call(self, link: str) -> None:
        assistant = await group_assistant(self, config.LOGGER_ID)
        # prepare local if needed
        local = await prepare_media(link, video=True)
        try:
            src = local or link
            await assistant.play(config.LOGGER_ID, MediaStream(src))
            await asyncio.sleep(8)
        finally:
            try:
                await assistant.leave_call(config.LOGGER_ID)
            except:
                pass

    @capture_internal_err
    async def join_call(
        self,
        chat_id: int,
        original_chat_id: int,
        link: str,
        video: Union[bool, str] = None,
        image: Union[bool, str] = None,
    ) -> None:
        assistant = await group_assistant(self, chat_id)
        lang = await get_lang(chat_id)
        _ = get_string(lang)

        # prepare local file when possible
        local = await prepare_media(link, video=bool(video))
        src = local or link
        stream = dynamic_media_stream(path=src, video=bool(video))

        # ✅ FIX: Force leave first to prevent Ghost Call issues
        try:
            await assistant.leave_call(chat_id)
            await asyncio.sleep(1)
        except:
            pass
        # ====================================================

        try:
            # attempt play (local or url)
            await assistant.play(chat_id, stream)
        except (NoActiveGroupCall, ChatAdminRequired):
            raise AssistantErr(_["call_8"])
        except NoAudioSourceFound:
            raise AssistantErr(_["call_11"])
        except NoVideoSourceFound:
            # if source is url, try convert to local mp4 then retry
            try:
                if src and src.startswith("http"):
                    converted = await prepare_media(src, video=True, prefer_mp4=True)
                    if converted:
                        stream2 = dynamic_media_stream(path=converted, video=True)
                        await assistant.play(chat_id, stream2)
                        src = converted
                    else:
                        raise AssistantErr(_["call_12"])
                else:
                    raise AssistantErr(_["call_12"])
            except AssistantErr:
                raise
            except Exception:
                raise AssistantErr(_["call_12"])
        except (ConnectionNotFound, TelegramServerError):
            raise AssistantErr(_["call_10"])
        except Exception as e:
            try:
                await asyncio.sleep(1)
                await assistant.play(chat_id, stream)
            except Exception as ex:
                raise AssistantErr(
                    f"ᴜɴᴀʙʟᴇ ᴛᴏ ᴊᴏɪɴ ᴛʜᴇ ɢʀᴏᴜᴘ ᴄᴀʟʟ.\nRᴇᴀsᴏɴ: {ex}"
                ) from ex

        self.active_calls.add(chat_id)
        await add_active_chat(chat_id)
        await music_on(chat_id)
        if video:
            await add_active_video_chat(chat_id)

        if await is_autoend():
            counter[chat_id] = {}
            users = len(await assistant.get_participants(chat_id))
            if users == 1:
                autoend[chat_id] = datetime.now() + timedelta(minutes=1)


    @capture_internal_err
    async def play(self, client, chat_id: int) -> None:
        check = db.get(chat_id)
        popped = None
        loop = await get_loop(chat_id)
        try:
            if loop == 0:
                popped = check.pop(0)
            else:
                loop = loop - 1
                await set_loop(chat_id, loop)
            await auto_clean(popped)
            if not check:
                    await _clear_(chat_id)
                    if chat_id in self.active_calls:
                        try:
                            await client.leave_call(chat_id)
                        except NoActiveGroupCall:
                            pass
                        except Exception:
                            pass
                        finally:
                            self.active_calls.discard(chat_id)
                    return
        except:
            try:
                await _clear_(chat_id)
                return await client.leave_call(chat_id)
            except:
                return
        else:
            queued = check[0]["file"]
            language = await get_lang(chat_id)
            _ = get_string(language)
            title = (check[0]["title"]).title()
            user = check[0]["by"]
            original_chat_id = check[0]["chat_id"]
            streamtype = check[0]["streamtype"]
            videoid = check[0]["vidid"]
            db[chat_id][0]["played"] = 0

            exis = (check[0]).get("old_dur")
            if exis:
                db[chat_id][0]["dur"] = exis
                db[chat_id][0]["seconds"] = check[0]["old_second"]
                db[chat_id][0]["speed_path"] = None
                db[chat_id][0]["speed"] = 1.0

            video = True if str(streamtype) == "video" else False

            if "live_" in queued:
                n, link = await YouTube.video(videoid, True)
                if n == 0:
                    return await app.send_message(original_chat_id, text=_["call_6"])

                # prepare local when possible (for PyTgCalls stability)
                local = await prepare_media(link, video=video)
                src = local or link
                stream = dynamic_media_stream(path=src, video=video)
                try:
                    await client.play(chat_id, stream)
                except Exception:
                    return await app.send_message(original_chat_id, text=_["call_6"])

                img = await get_thumb(videoid)
                button = stream_markup(_, chat_id)
                run = await app.send_photo(
                    chat_id=original_chat_id,
                    photo=img,
                    caption=_["stream_1"].format(
                        f"https://t.me/{app.username}?start=info_{videoid}",
                        title[:23],
                        check[0]["dur"],
                        user,
                    ),
                    reply_markup=InlineKeyboardMarkup(button),
                )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "tg"

            elif "vid_" in queued:
                mystic = await app.send_message(original_chat_id, _["call_7"])
                try:
                    file_path, direct = await YouTube.download(
                        videoid,
                        mystic,
                        videoid=True,
                        video=True if str(streamtype) == "video" else False,
                    )
                except:
                    return await mystic.edit_text(
                        _["call_6"], disable_web_page_preview=True
                    )

                # prepare local if needed (YouTube.download usually returns local file)
                local = await prepare_media(file_path, video=video)
                src = local or file_path
                stream = dynamic_media_stream(path=src, video=video)
                try:
                    await client.play(chat_id, stream)
                except:
                    return await app.send_message(original_chat_id, text=_["call_6"])

                img = await get_thumb(videoid)
                button = stream_markup(_, chat_id)
                await mystic.delete()
                run = await app.send_photo(
                    chat_id=original_chat_id,
                    photo=img,
                    caption=_["stream_1"].format(
                        f"https://t.me/{app.username}?start=info_{videoid}",
                        title[:23],
                        check[0]["dur"],
                        user,
                    ),
                    reply_markup=InlineKeyboardMarkup(button),
                )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "stream"

            elif "index_" in queued:
                # index_ قد يحمل رابط مباشر - نحضر الـ media أولاً
                local = await prepare_media(videoid, video=video)
                src = local or videoid
                stream = dynamic_media_stream(path=src, video=video)
                try:
                    await client.play(chat_id, stream)
                except:
                    return await app.send_message(original_chat_id, text=_["call_6"])

                button = stream_markup(_, chat_id)
                run = await app.send_photo(
                    chat_id=original_chat_id,
                    photo=config.STREAM_IMG_URL,
                    caption=_["stream_2"].format(user),
                    reply_markup=InlineKeyboardMarkup(button),
                )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "tg"

            else:
                # queued could be a local file or URL - prepare it
                local = await prepare_media(queued, video=video)
                src = local or queued
                stream = dynamic_media_stream(path=src, video=video)
                try:
                    await client.play(chat_id, stream)
                except NoVideoSourceFound:
                    # try converting again if src was URL
                    if src and src.startswith("http"):
                        converted = await prepare_media(src, video=video, prefer_mp4=True)
                        if converted:
                            stream2 = dynamic_media_stream(path=converted, video=video)
                            try:
                                await client.play(chat_id, stream2)
                                src = converted
                            except Exception:
                                return await app.send_message(original_chat_id, text=_["call_6"])
                        else:
                            return await app.send_message(original_chat_id, text=_["call_6"])
                    else:
                        return await app.send_message(original_chat_id, text=_["call_6"])
                except Exception:
                    return await app.send_message(original_chat_id, text=_["call_6"])

                if videoid == "telegram":
                    button = stream_markup(_, chat_id)
                    run = await app.send_photo(
                        chat_id=original_chat_id,
                        photo=(
                            config.TELEGRAM_AUDIO_URL
                            if str(streamtype) == "audio"
                            else config.TELEGRAM_VIDEO_URL
                        ),
                        caption=_["stream_1"].format(
                            config.SUPPORT_CHAT, title[:23], check[0]["dur"], user
                        ),
                        reply_markup=InlineKeyboardMarkup(button),
                    )
                    db[chat_id][0]["mystic"] = run
                    db[chat_id][0]["markup"] = "tg"

                elif videoid == "soundcloud":
                    button = stream_markup(_, chat_id)
                    run = await app.send_photo(
                        chat_id=original_chat_id,
                        photo=config.SOUNCLOUD_IMG_URL,
                        caption=_["stream_1"].format(
                            config.SUPPORT_CHAT, title[:23], check[0]["dur"], user
                        ),
                        reply_markup=InlineKeyboardMarkup(button),
                    )
                    db[chat_id][0]["mystic"] = run
                    db[chat_id][0]["markup"] = "tg"

                else:
                    img = await get_thumb(videoid)
                    button = stream_markup(_, chat_id)
                    try:
                        run = await app.send_photo(
                            chat_id=original_chat_id,
                            photo=img,
                            caption=_["stream_1"].format(
                                f"https://t.me/{app.username}?start=info_{videoid}",
                                title[:23],
                                check[0]["dur"],
                                user,
                            ),
                            reply_markup=InlineKeyboardMarkup(button),
                        )
                    except FloodWait as e:
                        LOGGER(__name__).warning(f"FloodWait: Sleeping for {e.value}")
                        await asyncio.sleep(e.value)
                        run = await app.send_photo(
                            chat_id=original_chat_id,
                            photo=img,
                            caption=_["stream_1"].format(
                                f"https://t.me/{app.username}?start=info_{videoid}",
                                title[:23],
                                check[0]["dur"],
                                user,
                            ),
                            reply_markup=InlineKeyboardMarkup(button),
                        )
                    db[chat_id][0]["mystic"] = run
                    db[chat_id][0]["markup"] = "stream"


    async def start(self) -> None:
        LOGGER(__name__).info("Starting PyTgCalls Clients...")
        if config.STRING1:
            await self.one.start()
        if config.STRING2:
            await self.two.start()
        if config.STRING3:
            await self.three.start()
        if config.STRING4:
            await self.four.start()
        if config.STRING5:
            await self.five.start()

    @capture_internal_err
    async def ping(self) -> str:
        pings = []
        if config.STRING1:
            pings.append(self.one.ping)
        if config.STRING2:
            pings.append(self.two.ping)
        if config.STRING3:
            pings.append(self.three.ping)
        if config.STRING4:
            pings.append(self.four.ping)
        if config.STRING5:
            pings.append(self.five.ping)
        return str(round(sum(pings) / len(pings), 3)) if pings else "0.0"

    @capture_internal_err
    async def decorators(self) -> None:
        assistants = list(filter(None, [self.one, self.two, self.three, self.four, self.five]))

        CRITICAL = (
            ChatUpdate.Status.KICKED
            | ChatUpdate.Status.LEFT_GROUP
            | ChatUpdate.Status.CLOSED_VOICE_CHAT
        )

        async def unified_update_handler(client, update: Update) -> None:
            if isinstance(update, StreamEnded):
                if update.stream_type == StreamEnded.Type.AUDIO:
                    assistant = await group_assistant(self, update.chat_id)
                    await self.play(assistant, update.chat_id)
            
            elif isinstance(update, ChatUpdate):
                status = update.status
                if (status & ChatUpdate.Status.LEFT_CALL) or (status & CRITICAL):
                    await self.stop_stream(update.chat_id)
                    return

        for assistant in assistants:
            assistant.on_update()(unified_update_handler)


StreamController = Call()
