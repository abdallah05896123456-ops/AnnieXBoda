import asyncio
import logging
from typing import List
from typing import Optional
from typing import Union

from ntgcalls import Frame as RawFrame
from ntgcalls import MediaDescription
from ntgcalls import MediaState
from ntgcalls import NetworkInfo
from ntgcalls import SegmentPartRequest
from ntgcalls import StreamDevice
from ntgcalls import StreamMode
from ntgcalls import StreamType
from pyrogram.errors import FloodWait

from .handlers import HandlersHolder
from .types import CallConfig
from .types import GroupCallConfig
from .types import Update
from .chat_lock import ChatLock
from .exceptions import PyTgCallsError
from .wait_counter_lock import WaitCounterLock

py_logger = logging.getLogger('pytgcalls')

class Scaffold(HandlersHolder):
    _REQUIRED_PYROGRAM_VERSION = '1.2.20'
    _REQUIRED_TELETHON_VERSION = '1.24.0'
    _REQUIRED_HYDROGRAM_VERSION = '0.1.4'

    def __init__(self):
        super().__init__()
        self._app = None
        self._is_running = False
        self._my_id = 0
        self._env_checker = None
        self._cache_user_peer = {}
        self._cache_local_peer = {}
        self._handlers = []
        self._binding = None
        self.loop = asyncio.get_event_loop()
        self._need_unmute = set()
        self._p2p_configs = {}
        self._call_sources = {}
        self._wait_connect = {}
        self._presentations = set()
        self._pending_connections = {}
        
        # استرجاع الأقفال للأمان (ضروري جداً)
        self._chat_lock = ChatLock()
        self._wait_counter_lock = WaitCounterLock()

    async def start(self):
        self._is_running = True
        # انتظار لحظي لضمان استقرار الاتصال بالمكتبة الداخلية (C++)
        await asyncio.sleep(0.05)
        return

    async def play(self, chat_id: Union[int, str], stream=None, config=None):
        chat_id = await self.resolve_chat_id(chat_id)
        
        # قفل المحادثة لمنع تداخل الأوامر (حماية من الكراش)
        await self._chat_lock.wait(chat_id)

        try:
            media_description = stream if stream else MediaDescription()
            if config is None:
                config = GroupCallConfig()

            # محاولة الاتصال
            await self._connect_call(
                chat_id,
                media_description,
                config,
                None
            )
        finally:
            # تحرير القفل فوراً
            self._chat_lock.release(chat_id)

    async def _connect_call(
        self,
        chat_id: int,
        media_description: MediaDescription,
        config: Union[CallConfig, GroupCallConfig],
        payload: Optional[str],
    ):
        try:
            if self._binding:
                await self._binding.connect(
                    chat_id,
                    media_description,
                    config,
                    payload if payload else ""
                )
        except FloodWait as e:
            # التعامل الذكي مع حظر التكرار (FloodWait)
            py_logger.warning(f"FloodWait: Sleeping {e.value}s")
            await asyncio.sleep(e.value)
            # إعادة المحاولة بعد انتهاء الوقت
            await self._connect_call(chat_id, media_description, config, payload)
        except Exception as e:
            py_logger.error(f"Connect Error: {e}")
            raise e

    async def resolve_chat_id(self, chat_id: Union[int, str]):
        if isinstance(chat_id, int):
            return chat_id
        
        # محاولة حل المعرف (Username) إلى ID
        if self._app:
            try:
                if chat_id in self._cache_user_peer:
                    return self._cache_user_peer[chat_id]
                
                peer = await self._app.resolve_peer(chat_id)
                res_id = peer.channel_id if hasattr(peer, 'channel_id') else peer.user_id
                self._cache_user_peer[chat_id] = res_id
                return res_id
            except Exception:
                pass
        
        # لو فشل الحل، نرجعه كرقم (محاولة أخيرة)
        try:
            return int(chat_id)
        except:
            return chat_id

    async def _join_presentation(self, chat_id: Union[int, str], join: bool):
        chat_id = await self.resolve_chat_id(chat_id)
        if self._binding:
            await self._binding.join_presentation(int(chat_id), join)

    async def _clear_call(self, chat_id: int):
        if self._binding:
            await self._binding.stop(chat_id)

    async def _handle_stream_ended(
        self,
        chat_id: int,
        stream_type: StreamType,
        device: StreamDevice,
    ):
        # تشغيل الحدث في الخلفية لسرعة الانتقال للأغنية التالية
        for handler in self._handlers:
            if hasattr(handler, 'on_stream_end'):
                try:
                    asyncio.create_task(handler.on_stream_end(chat_id))
                except Exception as e:
                    py_logger.error(f"Stream End Error: {e}")

    # --- دوال الربط الأساسية (Binding Handlers) ---
    
    def _handle_mtproto(self):
        pass

    async def _init_mtproto(self):
        pass

    async def _update_sources(self, chat_id: Union[int, str]):
        pass

    async def _update_status(self, chat_id: int, state: MediaState):
        for handler in self._handlers:
            if hasattr(handler, 'on_call_status_updated'):
                try:
                    asyncio.create_task(handler.on_call_status_updated(chat_id, state))
                except:
                    pass

    async def _switch_connection(self, chat_id: int):
        pass

    async def _emit_sig_data(self, chat_id: int, data: bytes):
        pass

    async def _request_broadcast_timestamp(self, chat_id: int):
        pass

    async def _request_broadcast_part(self, chat_id: int, part_request: SegmentPartRequest):
        pass

    async def _handle_stream_frame(
        self,
        chat_id: int,
        mode: StreamMode,
        device: StreamDevice,
        frames: List[RawFrame],
    ):
        pass

    async def _handle_connection_changed(
        self,
        chat_id: int,
        net_state: NetworkInfo,
    ):
        pass

    async def _handle_mtproto_updates(self, update: Update):
        pass

    @staticmethod
    def _log_retries(r: int):
        pass

    def _clear_cache(self, chat_id: int):
        if chat_id in self._cache_user_peer:
            del self._cache_user_peer[chat_id]

    def on_update(self, filters=None):
        def decorator(func):
            self.add_handler(func, filters)
            return func
        return decorator
