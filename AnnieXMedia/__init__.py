# Authored By Certified Coders © 2025
# NUCLEAR EDITION: Local Server Support for 2GB Uploads & RAM Disk
# [attachment_0](attachment)

from AnnieXMedia.core.bot import MusicBotClient
from AnnieXMedia.core.dir import StorageManager
from AnnieXMedia.core.git import git
from AnnieXMedia.core.userbot import Userbot
from AnnieXMedia.misc import dbb, heroku

from .logging import LOGGER

# 1. تهيئة البنية التحتية (الرام ديسك، الجيت، وقاعدة البيانات)
# يتم توجيه التحميلات تلقائياً إلى /dev/shm/AnnieDownloads لضمان السرعة
StorageManager()
git()
dbb()
heroku()

# 2. تشغيل العميل النووي
# الكلاس MusicBotClient مبرمج الآن لتفعيل الـ Local Server يدوياً
app = MusicBotClient()

# 3. تشغيل الحساب المساعد (Userbot)
userbot = Userbot()

# 4. استيراد وتهيئة منصات الميديا
# ملاحظة: YouTubeAPI الآن مربوط بالـ app الذي يدعم رفع ملفات حتى 2 جيجا
from .platforms import *

Apple = AppleAPI()
Carbon = CarbonAPI()
SoundCloud = SoundAPI()
Spotify = SpotifyAPI()
Resso = RessoAPI()
Telegram = TeleAPI()
YouTube = YouTubeAPI()

LOGGER(__name__).info("Nuclear Core Initialized: 2GB Uploads Enabled via Local Server.")
