from enum import Enum

from ..py_object import PyObject


class VideoQuality(PyObject, Enum):
    # 🔥 NUCLEAR EDITION: All Resolutions Unlocked to 60 FPS 🔥
    
    # الجودات العالية (للسيرفرات الجبارة فقط)
    UHD_4K = (3840, 2160, 60)
    QHD_2K = (2560, 1440, 60)
    FHD_1080p = (1920, 1080, 60)
    
    # 🔥 التعديل هنا: رفعنا الفريمات لـ 60 عشان الفيديو يبقى "زبدة"
    # الـ 16 كور هيقدروا يعالجوا 60 فريم في الثانية مستريح جداً
    HD_720p = (1280, 720, 60)   # كانت 30، خليناها 60
    SD_480p = (854, 480, 60)    # كانت 30، خليناها 60
    SD_360p = (640, 360, 60)    # كانت 30، خليناها 60
