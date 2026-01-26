# Authored By Certified Coders © 2026
# MOVIE SEARCH SYSTEM - AnnieXMedia OFFICIAL
# Logic: TMDB Metadata + AI-Powered Web Scanning for Streaming Links

import httpx
import os
import re
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.enums import ParseMode
from g4f.client import AsyncClient as AIClient
from AnnieXMedia import app

# --- إعدادات المحركات والبيانات الأساسية ---
TMDB_API_KEY = "23c3b139c6d59ebb608fe6d5b974d888"
TMDB_BASE_URL = "https://api.themoviedb.org/3"
IMAGE_SERVER = "https://image.tmdb.org/t/p/w500"

# تهيئة محرك البحث الذكي (AI Engine)
search_engine = AIClient()

async def get_streaming_link_via_ai(movie_name: str):
    """
    استخدام تقنيات الاستدلال المنطقي للذكاء الاصطناعي للبحث عن 
    روابط المشاهدة النشطة في الوقت الحالي.
    """
    instruction = (
        "أنت محرك بحث متقدم متخصص في العثور على روابط الأفلام العربية. "
        "مهمتك هي تزويدي برابط مباشر وصالح لمشاهدة الفيلم المطلوب من مواقع: "
        "إيجي بيست، عرب سيد، أو فاصل إعلاني. "
        "يجب أن يكون الرد عبارة عن الرابط فقط بدون أي نصوص أو مقدمات. "
        "إذا تعذر العثور على رابط مباشر، رد بكلمة NULL."
    )
    try:
        response = await search_engine.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": instruction},
                {"role": "user", "content": f"ابحث عن رابط مشاهدة فيلم: {movie_name}"}
            ]
        )
        found_link = response.choices[0].message.content.strip()
        if found_link and found_link.startswith("http") and "NULL" not in found_link:
            return found_link
        return None
    except Exception:
        return None

async def fetch_movie_metadata(movie_query: str):
    """جلب المعلومات الرسمية من قاعدة بيانات TMDB"""
    async with httpx.AsyncClient(timeout=20.0) as client:
        # البحث الأولي عن الفيلم مع تفعيل اللغة العربية
        search_req = await client.get(f"{TMDB_BASE_URL}/search/movie", params={
            "api_key": TMDB_API_KEY,
            "query": movie_query,
            "language": "ar"
        })
        results = search_req.json().get("results")
        if not results:
            return None

        primary_data = results[0]
        movie_id = primary_data["id"]

        # جلب التفاصيل الإضافية (مثل الإيرادات والموقع الرسمي)
        details_req = await client.get(f"{TMDB_BASE_URL}/movie/{movie_id}", params={
            "api_key": TMDB_API_KEY,
            "language": "ar"
        })
        details = details_req.json()

        # جلب قائمة الممثلين الرئيسية
        credits_req = await client.get(f"{TMDB_BASE_URL}/movie/{movie_id}/credits", params={
            "api_key": TMDB_API_KEY,
            "language": "ar"
        })
        cast_list = ", ".join([member["name"] for member in credits_req.json().get("cast", [])[:5]])

        # تنسيق البيانات النصية
        revenue_val = details.get("revenue", 0)
        revenue_formatted = f"${revenue_val:,}" if revenue_val > 0 else "غير متوفر"
        
        caption_text = (
            f"العنوان: {details.get('title')}\n"
            f"تاريخ الإصدار: {details.get('release_date')}\n"
            f"التقييم العام: {details.get('vote_average')}/10\n"
            f"طاقم التمثيل: {cast_list}\n"
            f"صندوق التذاكر: {revenue_formatted}\n\n"
            f"قصة الفيلم:\n{details.get('overview')}\n\n"
            f"نظام معلومات AnnieXMedia"
        )

        return {
            "id_title": details.get('title'),
            "caption": caption_text,
            "poster": f"{IMAGE_SERVER}{details.get('poster_path')}" if details.get('poster_path') else None,
            "official_url": details.get("homepage")
        }

# --- معالج الأوامر المباشر (No-Prefix) ---
@app.on_message(filters.regex(r"^(فيلم|فلم|movie)($| )") & ~filters.bot)
async def movie_search_processor(client: Client, message: Message):
    # التحقق من وجود اسم الفيلم في نص الرسالة
    if len(message.text.split()) < 2:
        return await message.reply_text("يرجى كتابة اسم الفيلم بعد الأمر لبدء عملية البحث.")

    search_query = message.text.split(None, 1)[1]
    status_prompt = await message.reply_text("جاري استخلاص البيانات الرسمية والبحث عن روابط المشاهدة عبر الذكاء الاصطناعي...")

    try:
        # 1. جلب البيانات الأساسية والبوستر
        metadata = await fetch_movie_metadata(search_query)
        if not metadata:
            return await status_prompt.edit("لم يتم العثور على الفيلم المطلوب في قاعدة البيانات.")

        # 2. البحث عن روابط خارجية للمشاهدة (البحث الذكي)
        streaming_url = await get_streaming_link_via_ai(metadata["id_title"])
        
        # 3. بناء لوحة التحكم (الروابط)
        navigation_buttons = []
        if streaming_url:
            navigation_buttons.append([InlineKeyboardButton(text="روابـط الـتـنـزيـل", url=streaming_url)])
        
        if metadata["official_url"]:
            navigation_buttons.append([InlineKeyboardButton(text="الموقع الرسمي", url=metadata["official_url"])])
            
        markup_interface = InlineKeyboardMarkup(navigation_buttons) if navigation_buttons else None

        # 4. تسليم النتيجة للمستخدم
        if metadata["poster"]:
            await message.reply_photo(
                photo=metadata["poster"],
                caption=metadata["caption"],
                reply_markup=markup_interface,
                parse_mode=ParseMode.MARKDOWN
            )
            await status_prompt.delete()
        else:
            await status_prompt.edit(metadata["caption"], reply_markup=markup_interface, parse_mode=ParseMode.MARKDOWN)

    except Exception:
        await status_prompt.edit("حدث خطأ فني غير متوقع أثناء معالجة طلبك.")
