# Authored By Certified Coders 2026
# Module: Anime Commands (Tools)

from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ParseMode
import config
from AnnieXMedia import app
from AnnieXMedia.misc import SUDOERS

# استيراد دالة البحث من ملف المنطق في misc
from AnnieXMedia.plugins.misc.anime_core import get_anime_info, clean_description, STATUS_MAP

# تهيئة وضع الانمي (مفعل افتراضياً)
if not hasattr(config, "ANIME_MODE"):
    config.ANIME_MODE = True

# ─── 1. أوامر التحكم (للمطورين) ───

@app.on_message(filters.command(["تفعيل الانمي", "تعطيل الانمي"]) & SUDOERS)
async def toggle_anime_mode(client, message):
    command = message.text
    
    if "تفعيل" in command:
        config.ANIME_MODE = True
        await message.reply_text("تم تفعيل البحث عن الانمي بنجاح.")
    else:
        config.ANIME_MODE = False
        await message.reply_text("تم تعطيل البحث عن الانمي بنجاح.")

# ─── 2. أمر البحث (للأعضاء) ───

@app.on_message(
    filters.command(["anime", "انمي", "بحث انمي", "كارتون"], prefixes=["", "/", "!", "."])
)
async def anime_search_cmd(client: Client, message: Message):
    # التحقق من حالة التفعيل
    if not config.ANIME_MODE:
        return await message.reply_text("عذرا، خدمة البحث عن الانمي معطلة حاليا.")

    if len(message.command) < 2:
        return await message.reply_text(
            "**يرجى كتابة اسم الانمي للبحث.**\nمثال: `انمي ون بيس`",
            parse_mode=ParseMode.MARKDOWN
        )

    processing = await message.reply_text("جـاري الـبـحـث ...")
    anime_name = " ".join(message.command[1:])
    
    # استدعاء الدالة من ملف misc
    result, error = await get_anime_info(anime_name)

    if not result:
        return await processing.edit_text(error or "لم يتم العثور على الانمي.")

    # استخراج وتنسيق البيانات
    title_romaji = result['title']['romaji']
    title_english = result['title'].get('english', 'غير متاح')
    title_native = result['title']['native']
    
    episodes = result.get('episodes', 'غير معروف')
    
    raw_status = result.get('status', 'UNKNOWN')
    status = STATUS_MAP.get(raw_status, raw_status)
    
    score = result.get('averageScore', 'N/A')
    desc = clean_description(result.get('description'))
    image = result['coverImage']['large']
    genres = ", ".join(result.get('genres', []))

    caption = (
        f"**الاسـم (رومانجي):** {title_romaji}\n"
        f"**الاسـم (انجليزي):** {title_english}\n"
        f"**الاسـم (اصلي):** {title_native}\n\n"
        
        f"**الـحـالـة:** {status}\n"
        f"**الـحـلـقـات:** {episodes}\n"
        f"**الـتـقـيـيـم:** {score}/100\n"
        f"**الـتـصـنـيـف:** {genres}\n\n"
        
        f"**الـقـصـة:**\n{desc}"
    )

    await processing.delete()
    await message.reply_photo(
        image,
        caption=caption,
        parse_mode=ParseMode.MARKDOWN
    )
