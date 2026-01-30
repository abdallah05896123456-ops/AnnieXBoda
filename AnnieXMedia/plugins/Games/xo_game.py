# Authored By Certified Coders 2026
# Module: XO Game Advanced System (Games)

import asyncio
import random
from pyrogram import filters, Client
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from pyrogram.errors import MessageNotModified

from AnnieXMedia import app
import config

# ─── Game Configuration ───

GAME_IMAGE = "https://files.catbox.moe/gy85j3.jpg"

# Game Storage
active_games = {} 
waiting_for_input = {} 

# Board Symbols
SYM_X = "❌"
SYM_O = "⭕"
SYM_E = "◻️" 

WINNING_COMBINATIONS = [
    [0, 1, 2], [3, 4, 5], [6, 7, 8], # Horizontal
    [0, 3, 6], [1, 4, 7], [2, 5, 8], # Vertical
    [0, 4, 8], [2, 4, 6]             # Diagonal
]

# ─── AI Logic ───

def get_ai_move(board, difficulty):
    # Check for Cheat Mode (If active, force Easy/Random mode)
    if hasattr(config, "XO_CHEAT") and config.XO_CHEAT:
        empty_spots = [i for i, x in enumerate(board) if x == SYM_E]
        return random.choice(empty_spots) if empty_spots else None

    # 1. Hard Mode: Try to Win, then Block, then Center
    if difficulty == "Hard":
        # Try to win
        for combo in WINNING_COMBINATIONS:
            line = [board[i] for i in combo]
            if line.count(SYM_O) == 2 and line.count(SYM_E) == 1:
                return combo[line.index(SYM_E)]
        # Block opponent
        for combo in WINNING_COMBINATIONS:
            line = [board[i] for i in combo]
            if line.count(SYM_X) == 2 and line.count(SYM_E) == 1:
                return combo[line.index(SYM_E)]
        # Take center
        if board[4] == SYM_E:
            return 4

    # 2. Medium Mode: Try to Win only
    if difficulty == "Medium":
        for combo in WINNING_COMBINATIONS:
            line = [board[i] for i in combo]
            if line.count(SYM_O) == 2 and line.count(SYM_E) == 1:
                return combo[line.index(SYM_E)]

    # 3. Easy Mode (or fallthrough): Random Move
    empty_spots = [i for i, x in enumerate(board) if x == SYM_E]
    return random.choice(empty_spots) if empty_spots else None

# ─── Helper Functions ───

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

# ─── Game Entry Point ───

@app.on_message(filters.command(["xo", "اكس او", "لعبة xo"], prefixes=["", "/", "!"]))
async def start_xo(client, message):
    if hasattr(config, "XO_ENABLED") and not config.XO_ENABLED:
        return await message.reply_text("The game is currently disabled by the owner.")

    text = (
        f"**Hello Game Xo In Source**\n"
        f"**Game ID :** `{message.id}`"
    )
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Join Game", callback_data=f"xo_join_{message.from_user.id}")],
        [InlineKeyboardButton("Play vs AI", callback_data=f"xo_pre_ai_{message.from_user.id}")],
        [InlineKeyboardButton("Request Player", callback_data=f"xo_req_{message.from_user.id}")]
    ])
    
    await message.reply_photo(
        photo=GAME_IMAGE,
        caption=text,
        reply_markup=keyboard
    )

# ─── Menu Callback Handler ───

@app.on_callback_query(filters.regex(r"^xo_(join|pre_ai|sel_ai|req)_"))
async def xo_menu_callback(client, callback_query: CallbackQuery):
    data_parts = callback_query.data.split("_")
    action = data_parts[1] 
    
    # Handling ID extraction based on action length
    if action == "sel": # xo_sel_ai_Diff_OwnerID
        owner_id = int(data_parts[4])
    elif action == "pre": # xo_pre_ai_OwnerID
        owner_id = int(data_parts[3])
    else: # xo_join_OwnerID
        owner_id = int(data_parts[2])

    user = callback_query.from_user
    chat_id = callback_query.message.chat.id
    msg_id = callback_query.message.id
    game_key = f"{chat_id}_{msg_id}"

    # 1. Join Game (PvP)
    if action == "join":
        if user.id == owner_id:
            return await callback_query.answer("Wait for an opponent to join.", show_alert=True)
        
        active_games[game_key] = {
            "board": [SYM_E] * 9,
            "turn": owner_id,
            "p1": owner_id,
            "p2": user.id,
            "p1_name": (await client.get_users(owner_id)).first_name,
            "p2_name": user.first_name,
            "mode": "pvp"
        }
        await update_game_message(client, callback_query.message, game_key)

    # 2. Pre-AI (Choose Difficulty)
    elif action == "pre": # pre_ai
        if user.id != owner_id:
            return await callback_query.answer("This game is not for you.", show_alert=True)
            
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Easy", callback_data=f"xo_sel_ai_Easy_{owner_id}"),
                InlineKeyboardButton("Medium", callback_data=f"xo_sel_ai_Medium_{owner_id}"),
                InlineKeyboardButton("Hard", callback_data=f"xo_sel_ai_Hard_{owner_id}")
            ],
            [InlineKeyboardButton("Back", callback_data=f"xo_back_{owner_id}")] # Back Logic handled separately or ignored for simplicity
        ])
        await callback_query.edit_message_caption(
            caption="**Choose Difficulty Level :**",
            reply_markup=keyboard
        )

    # 3. Select AI Difficulty & Start
    elif action == "sel": # sel_ai
        if user.id != owner_id:
            return await callback_query.answer("This game is not for you.", show_alert=True)
        
        difficulty = data_parts[3] # Easy/Medium/Hard
        
        active_games[game_key] = {
            "board": [SYM_E] * 9,
            "turn": owner_id,
            "p1": owner_id,
            "p2": "AI",
            "p1_name": user.first_name,
            "p2_name": f"AI ({difficulty})",
            "mode": "ai",
            "diff": difficulty
        }
        await update_game_message(client, callback_query.message, game_key)

    # 4. Request Player
    elif action == "req":
        if user.id != owner_id:
            return await callback_query.answer("This game is not for you.", show_alert=True)
            
        waiting_for_input[user.id] = {"chat_id": chat_id, "msg_id": msg_id}
        
        await callback_query.edit_message_caption(
            caption="**Send the username or ID of the player you want to invite.**",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Cancel", callback_data=f"xo_cancel_{owner_id}")]])
        )

# ─── Invite Handler ───

@app.on_message(filters.text & ~filters.command("xo") & filters.group)
async def handle_invite_input(client, message):
    user_id = message.from_user.id
    if user_id in waiting_for_input:
        if message.chat.id != waiting_for_input[user_id]["chat_id"]:
            return
            
        target = message.text
        data = waiting_for_input.pop(user_id)
        original_msg_id = data["msg_id"]
        
        try:
            target_user = await client.get_users(target)
        except:
            return await message.reply_text("User not found.")

        text = f"**You have been invited to an XO Game**\n**By:** {message.from_user.mention}"
        
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Accept", callback_data=f"xo_acc_{user_id}_{target_user.id}_{original_msg_id}"),
                InlineKeyboardButton("Refuse", callback_data=f"xo_dny_{user_id}_{target_user.id}_{original_msg_id}")
            ]
        ])
        await message.reply_text(text, reply_markup=keyboard)

# ─── Invite Response ───

@app.on_callback_query(filters.regex(r"^xo_(acc|dny)_"))
async def invite_response(client, callback_query):
    data = callback_query.data.split("_")
    action, p1_id, p2_id, origin_msg_id = data[1], int(data[2]), int(data[3]), int(data[4])
    
    if callback_query.from_user.id != p2_id:
        return await callback_query.answer("This invite is not for you.", show_alert=True)

    if action == "dny":
        await callback_query.message.edit_text("Invitation declined.")
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
            await callback_query.message.reply_text("Error accessing the original game message.")

@app.on_callback_query(filters.regex(r"^xo_cancel_"))
async def cancel_req(client, callback_query):
    if callback_query.from_user.id == int(callback_query.data.split("_")[2]):
        waiting_for_input.pop(callback_query.from_user.id, None)
        await callback_query.message.delete()

# ─── Game Logic (Move Handling) ───

@app.on_callback_query(filters.regex(r"^xo_m_"))
async def play_move(client, callback_query):
    data = callback_query.data.split("_")
    # Structure: xo_m_chatId_msgId_position
    try:
        pos = int(data[-1])
        game_key = "_".join(data[2:-1])
    except:
        return await callback_query.answer("Data Error.")

    game = active_games.get(game_key)
    if not game:
        return await callback_query.answer("Game Session Expired.", show_alert=True)

    user_id = callback_query.from_user.id

    # Turn Check
    if user_id != game["turn"]:
        if user_id in [game["p1"], game["p2"]] or (game["p2"] == "AI" and user_id == game["p1"]):
             return await callback_query.answer("It is not your turn!", show_alert=True)
        else:
            return await callback_query.answer("You are not in this game.", show_alert=True)

    # Empty Spot Check
    if game["board"][pos] != SYM_E:
        return await callback_query.answer("Spot taken!", show_alert=True)

    # Execute Move
    symbol = SYM_X if user_id == game["p1"] else SYM_O
    game["board"][pos] = symbol
    
    # Check Win
    winner = check_winner(game["board"])
    if winner:
        await end_game(client, callback_query.message, game, winner)
        del active_games[game_key]
        return

    # Switch Turn
    if game["mode"] == "pvp":
        game["turn"] = game["p2"] if user_id == game["p1"] else game["p1"]
        await update_game_message(client, callback_query.message, game_key)
        
    elif game["mode"] == "ai":
        # AI Turn
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

# ─── Update & End Functions ───

async def update_game_message(client, message, game_key):
    game = active_games[game_key]
    
    turn_name = game["p1_name"] if game["turn"] == game["p1"] else game["p2_name"]
    sym_turn = SYM_X if game["turn"] == game["p1"] else SYM_O
    
    # Formatting Usernames
    p1_link = format_name(game['p1'], game['p1_name'])
    p2_link = game['p2_name'] if game['p2'] == "AI" else format_name(game['p2'], game['p2_name'])
    
    text = (
        f"**Games : {SYM_X} VS {SYM_O} .**\n\n"
        f"**Players : {p1_link} VS {p2_link} .**\n\n"
        f"**Turn : {turn_name} ({sym_turn})**"
    )
    
    try:
        await message.edit_caption(
            caption=text,
            reply_markup=build_keyboard(game["board"], game_key)
        )
    except MessageNotModified:
        pass

async def end_game(client, message, game, winner):
    if winner == "Draw":
        result_text = "**Game Over : Draw !**"
    else:
        win_name = game["p1_name"] if winner == SYM_X else game["p2_name"]
        result_text = f"**Winner : {win_name} ({winner}) !**"

    p1_link = format_name(game['p1'], game['p1_name'])
    p2_link = game['p2_name'] if game['p2'] == "AI" else format_name(game['p2'], game['p2_name'])

    final_text = (
        f"**Games : {SYM_X} VS {SYM_O} .**\n\n"
        f"**Players : {p1_link} VS {p2_link} .**\n\n"
        f"{result_text}"
    )
    
    # Remove interactivity
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
