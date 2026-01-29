# Authored By Certified Coders 2026
# Module: Anime Search - Arabic & No Emojis

import httpx
import re
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ParseMode
from AnnieXMedia import app

# خريطة ترجمة الحالة
STATUS_MAP = {
    "FINISHED": "مكتمل",
    "RELEASING": "مستمر",
    "NOT_YET_RELEASED": "لم يعرض بعد",
    "CANCELLED": "ملغي",
    "HIATUS": "متوقف مؤقتا"
}

async def get_anime_info(anime_name):
    url = 'https://graphql.anilist.co'
    query = '''
    query ($anime: String) {
      Media (search: $anime, type: ANIME) {
        id
        title {
          romaji
          english
          native
        }
        description(asHtml: false)
        episodes
        status
        averageScore
        coverImage {
          large
        }
        genres
      }
    }
    '''
    variables = {"anime": anime_name}
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.post(url, json={'query': query, 'variables': variables})
            data = response.json()
            if 'errors' in data:
                return None, "لم يتم العثور على الانمي."
            return data['data']['Media'], None
        except Exception as e:
            return None, f"حدث خطأ اثناء البحث: {e}"


def clean_description(desc):
    if not desc:
        return "لا يوجد وصف متاح."
    # تنظيف النص من اكواد HTML
    desc = re.sub(r"<br\s*/?>", "\n", desc)
    desc = re.sub(r"<[^>]+>", "", desc)
    # تقليل النص لو طويل جدا
    return desc.strip()[:800] + "..." if len(desc) > 800 else desc


@app.on_message(
    filters.command(["anime", "انمي", "بحث انمي", "كارتون"], prefixes=["", "/", "!", "."])
)
async def anime_info(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text(
            "**يرجى كتابة اسم الانمي للبحث.**\nمثال: `انمي ون بيس`",
            parse_mode=ParseMode.MARKDOWN
        )

    processing = await message.reply_text("جـاري الـبـحـث ...")
    anime_name = " ".join(message.command[1:])
    result, error = await get_anime_info(anime_name)

    if not result:
        return await processing.edit_text(error or "لم يتم العثور على الانمي.")

    # استخراج البيانات
    title_romaji = result['title']['romaji']
    title_english = result['title'].get('english', 'غير متاح')
    title_native = result['title']['native']
    
    episodes = result.get('episodes', 'غير معروف')
    
    # ترجمة الحالة
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
