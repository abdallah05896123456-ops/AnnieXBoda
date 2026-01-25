from ...statictypes import statictypes
from ..py_object import PyObject
from ..stream.audio_quality import AudioQuality


class AudioParameters(PyObject):
    @statictypes
    def __init__(
        self,
        bitrate: int = 48000,
        channels: int = 2, # 🔥 تعديل: خلينا الافتراضي 2 (ستيريو) بدل 1 (مونو)
    ):
        # 🔥 إلغاء القيود: مسحنا كود الـ min و max عشان المكتبة متقللش الجودة غصب عننا
        # دلوقتي هيقبل الـ 48000 والـ 2 Channels زي ما هم
        self.bitrate: int = bitrate
        self.channels: int = channels
