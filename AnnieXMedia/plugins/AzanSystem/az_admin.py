import asyncio
from datetime import datetime
from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import FloodWait

# استدعاء مكتبات السورس الأساسية
from BrandrdXMusic import app
from config import BANNED_USERS

# استدعاء المتغيرات والدوال من ملفات الأذان
from .az_conf import (
    MAIN_OWNER, DEVS, AZAN_GROUP, PRAYER_NAMES_AR, PRAYER_NAMES_REV, 
    local_cache, admin_state, resources_db, settings_db, 
    CURRENT_RESOURCES, CURRENT_DUA_STICKER
)
from .az_utils import (
    check_rights, get_chat_doc, update_doc, start_azan_stream, 
    get_azan_times, extract_vidid, scheduler, init_azan_scheduler
)

# --- [ 0. نظام التشغيل الآمن ] ---
# متغير للتأكد من أن النظام بدأ مرة واحدة فقط
is_azan_system_started = False

@app.on_message(group=AZAN_GROUP + 1)
async def auto_start_azan_system_safe(_, __):
    """تشغيل المجدول تلقائياً مع أول رسالة يستقبلها البوت لضمان الجاهزية"""
    global is_azan_system_started
    if not is_azan_system_started:
        try:
            init_azan_scheduler()
            is_azan_system_started = True
        except Exception:
            pass

# --- [ 1. أوامر المعلومات العامة ] ---

@app.on_message(filters.regex(r"^(الصلاة|مواعيد الصلاة|اوقات الصلاة|الصلاه)$") & filters.group, group=AZAN_GROUP)
async def next_prayer_info(client, message):
    """عرض مواقيت الصلاة لليوم والوقت المتبقي للصلاة القادمة"""
    chat_id = message.chat.id
    doc = await get_chat_doc(chat_id)
    
    if not doc.get("azan_active"):
        return await message.reply_text("خدمة الأذان متوقفة حالياً في هذه المجموعة.")

    times = await get_azan_times()
    if not times:
        return await message.reply_text("تعذر الوصول إلى خادم المواقيت في الوقت الحالي، يرجى المحاولة لاحقاً.")

    now = datetime.now()
    
    # تنسيق الرسالة
    text = "مواقيت الصلاة بتوقيت مدينة القاهرة لهذا اليوم:\n\n"
    next_prayer = None
    min_diff = float('inf')

    for key, name in PRAYER_NAMES_AR.items():
        t = times[key] # Format: HH:MM
        # تحويل الوقت لـ datetime للمقارنة
        prayer_time = datetime.strptime(t, "%H:%M").replace(year=now.year, month=now.month, day=now.day)
        
        # تنسيق الوقت لـ 12 ساعة
        display_time = prayer_time.strftime("%I:%M %p")
        
        # تحديد الصلاة القادمة
        diff = (prayer_time - now).total_seconds()
        if 0 < diff < min_diff:
            min_diff = diff
            next_prayer = (name, diff)

        text += f"- {name}: {display_time}\n"

    text += "\n"
    if next_prayer:
        name, seconds = next_prayer
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        text += f"الصلاة القادمة هي صلاة {name} (يتبقى {hours} ساعة و {minutes} دقيقة على رفع الأذان)."
    else:
        text += "انتهت كافة الصلوات لهذا اليوم، موعدنا مع صلاة الفجر ليوم الغد بإذن الله."

    await message.reply_text(text)

# --- [ 2. أوامر المشرفين (التحكم) ] ---

@app.on_message(filters.regex(r"^تفعيل الاذان$") & filters.group & ~BANNED_USERS, group=AZAN_GROUP)
async def admin_enable_azan(_, m):
    if not await check_rights(m.from_user.id, m.chat.id):
        return await m.reply_text("عذراً، هذا الأمر مخصص للمشرفين فقط.")
    
    doc = await get_chat_doc(m.chat.id)
    if doc.get("azan_active"): 
        return await m.reply_text("خدمة الأذان مفعلة بالفعل في هذه المجموعة.")
    
    await update_doc(m.chat.id, "azan_active", True)
    await m.reply_text("تم تفعيل خدمة الأذان والتنبيهات بنجاح في هذه المجموعة.")

@app.on_message(filters.regex(r"^قفل الاذان$") & filters.group & ~BANNED_USERS, group=AZAN_GROUP)
async def admin_disable_azan(_, m):
    if not await check_rights(m.from_user.id, m.chat.id):
        return await m.reply_text("عذراً، هذا الأمر مخصص للمشرفين فقط.")
    
    doc = await get_chat_doc(m.chat.id)
    
    # حماية التفعيل الإجباري
    if doc.get("forced_active", False):
        if m.from_user.id not in DEVS:
            return await m.reply_text("عذراً، لا يمكنك إيقاف الخدمة لأنها مفعلة إجبارياً من قبل مطور البوت.")

    if not doc.get("azan_active"): 
        return await m.reply_text("خدمة الأذان متوقفة بالفعل.")
        
    await update_doc(m.chat.id, "azan_active", False)
    await m.reply_text("تم تعطيل خدمة الأذان في هذه المجموعة بناءً على طلبك.")

@app.on_message(filters.regex(r"^(تفعيل الاذكار|تفعيل الدعاء)$") & filters.group & ~BANNED_USERS, group=AZAN_GROUP)
async def admin_enable_duas(_, m):
    if not await check_rights(m.from_user.id, m.chat.id): return
    await update_doc(m.chat.id, "dua_active", True)
    await update_doc(m.chat.id, "night_dua_active", True)
    await m.reply_text("تم تفعيل خدمة نشر الأذكار والأدعية اليومية (الصباح والمساء).")

@app.on_message(filters.regex(r"^(قفل الاذكار|قفل الدعاء)$") & filters.group & ~BANNED_USERS, group=AZAN_GROUP)
async def admin_disable_duas(_, m):
    if not await check_rights(m.from_user.id, m.chat.id): return
    doc = await get_chat_doc(m.chat.id)

    if doc.get("forced_dua_active", False) and m.from_user.id not in DEVS:
        return await m.reply_text("عذراً، الأذكار مفعلة إجبارياً من قبل مطور البوت.")

    await update_doc(m.chat.id, "dua_active", False)
    await update_doc(m.chat.id, "night_dua_active", False)
    await m.reply_text("تم تعطيل خدمة نشر الأذكار والأدعية التلقائية.")


# --- [ 3. لوحة التحكم التفاعلية ] ---

@app.on_message(filters.regex(r"^(اعدادات الاذان|انلاين الاذان|الاذان|أوامر الاذان)$") & filters.group & ~BANNED_USERS, group=AZAN_GROUP)
async def azan_commands_panel(_, m):
    text = (
        "مرحباً بك في لوحة تحكم الأذان.\n"
        "يمكنك التحكم في تفعيل وتعطيل الصلوات والأذكار من هنا.\n\n"
        "يرجى اختيار القسم المناسب لصلاحياتك:"
    )
    
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("أوامر المطور", callback_data="cmd_owner")],
        [InlineKeyboardButton("إعدادات المجموعة", callback_data="cmd_admin")],
        [InlineKeyboardButton("إغلاق اللوحة", callback_data="cmd_close")]
    ])
    await m.reply_text(text, reply_markup=kb)

# استقبال رابط الإعدادات في الخاص (لتجنب زحمة الجروب)
@app.on_message(filters.regex("^/start azset_") & filters.private, group=AZAN_GROUP)
async def open_panel_private(_, m):
    try: target_cid = int(m.text.split("azset_")[1])
    except: return
    
    # التحقق من أن المستخدم مشرف في الجروب المستهدف
    if not await check_rights(m.from_user.id, target_cid):
        return await m.reply("يجب أن تكون مشرفاً في المجموعة لتتمكن من تعديل إعداداتها.")
        
    await show_panel(m, target_cid)

async def show_panel(m, chat_id):
    """عرض لوحة التحكم بالأزرار مع الحالة الحالية"""
    # تحديث الكاش لضمان دقة البيانات
    if chat_id in local_cache: del local_cache[chat_id]
    doc = await get_chat_doc(chat_id)
    prayers = doc.get("prayers", {})
    if not prayers: prayers = {k: True for k in CURRENT_RESOURCES.keys()}
    
    kb = []
    
    # الصف الأول: التحكم العام
    st_main = "مفعل" if doc.get("azan_active", True) else "معطل"
    kb.append([InlineKeyboardButton(f"الاذان العام : {st_main}", callback_data=f"set_main_{chat_id}")])
    
    # الصف الثاني: الأذكار
    st_dua = "مفعل" if doc.get("dua_active", True) else "معطل"
    st_ndua = "مفعل" if doc.get("night_dua_active", True) else "معطل"
    kb.append([
        InlineKeyboardButton(f"الصباح : {st_dua}", callback_data=f"set_dua_{chat_id}"),
        InlineKeyboardButton(f"المساء : {st_ndua}", callback_data=f"set_ndua_{chat_id}")
    ])

    # الصفوف التالية: الصلوات الفردية
    row = []
    for k, name in PRAYER_NAMES_AR.items():
        is_active = prayers.get(k, True)
        pst = "مفعل" if is_active else "معطل"
        row.append(InlineKeyboardButton(f"{name} : {pst}", callback_data=f"set_p_{k}_{chat_id}"))
        if len(row) == 2: kb.append(row); row = []
    if row: kb.append(row)

    kb.append([InlineKeyboardButton("تجربة الأذان", callback_data=f"test_azan_single_{chat_id}")])
    kb.append([InlineKeyboardButton("تحديث", callback_data=f"refresh_{chat_id}")])
    
    chat_title = str(chat_id)
    try:
        chat = await app.get_chat(chat_id)
        chat_title = chat.title
    except: pass

    text = f"إعدادات الأذان الخاصة بمجموعة: {chat_title}"
    
    try:
        if isinstance(m, Message): await m.reply_text(text, reply_markup=InlineKeyboardMarkup(kb))
        else: await m.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))
    except: pass

# معالج الضغط على الأزرار
@app.on_callback_query(filters.regex(r"^(set_|help_|close_|devset_|dev_cancel|test_azan|test_global|cmd_|refresh_)"), group=AZAN_GROUP)
async def cb_handler(_, q):
    data = q.data
    uid = q.from_user.id
    chat_id = q.message.chat.id
    
    if data == "cmd_close":
        if not await check_rights(uid, chat_id):
            return await q.answer("هذا الزر للمشرفين فقط", show_alert=True)
        return await q.message.delete()
        
    if data == "cmd_owner":
        if uid != MAIN_OWNER and uid not in DEVS:
            return await q.answer("هذا القسم خاص بمطور البوت فقط", show_alert=True)
        
        # إحصائيات سريعة للمطور
        active_count = await settings_db.count_documents({"azan_active": True})
        
        text = (
            "لوحة تحكم المطور:\n\n"
            f"عدد المجموعات المفعلة: {active_count}\n\n"
            "التحكم الكامل متاح عبر الأزرار أدناه:"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("تجربة الأذان (هنا)", callback_data=f"test_azan_single_{chat_id}")],
            [InlineKeyboardButton("تجربة عامة (للكل)", url=f"https://t.me/{(await app.get_me()).username}?start=test_global")],
            [InlineKeyboardButton("تغيير الاستيكر", callback_data="devset_menu_sticker")],
            [InlineKeyboardButton("رجوع", callback_data="cmd_back_main")]
        ])
        return await q.edit_message_text(text, reply_markup=kb)

    if data == "cmd_admin":
        if not await check_rights(uid, chat_id):
            return await q.answer("هذا القسم للمشرفين فقط", show_alert=True)
            
        bot_username = (await app.get_me()).username
        settings_link = f"https://t.me/{bot_username}?start=azset_{chat_id}"
        
        text = (
            "أوامر المشرفين:\n"
            "يمكنك التحكم السريع عبر الأزرار.\n"
            "لضبط صلوات محددة يرجى الانتقال للإعدادات المتقدمة في الخاص."
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("الإعدادات المتقدمة (خاص)", url=settings_link)],
            [InlineKeyboardButton("رجوع", callback_data="cmd_back_main")]
        ])
        return await q.edit_message_text(text, reply_markup=kb)

    if data == "cmd_back_main":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("أوامر المطور", callback_data="cmd_owner")],
            [InlineKeyboardButton("إعدادات المشرفين", callback_data="cmd_admin")],
            [InlineKeyboardButton("إغلاق اللوحة", callback_data="cmd_close")]
        ])
        return await q.edit_message_text("القائمة الرئيسية:", reply_markup=kb)

    if data.startswith("refresh_"):
        target = int(data.split("_")[1])
        if not await check_rights(uid, target): return await q.answer("لا تملك صلاحية")
        await show_panel(q, target)
        await q.answer("تم تحديث البيانات")
        return

    if data.startswith("test_azan_single_"):
        target_id = int(data.split("_")[3])
        if not await check_rights(uid, target_id):
             return await q.answer("للمشرفين فقط", show_alert=True)
        
        await q.answer("جاري بدء البث التجريبي...", show_alert=False)
        try:
            await start_azan_stream(target_id, "Fajr", force_test=True)
        except Exception as e:
            await q.message.reply(f"حدث خطأ: {e}")
        return

    # معالجة تغيير الإعدادات (Setters)
    if data.startswith("set_"):
        parts = data.split("_")
        
        if "_p_" in data: # تغيير صلاة محددة
            pkey = parts[2]
            target_cid = int(parts[3])
            
            if not await check_rights(uid, target_cid): return await q.answer("لا تملك صلاحية")

            doc = await get_chat_doc(target_cid)
            new_st = not doc.get("prayers", {}).get(pkey, True)
            await update_doc(target_cid, new_st, new_st, sub_key=pkey)
            await show_panel(q, target_cid)
            await q.answer(f"تم تغيير حالة صلاة {PRAYER_NAMES_AR[pkey]}")
            
        elif "main" in data: # تغيير الأذان العام
            target_cid = int(parts[-1])
            if not await check_rights(uid, target_cid): return await q.answer("لا تملك صلاحية")
            doc = await get_chat_doc(target_cid)
            new_val = not doc.get("azan_active", True)
            await update_doc(target_cid, "azan_active", new_val)
            await show_panel(q, target_cid)
            await q.answer("تم تغيير الحالة العامة")
            
        elif "_dua_" in data or "_ndua_" in data: # تغيير الأذكار
            target_cid = int(parts[-1])
            if not await check_rights(uid, target_cid): return await q.answer("لا تملك صلاحية")
            doc = await get_chat_doc(target_cid)
            key = "dua_active" if "_dua_" in data else "night_dua_active"
            new_val = not doc.get(key, True)
            await update_doc(target_cid, key, new_val)
            await show_panel(q, target_cid)

    # معالجة أدوات المطور
    elif data == "dev_cancel":
        if uid in admin_state: del admin_state[uid]
        return await q.message.delete()
    
    elif data == "devset_menu_sticker":
        kb = []
        for k, n in PRAYER_NAMES_AR.items():
            kb.append([InlineKeyboardButton(f"استيكر {n}", callback_data=f"devset_sticker_{k}")])
        kb.append([InlineKeyboardButton("استيكر الأذكار", callback_data="devset_sticker_dua")])
        kb.append([InlineKeyboardButton("إلغاء", callback_data="dev_cancel")])
        await q.edit_message_text("اختر الاستيكر الذي تريد تغييره:", reply_markup=InlineKeyboardMarkup(kb))
        
    elif data.startswith("devset_"):
        if uid not in DEVS: return await q.answer("للمطورين فقط", show_alert=True)
        parts = data.split("_")
        atype, pkey = parts[1], parts[2]
        
        if pkey == "dua":
            admin_state[uid] = {"action": "wait_dua_sticker"}
            await q.message.edit_text("قم بإرسال الاستيكر الجديد للأذكار الآن:")
        else:
            admin_state[uid] = {"action": f"wait_azan_{atype}", "key": pkey}
            req = "استيكر" if atype == "sticker" else "رابط"
            await q.message.edit_text(f"قم بإرسال {req} صلاة {PRAYER_NAMES_AR[pkey]} الآن:")


# --- [ 4. استقبال مدخلات المطور ] ---

@app.on_message((filters.text | filters.sticker) & filters.user(DEVS), group=AZAN_GROUP)
async def dev_input_wait(_, m):
    uid = m.from_user.id
    if uid not in admin_state: return
    state = admin_state[uid]
    action = state["action"]

    # تغيير استيكر الأذكار
    if action == "wait_dua_sticker":
        if not m.sticker: return await m.reply("يرجى إرسال ملف استيكر فقط.")
        global CURRENT_DUA_STICKER
        CURRENT_DUA_STICKER = m.sticker.file_id
        await resources_db.update_one({"type": "dua_sticker"}, {"$set": {"sticker_id": CURRENT_DUA_STICKER}}, upsert=True)
        await m.reply("تم حفظ استيكر الأذكار الجديد بنجاح.")
        del admin_state[uid]

    # تغيير استيكر أو رابط الأذان
    elif action.startswith("wait_azan_"): 
        pkey = state["key"]
        
        if "sticker" in action:
            if not m.sticker: return await m.reply("يرجى إرسال ملف استيكر فقط.")
            CURRENT_RESOURCES[pkey]["sticker"] = m.sticker.file_id
            await resources_db.update_one({"type": "azan_data"}, {"$set": {f"data.{pkey}.sticker": m.sticker.file_id}}, upsert=True)
            await m.reply(f"تم تغيير استيكر صلاة {PRAYER_NAMES_AR[pkey]} بنجاح.")
            
        elif "link" in action:
            if not m.text: return
            vid = extract_vidid(m.text)
            if not vid: return await m.reply("الرابط غير صالح، يرجى التأكد من إرسال رابط يوتيوب صحيح.")
            CURRENT_RESOURCES[pkey]["link"] = m.text
            CURRENT_RESOURCES[pkey]["vidid"] = vid
            await resources_db.update_one({"type": "azan_data"}, {"$set": {f"data.{pkey}.link": m.text, f"data.{pkey}.vidid": vid}}, upsert=True)
            await m.reply(f"تم تغيير صوت الأذان لصلاة {PRAYER_NAMES_AR[pkey]} بنجاح.")
            
        del admin_state[uid]

@app.on_message(filters.regex(r"^تغيير رابط الاذان") & filters.user(DEVS), group=AZAN_GROUP)
async def change_azan_link_cmd(client, message):
    if message.from_user.id != MAIN_OWNER: return
    
    args = message.text.split()
    if len(args) < 4:
        return await message.reply("طريقة الاستخدام الصحيحة:\nتغيير رابط الاذان الفجر")
    
    prayer_name = args[-1]
    prayer_key = PRAYER_NAMES_REV.get(prayer_name)
    
    if not prayer_key:
        return await message.reply(f"اسم الصلاة غير صحيح. الأسماء المتاحة هي: {', '.join(PRAYER_NAMES_AR.values())}")
        
    admin_state[message.from_user.id] = {"action": "wait_azan_link", "key": prayer_key}
    await message.reply(f"قم بإرسال رابط اليوتيوب الجديد لأذان صلاة {prayer_name} الآن:")


# --- [ 5. أوامر المالك الإجبارية والتشخيصية ] ---

@app.on_message(filters.regex("^/start test_global") & filters.private, group=AZAN_GROUP)
async def test_global_start_trigger(_, m):
    if m.from_user.id != MAIN_OWNER: return
    status_msg = await m.reply("جاري بدء البث في جميع المجموعات المفعلة...")
    count = 0
    
    async for doc in settings_db.find({"azan_active": True}):
        cid = doc.get("chat_id")
        if cid:
            asyncio.create_task(start_azan_stream(cid, "Fajr", force_test=True))
            count += 1
            if count % 10 == 0: await status_msg.edit(f"تم الارسال لـ {count} مجموعة...")
            await asyncio.sleep(0.5)
            
    await status_msg.edit(f"تم الانتهاء من إرسال البث التجريبي لـ {count} مجموعة.")

@app.on_message(filters.regex(r"^تست دعاء صباح$") & filters.user(DEVS), group=AZAN_GROUP)
async def tst_morning(client, message):
    if message.from_user.id != MAIN_OWNER: return
    await message.reply("جاري تجربة أذكار الصباح في هذه المحادثة...")
    from .az_utils import send_duas_batch, MORNING_DUAS
    await send_duas_batch(MORNING_DUAS, None, "أذكار الصباح", target_chat_id=message.chat.id)

@app.on_message(filters.regex(r"^تست دعاء مساء$") & filters.user(DEVS), group=AZAN_GROUP)
async def tst_evening(client, message):
    if message.from_user.id != MAIN_OWNER: return
    await message.reply("جاري تجربة أذكار المساء في هذه المحادثة...")
    from .az_utils import send_duas_batch, NIGHT_DUAS
    await send_duas_batch(NIGHT_DUAS, None, "أذكار المساء", target_chat_id=message.chat.id)

@app.on_message(filters.regex(r"^فحص الاذان$") & filters.group, group=AZAN_GROUP)
async def activate_and_debug(client, message):
    """أمر تشخيصي للتحقق من سلامة النظام"""
    if not await check_rights(message.from_user.id, message.chat.id):
        return 
    
    log = "تقرير فحص حالة نظام الأذان:\n\n"
    msg = await message.reply_text(log + "جاري الاتصال بالخوادم...")
    
    # 1. فحص الداتابيز
    try:
        await settings_db.find_one({})
        log += "- قاعدة البيانات: متصلة\n"
    except Exception as e:
        log += f"- قاعدة البيانات: خطأ ({e})\n"
    
    # 2. فحص API المواقيت
    try:
        times = await get_azan_times()
        if times: log += "- مواقيت الصلاة: تم الجلب بنجاح\n"
        else: log += "- مواقيت الصلاة: لا يوجد استجابة\n"
    except Exception as e:
        log += f"- مواقيت الصلاة: خطأ ({e})\n"

    # 3. فحص المجدول
    if not scheduler.running:
        init_azan_scheduler()
        log += "- المجدول الزمني: كان متوقفاً وتمت إعادة تشغيله\n"
    else:
        log += "- المجدول الزمني: يعمل بشكل طبيعي\n"
        
    await msg.edit_text(log + "\nعملية الفحص مكتملة.")

# أوامر التحكم الإجباري (Force)
@app.on_message(filters.regex(r"^تفعيل الاذان الاجباري$") & filters.user(DEVS), group=AZAN_GROUP)
async def force_enable(_, m):
    if m.from_user.id != MAIN_OWNER: return
    msg = await m.reply("جاري التفعيل الإجباري لجميع المجموعات...")
    c = 0
    text_to_send = "تم تفعيل خدمة الأذان في هذه المجموعة من قبل مطور البوت."
    
    async for doc in settings_db.find({}):
        chat_id = doc.get("chat_id")
        await settings_db.update_one(
            {"_id": doc["_id"]}, 
            {"$set": {"azan_active": True, "forced_active": True}}
        )
        try: 
            await app.send_message(chat_id, text_to_send)
            c += 1
            if c % 20 == 0: await asyncio.sleep(1)
        except: pass
        
    local_cache.clear()
    await msg.edit_text(f"تم التفعيل الإجباري بنجاح لـ {c} مجموعة.")

@app.on_message(filters.regex(r"^قفل الاذان الاجباري$") & filters.user(DEVS), group=AZAN_GROUP)
async def force_disable(_, m):
    if m.from_user.id != MAIN_OWNER: return
    msg = await m.reply("جاري الإيقاف الإجباري لجميع المجموعات...")
    c = 0
    text_to_send = "تم إيقاف خدمة الأذان مؤقتاً للصيانة من قبل المطور."
    
    async for doc in settings_db.find({}):
        chat_id = doc.get("chat_id")
        await settings_db.update_one(
            {"_id": doc["_id"]}, 
            {"$set": {"azan_active": False, "forced_active": False}}
        )
        try: 
            await app.send_message(chat_id, text_to_send)
            c += 1
        except: pass
        
    local_cache.clear()
    await msg.edit_text(f"تم الإيقاف بنجاح لـ {c} مجموعة.")
