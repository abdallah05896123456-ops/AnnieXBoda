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

        # 🔥 NUCLEAR CONFIGURATION 🔥
        commands = [
            'yt-dlp',
            '-g',  # استخراج الرابط فقط
            '-f',
            # طلب أفضل فيديو + أفضل صوت بدون قيود (Server Handles Everything)
            'bestvideo+bestaudio/best', 
            '--force-ipv4', # استقرار أعلى في السيرفرات
            '--no-warnings',
            '--ignore-errors',
        ]

        if add_commands:
            # تمرير الأوامر الإضافية مباشرة
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
                # زيادة المهلة لـ 60 ثانية لاستيعاب دقة 4K/8K
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    60,
                )
            except asyncio.TimeoutError:
                try:
                    proc.terminate()
                except:
                    pass
                raise YtDlpError('yt-dlp process timeout')
            
            # تجاهل الأخطاء البسيطة والتركيز على الخرج
            if not stdout and stderr:
                raise YtDlpError(stderr.decode())
            
            data = stdout.decode().strip().split('\n')
            if data:
                # إرجاع رابط الفيديو ورابط الصوت (لأن الجودات العالية بتفصلهم)
                return data[0], data[1] if len(data) >= 2 else data[0]
            raise YtDlpError('No video URLs found')
        except FileNotFoundError:
            raise YtDlpError('yt-dlp is not installed on your system')
