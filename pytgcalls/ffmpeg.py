# Authored By Certified Coders © 2026
# Verbatim Edition - Full Code with Race Mode Injections
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

# 🔥 تعديل وضع السباق: إعدام الانتظار
async def check_stream(
    ffmpeg_parameters: Optional[str],
    path: str,
    stream_parameters: Union[AudioParameters, VideoParameters],
    before_commands: Optional[List[str]] = None,
    headers: Optional[Dict[str, str]] = None,
):
    # في المسابقات مش بنفحص الرابط، بنشغله فوراً
    # تم تعطيل ffprobe لضمان تشغيل في 0 ثانية
    if isinstance(stream_parameters, VideoParameters):
        if not stream_parameters.width:
            stream_parameters.width = 1280
            stream_parameters.height = 720
    return 

# 🔥 تعديل وضع السباق: تخطي فحص الأوامر المدعومة
async def cleanup_commands(
    commands: List[str],
    process_name: Optional[str] = None,
    blacklist: Optional[List[str]] = None,
) -> List[str]:
    # إرجاع الأوامر فوراً بدون تشغيل ffmpeg -h وتضييع 0.4 ثانية
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

    # حقن أعلام السرعة النووية في بداية الأمر
    if name == 'ffmpeg':
        ffmpeg_command += [
            '-probesize', '32',
            '-analyzeduration', '0',
            '-fflags', 'nobuffer+fastseek+discardcorrupt',
        ]

    ffmpeg_command += command['start']

    if not os.path.exists(path) \
            and not is_livestream\
            and name == 'ffmpeg':
        ffmpeg_command += [
            '-reconnect', '1',
            '-reconnect_at_eof', '1',
            '-reconnect_streamed', '1',
            '-reconnect_delay_max', '2',
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
            arg_name = part[2:]
            if arg_name in arg_names:
                current_arg = arg_name
            else:
                command_args[current_arg].append(part)
    command_args = {
        command: _extract_stream_params(command_args[command])
        for command in command_args
    }

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
        arg_name = part[3:]
        if arg_name in arg_names:
            current_arg = arg_name
        else:
            command_args[current_arg].append(part)

    return command_args

def _build_ffmpeg_options(
        stream_parameters: Union[AudioParameters, VideoParameters],
) -> List[str]:
    # إجبار مستوى اللوج على quiet لتقليل استهلاك المعالج
    ffmpeg_level = 'quiet'

    options = ['-v', ffmpeg_level, '-f']

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
            '-pix_fmt', 'yuv420p',
            '-vf', f'scale={stream_parameters.width}:{stream_parameters.height}',
        ])

    return options
