# Authored By Certified Coders 2026
# Module: Boredom Buster - Limited Commands (bored / اعمل اي)

from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from AnnieXMedia import app
from AnnieXMedia.misc import SUDOERS
import httpx
from googletrans import Translator

# ─── المتغير المتحكم (مغلق افتراضيا) ───
BORED_MODE = False

# تهيئة المترجم
trans = Translator()

# رابط API
BORED_API_URL = "https://apis.scrimba.com/bored/api/activity"

# ⛔ قائمة الكلمات الممنوعة (يتم حجب الاقتراح لو احتوى عليها)
BANNED_WORDS = [
    "kiss", "girlfriend", "boyfriend", "date", "romance", "romantic",
    "beer", "alcohol", "wine", "drink", "pub", "bar", "cocktail",
    "party", "club", "dating", "sex", "nude", "casino", "gambling",
    "poker", "cards", "church", "christmas"
]

# ─── أوامر التفعيل والتعطيل (للمطورين فقط) ───

@app.on_message(filters.command(["تفعيل الاقتراحات", "تعطيل الاقتراحات"]) & SUDOERS)
async def toggle_bored_mode(client, message):
    global BORED_MODE
    command = message.text
    
    if "تفعيل" in command:
        BORED_MODE = True
        await message.reply_text("✅ تم تفعيل وضع الاقتراحات بنجاح.")
    else:
        BORED_MODE = False
        await message.reply_text("⛔ تم تعطيل وضع الاقتراحات بنجاح.")

# ─── الأمر (اعمل اي / bored) فقط ───

@app.on_message(filters.command(["bored", "اعمل اي"], prefixes=["", "/", "!", "."]))
async def bored_command(client, message):
    global BORED_MODE

    # التحقق من حالة الوضع
    if not BORED_MODE:
        return await message.reply_text("الوضع متوقف مؤقتا .")

    try:
        async with httpx.AsyncClient(timeout=10.0) as http:
            response = await http.get(BORED_API_URL)

        if response.status_code != 200:
            return await message.reply_text("حدث خطأ، حاول مرة اخرى.")

        data = response.json()
        activity_en = data.get("activity", "")

        if not activity_en:
            return await message.reply_text("لا يوجد اقتراح حاليا.")

        # ─── الفلترة (منع المحتوى غير المناسب) ───
        is_safe = True
        for word in BANNED_WORDS:
            if word in activity_en.lower():
                is_safe = False
                break
        
        if not is_safe:
            return await message.reply_text(
                "⚠️ الاقتراح كان غير مناسب وتم حجبه، حاول مرة اخرى."
            )

        # ─── الترجمة للعربية ───
        try:
            translated = trans.translate(activity_en, dest="ar").text
        except Exception:
            translated = activity_en

        # إرسال الاقتراح
        await message.reply_text(
            f"🎯 **جرب تعمل ده:** `{translated}`",
            parse_mode=ParseMode.MARKDOWN
        )

    except Exception as e:
        print(f"Bored API error: {e}")
        await message.reply_text("حدث خطأ غير متوقع.")
