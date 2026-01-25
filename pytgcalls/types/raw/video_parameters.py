from ...statictypes import statictypes
from ..py_object import PyObject
from ..stream.video_quality import VideoQuality


class VideoParameters(PyObject):
    @statictypes
    def __init__(
        self,
        width: int = 1280,      # 🔥 تعديل: خلينا الافتراضي HD 720p
        height: int = 720,      # 🔥 تعديل: ارتفاع 720 بدل 360
        frame_rate: int = 30,   # 🔥 تعديل: 30 فريم عشان السلاسة (بدل 20 المتقطعة)
        adjust_by_height: bool = True,
    ):
        # 🔥 تم نسف القيود: مسحنا كود الـ max و min
        # دلوقتي المكتبة هتحترم قدرات السيرفر وهتقبل الجودة العالية اللي طلبناها في call.py
        
        self.width: int = width
        self.height: int = height
        self.frame_rate: int = frame_rate
        self.adjust_by_height: bool = adjust_by_height
