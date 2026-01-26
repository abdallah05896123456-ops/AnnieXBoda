# Authored By Certified Coders © 2026
# Security Module: Database Manager
# Optimized to reuse AnnieXMedia Core Mongo Connection

from AnnieXMedia.core.mongo import mongodb

# --- تعريف مجموعات الحماية (Collections) ---
# سيتم إنشاء هذه المجموعات تلقائياً داخل نفس قاعدة بيانات السورس
db_locks = mongodb.protection_locks
db_warns = mongodb.protection_warns

# ==========================================
# دالات جلب وتحديث الأقفال (Locks)
# ==========================================

async def get_locks(chat_id: int):
    """جلب الأقفال المفعلة في المجموعة"""
    try:
        doc = await db_locks.find_one({"chat_id": chat_id})
        return set(doc.get("locks", [])) if doc else set()
    except Exception as e:
        print(f"Error getting locks: {e}")
        return set()

async def update_lock(chat_id: int, key: str, lock: bool = True):
    """تفعيل أو تعطيل قفل معين"""
    try:
        if lock:
            await db_locks.update_one(
                {"chat_id": chat_id}, 
                {"$addToSet": {"locks": key}}, 
                upsert=True
            )
        else:
            await db_locks.update_one(
                {"chat_id": chat_id}, 
                {"$pull": {"locks": key}}, 
                upsert=True
            )
    except Exception as e:
        print(f"Error updating lock: {e}")

# ==========================================
# دالات نظام التحذيرات (Warnings)
# ==========================================

async def get_warn_limit(chat_id: int):
    """جلب ليمت التحذيرات للمجموعة"""
    try:
        doc = await db_warns.find_one({"chat_id": chat_id})
        return doc.get("limit", 3) if doc else 3
    except:
        return 3

async def set_warn_limit_db(chat_id: int, limit: int):
    """تعديل ليمت التحذيرات"""
    try:
        await db_warns.update_one(
            {"chat_id": chat_id}, 
            {"$set": {"limit": limit}}, 
            upsert=True
        )
    except:
        pass

async def get_current_warns(chat_id: int, user_id: int):
    """جلب عدد تحذيرات المستخدم الحالي"""
    try:
        doc = await db_warns.find_one({"chat_id": chat_id})
        if doc and "users" in doc:
            return doc["users"].get(str(user_id), 0)
        return 0
    except:
        return 0

async def update_user_warns(chat_id: int, user_id: int, count: int):
    """تحديث سجل تحذيرات المستخدم"""
    try:
        await db_warns.update_one(
            {"chat_id": chat_id}, 
            {"$set": {f"users.{user_id}": count}}, 
            upsert=True
        )
    except:
        pass
