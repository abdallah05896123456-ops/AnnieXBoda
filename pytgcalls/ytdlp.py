# Authored By Certified Coders © 2026
# RACE MODE: Android/iOS Spoofing + No-Check Flags + IPv4 Force

import asyncio
import logging
import re
import shlex
from typing import Optional
from typing import Tuple

from .exceptions import YtDlpError
from .ffmpeg import cleanup_commands
from .list_to_cmd import list_to_cmd
from .types.raw import VideoParameters

py_logger = logging.getLogger('pytgcalls')


class YtDlp:
    YOUTUBE_REGX = re.compile(
        r'^((?:https?:)?//)?((?:www|m)\.)?'
        r'(youtube(-nocookie)?\.com|youtu.be)'
        r'(/(?:[\w\-]+\?v=|embed/|live/|v/)?)'
        r'([\w\-]+)(\S+)?$',
    )

    @staticmethod
    def is_valid(link: str) -> bool:
        return bool(YtDlp.YOUTUBE_REGX.match(link))

    @staticmethod
    async def extract(
        link: Optional[str],
        video_parameters: VideoParameters,
        add_commands: Optional[str],
    ) -> Tuple[Optional[str], Optional[str]]:
        if link is None:
            return None, None

        # 🔥 RACE MODE: NUCLEAR CONFIGURATION (16-Core Optimized) 🔥
        commands = [
            'yt-dlp',
            '-g',
            # استخدام أندرويد و iOS لأن استجابتهم أسرع (JSON أصغر)
            '--extractor-args', 'youtube:player_client=android,ios,web',
            
            # تحديد الصيغ (صوت فقط للسرعة، أو فيديو خفيف)
            '--format', 'bestaudio/best',
            
            # --- تحسينات الشبكة (Network Boost) ---
            '--force-ipv4',               # يمنع تأخير DNS في IPv6
            '--no-check-certificate',     # تجاوز SSL Handshake
            '--socket-timeout', '10',     # لو السيرفر ماردش في 10 ثواني اقطع
            
            # --- تخطي الفحوصات (Skip Checks) ---
            '--no-playlist',              
            '--no-check-formats',         # سرعة صاروخية (يأخذ أول صيغة تقابله)
            '--no-remote-subtitles',      # توفير HTTP Request
            '--no-write-subs',
            '--no-warnings',
            '--ignore-errors',
            '--no-call-home',             # منع التحديثات
            '--no-cache-dir',             # عدم القراءة/الكتابة على الهارد
        ]

        if add_commands:
            commands += shlex.split(add_commands)

        commands.append(link)

        py_logger.log(
            logging.DEBUG,
            f'Running with "{list_to_cmd(commands)}" command',
        )
        try:
            proc = await asyncio.create_subprocess_exec(
                *commands,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                # المهلة الزمنية للسباق (Race Timeout)
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=12, # 12 ثانية كحد أقصى للعملية بالكامل
                )
            except asyncio.TimeoutError:
                try:
                    proc.kill() # Kill أسرع من Terminate في الحالات الحرجة
                except:
                    pass
                raise YtDlpError('yt-dlp process timeout (Race Lost)')
            
            if not stdout and stderr:
                # أحياناً yt-dlp يرمي تحذيرات في stderr بس بيجيب الرابط في stdout
                # هنتأكد الأول إن مفيش داتا رجعت
                if not stdout:
                    raise YtDlpError(stderr.decode())
            
            data = stdout.decode().strip().split('\n')
            if data:
                # العودة بالرابط المباشر
                return data[0], data[1] if len(data) >= 2 else data[0]
            raise YtDlpError('No video URLs found')
        except FileNotFoundError:
            raise YtDlpError('yt-dlp is not installed on your system')
