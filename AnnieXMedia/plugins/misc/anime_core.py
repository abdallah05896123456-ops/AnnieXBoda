# Authored By Certified Coders 2026
# Module: Anime Logic Core (Misc)

import httpx
import re

# خريطة ترجمة الحالة
STATUS_MAP = {
    "FINISHED": "مكتمل",
    "RELEASING": "مستمر",
    "NOT_YET_RELEASED": "لم يعرض بعد",
    "CANCELLED": "ملغي",
    "HIATUS": "متوقف مؤقتا"
}

async def get_anime_info(anime_name):
    """دالة الاتصال بـ AniList API"""
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
    """تنظيف النص من الوسوم الزائدة"""
    if not desc:
        return "لا يوجد وصف متاح."
    # تنظيف النص من اكواد HTML
    desc = re.sub(r"<br\s*/?>", "\n", desc)
    desc = re.sub(r"<[^>]+>", "", desc)
    # تقليل النص لو طويل جدا
    return desc.strip()[:800] + "..." if len(desc) > 800 else desc
