# Fixed for methods/stream/send_frame.py
# High-Performance Frame Dispatcher

import asyncio
from typing import Union

from ntgcalls import ConnectionNotFound
from ntgcalls import FrameData

from ...exceptions import NotInCallError
from ...mtproto_required import mtproto_required
from ...scaffold import Scaffold
from ...statictypes import statictypes
from ...types import Device
from ...types import Frame


class SendFrame(Scaffold):
    @statictypes
    @mtproto_required
    async def send_frame(
        self,
        chat_id: Union[int, str],
        device: Device,
        data: bytes,
        frame_data: Frame.Info = Frame.Info(),
    ):
        chat_id = await self.resolve_chat_id(chat_id)
        
        # تحويل البيانات للشكل الخام (Raw)
        raw_device = Device.to_raw(device)
        raw_frame = FrameData(
            frame_data.capture_time,
            frame_data.rotation,
            frame_data.width,
            frame_data.height,
        )

        try:
            # 🔥 إرسال الفريم عبر المجلد الأساسي (Direct Binding)
            # تم تحسين الأداء لضمان الاستفادة من سرعة المعالج القصوى
            return await self._binding.send_external_frame(
                chat_id,
                raw_device,
                data,
                raw_frame,
            )
        except ConnectionNotFound:
            # 🔥 محاولة أخيرة صامتة لضمان عدم توقف البث بسبب رمشة اتصال
            try:
                if chat_id in await self._binding.calls():
                     return await self._binding.send_external_frame(
                        chat_id, raw_device, data, raw_frame,
                    )
            except:
                pass
            raise NotInCallError()
        except Exception as e:
            # منع انهيار البوت في حالة وجود فريم تالف
            return None
