# Authored By Certified Coders © 2025
# NUCLEAR EDITION: Local Server Support for 2GB Uploads

from AnnieXMedia.core.bot import MusicBotClient
from AnnieXMedia.core.dir import StorageManager
from AnnieXMedia.core.git import git
from AnnieXMedia.core.userbot import Userbot
from AnnieXMedia.misc import dbb, heroku

from .logging import LOGGER

# تهيئة مديري التخزين والأنظمة الأساسية
StorageManager()
git()
dbb()
heroku()

# تشغيل البوت مع دعم السيرفر المحلي لرفع ملفات حتى 2 جيجابايت
# ملاحظة: تأكد من تشغيل telegram-bot-api في الخلفية على منفذ 8081
app = MusicBotClient()

# ربط العميل بالسيرفر المحلي (يتم ضبط هذا غالباً داخل كلاس MusicBotClient)
# إذا أردت التأكيد البرمجي هنا، تأكد أن الكلاس يدعم تمرير الإعدادات
userbot = Userbot()

from .platforms import *

Apple = AppleAPI()
Carbon = CarbonAPI()
SoundCloud = SoundAPI()
Spotify = SpotifyAPI()
Resso = RessoAPI()
Telegram = TeleAPI()
YouTube = YouTubeAPI()
