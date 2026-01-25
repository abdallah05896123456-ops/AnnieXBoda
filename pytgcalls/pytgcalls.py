import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any

# 🔥 محاولة تفعيل UVLoop لسرعة استجابة جنونية على لينكس
try:
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except ImportError:
    pass

from ntgcalls import NTgCalls

from .chat_lock import ChatLock
from .environment import Environment
from .methods import Methods
from .mtproto import MtProtoClient
from .scaffold import Scaffold
from .statictypes import statictypes
from .types import Cache


class PyTgCalls(Methods, Scaffold):
    # 🔥 NUCLEAR WORKERS CONFIGURATION 🔥
    # المعادلة القديمة كانت بتحط سقف 32 عامل، وده قليل على سيرفر 16 كور.
    # الجديد: (عدد الكورات * 4). يعني 16 * 4 = 64 عامل في نفس اللحظة!
    # ده هيخلي معالجة التحديثات (Updates) فورية.
    WORKERS = (os.cpu_count() or 1) * 4
    
    # 🔥 MASSIVE CACHE: 24 Hours 🔥
    # الرام 88 جيجا، مش محتاجين نمسح الكاش كل ساعة.
    # خليته يحفظ بيانات المستخدمين ليوم كامل عشان يقلل طلبات الـ API لتيليجرام.
    CACHE_DURATION = 86400 

    @statictypes
    def __init__(
        self,
        app: Any,
        workers: int = WORKERS,
        cache_duration: int = CACHE_DURATION,
    ):
        super().__init__()
        self._mtproto = app
        self._app = MtProtoClient(
            cache_duration,
            self._mtproto,
        )
        self._is_running = False
        self._env_checker = Environment(
            self._REQUIRED_PYROGRAM_VERSION,
            self._REQUIRED_TELETHON_VERSION,
            self._REQUIRED_HYDROGRAM_VERSION,
            self._app.package_name,
        )
        self._cache_user_peer = Cache()
        self._binding = NTgCalls()
        
        # التأكد من استخدام اللوب الحالي أو إنشاء واحد جديد ومحسن
        try:
            self.loop = asyncio.get_running_loop()
        except RuntimeError:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            
        self.workers = workers
        self._chat_lock = ChatLock()
        
        # استخدام ThreadPool بعدد العمال الجديد (64+)
        self.executor = ThreadPoolExecutor(
            max_workers=self.workers,
            thread_name_prefix='Titan_Handler', # اسم مميز للعمليات
        )

    @property
    def cache_user_peer(self) -> Cache:
        return self._cache_user_peer

    @property
    def mtproto_client(self):
        return self._mtproto
