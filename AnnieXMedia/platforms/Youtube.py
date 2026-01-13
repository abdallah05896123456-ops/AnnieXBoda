import asyncio
import uvloop
from pyrogram.types import Message
from pyrogram.enums import MessageEntityType
import yt_dlp
import ffmpeg
from youtubesearchpython import VideosSearch, PlaylistsSearch, Playlist, ResultMode
import re
import json
import os
import time
import functools
from typing import Any, Dict, List, Optional, Tuple
from AnnieXMedia.utils.cookie_handler import COOKIE_PATH
from AnnieXMedia.utils.database import is_on_off
from AnnieXMedia.utils.downloader import yt_dlp_download
from AnnieXMedia.utils.errors import capture_internal_err
from AnnieXMedia.utils.formatters import time_to_seconds
from AnnieXMedia.utils.tuning import YTDLP_TIMEOUT, YOUTUBE_META_MAX, YOUTUBE_META_TTL

uvloop.install()

class YouTubeAPI:
    """
    YouTubeAPI provides methods to interact with YouTube content for the Telegram bot.
    It handles searching, fetching details, playlist management, format retrieval, and downloading media.
    """
    _cache: Dict[str, Any] = {}
    _cache_time: Dict[str, float] = {}
    _formats_cache: Dict[str, Any] = {}
    _formats_time: Dict[str, float] = {}
    _cache_lock: asyncio.Lock = asyncio.Lock()
    _formats_lock: asyncio.Lock = asyncio.Lock()

    def __init__(self) -> None:
        """
        Initialize the YouTubeAPI instance with caches and locks.
        """
        print("[YouTubeAPI] Initializing YouTubeAPI instance.")
        # Initialize caches and locks
        # (Locks are already defined at class level)
        pass

    async def _run_sync(self, func: Any) -> Any:
        """
        Run a synchronous function in an executor to prevent blocking.
        """
        print(f"[YouTubeAPI] Running synchronous function in executor: {func}")
        loop = asyncio.get_running_loop()
        try:
            result = await loop.run_in_executor(None, func)
            print(f"[YouTubeAPI] Synchronous function executed successfully.")
            return result
        except Exception as e:
            print(f"[YouTubeAPI] Error running synchronous function: {e}")
            capture_internal_err(e)
            return None

    async def _exec_proc(self, ytdl_args: List[str]) -> Optional[str]:
        """
        Execute yt-dlp as a subprocess with specified arguments and return output.
        Uses turbo mode flags and handles timeouts strictly.
        """
        print(f"[YouTubeAPI] Executing yt-dlp with args: {ytdl_args}")
        try:
            process = await asyncio.create_subprocess_exec(
                "yt-dlp",
                *ytdl_args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=YTDLP_TIMEOUT)
            except asyncio.TimeoutError:
                print("[YouTubeAPI] yt-dlp process timed out. Killing process.")
                process.kill()
                await process.communicate()
                return None
            if process.returncode != 0:
                error_msg = stderr.decode(errors='ignore')
                print(f"[YouTubeAPI] yt-dlp returned error code {process.returncode}: {error_msg}")
                return None
            output = stdout.decode(errors='ignore')
            print("[YouTubeAPI] yt-dlp process completed successfully.")
            return output
        except Exception as e:
            print(f"[YouTubeAPI] Exception in _exec_proc: {e}")
            capture_internal_err(e)
            return None

    def _clean_link(self, link: Optional[str] = None, videoid: Optional[str] = None) -> Optional[str]:
        """
        Clean and normalize YouTube links from various formats (shorts, live, standard).
        Returns a standard YouTube watch URL or None if invalid.
        """
        print(f"[YouTubeAPI] Cleaning link. Input link: {link}, videoid: {videoid}")
        if videoid:
            url = f"https://www.youtube.com/watch?v={videoid}"
            print(f"[YouTubeAPI] Using video ID to construct URL: {url}")
            return url
        if not link:
            print("[YouTubeAPI] No link provided.")
            return None
        link = link.strip()
        # youtu.be short link
        if "youtu.be/" in link:
            vid = link.split("youtu.be/")[1].split('?')[0]
            url = f"https://www.youtube.com/watch?v={vid}"
            print(f"[YouTubeAPI] Shortened youtu.be URL converted to standard: {url}")
            return url
        # YouTube shorts
        if "youtube.com/shorts/" in link:
            vid = link.split("/shorts/")[1].split('?')[0]
            url = f"https://www.youtube.com/watch?v={vid}"
            print(f"[YouTubeAPI] Shorts URL converted to standard: {url}")
            return url
        # YouTube live
        if "youtube.com/live/" in link:
            vid = link.split("/live/")[1].split('?')[0]
            url = f"https://www.youtube.com/watch?v={vid}"
            print(f"[YouTubeAPI] Live URL converted to standard: {url}")
            return url
        # Standard watch URL
        match = re.search(r"v=([A-Za-z0-9_-]{11})", link)
        if match:
            vid = match.group(1)
            url = f"https://www.youtube.com/watch?v={vid}"
            print(f"[YouTubeAPI] Watch URL with v= parameter cleaned: {url}")
            return url
        # If link contains '/embed/' or '/v/' patterns
        match = re.search(r"(?:embed/|v/)([A-Za-z0-9_-]{11})", link)
        if match:
            vid = match.group(1)
            url = f"https://www.youtube.com/watch?v={vid}"
            print(f"[YouTubeAPI] Embedded or /v/ URL converted to standard: {url}")
            return url
        print("[YouTubeAPI] Link format not recognized.")
        return None

    async def exists(self, link: Optional[str] = None, videoid: Optional[str] = None) -> bool:
        """
        Check if a YouTube video exists by trying to fetch details.
        Returns True if exists, False otherwise.
        """
        url = self._clean_link(link, videoid)
        print(f"[YouTubeAPI] Checking existence of video. URL: {url}")
        if not url:
            print("[YouTubeAPI] No valid URL for existence check.")
            return False
        try:
            # Try to fetch video details to verify existence
            title, _, _, _, _ = await self.details(url, None)
            exists = title is not None
            print(f"[YouTubeAPI] Video exists: {exists}")
            return exists
        except Exception as e:
            print(f"[YouTubeAPI] Error checking existence: {e}")
            capture_internal_err(e)
            return False

    def url(self, message: Message) -> Optional[str]:
        """
        Extract a YouTube URL from a Pyrogram Message text or entities.
        Returns the first found YouTube URL or None.
        """
        print("[YouTubeAPI] Extracting URL from message.")
        text = message.text or message.caption or ""
        entities = message.entities or message.caption_entities or []
        # Check entities first
        for ent in entities:
            if ent.type == MessageEntityType.URL:
                offset = ent.offset
                length = ent.length
                url = text[offset:offset+length]
                print(f"[YouTubeAPI] Found URL entity: {url}")
                if "youtube.com" in url or "youtu.be" in url:
                    return url
            if ent.type == MessageEntityType.TEXT_LINK:
                url = ent.url
                print(f"[YouTubeAPI] Found text link entity: {url}")
                if "youtube.com" in url or "youtu.be" in url:
                    return url
        # Fallback to regex search in text
        match = re.search(r'(https?://[\w./?=&-]+)', text)
        if match:
            url = match.group(1)
            print(f"[YouTubeAPI] Found URL via regex in text: {url}")
            if "youtube.com" in url or "youtu.be" in url:
                return url
        print("[YouTubeAPI] No YouTube URL found in message.")
        return None

    async def details(self, link: Optional[str] = None, videoid: Optional[str] = None) -> Tuple[Optional[str], Optional[str], Optional[int], Optional[str], Optional[str]]:
        """
        Fetch video details (title, duration_str, duration_sec, thumbnail, video_id) using yt-dlp.
        Results are cached for performance.
        """
        url = self._clean_link(link, videoid)
        print(f"[YouTubeAPI] Fetching details for URL: {url}")
        if not url:
            print("[YouTubeAPI] Invalid URL for details.")
            return (None, None, None, None, None)
        key = f"details:{url}"
        # Check cache
        async with self._cache_lock:
            # Evict expired entries
            if key in self._cache_time and time.time() - self._cache_time[key] > YOUTUBE_META_TTL:
                print(f"[YouTubeAPI] Cache expired for key: {key}")
                self._cache.pop(key, None)
                self._cache_time.pop(key, None)
            if key in self._cache:
                print(f"[YouTubeAPI] Cache hit for details key: {key}")
                title, duration_str, duration_sec, thumbnail, vidid = self._cache[key]
                return (title, duration_str, duration_sec, thumbnail, vidid)
        try:
            # Run yt-dlp to get video info as JSON
            print(f"[YouTubeAPI] Calling yt-dlp for details.")
            proc = await self._exec_proc(["-j", "--no-warnings", "--no-playlist", "--geo-bypass", "--cookies", COOKIE_PATH, url])
            info = json.loads(proc) if proc else {}
            title = info.get("title")
            duration_sec = info.get("duration")
            # Convert duration to string format "H:MM:SS"
            if duration_sec is not None:
                hrs = duration_sec // 3600
                mins = (duration_sec % 3600) // 60
                secs = duration_sec % 60
                if hrs > 0:
                    duration_str = f"{hrs}:{mins:02d}:{secs:02d}"
                else:
                    duration_str = f"{mins}:{secs:02d}"
            else:
                duration_str = None
            thumbnail = info.get("thumbnail")
            vidid = info.get("id")
            # Cache the details
            async with self._cache_lock:
                self._cache[key] = (title, duration_str, duration_sec, thumbnail, vidid)
                self._cache_time[key] = time.time()
                print(f"[YouTubeAPI] Details cached with key: {key}")
            return (title, duration_str, duration_sec, thumbnail, vidid)
        except Exception as e:
            print(f"[YouTubeAPI] Error fetching details: {e}")
            capture_internal_err(e)
            return (None, None, None, None, None)

    async def title(self, link: Optional[str] = None, videoid: Optional[str] = None) -> Optional[str]:
        """
        Get the title of a YouTube video, using cache if available.
        """
        print(f"[YouTubeAPI] Getting title for link: {link} videoid: {videoid}")
        details = await self.details(link, videoid)
        title = details[0]
        print(f"[YouTubeAPI] Title obtained: {title}")
        return title

    async def duration(self, link: Optional[str] = None, videoid: Optional[str] = None) -> Optional[int]:
        """
        Get the duration in seconds of a YouTube video, using cache if available.
        """
        print(f"[YouTubeAPI] Getting duration for link: {link} videoid: {videoid}")
        details = await self.details(link, videoid)
        duration_sec = details[2]
        print(f"[YouTubeAPI] Duration (seconds) obtained: {duration_sec}")
        return duration_sec

    async def thumbnail(self, link: Optional[str] = None, videoid: Optional[str] = None) -> Optional[str]:
        """
        Get the thumbnail URL of a YouTube video, using cache if available.
        """
        print(f"[YouTubeAPI] Getting thumbnail for link: {link} videoid: {videoid}")
        details = await self.details(link, videoid)
        thumbnail = details[3]
        print(f"[YouTubeAPI] Thumbnail obtained: {thumbnail}")
        return thumbnail

    async def track(self, link: Optional[str] = None, videoid: Optional[str] = None) -> Dict[str, Any]:
        """
        Return full track information (title, link, vidid, duration_min, thumb) for a video.
        """
        print(f"[YouTubeAPI] Fetching track information for link: {link} videoid: {videoid}")
        url = self._clean_link(link, videoid)
        if not url:
            print("[YouTubeAPI] Invalid URL for track.")
            return {}
        title, duration_str, duration_sec, thumbnail, vidid = await self.details(url, videoid)
        track_info: Dict[str, Any] = {
            "title": title,
            "link": url,
            "vidid": vidid,
            "duration_min": duration_str,
            "thumb": thumbnail
        }
        print(f"[YouTubeAPI] Track info obtained: {track_info}")
        return track_info

    async def video(self, link: Optional[str] = None, videoid: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """
        Check if the given video link is live and return (status, direct_link).
        Status is True if live, False otherwise. direct_link is the direct media link if live.
        """
        print(f"[YouTubeAPI] Checking if video is live for link: {link} videoid: {videoid}")
        url = self._clean_link(link, videoid)
        if not url:
            print("[YouTubeAPI] Invalid URL for video live check.")
            return False, None
        try:
            # Get video info
            print("[YouTubeAPI] Fetching video info to check live status.")
            info_json = await self._exec_proc(["-j", "--no-warnings", "--no-playlist", "--geo-bypass", "--cookies", COOKIE_PATH, url])
            info = json.loads(info_json) if info_json else {}
            is_live = info.get("is_live") or info.get("live_status") == "is_live" or False
            if is_live:
                print("[YouTubeAPI] Video is live. Fetching direct stream link.")
                # Get direct link (no download) for live stream
                direct_link = await self._exec_proc(["-g", "--no-warnings", "--no-playlist", "--geo-bypass", "--cookies", COOKIE_PATH, url])
                if direct_link:
                    direct_link = direct_link.strip()
                print(f"[YouTubeAPI] Direct live link obtained: {direct_link}")
                return True, direct_link
            else:
                print("[YouTubeAPI] Video is not live.")
                return False, None
        except Exception as e:
            print(f"[YouTubeAPI] Error checking live video: {e}")
            capture_internal_err(e)
            return False, None

    async def playlist(self, link: str, limit: Optional[int] = None) -> List[str]:
        """
        Fetch video IDs from a YouTube playlist link up to the given limit.
        """
        print(f"[YouTubeAPI] Fetching playlist videos for link: {link} with limit: {limit}")
        url = self._clean_link(link, None)
        if not url and "playlist?list=" in link:
            url = link  # If link is a playlist link, skip cleaning
        if not url:
            print("[YouTubeAPI] Invalid URL for playlist.")
            return []
        try:
            print("[YouTubeAPI] Using youtube-search-python Playlist.get to fetch playlist details.")
            playlist_data = await self._run_sync(lambda: Playlist.get(link, mode=ResultMode.json))
            video_ids: List[str] = []
            if playlist_data and "videos" in playlist_data:
                for video in playlist_data["videos"]:
                    vid = video.get("id")
                    if vid:
                        video_ids.append(vid)
                        if limit and len(video_ids) >= limit:
                            break
            print(f"[YouTubeAPI] Playlist video IDs obtained: {video_ids}")
            return video_ids
        except Exception as e:
            print(f"[YouTubeAPI] Error fetching playlist: {e}")
            capture_internal_err(e)
            return []

    async def formats(self, link: Optional[str] = None, videoid: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Retrieve available non-dash formats for a video for quality selection.
        Returns a list of format info dicts with keys: format, filesize, format_id, ext, format_note.
        """
        print(f"[YouTubeAPI] Fetching formats for link: {link} videoid: {videoid}")
        url = self._clean_link(link, videoid)
        if not url:
            print("[YouTubeAPI] Invalid URL for formats.")
            return []
        key = f"formats:{url}"
        # Check cache
        async with self._formats_lock:
            # Evict expired entries
            if key in self._formats_time and time.time() - self._formats_time[key] > YOUTUBE_META_TTL:
                print(f"[YouTubeAPI] Formats cache expired for key: {key}")
                self._formats_cache.pop(key, None)
                self._formats_time.pop(key, None)
            if key in self._formats_cache:
                print(f"[YouTubeAPI] Cache hit for formats key: {key}")
                return self._formats_cache[key]
        try:
            print("[YouTubeAPI] Running yt-dlp to get format list.")
            proc = await self._exec_proc(["-j", "--no-warnings", "--no-playlist", "--geo-bypass", "--cookies", COOKIE_PATH, url])
            info = json.loads(proc) if proc else {}
            formats_list: List[Dict[str, Any]] = []
            for fmt in info.get("formats", []):
                # Only include formats with both audio and video (non-dash)
                if fmt.get("acodec") == "none" or fmt.get("vcodec") == "none":
                    continue
                fmt_info = {
                    "format": fmt.get("format"),
                    "filesize": fmt.get("filesize") or fmt.get("filesize_approx"),
                    "format_id": fmt.get("format_id"),
                    "ext": fmt.get("ext"),
                    "format_note": fmt.get("format_note")
                }
                formats_list.append(fmt_info)
            # Cache formats
            async with self._formats_lock:
                self._formats_cache[key] = formats_list
                self._formats_time[key] = time.time()
                print(f"[YouTubeAPI] Formats cached with key: {key}")
            return formats_list
        except Exception as e:
            print(f"[YouTubeAPI] Error fetching formats: {e}")
            capture_internal_err(e)
            return []

    async def slider(self, link: str, query_type: str) -> List[str]:
        """
        Fetch search results or playlist video IDs for pagination (slider).
        query_type indicates whether to use video search or playlist.
        """
        print(f"[YouTubeAPI] Slider called with link: {link} query_type: {query_type}")
        try:
            if query_type == "playlist":
                print("[YouTubeAPI] Slider returning playlist IDs.")
                return await self.playlist(link, None)
            # Default: treat as video search query
            print("[YouTubeAPI] Performing video search for slider.")
            vs = VideosSearch(link, limit=YOUTUBE_META_MAX)
            result = await self._run_sync(vs.result)
            video_ids: List[str] = []
            if result and "result" in result:
                for item in result["result"]:
                    vid = item.get("id")
                    if vid:
                        video_ids.append(vid)
            print(f"[YouTubeAPI] Slider video IDs obtained: {video_ids}")
            return video_ids
        except Exception as e:
            print(f"[YouTubeAPI] Error in slider: {e}")
            capture_internal_err(e)
            return []

    async def download(self, link: Optional[str], mystic: Any, video: bool = False, videoid: Optional[str] = None) -> Tuple[Optional[str], bool]:
        """
        Download or get direct link to a YouTube video/audio.
        For video (video=True):
            If live: return direct link.
            If not live:
                If is_on_off(1) (maintenance mode on): download locally.
                Else: return direct link via yt-dlp -g.
        For audio (video=False): always download locally.
        Returns (path_or_link, is_direct_bool).
        """
        print(f"[YouTubeAPI] Starting download. Link: {link}, video: {video}, videoid: {videoid}")
        url = self._clean_link(link, videoid)
        if not url:
            print("[YouTubeAPI] Invalid URL for download.")
            return None, False
        try:
            # Check if live stream
            is_live, direct_link = await self.video(url, None)
            if video:
                if is_live:
                    print("[YouTubeAPI] Video is live, returning direct link.")
                    return direct_link, True
                # Not live
                if is_on_off(1):
                    print("[YouTubeAPI] Maintenance mode on. Downloading video locally.")
                    path = await yt_dlp_download(mystic, url, video=True)
                    print(f"[YouTubeAPI] Video downloaded to: {path}")
                    return path, False
                else:
                    print("[YouTubeAPI] Maintenance mode off. Returning direct video link.")
                    direct_link = await self._exec_proc(["-g", "--no-warnings", "--no-playlist", "--geo-bypass", "--cookies", COOKIE_PATH, url])
                    direct_link = direct_link.strip() if direct_link else None
                    print(f"[YouTubeAPI] Direct video link: {direct_link}")
                    return direct_link, True
            else:
                # Audio case: always download
                print("[YouTubeAPI] Downloading audio locally.")
                path = await yt_dlp_download(mystic, url, video=False)
                print(f"[YouTubeAPI] Audio downloaded to: {path}")
                return path, False
        except Exception as e:
            print(f"[YouTubeAPI] Error in download: {e}")
            capture_internal_err(e)
            return None, False
