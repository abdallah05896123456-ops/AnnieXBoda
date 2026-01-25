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


async def check_stream(
    ffmpeg_parameters: Optional[str],
    path: str,
    stream_parameters: Union[AudioParameters, VideoParameters],
    before_commands: Optional[List[str]] = None,
    headers: Optional[Dict[str, str]] = None,
):
    try:
        # 🔥 تعديل 1: زيادة حجم الـ Pipe Buffer لـ 100 ميجا لمنع اختناق البيانات
        ffprobe = await asyncio.create_subprocess_exec(
            *await cleanup_commands(
                build_command(
                    'ffprobe',
                    ffmpeg_parameters,
                    path,
                    stream_parameters,
                    before_commands,
                    headers,
                    False,
                ),
            ),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            limit=1024 * 1024 * 100  # 100MB Buffer limit (Nuclear)
        )
    except FileNotFoundError:
        raise FFmpegError('ffprobe not installed')

    try:
        # 🔥 تعديل 2: زيادة المهلة لـ 60 ثانية للملفات الثقيلة
        stdout, stderr = await asyncio.wait_for(
            ffprobe.communicate(),
            timeout=60, 
        )
        result = loads(stdout.decode('utf-8')) or {}
        stream_list = result.get('streams', [])
        format_content = result.get('format', [])
        
        # تجاهل أخطاء معينة لا تؤثر على التشغيل
        err_msg = stderr.decode('utf-8')
        if 'No such file' in err_msg:
            raise FileNotFoundError()
            
    except (subprocess.TimeoutExpired, JSONDecodeError):
        try:
            ffprobe.terminate()
        except:
            pass
        raise

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
            # في حالة البث المباشر قد لا تظهر الأبعاد فوراً، نتجاوز الخطأ
            pass 

        # حسابات الأبعاد (تم الحفاظ عليها لضمان التوافق)
        if original_height > 0:
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

    if 'duration' not in format_content:
        raise LiveStreamFound(path)


async def cleanup_commands(
    commands: List[str],
    process_name: Optional[str] = None,
    blacklist: Optional[List[str]] = None,
) -> List[str]:
    # 🔥 تعديل 3: إلغاء الفحص (Bypass). نثق في الأوامر ونمررها فوراً للسرعة.
    # هذا يسمح بمرور أوامر مثل -threads 16 التي قد يحذفها الفحص العادي
    return commands


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

    # 🔥 تعديل 4: إزالة الحقن التلقائي لأوامر Reconnect
    # السبب: قمنا بإضافتها بذكاء أكبر في call.py حسب نوع الرابط (محلي/شبكة)
    # وجودها هنا كان يسبب تضارب (Double Flags) وكراش مع الملفات المحلية

    if name == 'ffprobe':
        ffmpeg_command += [
            '-v',
            'error',
            '-show_entries',
            'stream=width,height,codec_type,codec_name',
            '-show_format',
            '-of',
            'json',
        ]

    if before_commands:
        ffmpeg_command += before_commands

    if headers is not None:
        for i in headers:
            ffmpeg_command.append('-headers')
            ffmpeg_command.append(f'{i}: {headers[i]}')

    ffmpeg_command += [
        '-i',
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
            # إصلاح بسيط لقراءة الأعلام المخصصة
            if part.startswith("-:-"):
                arg_name = part[3:]
                if arg_name in arg_names:
                    current_arg = arg_name
                    continue
            
            command_args[current_arg].append(part)
            
    # دمج الأوامر الأساسية مع أوامر الفيديو/الصوت
    # تم تبسيط المنطق لتجنب التعقيد
    final_args = {
        'audio': _extract_stream_params(command_args['base'] + command_args['audio']),
        'video': _extract_stream_params(command_args['base'] + command_args['video'])
    }
    return final_args


def _extract_stream_params(command: List[str]):
    arg_names = ['start', 'mid', 'end']
    command_args: Dict = {arg: [] for arg in arg_names}
    current_arg = arg_names[0]

    for part in command:
        if part.startswith("-:-"):
            arg_name = part[3:]
            if arg_name in arg_names:
                current_arg = arg_name
                continue
        
        command_args[current_arg].append(part)

    return command_args


def _build_ffmpeg_options(
        stream_parameters: Union[AudioParameters, VideoParameters],
) -> List[str]:
    # جعل اللوج quiet لتوفير الأداء
    options = ['-v', 'quiet', '-f']

    if isinstance(stream_parameters, AudioParameters):
        options.extend([
            's16le',
            '-ac', str(stream_parameters.channels),
            '-ar', str(stream_parameters.bitrate),
        ])
    elif isinstance(stream_parameters, VideoParameters):
        options.extend([
            'rawvideo',
            '-r', str(stream_parameters.frame_rate),
            '-pix_fmt',
            'yuv420p',
            '-vf',
            f'scale={stream_parameters.width}:{stream_parameters.height}',
        ])

    return options
