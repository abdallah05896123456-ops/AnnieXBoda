# Authored By Certified Coders © 2025
"""
Core call controller for AnnieXMedia.
- Ensures remote manifests (m3u8) are converted to local files via the downloader.
- Starts cache cleaner on startup.
- Exposes StreamController = Call() for imports.
"""

import asyncio
import os
from datetime import datetime, timedelta
from typing import Union, Optional

from ntgcalls import TelegramServerError, ConnectionNotFound
from pyrogram import Client
from pyrogram.errors import FloodWait, ChatAdminRequired
from pyrogram.types import InlineKeyboardMarkup
from pytgcalls import PyTgCalls
from pytgcalls.exceptions import NoActiveGroupCall, NoAudioSourceFound, NoVideoSourceFound
from pytgcalls.types import AudioQuality, ChatUpdate, MediaStream, StreamEnded, Update, VideoQuality

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

# Integrations with our downloader/cache
from AnnieXMedia.utils.downloader import yt_dlp_download, init_cache_cleaner, _run_ffmpeg_convert

autoend = {}
counter = {}

def _is_true_flag(val) -> bool:
    if isinstance(val, bool):
        return val
    if val is None:
        return False
    s = str(val).strip().lower()
    return s in ("true", "1", "yes", "y", "t")


def dynamic_media_stream(path: str, video: Union[bool, str] = False, ffmpeg_params: str = None) -> MediaStream:
    is_video = _is_true_flag(video)
    default_ffmpeg = "-re -fflags nobuffer -flags low_delay -probesize 32 -analyzeduration 0 -ac 2"
    ffmpeg_params = ffmpeg_params or default_ffmpeg

    if is_video:
        return MediaStream(
            media_path=path,
            audio_parameters=AudioQuality.HIGH,
            video_parameters=VideoQuality.HD_720p,
            audio_flags=MediaStream.Flags.REQUIRED,
            video_flags=MediaStream.Flags.REQUIRED,
            ffmpeg_parameters=ffmpeg_params,
        )
    else:
        return MediaStream(
            media_path=path,
            audio_parameters=AudioQuality.HIGH,
            audio_flags=MediaStream.Flags.REQUIRED,
            video_flags=MediaStream.Flags.IGNORE,
            ffmpeg_parameters=ffmpeg_params,
        )

async def _clear_(chat_id: int) -> None:
    popped = db.pop(chat_id, None)
    if popped:
        await auto_clean(popped)
    db[chat_id] = []
    await remove_active_video_chat(chat_id)
    await remove_active_chat(chat_id)
    await set_loop(chat_id, 0)

# Ensure local media and guard against returned .m3u8 (extra safety)
async def ensure_local_media(path_or_url: Optional[str], kind: str, title: str = "", attempts: int = 2) -> Optional[str]:
    """
    Convert remote manifests to local files. Ensure final returned path is not a .m3u8.
    kind: "audio" or "video"
    """
    try:
        if not path_or_url:
            return None
        if isinstance(path_or_url, str) and os.path.exists(path_or_url):
            LOGGER.info(f"ensure_local_media: local path provided -> {path_or_url} ({kind})")
            return path_or_url
        if not (isinstance(path_or_url, str) and path_or_url.startswith("http")):
            LOGGER.debug(f"ensure_local_media: non-http input -> returning ({kind})")
            return path_or_url

        # try download/convert
        for i in range(attempts):
            LOGGER.info(f"ensure_local_media: attempt {i+1} -> downloading {kind} from {path_or_url}")
            try:
                local = await yt_dlp_download(path_or_url, kind, title=title or "")
                # safety: if yt_dlp returned a manifest file name (endswith .m3u8), try converting it here
                if local and os.path.exists(local):
                    if str(local).lower().endswith(".m3u8"):
                        # convert manifest file to final named file
                        vid = os.path.basename(local).split(".")[0]
                        # target ext by kind
                        target_ext = "mp4" if kind == "video" else "m4a"
                        out = os.path.join("downloads", f"{vid}_{kind}.{target_ext}")
                        LOGGER.info(f"ensure_local_media: got manifest file from downloader, converting -> {out}")
                        ok = await asyncio.get_event_loop().run_in_executor(None, _run_ffmpeg_convert, local, out)
                        if ok and os.path.exists(out) and os.path.getsize(out) > 0:
                            LOGGER.info(f"ensure_local_media: conversion succeeded -> {out}")
                            return out
                        LOGGER.warning(f"ensure_local_media: conversion failed for manifest {local}")
                        # continue attempts
                    else:
                        LOGGER.info(f"ensure_local_media: success ({kind}) -> {local}")
                        return local
            except Exception as e:
                LOGGER.warning(f"ensure_local_media: yt_dlp_download failed attempt {i+1} ({kind}): {e}")
            await asyncio.sleep(0.5)

        LOGGER.warning(f"ensure_local_media: failed to produce local file for {path_or_url} ({kind})")
        return path_or_url
    except Exception as e:
        LOGGER.exception(f"ensure_local_media fatal: {e}")
        return path_or_url


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

        # ensure local if URL (force video->local if requested)
        kind = "video" if _is_true_flag(video) else "audio"
        play_path = await ensure_local_media(link, kind, title="")
        stream = dynamic_media_stream(path=play_path, video=_is_true_flag(video))
        try:
            await assistant.play(chat_id, stream)
        except NoVideoSourceFound:
            # fallback: try audio-only local
            if play_path != link:
                fallback = await ensure_local_media(link, "audio", title="")
                try:
                    await assistant.play(chat_id, dynamic_media_stream(path=fallback, video=False))
                except Exception:
                    raise
            else:
                raise
        except NoAudioSourceFound:
            # try simpler audio fallback
            raise

    # rest of Call remains unchanged (play/join etc.) — kept from original implementation but using new ensure_local_media above.
    # for brevity, remaining methods are identical to previous implementation and unchanged.
    # (When pasting into your file, keep the full original Call class body as before; ensure start() calls init_cache_cleaner())
    async def vc_users(self, chat_id: int) -> list:
        assistant = await group_assistant(self, chat_id)
        participants = await assistant.get_participants(chat_id)
        return [p.user_id for p in participants if not p.is_muted]

    async def seek_stream(self, chat_id: int, file_path: str, to_seek: str, duration: str, mode: str) -> None:
        assistant = await group_assistant(self, chat_id)
        ffmpeg_params = f"-ss {to_seek} -to {duration}"
        is_video = mode == "video"
        stream = dynamic_media_stream(path=file_path, video=is_video, ffmpeg_params=ffmpeg_params)
        await assistant.play(chat_id, stream)

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
            cmd = f'ffmpeg -i "{file_path}" -filter:v "setpts={vs}*PTS" -filter:a atempo={speed} -y "{out}"'
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
        try:
            await assistant.play(config.LOGGER_ID, MediaStream(link))
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

        desired_kind = "video" if _is_true_flag(video) else "audio"
        play_path = await ensure_local_media(link, desired_kind, title="")

        stream = dynamic_media_stream(path=play_path, video=_is_true_flag(video))

        try:
            await assistant.leave_call(chat_id)
            await asyncio.sleep(1)
        except:
            pass

        try:
            await assistant.play(chat_id, stream)
        except (NoActiveGroupCall, ChatAdminRequired):
            raise AssistantErr(_["call_8"])
        except NoAudioSourceFound:
            if play_path and play_path != link:
                raise AssistantErr(_["call_11"])
            else:
                local_audio = await ensure_local_media(link, "audio", title="")
                if local_audio and os.path.exists(local_audio):
                    try:
                        await assistant.play(chat_id, dynamic_media_stream(path=local_audio, video=False))
                        play_path = local_audio
                    except Exception:
                        raise AssistantErr(_["call_11"])
                else:
                    raise AssistantErr(_["call_11"])
        except NoVideoSourceFound:
            local_audio = await ensure_local_media(link, "audio", title="")
            if local_audio and os.path.exists(local_audio):
                try:
                    await assistant.play(chat_id, dynamic_media_stream(path=local_audio, video=False))
                    play_path = local_audio
                except Exception:
                    raise AssistantErr(_["call_12"])
            else:
                raise AssistantErr(_["call_12"])
        except (ConnectionNotFound, TelegramServerError):
            raise AssistantErr(_["call_10"])
        except Exception as e:
            try:
                 await asyncio.sleep(0.8)
                 if play_path and os.path.exists(play_path):
                     await assistant.play(chat_id, dynamic_media_stream(path=play_path, video=_is_true_flag(video)))
                 else:
                     await assistant.play(chat_id, stream)
            except Exception as exc:
                 raise AssistantErr(
                    f"ᴜɴᴀʙʟᴇ ᴛᴏ ᴊᴏɪɴ ᴛʜᴇ ɢʀᴏᴜᴘ ᴄᴀʟʟ.\nRᴇᴀsᴏɴ: {exc}"
                )

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


    async def start(self) -> None:
        LOGGER.info("Starting PyTgCalls Clients...")
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

        try:
            init_cache_cleaner()
            LOGGER.info("Cache cleaner started.")
        except Exception:
            LOGGER.warning("Could not start cache cleaner.")


    # The rest of play() method and handlers are unchanged and should be kept as original in your file.
    # (When you paste this file, ensure you keep full play() implementation from earlier.)
    # For brevity in this message, remaining unchanged methods are omitted — keep them exactly as in your current file.

# export controller
StreamController = Call()
