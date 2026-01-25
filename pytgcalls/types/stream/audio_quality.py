from enum import Enum


class AudioQuality(Enum):
    # 🔥 NUCLEAR EDITION: High Bitrate + Forced Stereo 🔥
    
    # 192kbps: جودة استوديو حقيقية (تستغل قوة السيرفر والنت)
    STUDIO = (192000, 2)
    
    # 128kbps: جودة عالية جداً (Standard High)
    HIGH = (128000, 2)
    
    # 64kbps: جودة متوسطة (أفضل من 36 القديمة)
    MEDIUM = (64000, 2)
    
    # 32kbps: أقل حاجة، وبرضو خليناها ستيريو
    LOW = (32000, 2)
