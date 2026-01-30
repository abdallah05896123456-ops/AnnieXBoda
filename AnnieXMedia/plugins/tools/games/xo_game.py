# Authored By Certified Coders 2026
# Module: XO Game Advanced System (Games) - Arabic & Points

import asyncio
import random
import json
import os
from pyrogram import filters, Client
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from pyrogram.errors import MessageNotModified

from AnnieXMedia import app
import config

# ─── إعدادات اللعبة ───

GAME_IMAGE = "https://files.catbox.moe/gy85j3.jpg"

# تخزين بيانات اللعبة النشطة
active_games = {} 
waiting_for_input = {} 

# رموز اللعبة
SYM_X = "❌"
SYM_O = "⭕"
SYM_E = "◻️" 

WINNING_COMBINATIONS = [
    [0, 1, 2], [3, 4, 5], [6, 7, 8], # أفقي
    [0, 3, 6], [1, 4, 7], [2, 5, 8], # عمودي
    [0, 4, 8], [2, 4, 6]             # قطري
]

# ─── نظام النقاط (تخزين محلي) ───

POINTS_FILE = "xo_points.json"

class PointsManager:
    def __init__(self):
        self.points = self.load_points()

    def load_points(self):
        if not os.path.exists(POINTS_FILE):
            return {}
        try:
            with open(POINTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}

    def save_points(self):
        with open(POINTS_FILE, "w", encoding="utf-8") as f:
            json.dump(self.points, f, indent=4)

    def add_points(self, user_id, amount):
        uid = str(user_id)
        current = self.points.get(uid, 0)
        self.points[uid] = current + amount
        self.save_points()
        return self.points[uid]

    def get_points(self, user_id):
        return self.points.get(str(user_id), 0)

    def get_leaderboard(self):
        # ترتيب أعلى 5 لاعبين
        sorted_users = sorted(self.points.items(), key=lambda x: x[1], reverse=True)[:5]
        return sorted_users

pm = PointsManager()

# ─── منطق الذكاء الاصطناعي ───

def get_ai_move(board, difficulty):
    # وضع الغش (من لوحة التحكم)
    if hasattr(config, "XO_CHEAT") and config.XO_CHEAT:
        empty_spots = [i for i, x in enumerate(board) if x == SYM_E]
        return random.choice(empty_spots) if empty_spots else None

    # 1. صعب: يحاول الفوز، ثم يصد الخصم، ثم يسيطر على المركز
    if difficulty == "Hard":
        # محاولة الفوز
        for combo in WINNING_COMBINATIONS:
            line = [board[i] for i in combo]
            if line.count(SYM_O) == 2 and line.count(SYM_E) == 1:
                return combo[line.index(SYM_E)]
        # صد الخصم
        for combo in WINNING_COMBINATIONS:
            line = [board[i] for i in combo]
            if line.count(SYM_X) == 2 and line.count(SYM_E) == 1:
                return combo[line.index(SYM_E)]
        # السيطرة على المنتصف
        if board[4] == SYM_E:
            return 4

    # 2. متوسط: يحاول الفوز فقط
    if difficulty == "Medium":
        for combo in WINNING_COMBINATIONS:
            line = [board[i] for i in combo]
            if line.count(SYM_O) == 2 and line.count(SYM_E) == 1:
                return combo[line.index(SYM_E)]

    # 3. سهل (أو عشوائي)
    empty_spots = [i for i, x in enumerate(board) if x == SYM_E]
    return random.choice(empty_spots) if empty_spots else None

# ─── دوال مساعدة ───

def check_winner(board):
    for combo in WINNING_COMBINATIONS:
        if board[combo[0]] == board[combo[1]] == board[combo[2]] and board[combo[0]] != SYM_E:
            return board[combo[0]]
    if SYM_E not in board:
        return "Draw"
    return None

def build_keyboard(board, game_id):
    buttons = []
    row = []
    for i, cell in enumerate(board):
        row.append(InlineKeyboardButton(cell, callback_data=f"xo_m_{game_id}_{i}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    return InlineKeyboardMarkup(buttons)

def format_name(user_id, first_name):
    return f"[{first_name}](tg://user?id={user_id})"

# ─── بداية اللعبة ───

@app.on_message(filters.command(["xo", "اكس او", "لعبة xo"], prefixes=["", "/", "!"]))
async def start_xo(client, message):
    if hasattr(config, "XO_ENABLED") and not config.XO_ENABLED:
        return await message.reply_text("تم تعطيل اللعبة حالياً من قبل المطور .")

    my_points = pm.get_points(message.from_user.id)
    text = (
        f"**مرحباً بك في لعبة XO المطورة .**\n"
        f"**نقاطك الحالية :** `{my_points}`\n"
        f"**معرف اللعبة :** `{message.id}`"
    )
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("لعب ضد بوت", callback_data=f"xo_pre_ai_{message.from_user.id}")],
        [InlineKeyboardButton("تحدي لاعب", callback_data=f"xo_req_{message.from_user.id}")],
        [InlineKeyboardButton("قائمة المتصدرين", callback_data=f"xo_top_{message.from_user.id}")]
    ])
    
    await message.reply_photo(
        photo=GAME_IMAGE,
        caption=text,
        reply_markup=keyboard
    )

# ─── معالجة القوائم ───

@app.on_callback_query(filters.regex(r"^xo_(pre_ai|sel_ai|req|top)_"))
async def xo_menu_callback(client, callback_query: CallbackQuery):
    data_parts = callback_query.data.split("_")
    action = data_parts[1] 
    
    if action == "sel": # xo_sel_ai_Diff_OwnerID
        owner_id = int(data_parts[4])
    else: # xo_pre_ai_OwnerID
        owner_id = int(data_parts[-1])

    user = callback_query.from_user
    chat_id = callback_query.message.chat.id
    msg_id = callback_query.message.id
    game_key = f"{chat_id}_{msg_id}"

    if user.id != owner_id:
        return await callback_query.answer("هذه اللعبة ليست لك .", show_alert=True)

    # 1. قائمة المتصدرين
    if action == "top":
        top_list = pm.get_leaderboard()
        txt = "**🏆 قائمة أفضل 5 لاعبين :**\n\n"
        if not top_list:
            txt += "لا يوجد لاعبين حتى الآن ."
        else:
            for idx, (uid, pts) in enumerate(top_list, 1):
                try:
                    u = await client.get_users(uid)
                    name = u.first_name
                except:
                    name = "لاعب غير معروف"
                txt += f"{idx}. {name} : {pts} نقطة\n"
        
        await callback_query.edit_message_caption(
            caption=txt,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("رجوع", callback_data=f"xo_main_{owner_id}")]])
        )

    # 2. اختيار الصعوبة (ضد البوت)
    elif action == "pre": 
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("سهل", callback_data=f"xo_sel_ai_Easy_{owner_id}"),
                InlineKeyboardButton("متوسط", callback_data=f"xo_sel_ai_Medium_{owner_id}"),
                InlineKeyboardButton("صعب", callback_data=f"xo_sel_ai_Hard_{owner_id}")
            ]
        ])
        await callback_query.edit_message_caption(
            caption="**اختر مستوى الصعوبة :**",
            reply_markup=keyboard
        )

    # 3. بدء اللعب ضد البوت
    elif action == "sel": 
        difficulty = data_parts[3]
        active_games[game_key] = {
            "board": [SYM_E] * 9,
            "turn": owner_id,
            "p1": owner_id,
            "p2": "AI",
            "p1_name": user.first_name,
            "p2_name": f"البوت ({difficulty})",
            "mode": "ai",
            "diff": difficulty
        }
        await update_game_message(client, callback_query.message, game_key)

    # 4. طلب تحدي لاعب
    elif action == "req":
        waiting_for_input[user.id] = {"chat_id": chat_id, "msg_id": msg_id}
        await callback_query.edit_message_caption(
            caption="**أرسل معرف (يوزر) اللاعب أو قم بالرد على رسالته لتبدأ التحدي .**",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("إلغاء", callback_data=f"xo_cancel_{owner_id}")]])
        )

@app.on_callback_query(filters.regex(r"^xo_main_"))
async def back_main(client, callback_query):
    # إعادة القائمة الرئيسية
    message = callback_query.message
    my_points = pm.get_points(callback_query.from_user.id)
    text = (
        f"**مرحباً بك في لعبة XO المطورة .**\n"
        f"**نقاطك الحالية :** `{my_points}`\n"
        f"**معرف اللعبة :** `{message.id}`"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("لعب ضد بوت", callback_data=f"xo_pre_ai_{callback_query.from_user.id}")],
        [InlineKeyboardButton("تحدي لاعب", callback_data=f"xo_req_{callback_query.from_user.id}")],
        [InlineKeyboardButton("قائمة المتصدرين", callback_data=f"xo_top_{callback_query.from_user.id}")]
    ])
    await callback_query.edit_message_caption(caption=text, reply_markup=keyboard)


# ─── معالجة الدعوة للتحدي ───

@app.on_message(filters.text & ~filters.command("xo") & filters.group)
async def handle_invite_input(client, message):
    user_id = message.from_user.id
    if user_id in waiting_for_input:
        if message.chat.id != waiting_for_input[user_id]["chat_id"]:
            return
            
        data = waiting_for_input.pop(user_id)
        original_msg_id = data["msg_id"]
        
        target_user = None
        # التحقق هل هو رد أم يوزر
        if message.reply_to_message:
            target_user = message.reply_to_message.from_user
        else:
            try:
                target_user = await client.get_users(message.text)
            except:
                await message.reply_text("لم يتم العثور على اللاعب .")
                return

        if target_user.id == user_id:
             await message.reply_text("لا يمكنك تحدي نفسك .")
             return
        if target_user.is_bot:
             await message.reply_text("لا يمكنك تحدي البوتات .")
             return

        text = f"**لقد تمت دعوتك لتحدي XO**\n**بواسطة :** {message.from_user.mention}"
        
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("قبول", callback_data=f"xo_acc_{user_id}_{target_user.id}_{original_msg_id}"),
                InlineKeyboardButton("رفض", callback_data=f"xo_dny_{user_id}_{target_user.id}_{original_msg_id}")
            ]
        ])
        await message.reply_text(text, reply_markup=keyboard)

# ─── الاستجابة للدعوة ───

@app.on_callback_query(filters.regex(r"^xo_(acc|dny)_"))
async def invite_response(client, callback_query):
    data = callback_query.data.split("_")
    action, p1_id, p2_id, origin_msg_id = data[1], int(data[2]), int(data[3]), int(data[4])
    
    if callback_query.from_user.id != p2_id:
        return await callback_query.answer("هذه الدعوة ليست لك .", show_alert=True)

    if action == "dny":
        await callback_query.message.edit_text("تم رفض الدعوة .")
    else:
        game_key = f"{callback_query.message.chat.id}_{origin_msg_id}"
        p1_name = (await client.get_users(p1_id)).first_name
        p2_name = callback_query.from_user.first_name
        
        active_games[game_key] = {
            "board": [SYM_E] * 9,
            "turn": p1_id,
            "p1": p1_id,
            "p2": p2_id,
            "p1_name": p1_name,
            "p2_name": p2_name,
            "mode": "pvp"
        }
        
        await callback_query.message.delete()
        try:
            origin_msg = await client.get_messages(callback_query.message.chat.id, origin_msg_id)
            await update_game_message(client, origin_msg, game_key)
        except:
            await callback_query.message.reply_text("حدث خطأ في الوصول للرسالة الأصلية .")

@app.on_callback_query(filters.regex(r"^xo_cancel_"))
async def cancel_req(client, callback_query):
    if callback_query.from_user.id == int(callback_query.data.split("_")[2]):
        waiting_for_input.pop(callback_query.from_user.id, None)
        await callback_query.message.delete()

# ─── منطق اللعب (التحركات) ───

@app.on_callback_query(filters.regex(r"^xo_m_"))
async def play_move(client, callback_query):
    data = callback_query.data.split("_")
    try:
        pos = int(data[-1])
        game_key = "_".join(data[2:-1])
    except:
        return await callback_query.answer("خطأ في البيانات .")

    game = active_games.get(game_key)
    if not game:
        return await callback_query.answer("انتهت صلاحية الجلسة .", show_alert=True)

    user_id = callback_query.from_user.id

    # التحقق من الدور
    if user_id != game["turn"]:
        if user_id in [game["p1"], game["p2"]] or (game["p2"] == "AI" and user_id == game["p1"]):
             return await callback_query.answer("هذا ليس دورك .", show_alert=True)
        else:
            return await callback_query.answer("أنت لست مشاركاً في هذه اللعبة .", show_alert=True)

    # التحقق من المكان الفارغ
    if game["board"][pos] != SYM_E:
        return await callback_query.answer("المكان مشغول !", show_alert=True)

    # تنفيذ الحركة
    symbol = SYM_X if user_id == game["p1"] else SYM_O
    game["board"][pos] = symbol
    
    # فحص الفوز
    winner = check_winner(game["board"])
    if winner:
        await end_game(client, callback_query.message, game, winner)
        del active_games[game_key]
        return

    # تبديل الدور
    if game["mode"] == "pvp":
        game["turn"] = game["p2"] if user_id == game["p1"] else game["p1"]
        await update_game_message(client, callback_query.message, game_key)
        
    elif game["mode"] == "ai":
        # دور البوت
        ai_pos = get_ai_move(game["board"], game.get("diff", "Easy"))
        if ai_pos is not None:
            game["board"][ai_pos] = SYM_O
            winner_ai = check_winner(game["board"])
            if winner_ai:
                await end_game(client, callback_query.message, game, winner_ai)
                del active_games[game_key]
                return
        game["turn"] = game["p1"]
        await update_game_message(client, callback_query.message, game_key)

# ─── دوال التحديث والإنهاء ───

async def update_game_message(client, message, game_key):
    game = active_games[game_key]
    
    turn_name = game["p1_name"] if game["turn"] == game["p1"] else game["p2_name"]
    sym_turn = SYM_X if game["turn"] == game["p1"] else SYM_O
    
    p1_link = format_name(game['p1'], game['p1_name'])
    p2_link = game['p2_name'] if game['p2'] == "AI" else format_name(game['p2'], game['p2_name'])
    
    text = (
        f"**المباراة : {SYM_X} ضد {SYM_O} .**\n\n"
        f"**اللاعبين : {p1_link} ضد {p2_link} .**\n\n"
        f"**الدور : {turn_name} ({sym_turn})**"
    )
    
    try:
        await message.edit_caption(
            caption=text,
            reply_markup=build_keyboard(game["board"], game_key)
        )
    except MessageNotModified:
        pass

async def end_game(client, message, game, winner):
    winner_name = ""
    points_msg = ""
    
    if winner == "Draw":
        result_text = "**انتهت المباراة : تعادل .**"
        # نقاط التعادل
        pm.add_points(game['p1'], 5)
        if game['mode'] == 'pvp':
            pm.add_points(game['p2'], 5)
        points_msg = "\n(تم إضافة 5 نقاط لكل لاعب)"
    else:
        is_p1_winner = (winner == SYM_X)
        win_id = game["p1"] if is_p1_winner else game["p2"]
        win_name_text = game["p1_name"] if is_p1_winner else game["p2_name"]
        
        # تنسيق اسم الفائز المطلوب
        if game['mode'] == 'ai' and not is_p1_winner:
            winner_name = f"البوت"
        else:
            winner_name = format_name(win_id, win_name_text)
            
        result_text = f"**الفائز في المباراه : {winner_name} !**"
        
        # إضافة النقاط للفائز
        if game['mode'] == 'pvp':
            pm.add_points(win_id, 20) # 20 نقطة للفوز على لاعب
            points_msg = "\n(تم إضافة 20 نقطة للفائز)"
        elif game['mode'] == 'ai' and is_p1_winner:
            # نقاط حسب الصعوبة
            diff_points = {"Easy": 5, "Medium": 10, "Hard": 15}
            pts = diff_points.get(game.get("diff"), 5)
            pm.add_points(win_id, pts)
            points_msg = f"\n(تم إضافة {pts} نقاط للفوز)"

    p1_link = format_name(game['p1'], game['p1_name'])
    p2_link = game['p2_name'] if game['p2'] == "AI" else format_name(game['p2'], game['p2_name'])

    final_text = (
        f"**المباراة : {SYM_X} ضد {SYM_O} .**\n\n"
        f"**اللاعبين : {p1_link} ضد {p2_link} .**\n\n"
        f"{result_text}{points_msg}"
    )
    
    # إزالة الأزرار التفاعلية
    buttons = []
    row = []
    for cell in game["board"]:
        row.append(InlineKeyboardButton(cell, callback_data="none"))
        if len(row) == 3:
            buttons.append(row)
            row = []
            
    await message.edit_caption(
        caption=final_text,
        reply_markup=InlineKeyboardMarkup(buttons)
    )
