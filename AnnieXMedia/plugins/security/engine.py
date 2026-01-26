# Authored By Certified Coders © 2026
# Security Module: Main Protection Engine
# Logic: Real-time traffic analysis, Flood control, & Content Filtering

import asyncio
import re
import time
from pyrogram import filters
from pyrogram.types import Message
from fuzzywuzzy import fuzz

from AnnieXMedia import app
from .database import get_locks
from .helpers import has_permission, add_warn, scan_video_frames, check_porn_api

# --- مخازن البيانات المؤقتة (RAM Cache) لسرعة المعالجة ---
flood_cache = {} 
processed_cache = {}

# قائمة الكلمات المحظورة (تستخدم نظام الفحص الضبابي Fuzzy Logic)
BAD_WORDS = ["سكس", "نيك", "شرموط", "منيوك", "كسمك", "زب", "فحل", "بورن", "متناك", "مص", "كس", "طيز", "قحبه", "فاجره", "احاا", "متناكه", "خول"]



@app.on_message(filters.group & ~filters.me, group=-1)
async def protector_engine_handler(_, message: Message):
    try:
        chat_id = message.chat.id
        user_id = message.from_user.id if message.from_user else 0
        
        # 1. منع تكرار معالجة نفس الرسالة (Optimization)
        if chat_id not in processed_cache: 
            processed_cache[chat_id] = []
        if message.id in processed_cache[chat_id]: 
            return 
        processed_cache[chat_id].append(message.id)
        if len(processed_cache[chat_id]) > 100: 
            processed_cache[chat_id].pop(0)

        # 2. استثناء المطورين والادمنية من الفحص
        if user_id and await has_permission(chat_id, user_id): 
            return
        
        # 3. جلب حالة الأقفال للمجموعة
        active_locks = await get_locks(chat_id)
        if not active_locks: 
            return

        # --- [ أ ] نظام قفل الشات الشامل (Global Lock) ---
        if "all" in active_locks:  
            try: await message.delete()  
            except: pass  
            return  

        # --- [ ب ] محرك كاشف التكرار (Flood Control) ---
        if "flood" in active_locks:
            now = time.time()
            flood_key = f"{chat_id}:{user_id}"
            user_history = flood_cache.get(flood_key, [])
            # تنظيف السجل من الرسائل التي مر عليها اكثر من 5 ثواني
            user_history = [t for t in user_history if now - t < 5] 
            user_history.append(now)
            flood_cache[flood_key] = user_history
            if len(user_history) > 5:
                try: 
                    await message.delete()
                    flood_cache[flood_key] = [] 
                    return await add_warn(message, reason="flood")
                except: pass

        # --- [ ج ] معالجة رسائل النظام (Service Messages) ---
        if message.service:
            if "service" in active_locks: 
                try: await message.delete()
                except: pass
            if message.new_chat_members and "bots" in active_locks:
                for member in message.new_chat_members:
                    if member.is_bot:
                        try: 
                            await app.ban_chat_member(chat_id, member.id)
                            await message.delete()
                        except: pass
            if message.pinned_message and "pin" in active_locks:
                try: await message.unpin_all_messages()
                except: pass
            return

        # --- [ د ] معالجة النصوص (Text Analysis) ---
        message_text = message.text or message.caption or ""
        should_delete = False
        is_religious_offense = False
        
        if message_text:
            # كاشف السب الفائق (Fuzzy Logic)
            if "porn_text" in active_locks: 
                # تنظيف النص من الرموز والارقام للتركيز على الكلمات فقط
                clean_text = re.sub(r"[^\u0621-\u064A\s]", "", message_text)
                for word in clean_text.split():
                    if any(fuzz.ratio(bad, word) > 85 for bad in BAD_WORDS):
                        should_delete = True
                        is_religious_offense = True
                        break
            
            # بقية أقفال النصوص
            if not should_delete:
                if "links" in active_locks and any(x in message_text for x in ["http", ".com", ".net", "t.me", "www"]): 
                    should_delete = True
                elif "usernames" in active_locks and "@" in message_text: 
                    should_delete = True
                elif "hashtags" in active_locks and "#" in message_text: 
                    should_delete = True
                elif "markdown" in active_locks and any(x in message_text for x in ["**", "__", "`"]): 
                    should_delete = True
                elif "slashes" in active_locks and message_text.startswith("/"): 
                    should_delete = True
                elif "long_msgs" in active_locks and len(message_text) > 800: 
                    should_delete = True

        # --- [ هـ ] معالجة الوسائط (Media Filtering) ---
        if not should_delete:
            if "photos" in active_locks and message.photo: should_delete = True
            elif "videos" in active_locks and message.video: should_delete = True
            elif "animations" in active_locks and message.animation: should_delete = True
            elif "stickers" in active_locks and message.sticker: should_delete = True
            elif "docs" in active_locks and message.document: should_delete = True
            elif "voice" in active_locks and (message.voice or message.audio): should_delete = True
            elif "video_notes" in active_locks and message.video_note: should_delete = True 
            elif "contacts" in active_locks and message.contact: should_delete = True
            elif "inline" in active_locks and message.via_bot: should_delete = True
            elif "forward" in active_locks and (message.forward_date or message.forward_from): should_delete = True

        # تنفيذ قرار الحذف والتحذير للنصوص والوسائط العادية
        if should_delete:
            try: await message.delete()
            except: pass
            return await add_warn(message, reason="religious" if is_religious_offense else "normal")

        # --- [ و ] كاشف الميديا الإباحية المتقدم (Advanced Media Scanning) ---
        if "porn_media" in active_locks:
            file_to_check = None
            if message.photo:
                file_to_check = f"check_{chat_id}_{message.id}.jpg" 
            elif message.video and message.video.file_size < 30*1024*1024: # ليمت 30 ميجا للفحص السريع
                file_to_check = f"check_{chat_id}_{message.id}.mp4" 

            if file_to_check:
                try:
                    downloaded_path = await message.download(file_name=file_to_check)
                    is_porn = False
                    if message.video:
                        is_porn = await asyncio.get_event_loop().run_in_executor(None, scan_video_frames, downloaded_path)
                    else:
                        is_porn = await asyncio.get_event_loop().run_in_executor(None, check_porn_api, downloaded_path)
                    
                    if os.path.exists(downloaded_path): 
                        os.remove(downloaded_path)
                    
                    if is_porn:
                        try: 
                            await message.delete()
                            return await add_warn(message, reason="religious")
                        except: pass
                except: 
                    pass
    except Exception:
        pass
