# Authored By Certified Coders © 2026
# Security Module: Intelligence Helpers
# Logic: Media Scanning, Permissions, & Warning System

import asyncio
import os
import requests
import cv2
from datetime import datetime, timedelta
from pyrogram.enums import ChatMemberStatus
from pyrogram.types import Message, ChatPermissions, InlineKeyboardMarkup, InlineKeyboardButton

from AnnieXMedia import app
from AnnieXMedia.misc import SUDOERS
from .database import get_warn_limit, get_current_warns, update_user_warns

# --- إعدادات المحرك الأمني ---
API_USER = "1800965377"
API_SECRET = "pp32KRVBbfQjJXqLYoah7goaU949hwjU"

# ==========================================
# دالات التحقق والتحكم في الرتب
# ==========================================

async def has_permission(chat_id: int, user_id: int):
    """التحقق من صلاحيات المستخدم (مطور، مالك، أو أدمن)"""
    if user_id in SUDOERS:
        return True
    try:
        member = await app.get_chat_member(chat_id, user_id)
        if member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
            return True
    except:
        return False
    return False

# ==========================================
# محرك فحص الوسائط (Porn/Nudity Detection)
# ==========================================

def check_porn_api(file_path: str):
    """الاتصال بمحرك التحليل الذكي للكشف عن المحتوى الإباحي"""
    try:
        params = {
            'models': 'nudity-2.0', 
            'api_user': API_USER, 
            'api_secret': API_SECRET
        }
        with open(file_path, 'rb') as f:
            r = requests.post('https://api.sightengine.com/1.0/check.json', files={'media': f}, data=params)
        
        output = r.json()
        if output.get('status') == 'success':
            n = output.get('nudity', {})
            # المعايير الأمنية: إذا تجاوزت نسبة المحتوى الجنسي 0.5 يتم الحذف
            return n.get('sexual_display', 0) > 0.5 or n.get('erotica', 0) > 0.5
    except Exception as e:
        print(f"Media Scan Error: {e}")
    return False

async def scan_video_frames(video_path: str):
    """تحليل لقطات عشوائية من الفيديو لضمان خلوه من المحتوى المحظور"""
    is_detected = False
    try:
        cam = cv2.VideoCapture(video_path)
        total_frames = int(cam.get(cv2.CAP_PROP_FRAME_COUNT))
        
        if total_frames > 0:
            # فحص 3 نقاط زمنية مختلفة في الفيديو (البداية، المنتصف، النهاية)
            check_points = [0.1, 0.5, 0.9]
            for point in check_points:
                frame_id = int(total_frames * point)
                cam.set(cv2.CAP_PROP_POS_FRAMES, frame_id)
                ret, frame = cam.read()
                if ret:
                    temp_frame = f"{video_path}_check_{int(point*100)}.jpg"
                    cv2.imwrite(temp_frame, frame)
                    if check_porn_api(temp_frame):
                        is_detected = True
                        os.remove(temp_frame)
                        break 
                    if os.path.exists(temp_frame):
                        os.remove(temp_frame)
        cam.release()
    except Exception as e:
        print(f"Video Frame Scan Error: {e}")
    return is_detected

# ==========================================
# نظام العقوبات والتحذيرات (Penalty Logic)
# ==========================================

async def add_warn(message: Message, reason="normal"):
    """إدارة نظام التحذيرات وتطبيق عقوبة الكتم التلقائي"""
    try:
        c_id = message.chat.id
        u_id = message.from_user.id
        mention = message.from_user.mention

        # منطق العقوبة التدريجي
        if reason == "religious":  
            limit = 4  
            mute_days = 7   
            msg_text = f"يا {mention} ، تذكر قول الله تعالي : ( مَا يَلْفِظُ مِنْ قَوْلٍ إِلَّا لَدَيْهِ رَقِيبٌ عَتِيدٌ ) وأن هذه الدنيا فانية"  
        else:  
            limit = await get_warn_limit(c_id)  
            mute_days = 1   
            msg_text = f"يا {mention} ، تم حذف رسالتك لمخالفة قوانين الحماية"  

        current = await get_current_warns(c_id, u_id)
        current += 1
        
        if current > limit:  
            await update_user_warns(c_id, u_id, 0)
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("فك الكتم", callback_data=f"u_unmute_{u_id}")]])  
            try:  
                await app.restrict_chat_member(
                    c_id, 
                    u_id, 
                    ChatPermissions(can_send_messages=False), 
                    until_date=datetime.now() + timedelta(days=mute_days)
                )
                await message.reply(f"{msg_text}\n\nتم كتمك لمدة {mute_days} أيام لتخطي التحذيرات المسموحة", reply_markup=kb)  
            except Exception:
                pass  
        else:  
            await update_user_warns(c_id, u_id, current)
            await message.reply(f"{msg_text}\n\nتحذيراتك الحالية هي : ({current}/{limit})")
    except Exception as e:
        print(f"Warning System Error: {e}")

# ==========================================
# نظام المسح الجماعي (Clear Logic)
# ==========================================

async def force_delete(chat_id: int, current_id: int, limit: int):
    """مسح الرسائل القديمة بسرعة عالية جداً"""
    count = 0
    msg_ids = list(range(current_id, current_id - (limit + 100), -1))
    
    # تقسيم عملية المسح لمجموعات (كل مجموعة 100 رسالة) لضمان السرعة
    for i in range(0, len(msg_ids), 100):
        if count >= limit:
            break
        try:
            await app.delete_messages(chat_id, msg_ids[i:i+100])
            count += 100 
        except:
            continue
    return count
