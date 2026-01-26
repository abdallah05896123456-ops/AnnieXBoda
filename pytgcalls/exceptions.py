# PyTgCalls: Exceptions | Definitions
# تم دمج الأكواد الأصلية مع تعريفات النظام السريع

# --- الكلاس الأساسي المفقود (سبب المشكلة) ---
class PyTgCallsError(Exception):
    """Exception raised by PyTgCalls."""
    pass

class PytgcallsConnectionError(PyTgCallsError):
    """Exception raised when connection fails."""
    pass

class NotConnected(PytgcallsConnectionError):
    """Exception raised when client is not connected."""
    pass

class GroupCallNotFound(PyTgCallsError):
    """Exception raised when the group call is not found."""
    pass

# --- أخطاء الإصدارات (من الكود الأصلي) ---
class TooOldPyrogramVersion(PyTgCallsError):
    def __init__(self, version_needed: str, pyrogram_version: str):
        super().__init__(
            f'Needed pyrogram {version_needed}+, actually installed is {pyrogram_version}',
        )

class TooOldTelethonVersion(PyTgCallsError):
    def __init__(self, version_needed: str, telethon_version: str):
        super().__init__(
            f'Needed telethon {version_needed}+, actually installed is {telethon_version}',
        )

class TooOldHydrogramVersion(PyTgCallsError):
    def __init__(self, version_needed: str, hydrogram_version: str):
        super().__init__(
            f'Needed hydrogram {version_needed}+, actually installed is {hydrogram_version}',
        )

# --- أخطاء الاتصال والمكالمات ---
class NoMTProtoClientSet(PyTgCallsError):
    def __init__(self):
        super().__init__('No MTProto client set')

class NoActiveGroupCall(PyTgCallsError):
    def __init__(self):
        super().__init__('No active group call')

class TimedOutAnswer(PyTgCallsError):
    def __init__(self):
        super().__init__('Timed out waiting for an answer')

class CallDeclined(PyTgCallsError):
    def __init__(self, user_id: int):
        super().__init__(f'Call declined by {user_id}')

class CallBusy(PyTgCallsError):
    def __init__(self, user_id: int):
        super().__init__(f'The user {user_id} is busy')

class CallDiscarded(PyTgCallsError):
    def __init__(self, user_id: int):
        super().__init__(f'Call discarded by {user_id}')

class NotInCallError(PyTgCallsError):
    def __init__(self):
        super().__init__('The userbot is not in a call')

class ClientNotStarted(PyTgCallsError):
    def __init__(self):
        super().__init__('Ensure you have started the process with start() before calling this method')

class PyTgCallsAlreadyRunning(PyTgCallsError):
    def __init__(self):
        super().__init__('PyTgCalls client is already running')

class TooManyCustomApiDecorators(PyTgCallsError):
    def __init__(self):
        super().__init__('Too Many Custom Api Decorators')

class InvalidMTProtoClient(PyTgCallsError):
    def __init__(self):
        super().__init__('Invalid MTProto Client')

class MTProtoClientNotConnected(PyTgCallsError):
    def __init__(self):
        super().__init__('MTProto client not connected')

class UnsupportedMethod(PyTgCallsError):
    def __init__(self):
        super().__init__('Unsupported method for this kind of call')

# --- أخطاء الوسائط (FFmpeg & YtDlp) ---

class FFmpegError(PyTgCallsError):
    """Generic FFmpeg error."""
    pass

class NoVideoSourceFound(FFmpegError):
    def __init__(self, path: str):
        super().__init__(f'No video source found on "{path}"')

class InvalidVideoProportion(FFmpegError):
    def __init__(self, message: str):
        super().__init__(message)

class NoAudioSourceFound(FFmpegError):
    def __init__(self, path: str):
        super().__init__(f'No audio source found on "{path}"')

class ImageSourceFound(FFmpegError):
    def __init__(self, path: str):
        super().__init__(f'Found an image source on "{path}"')

class LiveStreamFound(FFmpegError):
    def __init__(self, path: str):
        super().__init__(f'Found a livestream on "{path}"')

class YtDlpError(PyTgCallsError):
    def __init__(self, message: str):
        super().__init__(message)
