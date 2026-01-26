import asyncio
from typing import Callable, Optional

class WaitCounterLock:
    def __init__(self, remove_callback: Optional[Callable] = None, *args):
        self._lock = asyncio.Lock()
        self._waiters = 0
        self._remove_callback = remove_callback
        self._args = args

    def waiters(self):
        return self._waiters

    async def __aenter__(self):
        self._waiters += 1
        await self._lock.acquire()
        self._waiters -= 1
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self._lock.locked():
            self._lock.release()
        
        # التعديل هنا: التأكد من وجود الدالة قبل استدعائها
        if self._remove_callback:
            try:
                # التحقق مما إذا كانت الدالة Async أم لا لضمان التنفيذ
                if asyncio.iscoroutinefunction(self._remove_callback):
                    await self._remove_callback(*self._args)
                else:
                    self._remove_callback(*self._args)
            except Exception:
                # تجاهل الأخطاء أثناء التنظيف لعدم كسر النظام
                pass
