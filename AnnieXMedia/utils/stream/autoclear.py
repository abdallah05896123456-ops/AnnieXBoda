# Authored By Certified Coders © 2025
# Fixed for utils/stream/autoclear.py
# SMART RAM CACHE: Keeps files in RAM unless space runs low

import os
import shutil
from config import autoclean, DOWNLOAD_PATH

async def auto_clean(popped):
    try:
        rem = popped["file"]
        
        # 1. تحديث قائمة التتبع (عشان القائمة متكبرش وتتقل البوت)
        if rem in autoclean:
            autoclean.remove(rem)
            
        # 2. التأكد إن مفيش روم تانية بتسمع نفس الملف دلوقتي
        count = autoclean.count(rem)
        if count == 0:
            # لو هو رابط أو مش ملف حقيقي، اخرج
            if not rem or str(rem).startswith("http"):
                return
            
            # 🔥 نظام الكاش الذكي (Smart RAM Check) 🔥
            if os.path.exists(DOWNLOAD_PATH):
                try:
                    # فحص المساحة المتاحة في الرام (/dev/shm)
                    total, used, free = shutil.disk_usage(DOWNLOAD_PATH)
                    
                    # المعيار: سيب 5 جيجا فاضية للنظام، واستخدم الباقي (83 جيجا) كاش
                    if free > 5 * 1024 * 1024 * 1024: 
                        return # لا تمسح الملف، خليه كاش
                except:
                    pass

            # 3. الحذف الاضطراري (فقط لو الرام اتملت)
            if "vid_" not in rem or "live_" not in rem or "index_" not in rem:
                try:
                    if os.path.exists(rem):
                        os.remove(rem)
                except:
                    pass
    except:
        pass
