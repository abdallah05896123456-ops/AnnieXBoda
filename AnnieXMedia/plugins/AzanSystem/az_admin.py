import asyncio
from datetime import datetime
from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import FloodWait

# استدعاء مكتبات السورس الأساسية
from AnnieXMedia import app
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
is_azan_system_started = False

@app.on_message(group=AZAN_GROUP + 1)
async def auto_start_azan_system_safe(_, __):
    """تشغيل المجدول تلقائياً لضمان الجاهزية"""
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
    chat_id = message.chat.id
    doc = await get_chat_doc(chat_id)
    
    if not doc.get("azan_active"):
        return await message.reply_text("خـدمـة الـأذان مـتـوقـفـة حـالـيـاً فـي هـذه الـمـجـمـوعـة.")

    times = await get_azan_times()
    if not times:
        return await message.reply_text("تـعـذر الـوصـول إلـى خـادم الـمـواقـيـت.")

    now = datetime.now()
    text = "مـواقـيـت الـصـلاة بـتـوقـيـت الـقـاهـرة لـهـذا الـيـوم:\n\n"
    next_prayer = None
    min_diff = float('inf')

    for key, name in PRAYER_NAMES_AR.items():
        t = times[key]
        prayer_time = datetime.strptime(t, "%H:%M").replace(year=now.year, month=now.month, day=now.day)
        display_time = prayer_time.strftime("%I:%M %p")
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
        text += f"الـصـلاة الـقـادمـة هـي {name} (يـتـبـقـى {hours} سـاعـة و {minutes} دقـيـقـة)."
    else:
        text += "انـتـهـت كـافـة الـصـلـوات لـهـذا الـيـوم."

    await message.reply_text(text)

# --- [ 2. أوامر المشرفين (التحكم النصي) ] ---

@app.on_message(filters.regex(r"^تفعيل الاذان$") & filters.group & ~BANNED_USERS, group=AZAN_GROUP)
async def admin_enable_azan(_, m):
    if not await check_rights(m.from_user.id, m.chat.id): return
    doc = await get_chat_doc(m.chat.id)
    if doc.get("azan_active"): return await m.reply_text("الـخـدمـة مـفـعـلـة بـالـفـعـل.")
    await update_doc(m.chat.id, "azan_active", True)
    await m.reply_text("تـم تـفـعـيـل خـدمـة الـأذان.")

@app.on_message(filters.regex(r"^قفل الاذان$") & filters.group & ~BANNED_USERS, group=AZAN_GROUP)
async def admin_disable_azan(_, m):
    if not await check_rights(m.from_user.id, m.chat.id): return
    doc = await get_chat_doc(m.chat.id)
    if doc.get("forced_active", False) and m.from_user.id not in DEVS:
        return await m.reply_text("عـذراً، الـخـدمـة مـفـعـلـة إجـبـاريـاً.")
    if not doc.get("azan_active"): return await m.reply_text("الـخـدمـة مـتـوقـفـة بـالـفـعـل.")
    await update_doc(m.chat.id, "azan_active", False)
    await m.reply_text("تـم تـعـطـيـل خـدمـة الـأذان.")

@app.on_message(filters.regex(r"^(تفعيل الاذكار|تفعيل الدعاء)$") & filters.group & ~BANNED_USERS, group=AZAN_GROUP)
async def admin_enable_duas(_, m):
    if not await check_rights(m.from_user.id, m.chat.id): return
    await update_doc(m.chat.id, "dua_active", True)
    await update_doc(m.chat.id, "night_dua_active", True)
    await m.reply_text("تـم تـفـعـيـل الـأذكـار.")

@app.on_message(filters.regex(r"^(قفل الاذكار|قفل الدعاء)$") & filters.group & ~BANNED_USERS, group=AZAN_GROUP)
async def admin_disable_duas(_, m):
    if not await check_rights(m.from_user.id, m.chat.id): return
    doc = await get_chat_doc(m.chat.id)
    if doc.get("forced_dua_active", False) and m.from_user.id not in DEVS:
        return await m.reply_text("عـذراً، الـأذكـار مـفـعـلـة إجـبـاريـاً.")
    await update_doc(m.chat.id, "dua_active", False)
    await update_doc(m.chat.id, "night_dua_active", False)
    await m.reply_text("تـم تـعـطـيـل الـأذكـار.")


# --- [ 3. القسم الأول: دليل الأوامر النصية (المانيول) ] ---

@app.on_message(filters.regex(r"^أوامر الاذان$") & filters.group & ~BANNED_USERS, group=AZAN_GROUP)
async def azan_manual_panel(_, m):
    text = (
        "**دلـيـل أوامـر الـأذان الـنـصـيـة:**\n\n"
        "هـذه الـقـائـمـة تـعـرض لـك الـأوامـر لـنـسـخـهـا.\n"
        "لـلـتـحـكـم الـتـفـاعـلـي اسـتـخـدم أمـر (الاذان)."
    )
    # زراير تعرض نصوص فقط (بدون تحكم)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("• أوامـر الـمـالـك •", callback_data="man_owner"), InlineKeyboardButton("• أوامـر الـأدمـن •", callback_data="man_admin")],
        [InlineKeyboardButton("• إغـلاق •", callback_data="cmd_close")]
    ])
    await m.reply_text(text, reply_markup=kb)


# --- [ 4. القسم الثاني: لوحة التحكم التفاعلية (الريموت) ] ---

@app.on_message(filters.regex(r"^(اعدادات الاذان|انلاين الاذان|الاذان)$") & filters.group & ~BANNED_USERS, group=AZAN_GROUP)
async def azan_control_panel(_, m):
    text = (
        "**لـوحـة الـتـحـكـم بـالـأذان:**\n\n"
        "مـن هـنـا يـمـكـنـك الـتـحـكـم فـي الـإعـدادات مـبـاشـرة.\n"
        "اخـتـر الـقـسـم:"
    )
    # زراير تحكم (Settings, Test, Force Enable, etc)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("• تـحـكـم الـمـالـك •", callback_data="cmd_owner"), InlineKeyboardButton("• تـحـكـم الـأدمـن •", callback_data="cmd_admin")],
        [InlineKeyboardButton("• إغـلاق •", callback_data="cmd_close")]
    ])
    await m.reply_text(text, reply_markup=kb)


# استقبال رابط الإعدادات في الخاص
@app.on_message(filters.regex("^/start azset_") & filters.private, group=AZAN_GROUP)
async def open_panel_private(_, m):
    try: target_cid = int(m.text.split("azset_")[1])
    except: return
    if not await check_rights(m.from_user.id, target_cid):
        return await m.reply("يـجـب أن تـكـون مـشـرفـاً.") 
    await show_panel(m, target_cid)

async def show_panel(m, chat_id):
    """عرض أزرار تفعيل وتعطيل الصلوات"""
    if chat_id in local_cache: del local_cache[chat_id]
    doc = await get_chat_doc(chat_id)
    prayers = doc.get("prayers", {})
    if not prayers: prayers = {k: True for k in CURRENT_RESOURCES.keys()}
    
    kb = []
    st_main = "مـفـعـل" if doc.get("azan_active", True) else "مـعـطـل"
    kb.append([InlineKeyboardButton(f"الـأذان الـعـام : {st_main}", callback_data=f"set_main_{chat_id}")])
    
    st_dua = "مـفـعـل" if doc.get("dua_active", True) else "مـعـطـل"
    st_ndua = "مـفـعـل" if doc.get("night_dua_active", True) else "مـعـطـل"
    kb.append([
        InlineKeyboardButton(f"الـصـبـاح : {st_dua}", callback_data=f"set_dua_{chat_id}"),
        InlineKeyboardButton(f"الـمـسـاء : {st_ndua}", callback_data=f"set_ndua_{chat_id}")
    ])

    row = []
    for k, name in PRAYER_NAMES_AR.items():
        is_active = prayers.get(k, True)
        pst = "مـفـعـل" if is_active else "مـعـطـل"
        row.append(InlineKeyboardButton(f"{name} : {pst}", callback_data=f"set_p_{k}_{chat_id}"))
        if len(row) == 2: kb.append(row); row = []
    if row: kb.append(row)

    kb.append([InlineKeyboardButton("تـجـربـة الـأذان", callback_data=f"test_azan_single_{chat_id}")])
    kb.append([InlineKeyboardButton("تـحـديـث", callback_data=f"refresh_{chat_id}")])
    
    text = "إعـدادات الـأذان الـتـفـصـيـلـيـة:"
    try:
        if isinstance(m, Message): await m.reply_text(text, reply_markup=InlineKeyboardMarkup(kb))
        else: await m.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))
    except: pass

# --- [ معالجة الكيبورد (Callbacks) ] ---

@app.on_callback_query(filters.regex(r"^(set_|help_|close_|devset_|dev_cancel|test_azan|test_global|cmd_|man_|refresh_|inline_azan_)"), group=AZAN_GROUP)
async def cb_handler(_, q):
    data = q.data
    uid = q.from_user.id
    chat_id = q.message.chat.id
    
    if data == "cmd_close":
        if not await check_rights(uid, chat_id): return await q.answer("لـلـمـشـرفـيـن فـقـط")
        return await q.message.delete()
    
    # --- [ أزرار الرجوع ] ---
    if data == "cmd_back_main": # رجوع للوحة التحكم
        text = "لـوحـة الـتـحـكـم بـالـأذان (الـريـمـوت):"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("• تـحـكـم الـمـالـك •", callback_data="cmd_owner"), InlineKeyboardButton("• تـحـكـم الـأدمـن •", callback_data="cmd_admin")],
            [InlineKeyboardButton("• إغـلاق •", callback_data="cmd_close")]
        ])
        return await q.edit_message_text(text, reply_markup=kb)

    if data == "man_back_main": # رجوع للمانيول
        text = "دلـيـل أوامـر الـأذان الـنـصـيـة:"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("• أوامـر الـمـالـك •", callback_data="man_owner"), InlineKeyboardButton("• أوامـر الـأدمـن •", callback_data="man_admin")],
            [InlineKeyboardButton("• إغـلاق •", callback_data="cmd_close")]
        ])
        return await q.edit_message_text(text, reply_markup=kb)

    # ============================
    # 1. معالجات المانيول (نصوص فقط)
    # ============================
    
    if data == "man_owner":
        if uid != MAIN_OWNER and uid not in DEVS: return await q.answer("لـلـمـطـور فـقـط", show_alert=True)
        text = (
            "**أوامـر الـمـالـك (نـسـخ فـقـط):**\n\n"
            "- `تفعيل انلاين اذان`\n"
            "- `قفل انلاين اذان`\n"
            "- `نشر الصلاة علي النبي`\n"
            "- `نشر اذكار`\n"
            "- `نشر عام [الرسالة]`\n"
            "- `تفعيل الاذان الاجباري`\n"
            "- `قفل الاذان الاجباري`\n"
            "- `تفعيل الدعاء الاجباري`\n"
            "- `تغيير رابط الاذان [اسم الصلاة]`\n"
            "- `تست دعاء صباح`\n"
            "- `تست دعاء مساء`"
        )
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("• رجـوع •", callback_data="man_back_main")]])
        return await q.edit_message_text(text, reply_markup=kb)

    if data == "man_admin":
        if not await check_rights(uid, chat_id): return await q.answer("لـلـمـشـرفـيـن فـقـط", show_alert=True)
        text = (
            "**أوامـر الـأدمـن (نـسـخ فـقـط):**\n\n"
            "- `تفعيل الاذان`\n"
            "- `قفل الاذان`\n"
            "- `اعدادات الاذان`\n"
            "- `تفعيل الاذكار`\n"
            "- `قفل الاذكار`\n"
            "- `فحص الاذان`\n"
            "- `الصلاة`\n"
            "- `اذكار الصباح`\n"
            "- `اذكار المساء`"
        )
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("• رجـوع •", callback_data="man_back_main")]])
        return await q.edit_message_text(text, reply_markup=kb)


    # ============================
    # 2. معالجات التحكم (الريموت)
    # ============================

    if data == "cmd_owner":
        if uid != MAIN_OWNER and uid not in DEVS: return await q.answer("لـلـمـطـور فـقـط", show_alert=True)
        
        # هنا بقا فيه زراير التحكم
        text = "**لـوحـة تـحـكـم الـمـطـور:**"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("تـفـعـيـل انـلايـن اذان", callback_data="inline_azan_enable"), InlineKeyboardButton("قـفـل انـلايـن اذان", callback_data="inline_azan_disable")],
            [InlineKeyboardButton("تـجـربـة الـأذان (هـنـا)", callback_data=f"test_azan_single_{chat_id}")],
            [InlineKeyboardButton("تـجـربـة عـامـة (لـلـكـل)", url=f"https://t.me/{(await app.get_me()).username}?start=test_global")],
            [InlineKeyboardButton("تـغـيـيـر الـاسـتـيـكـر", callback_data="devset_menu_sticker")],
            [InlineKeyboardButton("• رجـوع •", callback_data="cmd_back_main")]
        ])
        return await q.edit_message_text(text, reply_markup=kb)

    if data == "cmd_admin":
        if not await check_rights(uid, chat_id): return await q.answer("لـلـمـشـرفـيـن فـقـط", show_alert=True)
        
        bot_username = (await app.get_me()).username
        settings_link = f"https://t.me/{bot_username}?start=azset_{chat_id}"
        
        text = "**تـحـكـم الـمـشـرفـيـن:**\nلـلـتـحـكـم فـي صـلـوات مـحـددة، انـتـقـل لـلـخـاص."
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("الـإعـدادات الـمـتـقـدمـة", url=settings_link)],
            [InlineKeyboardButton("• رجـوع •", callback_data="cmd_back_main")]
        ])
        return await q.edit_message_text(text, reply_markup=kb)


    # ============================
    # 3. تنفيذ الأوامر (Actions)
    # ============================

    if data == "inline_azan_enable":
        if uid != MAIN_OWNER and uid not in DEVS: return await q.answer("لـلـمـطـور فـقـط")
        await q.answer("جـارٍ الـتـفـعـيـل...")
        async for doc in settings_db.find({}):
            await settings_db.update_one({"_id": doc["_id"]}, {"$set": {"azan_active": True, "forced_active": True}})
        local_cache.clear()
        await q.message.edit_text("تـم تـفـعـيـل انـلايـن اذان (إجـبـاريـاً) لـلـجـمـيـع.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("• رجـوع •", callback_data="cmd_owner")]]))
        return

    if data == "inline_azan_disable":
        if uid != MAIN_OWNER and uid not in DEVS: return await q.answer("لـلـمـطـور فـقـط")
        await q.answer("جـارٍ الـإيـقـاف...")
        async for doc in settings_db.find({}):
            await settings_db.update_one({"_id": doc["_id"]}, {"$set": {"azan_active": False, "forced_active": False}})
        local_cache.clear()
        await q.message.edit_text("تـم قـفـل انـلايـن اذان (إجـبـاريـاً) لـلـجـمـيـع.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("• رجـوع •", callback_data="cmd_owner")]]))
        return
    
    if data.startswith("refresh_"):
        target = int(data.split("_")[1])
        if not await check_rights(uid, target): return await q.answer("لا تـمـلـك صـلاحـيـة")
        await show_panel(q, target)
        await q.answer("تـم الـتـحـديـث")
        return

    if data.startswith("test_azan_single_"):
        target_id = int(data.split("_")[3])
        if not await check_rights(uid, target_id): return await q.answer("لـلـمـشـرفـيـن فـقـط")
        await q.answer("جـارٍ الـتـجـربـة...")
        try: await start_azan_stream(target_id, "Fajr", force_test=True)
        except: pass
        return

    if data.startswith("set_"):
        parts = data.split("_")
        target_cid = int(parts[-1])
        if not await check_rights(uid, target_cid): return await q.answer("لا تـمـلـك صـلاحـيـة")
        
        if "main" in data:
            doc = await get_chat_doc(target_cid)
            await update_doc(target_cid, "azan_active", not doc.get("azan_active", True))
        elif "dua" in data:
            doc = await get_chat_doc(target_cid)
            new_val = not doc.get("dua_active", True)
            await update_doc(target_cid, "dua_active", new_val)
            await update_doc(target_cid, "night_dua_active", new_val)
        elif "_p_" in data:
            pkey = parts[2]
            doc = await get_chat_doc(target_cid)
            new_st = not doc.get("prayers", {}).get(pkey, True)
            await update_doc(target_cid, new_st, new_st, sub_key=pkey)
            
        await show_panel(q, target_cid)
        return

    # زر إلغاء
    if data == "dev_cancel":
        if uid in admin_state: del admin_state[uid]
        return await q.message.delete()
    
    # قائمة الاستيكر
    if data == "devset_menu_sticker":
        kb = []
        for k, n in PRAYER_NAMES_AR.items():
            kb.append([InlineKeyboardButton(f"اسـتـيـكـر {n}", callback_data=f"devset_sticker_{k}")])
        kb.append([InlineKeyboardButton("اسـتـيـكـر الـأذكـار", callback_data="devset_sticker_dua")])
        kb.append([InlineKeyboardButton("• إلـغـاء •", callback_data="dev_cancel")])
        await q.edit_message_text("اخـتـر الـاسـتـيـكـر:", reply_markup=InlineKeyboardMarkup(kb))
        
    elif data.startswith("devset_"):
        if uid not in DEVS: return await q.answer("لـلـمـطـوريـن فـقـط", show_alert=True)
        parts = data.split("_")
        atype, pkey = parts[1], parts[2]
        
        cancel_kb = InlineKeyboardMarkup([[InlineKeyboardButton("• إلـغـاء •", callback_data="dev_cancel")]])
        
        if pkey == "dua":
            admin_state[uid] = {"action": "wait_dua_sticker"}
            await q.message.edit_text("قـم بـإرسـال الـاسـتـيـكـر الـجـديـد:", reply_markup=cancel_kb)
        else:
            admin_state[uid] = {"action": f"wait_azan_{atype}", "key": pkey}
            req = "اسـتـيـكـر" if atype == "sticker" else "رابـط"
            await q.message.edit_text(f"قـم بـإرسـال {req} صـلاة {PRAYER_NAMES_AR[pkey]} الـآن:", reply_markup=cancel_kb)


# --- [ 4. استقبال مدخلات المطور ] ---

@app.on_message((filters.text | filters.sticker) & filters.user(DEVS), group=AZAN_GROUP)
async def dev_input_wait(_, m):
    uid = m.from_user.id
    if uid not in admin_state: return
    state = admin_state[uid]
    action = state["action"]

    if action == "wait_dua_sticker":
        if not m.sticker: return await m.reply("يـرجـى إرسـال اسـتـيـكـر.")
        global CURRENT_DUA_STICKER
        CURRENT_DUA_STICKER = m.sticker.file_id
        await resources_db.update_one({"type": "dua_sticker"}, {"$set": {"sticker_id": CURRENT_DUA_STICKER}}, upsert=True)
        await m.reply("تـم الـحـفـظ.")
        del admin_state[uid]

    elif action.startswith("wait_azan_"): 
        pkey = state["key"]
        
        if "sticker" in action:
            if not m.sticker: return await m.reply("يـرجـى إرسـال اسـتـيـكـر.")
            CURRENT_RESOURCES[pkey]["sticker"] = m.sticker.file_id
            await resources_db.update_one({"type": "azan_data"}, {"$set": {f"data.{pkey}.sticker": m.sticker.file_id}}, upsert=True)
            await m.reply(f"تـم تـغـيـيـر اسـتـيـكـر {PRAYER_NAMES_AR[pkey]}.")
            
        elif "link" in action:
            if not m.text: return
            vid = extract_vidid(m.text)
            if not vid: return await m.reply("الـرابـط غـيـر صـالـح.")
            CURRENT_RESOURCES[pkey]["link"] = m.text
            CURRENT_RESOURCES[pkey]["vidid"] = vid
            await resources_db.update_one({"type": "azan_data"}, {"$set": {f"data.{pkey}.link": m.text, f"data.{pkey}.vidid": vid}}, upsert=True)
            await m.reply(f"تـم تـغـيـيـر صـوت {PRAYER_NAMES_AR[pkey]}.")
            
        del admin_state[uid]

@app.on_message(filters.regex(r"^تغيير رابط الاذان") & filters.user(DEVS), group=AZAN_GROUP)
async def change_azan_link_cmd(client, message):
    if message.from_user.id != MAIN_OWNER: return
    
    args = message.text.split()
    if len(args) < 4:
        return await message.reply("طـريـقـة الـاسـتـخـدام:\nتـغـيـيـر رابـط الـاذان الـفـجـر")
    
    prayer_name = args[-1]
    prayer_key = PRAYER_NAMES_REV.get(prayer_name)
    
    if not prayer_key:
        return await message.reply(f"اسـم الـصـلاة غـيـر صـحـيـح.")
        
    admin_state[message.from_user.id] = {"action": "wait_azan_link", "key": prayer_key}
    await message.reply(f"قـم بـإرسـال رابـط الـيـوتـيـوب الـجـديـد لـأذان صـلاة {prayer_name} الـآن:")


# --- [ 5. أوامر المالك الإجبارية والتشخيصية ] ---

@app.on_message(filters.regex("^/start test_global") & filters.private, group=AZAN_GROUP)
async def test_global_start_trigger(_, m):
    if m.from_user.id != MAIN_OWNER: return
    status_msg = await m.reply("جـارٍ بـدء الـبـث الـعـام...")
    count = 0
    
    async for doc in settings_db.find({"azan_active": True}):
        cid = doc.get("chat_id")
        if cid:
            asyncio.create_task(start_azan_stream(cid, "Fajr", force_test=True))
            count += 1
            if count % 10 == 0: await status_msg.edit(f"تـم الـارسـال لـ {count}...")
            await asyncio.sleep(0.5)
            
    await status_msg.edit(f"تـم الـانـتـهـاء.")

@app.on_message(filters.regex(r"^تست دعاء صباح$") & filters.user(DEVS), group=AZAN_GROUP)
async def tst_morning(client, message):
    if message.from_user.id != MAIN_OWNER: return
    await message.reply("جـارٍ تـجـربـة أذكـار الـصـبـاح...")
    from .az_utils import send_duas_batch, MORNING_DUAS
    await send_duas_batch(MORNING_DUAS, None, "أذكـار الـصـبـاح", target_chat_id=message.chat.id)

@app.on_message(filters.regex(r"^تست دعاء مساء$") & filters.user(DEVS), group=AZAN_GROUP)
async def tst_evening(client, message):
    if message.from_user.id != MAIN_OWNER: return
    await message.reply("جـارٍ تـجـربـة أذكـار الـمـسـاء...")
    from .az_utils import send_duas_batch, NIGHT_DUAS
    await send_duas_batch(NIGHT_DUAS, None, "أذكـار الـمـسـاء", target_chat_id=message.chat.id)

@app.on_message(filters.regex(r"^فحص الاذان$") & filters.group, group=AZAN_GROUP)
async def activate_and_debug(client, message):
    if not await check_rights(message.from_user.id, message.chat.id): return 
    
    log = "تـقـريـر الـفـحـص:\n\n"
    msg = await message.reply_text(log + "جـارٍ الـفـحـص...")
    
    try:
        await settings_db.find_one({})
        log += "- الـقـاعـدة: مـتـصـلـة\n"
    except Exception as e:
        log += f"- الـقـاعـدة: خـطـأ ({e})\n"
    
    try:
        times = await get_azan_times()
        if times: log += "- الـمـواقـيـت: تـم الـجـلـب\n"
        else: log += "- الـمـواقـيـت: لا يـوجـد رد\n"
    except Exception as e:
        log += f"- الـمـواقـيـت: خـطـأ ({e})\n"

    if not scheduler.running:
        init_azan_scheduler()
        log += "- الـمـجـدول: تـم إعـادة الـتـشـغـيـل\n"
    else:
        log += "- الـمـجـدول: يـعـمـل\n"
        
    await msg.edit_text(log + "\nتـم.")

# --- [ 6. أوامر التحكم في انلاين اذان (تفعيل/قفل) ] ---

@app.on_message(filters.regex(r"^(تفعيل انلاين اذان|تفعيل الاذان الاجباري)$") & filters.user(DEVS), group=AZAN_GROUP)
async def force_enable(_, m):
    if m.from_user.id != MAIN_OWNER: return
    msg = await m.reply("جـارٍ تـفـعـيـل الـكـل...")
    c = 0
    
    async for doc in settings_db.find({}):
        chat_id = doc.get("chat_id")
        await settings_db.update_one(
            {"_id": doc["_id"]}, 
            {"$set": {"azan_active": True, "forced_active": True}}
        )
        try: 
            await app.send_message(chat_id, "تـم تـفـعـيـل خـدمـة الـأذان إجـبـاريـاً.")
            c += 1
            if c % 20 == 0: await asyncio.sleep(1)
        except: pass
        
    local_cache.clear()
    await msg.edit_text(f"تـم الـتـفـعـيـل لـ {c} مـجـمـوعـة.")

@app.on_message(filters.regex(r"^(قفل انلاين اذان|قفل الاذان الاجباري)$") & filters.user(DEVS), group=AZAN_GROUP)
async def force_disable(_, m):
    if m.from_user.id != MAIN_OWNER: return
    msg = await m.reply("جـارٍ الـقـفـل لـلـكـل...")
    c = 0
    
    async for doc in settings_db.find({}):
        chat_id = doc.get("chat_id")
        await settings_db.update_one(
            {"_id": doc["_id"]}, 
            {"$set": {"azan_active": False, "forced_active": False}}
        )
        try: 
            await app.send_message(chat_id, "تـم إيـقـاف خـدمـة الـأذان مـؤقـتـاً.")
            c += 1
        except: pass
        
    local_cache.clear()
    await msg.edit_text(f"تـم الـقـفـل لـ {c} مـجـمـوعـة.")
