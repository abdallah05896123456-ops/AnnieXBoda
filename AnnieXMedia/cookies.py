# Authored By Certified Coders © 2025
import os
import aiohttp
import aiofiles
import config
from AnnieXMedia import LOGGER

async def save_cookies():
    # البحث عن رابط الكوكيز في الكونفج أو متغيرات النظام
    cookie_link = getattr(config, "COOKIE_URL", None) or os.getenv("COOKIE_URL")
    
    if not cookie_link:
        LOGGER(__name__).warning("⚠️ No COOKIE_URL found in vars. Skipping cookie download.")
        return

    LOGGER(__name__).info("🍪 Found COOKIE_URL, downloading...")

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(cookie_link) as response:
                if response.status != 200:
                    LOGGER(__name__).error(f"❌ Failed to fetch cookies. HTTP Status: {response.status}")
                    return
                content = await response.text()
        except Exception as e:
            LOGGER(__name__).error(f"❌ Cookie Connection Error: {e}")
            return

        if content:
            # حفظ الملف باسم cookies.txt في المسار الرئيسي
            file_path = "cookies.txt"
            try:
                async with aiofiles.open(file_path, "w") as file:
                    await file.write(content)
                
                # التأكد من أن الملف ليس فارغاً
                if os.path.getsize(file_path) > 0:
                    LOGGER(__name__).info(f"✅ Cookies saved successfully to {file_path}.")
                else:
                    LOGGER(__name__).error("⚠️ Downloaded cookie file is empty!")
            except Exception as e:
                LOGGER(__name__).error(f"❌ Failed to write cookie file: {e}")
        else:
            LOGGER(__name__).error("⚠️ Cookie content is empty/null.")
