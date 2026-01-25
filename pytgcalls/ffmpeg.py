import asyncio
import logging
import os.path
import re
import shlex
import subprocess
from json import JSONDecodeError
from json import loads
from typing import Dict
from typing import List
from typing import Optional
from typing import Union

from ntgcalls import FFmpegError

from .exceptions import ImageSourceFound
from .exceptions import InvalidVideoProportion
from .exceptions import LiveStreamFound
from .exceptions import NoAudioSourceFound
from .exceptions import NoVideoSourceFound
from .types.raw import AudioParameters
from .types.raw import VideoParameters

py_logger = logging.getLogger('pytgcalls')


async def check_stream(
    ffmpeg_parameters: Optional[str],
    path: str,
    stream_parameters: Union[AudioParameters, VideoParameters],
    before_commands: Optional[List[str]] = None,
    headers: Optional[Dict[str, str]] = None,
):
    try:
        # بناء أمر ffprobe مع ضمان تنظيفه من الأوامر التي لا يدعمها
        cmd = await cleanup_commands(
            build_command(
                'ffprobe',
                ffmpeg_parameters,
                path,
                stream_parameters,
                before_commands,
                headers,
                False,
            ),
        )
        ffprobe = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError:
        raise FFmpegError('ffprobe not installed')

    try:
        stdout, stderr = await asyncio.wait_for(
            ffprobe.communicate(),
            timeout=25, # زيادة المهلة لضمان فحص الروابط الثقيلة
        )
        
        # 🔥 TitanOS Fix: منع انهيار البوت إذا كان رد ffprobe غير صالح
        out_raw = stdout.decode('utf-8').strip()
        if not out_raw:
            py_logger.warning(f"ffprobe returned empty for {path}. Using safe defaults.")
            if isinstance(stream_parameters, VideoParameters):
                stream_parameters.width = 1280
                stream_parameters.height = 720
            return

        result = loads(out_raw) or {}
        stream_list = result.get('streams', [])
        format_content = result.get('format', {})
        
        if 'No such file' in stderr.decode('utf-8'):
            raise FileNotFoundError()
            
    except (subprocess.TimeoutExpired, JSONDecodeError):
        try:
            ffprobe.terminate()
        except:
            pass
        # في حالة فشل الفحص، نتجاوز الخطأ لضمان دخول المساعد للمكالمة وعدم خروجه فوراً
        return

    have_video = False
    is_image = True
    have_audio = False
    have_valid_video = False

    original_width, original_height = 0, 0

    for stream in stream_list:
        codec_type = stream.get('codec_type', '')
        codec_name = stream.get('codec_name', '')
        image_codecs = ['png', 'jpeg', 'jpg', 'mjpeg']
        if codec_type == 'video':
            is_image &= codec_name in image_codecs
            have_video = True
            original_width = int(stream.get('width', 0))
            original_height = int(stream.get('height', 0))
            if original_height and original_width:
                have_valid_video = True
        elif codec_type == 'audio':
            have_audio = True

    if isinstance(stream_parameters, VideoParameters):
        if not have_video:
            raise NoVideoSourceFound(path)
        if not have_valid_video:
            # نتجاوز هذا الخطأ لضمان استمرار البث حتى لو لم نجد الأبعاد بدقة
            return

        ratio = float(original_width) / original_height
        new_w = min(original_width, stream_parameters.width)
        new_h = int(new_w / ratio)

        if (
            new_h > stream_parameters.height and
            stream_parameters.adjust_by_height
        ):
            new_h = stream_parameters.height
            new_w = int(new_h * ratio)

        new_w = new_w - 1 if new_w % 2 else new_w
        new_h = new_h - 1 if new_h % 2 else new_h
        stream_parameters.height = new_h
        stream_parameters.width = new_w
        if is_image:
            stream_parameters.frame_rate = 10
            raise ImageSourceFound(path)

    if isinstance(stream_parameters, AudioParameters) and not have_audio:
        raise NoAudioSourceFound(path)

    # التحقق من أن الملف ليس بثاً مباشراً إلا إذا كان رابط HTTP
    if 'duration' not in format_content and not str(path).startswith('http'):
        raise LiveStreamFound(path)


async def cleanup_commands(
    commands: List[str],
    process_name: Optional[str] = None,
    blacklist: Optional[List[str]] = None,
) -> List[str]:
    try:
        proc_res = await asyncio.create_subprocess_exec(
            commands[0] if not process_name else process_name,
            '-h',
            'full',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, _ = await asyncio.wait_for(
                proc_res.communicate(),
                timeout=20,
            )
            result = stdout.decode('utf-8')
        except (subprocess.TimeoutExpired, Exception):
            try: proc_res.terminate()
            except: pass
            return commands # نمرر الأوامر كما هي في حالة الفشل

        supported = re.findall(r'(?m)^ *(-\w+).*?\s+', result)
        supported += ['-i']
        new_commands = []
        ignore_next = False

        for v in commands:
            if len(v) > 0:
                if v[0] == '-':
                    ignore_next = v not in supported or \
                        blacklist is not None and v in blacklist

                if not ignore_next:
                    new_commands += [v]
                elif v[0] != '-':
                    ignore_next = False
        return new_commands
    except FileNotFoundError:
        raise FFmpegError(f'{commands[0]} not installed')


def build_command(
    name: str,
    ffmpeg_parameters: Optional[str],
    path: Optional[str],
    stream_parameters: Union[AudioParameters, VideoParameters],
    before_commands: Optional[List[str]] = None,
    headers: Optional[Dict[str, str]] = None,
    is_livestream: bool = False,
) -> List[str]:
    if not path:
        return []
    command = _get_stream_params(ffmpeg_parameters)

    if isinstance(stream_parameters, VideoParameters):
        command = command['video']
    else:
        command = command['audio']

    ffmpeg_command: List = [name]

    ffmpeg_command += command['start']

    # 🔥 Reconnect Logic: منع التقطيع في روابط يوتيوب والروابط الخارجية
    if not os.path.exists(path) \
            and not is_livestream\
            and name == 'ffmpeg':
        ffmpeg_command += [
            '-reconnect', '1',
            '-reconnect_at_eof', '1',
            '-reconnect_streamed', '1',
            '-reconnect_delay_max', '5', # زيادة مهلة إعادة الاتصال للاستقرار
        ]

    if name == 'ffprobe':
        ffmpeg_command += [
            '-v', 'error',
            '-show_entries', 'stream=width,height,codec_type,codec_name',
            '-show_format',
            '-of', 'json',
        ]

    if before_commands:
        ffmpeg_command += before_commands

    if headers is not None:
        for i in headers:
            ffmpeg_command.append('-headers')
            ffmpeg_command.append(f'{i}: {headers[i]}')

    ffmpeg_command += [
        f'{path}' if name == 'ffmpeg' else path,
    ]
    ffmpeg_command += command['mid']

    if name == 'ffmpeg':
        ffmpeg_command += _build_ffmpeg_options(stream_parameters)

    ffmpeg_command += command['end']
    if name == 'ffmpeg':
        ffmpeg_command.append('pipe:1')

    return ffmpeg_command


def _get_stream_params(command: Optional[str]):
    arg_names = ['base', 'audio', 'video']
    command_args: Dict = {arg: [] for arg in arg_names}
    current_arg = arg_names[0]

    if command:
        for part in shlex.split(command):
            # الكود الأصلي الصحيح الذي يبحث عن العلم بعد الحرفين الأولين (--)
            if part.startswith('--'):
                arg_name = part[2:]
                if arg_name in arg_names:
                    current_arg = arg_name
                    continue
            command_args[current_arg].append(part)

    command_args = {
        command: _extract_stream_params(command_args[command])
        for command in command_args
    }

    # دمج الأوامر الأساسية (Base) مع إعدادات الصوت والفيديو
    for arg in arg_names[1:]:
        for x in command_args[arg_names[0]]:
            command_args[arg][x] += command_args[arg_names[0]][x]

    del command_args[arg_names[0]]

    return command_args


def _extract_stream_params(command: List[str]):
    arg_names = ['start', 'mid', 'end']
    command_args: Dict = {arg: [] for arg in arg_names}
    current_arg = arg_names[0]

    for part in command:
        if part.startswith('-:-'):
            arg_name = part[3:]
            if arg_name in arg_names:
                current_arg = arg_name
                continue
        command_args[current_arg].append(part)

    return command_args


def _build_ffmpeg_options(
        stream_parameters: Union[AudioParameters, VideoParameters],
) -> List[str]:
    # جعل اللوج صامت لتوفير الأداء (أو info للتدقيق)
    options = ['-v', 'quiet', '-f']

    # 🔥 TitanOS Injection: إجبار الستيريو واستغلال الـ 16 كور
    # threads 16: لاستغلال كامل قدرة المعالج
    # ac 2: لضمان صوت Stereo في جميع الظروف
    options.extend(['-threads', '16'])

    if isinstance(stream_parameters, AudioParameters):
        options.extend([
            's16le',
            '-ac', '2', # Force Stereo
            '-ar', str(stream_parameters.bitrate),
        ])
    elif isinstance(stream_parameters, VideoParameters):
        options.extend([
            'rawvideo',
            '-r', str(stream_parameters.frame_rate),
            '-pix_fmt', 'yuv420p',
            '-vf', f'scale={stream_parameters.width}:{stream_parameters.height}',
        ])

    return options
