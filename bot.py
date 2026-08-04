# ============================================================
# 🎮 ربات حرفه‌ای بازی دو نفره برای روبیکا (فقط با توکن)
# ============================================================
# 💰 سیستم کمیسیون: ۱۰٪ از هر بازی به حساب مالک ربات واریز می‌شود
# 🔥 بهترین بازی‌های دو نفره: سنگ کاغذ قیچی، تاس، فوتبال، حدس عدد
# ============================================================

import asyncio
import random
import sqlite3
import re
from datetime import datetime

from rubika import Client, filters
from rubika.types import Message, CallbackQuery
from rubika.keyboard import InlineKeyboard, InlineKeyboardButton

# ========== تنظیمات ==========
BOT_TOKEN = "FFCBI0PAKVSLWTWEKLBFDTRHFHNFJRVLCETMMNKCGBBHFQCKUQFFRTLWRBUGDRKA"  # توکن ربات
ADMIN_USER_ID = "u0If7GJ01a6b90d62c1ac6f0162a465e"  # گوید ادمین (مالک ربات)

# تنظیمات بازی
GAME_PRICES = [50, 100, 200, 500, 1000]  # مبالغ شرط
MIN_WITHDRAW_COINS = 100
COIN_TO_TOMAN = 1000
COMMISSION_RATE = 0.10  # ۱۰٪ کمیسیون

# ========== دیتابیس ==========
class Database:
    def __init__(self, db_file="game_bot.db"):
        self.conn = sqlite3.connect(db_file, check_same_thread=False)
        self.create_tables()
    
    def create_tables(self):
        cursor = self.conn.cursor()
        
        # کاربران
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                guid TEXT PRIMARY KEY,
                username TEXT,
                coins INTEGER DEFAULT 100,
                total_games INTEGER DEFAULT 0,
                total_wins INTEGER DEFAULT 0,
                total_commission INTEGER DEFAULT 0,  -- کمیسیون پرداخت شده به مالک
                last_seen TIMESTAMP,
                join_date TIMESTAMP,
                is_banned BOOLEAN DEFAULT FALSE
            )
        """)
        
        # اتاق‌های بازی
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rooms (
                room_code TEXT PRIMARY KEY,
                creator_guid TEXT,
                opponent_guid TEXT,
                bet_amount INTEGER,
                game_type TEXT,
                status TEXT DEFAULT 'waiting',
                winner_guid TEXT,
                commission INTEGER DEFAULT 0,
                created_at TIMESTAMP,
                player1_choice TEXT,
                player2_choice TEXT,
                FOREIGN KEY (creator_guid) REFERENCES users(guid),
                FOREIGN KEY (opponent_guid) REFERENCES users(guid)
            )
        """)
        
        # صف بازی سریع
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS quick_queue (
                guid TEXT PRIMARY KEY,
                bet_amount INTEGER,
                game_type TEXT,
                joined_at TIMESTAMP
            )
        """)
        
        # زیرمجموعه‌ها
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_guid TEXT,
                referred_guid TEXT UNIQUE,
                is_active BOOLEAN DEFAULT FALSE,
                games_played INTEGER DEFAULT 0,
                join_date TIMESTAMP
            )
        """)
        
        # ماموریت روزانه
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_missions (
                user_guid TEXT PRIMARY KEY,
                games_played INTEGER DEFAULT 0,
                last_played DATE,
                last_claimed DATE
            )
        """)
        
        # درخواست‌های برداشت
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS withdrawals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_guid TEXT,
                coins INTEGER,
                toman INTEGER,
                card_number TEXT,
                card_holder TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
        """)
        
        # تاریخچه بازی‌ها (برای گزارش)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS game_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                room_code TEXT,
                player1_guid TEXT,
                player2_guid TEXT,
                bet_amount INTEGER,
                game_type TEXT,
                winner_guid TEXT,
                commission INTEGER,
                played_at TIMESTAMP
            )
        """)
        
        self.conn.commit()
    
    def get_user(self, guid):
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM users WHERE guid = ?", (guid,))
        return cursor.fetchone()
    
    def create_user(self, guid, username):
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO users (guid, username, last_seen, join_date)
            VALUES (?, ?, ?, ?)
        """, (guid, username, datetime.now(), datetime.now()))
        self.conn.commit()
    
    def update_coins(self, guid, amount):
        cursor = self.conn.cursor()
        cursor.execute("UPDATE users SET coins = coins + ? WHERE guid = ?", (amount, guid))
        self.conn.commit()
    
    def add_commission(self, guid, amount):
        cursor = self.conn.cursor()
        cursor.execute("UPDATE users SET total_commission = total_commission + ? WHERE guid = ?", (amount, guid))
        self.conn.commit()
    
    def add_referral(self, referrer_guid, referred_guid):
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO referrals (referrer_guid, referred_guid, join_date)
            VALUES (?, ?, ?)
        """, (referrer_guid, referred_guid, datetime.now()))
        self.conn.commit()
    
    def get_referral_stats(self, guid):
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM referrals WHERE referrer_guid = ?", (guid,))
        total = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM referrals WHERE referrer_guid = ? AND is_active = 1", (guid,))
        active = cursor.fetchone()[0]
        return {"total": total, "active": active}
    
    def add_daily_game(self, guid):
        today = datetime.now().date()
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO daily_missions (user_guid, games_played, last_played)
            VALUES (?, 1, ?)
            ON CONFLICT(user_guid) DO UPDATE SET
                games_played = CASE 
                    WHEN last_played = ? THEN games_played + 1 
                    ELSE 1 
                END,
                last_played = ?
        """, (guid, today, today, today))
        self.conn.commit()
    
    def get_daily_progress(self, guid):
        today = datetime.now().date()
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT games_played, last_claimed FROM daily_missions 
            WHERE user_guid = ? AND last_played = ?
        """, (guid, today))
        row = cursor.fetchone()
        if row:
            return {"played": row[0], "claimed": row[1] == str(today) if row[1] else False}
        return {"played": 0, "claimed": False}
    
    def save_game_history(self, room_code, player1, player2, bet, game_type, winner, commission):
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO game_history 
            (room_code, player1_guid, player2_guid, bet_amount, game_type, winner_guid, commission, played_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (room_code, player1, player2, bet, game_type, winner, commission, datetime.now()))
        self.conn.commit()

# ========== ربات اصلی ==========
bot = Client(
    session="game_bot",
    bot_token=BOT_TOKEN  # فقط توکن
)

db = Database()
temp_data = {}

# ========== منوها ==========
def main_menu():
    return InlineKeyboard([
        [InlineKeyboardButton("🏠 ساخت اتاق", callback_data="create_room")],
        [InlineKeyboardButton("🚀 بازی سریع", callback_data="quick_game")],
        [InlineKeyboardButton("💰 سکه‌ها", callback_data="my_coins")],
        [InlineKeyboardButton("👥 زیرمجموعه‌ها", callback_data="referrals")],
        [InlineKeyboardButton("🎯 ماموریت روزانه", callback_data="daily_mission")],
        [InlineKeyboardButton("💎 برداشت", callback_data="withdraw")],
        [InlineKeyboardButton("🏆 آمار", callback_data="stats")],
        [InlineKeyboardButton("📊 پنل ادمین", callback_data="admin_panel")]
    ])

def price_menu(callback_data_prefix):
    keyboard = InlineKeyboard()
    row = []
    for price in GAME_PRICES:
        row.append(InlineKeyboardButton(f"{price}💰", callback_data=f"{callback_data_prefix}_{price}"))
        if len(row) == 2:
            keyboard.row(*row)
            row = []
    if row:
        keyboard.row(*row)
    keyboard.row(InlineKeyboardButton("🔙 برگشت", callback_data="back_to_main"))
    return keyboard

def game_type_menu(room_code=None, bet_amount=None):
    keyboard = InlineKeyboard([
        [InlineKeyboardButton("🪨 سنگ کاغذ قیچی", callback_data=f"game_rps_{room_code or '0'}_{bet_amount or 0}")],
        [InlineKeyboardButton("🎲 تاس", callback_data=f"game_dice_{room_code or '0'}_{bet_amount or 0}")],
        [InlineKeyboardButton("⚽ فوتبال", callback_data=f"game_football_{room_code or '0'}_{bet_amount or 0}")],
        [InlineKeyboardButton("🔢 حدس عدد", callback_data=f"game_guess_{room_code or '0'}_{bet_amount or 0}")],
        [InlineKeyboardButton("🔙 برگشت", callback_data="back_to_main")]
    ])
    return keyboard

# ========== دستورات ==========
@bot.on_message(filters.command("شروع"))
async def start_command(client, message: Message):
    guid = message.author_guid
    username = message.author_username or f"کاربر_{guid[:8]}"
    
    db.create_user(guid, username)
    
    # بررسی referral
    if message.text and " " in message.text:
        parts = message.text.split()
        if len(parts) > 1 and parts[1].startswith("ref_"):
            referrer = parts[1].replace("ref_", "")
            if referrer != guid:
                db.add_referral(referrer, guid)
                await message.reply(f"✅ شما توسط یک کاربر دعوت شدید!")
    
    await message.reply(
        f"🎮 به ربات حرفه‌ای بازی دو نفره خوش اومدی {username}!\n\n"
        f"💰 سکه اولیه: ۱۰۰\n"
        f"🔥 کمیسیون هر بازی: ۱۰٪ به مالک ربات\n\n"
        f"از منوی زیر یکی رو انتخاب کن:",
        reply_markup=main_menu()
    )

@bot.on_callback_query("back_to_main")
async def back_to_main(callback: CallbackQuery):
    await callback.message.edit_text(
        "🎮 منوی اصلی:",
        reply_markup=main_menu()
    )
    await callback.answer()

# ========== ساخت اتاق ==========
@bot.on_callback_query("create_room")
async def create_room(callback: CallbackQuery):
    await callback.message.edit_text(
        "💰 مبلغ شرط رو انتخاب کن:",
        reply_markup=price_menu("room_price")
    )
    await callback.answer()

@bot.on_callback_query(lambda c: c.data.startswith("room_price_"))
async def set_room_price(callback: CallbackQuery):
    bet_amount = int(callback.data.replace("room_price_", ""))
    guid = callback.message.author_guid
    
    user = db.get_user(guid)
    if not user or user[2] < bet_amount:
        await callback.answer(f"❌ سکه کافی نیست! نیاز به {bet_amount} سکه داری", show_alert=True)
        return
    
    room_code = str(random.randint(100000, 999999))
    
    cursor = db.conn.cursor()
    cursor.execute("""
        INSERT INTO rooms (room_code, creator_guid, bet_amount, status, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (room_code, guid, bet_amount, "waiting", datetime.now()))
    db.conn.commit()
    
    temp_data[f"room_{room_code}"] = {"creator": guid, "price": bet_amount}
    
    await callback.message.edit_text(
        f"✅ اتاق ساخته شد!\n\n"
        f"🔑 کد اتاق: `{room_code}`\n"
        f"💰 مبلغ شرط: {bet_amount} سکه\n"
        f"🔥 کمیسیون: {int(bet_amount * COMMISSION_RATE * 2)} سکه (۱۰٪ از جایزه)\n\n"
        f"حالا نوع بازی رو انتخاب کن:",
        reply_markup=game_type_menu(room_code, bet_amount)
    )
    await callback.answer()

@bot.on_callback_query(lambda c: c.data.startswith("game_"))
async def select_game_type(callback: CallbackQuery):
    parts = callback.data.split("_")
    game_type = parts[1]
    room_code = parts[2]
    bet_amount = int(parts[3])
    guid = callback.message.author_guid
    
    cursor = db.conn.cursor()
    cursor.execute("UPDATE rooms SET game_type = ? WHERE room_code = ?", (game_type, room_code))
    db.conn.commit()
    
    # نمایش پیام انتظار
    game_names = {
        "rps": "سنگ کاغذ قیچی",
        "dice": "تاس",
        "football": "فوتبال",
        "guess": "حدس عدد"
    }
    
    await callback.message.edit_text(
        f"🏠 اتاق {room_code}\n"
        f"💰 شرط: {bet_amount} سکه\n"
        f"🎮 بازی: {game_names.get(game_type, game_type)}\n"
        f"🔥 کمیسیون: {int(bet_amount * COMMISSION_RATE * 2)} سکه\n\n"
        f"📋 کد رو به دوستت بده تا وارد شه:\n"
        f"`/join {room_code}`\n\n"
        f"⏳ منتظر حریف...",
        reply_markup=InlineKeyboard([
            [InlineKeyboardButton("❌ لغو اتاق", callback_data=f"cancel_room_{room_code}")],
            [InlineKeyboardButton("🔙 برگشت", callback_data="back_to_main")]
        ])
    )
    await callback.answer()

@bot.on_callback_query(lambda c: c.data.startswith("cancel_room_"))
async def cancel_room(callback: CallbackQuery):
    room_code = callback.data.replace("cancel_room_", "")
    cursor = db.conn.cursor()
    cursor.execute("DELETE FROM rooms WHERE room_code = ?", (room_code,))
    db.conn.commit()
    await callback.message.edit_text("❌ اتاق لغو شد.", reply_markup=main_menu())
    await callback.answer()

# ========== ورود به اتاق ==========
@bot.on_message(filters.command("join"))
async def join_room(client, message: Message):
    guid = message.author_guid
    parts = message.text.split()
    
    if len(parts) < 2:
        await message.reply("❌ کد اتاق رو وارد کن: /join 123456")
        return
    
    room_code = parts[1]
    
    cursor = db.conn.cursor()
    cursor.execute("""
        SELECT creator_guid, bet_amount, game_type, status 
        FROM rooms WHERE room_code = ? AND status = 'waiting'
    """, (room_code,))
    room = cursor.fetchone()
    
    if not room:
        await message.reply("❌ اتاق پیدا نشد یا پر شده!")
        return
    
    creator_guid = room[0]
    bet_amount = room[1]
    game_type = room[2]
    
    if guid == creator_guid:
        await message.reply("❌ نمی‌تونی با خودت بازی کنی!")
        return
    
    user = db.get_user(guid)
    if not user or user[2] < bet_amount:
        await message.reply(f"❌ سکه کافی نیست! نیاز به {bet_amount} سکه داری")
        return
    
    cursor.execute("""
        UPDATE rooms 
        SET opponent_guid = ?, status = 'playing'
        WHERE room_code = ?
    """, (guid, room_code))
    db.conn.commit()
    
    # کم کردن سکه از هر دو (با احتساب کمیسیون از برنده بعداً)
    db.update_coins(creator_guid, -bet_amount)
    db.update_coins(guid, -bet_amount)
    
    db.add_daily_game(creator_guid)
    db.add_daily_game(guid)
    
    # شروع بازی
    if game_type == "rps":
        await start_rps(creator_guid, guid, room_code, bet_amount)
    elif game_type == "dice":
        await start_dice(creator_guid, guid, room_code, bet_amount)
    elif game_type == "football":
        await start_football(creator_guid, guid, room_code, bet_amount)
    elif game_type == "guess":
        await start_guess(creator_guid, guid, room_code, bet_amount)

# ========== بازی سنگ کاغذ قیچی ==========
async def start_rps(player1, player2, room_code, bet_amount):
    keyboard = InlineKeyboard([
        [
            InlineKeyboardButton("🪨 سنگ", callback_data=f"rps_{room_code}_rock"),
            InlineKeyboardButton("📄 کاغذ", callback_data=f"rps_{room_code}_paper"),
            InlineKeyboardButton("✂️ قیچی", callback_data=f"rps_{room_code}_scissors")
        ]
    ])
    
    msg = f"🎮 سنگ کاغذ قیچی\n💰 شرط: {bet_amount} سکه\n🔥 کمیسیون: {int(bet_amount * COMMISSION_RATE * 2)} سکه\n👥 حریف: {player2[:8]}...\n\nیک گزینه رو انتخاب کن:"
    
    await bot.send_message(player1, msg, reply_markup=keyboard)
    await bot.send_message(player2, msg, reply_markup=keyboard)

@bot.on_callback_query(lambda c: c.data.startswith("rps_"))
async def rps_choice(callback: CallbackQuery):
    parts = callback.data.split("_")
    room_code = parts[1]
    choice = parts[2]
    guid = callback.message.author_guid
    
    cursor = db.conn.cursor()
    cursor.execute("SELECT creator_guid, opponent_guid, bet_amount FROM rooms WHERE room_code = ?", (room_code,))
    room = cursor.fetchone()
    if not room:
        await callback.answer("❌ اتاق پیدا نشد!", show_alert=True)
        return
    
    creator, opponent, bet = room
    
    if guid == creator:
        cursor.execute("UPDATE rooms SET player1_choice = ? WHERE room_code = ?", (choice, room_code))
    elif guid == opponent:
        cursor.execute("UPDATE rooms SET player2_choice = ? WHERE room_code = ?", (choice, room_code))
    else:
        await callback.answer("❌ شما در این بازی نیستید!", show_alert=True)
        return
    
    db.conn.commit()
    await callback.answer(f"✅ انتخاب شما: {choice}")
    
    cursor.execute("SELECT player1_choice, player2_choice FROM rooms WHERE room_code = ?", (room_code,))
    choices = cursor.fetchone()
    
    if choices[0] and choices[1]:
        p1_choice = choices[0]
        p2_choice = choices[1]
        
        # محاسبه کمیسیون
        commission = int(bet * COMMISSION_RATE * 2)  # ۱۰٪ از کل جایزه
        
        if p1_choice == p2_choice:
            result = "مساوی"
            winner = None
            db.update_coins(creator, bet)
            db.update_coins(opponent, bet)
            commission = 0
        elif (p1_choice == "rock" and p2_choice == "scissors") or \
             (p1_choice == "scissors" and p2_choice == "paper") or \
             (p1_choice == "paper" and p2_choice == "rock"):
            result = "برنده: سازنده اتاق"
            winner = creator
            prize = bet * 2 - commission
            db.update_coins(creator, prize)
            db.add_commission(ADMIN_USER_ID, commission)
        else:
            result = "برنده: حریف"
            winner = opponent
            prize = bet * 2 - commission
            db.update_coins(opponent, prize)
            db.add_commission(ADMIN_USER_ID, commission)
        
        # ذخیره تاریخچه
        db.save_game_history(room_code, creator, opponent, bet, "rps", winner, commission)
        
        msg = f"🎮 نتیجه بازی سنگ کاغذ قیچی:\n\n"
        msg += f"🪨 سازنده: {p1_choice}\n"
        msg += f"✂️ حریف: {p2_choice}\n\n"
        msg += f"🏆 {result}\n"
        msg += f"💰 جایزه: {bet * 2 - commission if winner else bet} سکه\n"
        if commission > 0:
            msg += f"🔥 کمیسیون (۱۰٪): {commission} سکه به مالک ربات\n"
        
        for g in [creator, opponent]:
            await bot.send_message(g, msg, reply_markup=main_menu())
        
        cursor.execute("DELETE FROM rooms WHERE room_code = ?", (room_code,))
        db.conn.commit()

# ========== بازی تاس (حدس عدد) ==========
async def start_dice(player1, player2, room_code, bet_amount):
    keyboard = InlineKeyboard()
    row = []
    for i in range(1, 7):
        row.append(InlineKeyboardButton(str(i), callback_data=f"dice_{room_code}_{i}"))
        if len(row) == 3:
            keyboard.row(*row)
            row = []
    if row:
        keyboard.row(*row)
    
    msg = f"🎲 بازی تاس\n💰 شرط: {bet_amount} سکه\n🔥 کمیسیون: {int(bet_amount * COMMISSION_RATE * 2)} سکه\n👥 حریف: {player2[:8]}...\n\nیک عدد ۱ تا ۶ رو انتخاب کن:"
    
    await bot.send_message(player1, msg, reply_markup=keyboard)
    await bot.send_message(player2, msg, reply_markup=keyboard)

@bot.on_callback_query(lambda c: c.data.startswith("dice_"))
async def dice_choice(callback: CallbackQuery):
    parts = callback.data.split("_")
    room_code = parts[1]
    number = int(parts[2])
    guid = callback.message.author_guid
    
    cursor = db.conn.cursor()
    cursor.execute("SELECT creator_guid, opponent_guid, bet_amount FROM rooms WHERE room_code = ?", (room_code,))
    room = cursor.fetchone()
    if not room:
        await callback.answer("❌ اتاق پیدا نشد!", show_alert=True)
        return
    
    creator, opponent, bet = room
    
    if guid == creator:
        cursor.execute("UPDATE rooms SET player1_choice = ? WHERE room_code = ?", (str(number), room_code))
    elif guid == opponent:
        cursor.execute("UPDATE rooms SET player2_choice = ? WHERE room_code = ?", (str(number), room_code))
    else:
        await callback.answer("❌ شما در این بازی نیستید!", show_alert=True)
        return
    
    db.conn.commit()
    await callback.answer(f"✅ عدد شما: {number}")
    
    cursor.execute("SELECT player1_choice, player2_choice FROM rooms WHERE room_code = ?", (room_code,))
    choices = cursor.fetchone()
    
    if choices[0] and choices[1]:
        p1_num = int(choices[0])
        p2_num = int(choices[1])
        dice_result = random.randint(1, 6)
        
        commission = int(bet * COMMISSION_RATE * 2)
        
        p1_diff = abs(p1_num - dice_result)
        p2_diff = abs(p2_num - dice_result)
        
        if p1_diff == p2_diff:
            result = "مساوی"
            winner = None
            db.update_coins(creator, bet)
            db.update_coins(opponent, bet)
            commission = 0
        elif p1_diff < p2_diff:
            result = "برنده: سازنده اتاق"
            winner = creator
            prize = bet * 2 - commission
            db.update_coins(creator, prize)
            db.add_commission(ADMIN_USER_ID, commission)
        else:
            result = "برنده: حریف"
            winner = opponent
            prize = bet * 2 - commission
            db.update_coins(opponent, prize)
            db.add_commission(ADMIN_USER_ID, commission)
        
        db.save_game_history(room_code, creator, opponent, bet, "dice", winner, commission)
        
        msg = f"🎲 نتیجه بازی تاس:\n\n"
        msg += f"🎲 عدد تاس: {dice_result}\n"
        msg += f"👤 سازنده: {p1_num} (فاصله: {p1_diff})\n"
        msg += f"👤 حریف: {p2_num} (فاصله: {p2_diff})\n\n"
        msg += f"🏆 {result}\n"
        msg += f"💰 جایزه: {bet * 2 - commission if winner else bet} سکه\n"
        if commission > 0:
            msg += f"🔥 کمیسیون (۱۰٪): {commission} سکه به مالک ربات\n"
        
        for g in [creator, opponent]:
            await bot.send_message(g, msg, reply_markup=main_menu())
        
        cursor.execute("DELETE FROM rooms WHERE room_code = ?", (room_code,))
        db.conn.commit()

# ========== بازی فوتبال (شانسی) ==========
async def start_football(player1, player2, room_code, bet_amount):
    keyboard = InlineKeyboard([
        [InlineKeyboardButton("⚽ ضربه بزن!", callback_data=f"football_{room_code}_kick")]
    ])
    
    msg = f"⚽ بازی فوتبال\n💰 شرط: {bet_amount} سکه\n🔥 کمیسیون: {int(bet_amount * COMMISSION_RATE * 2)} سکه\n👥 حریف: {player2[:8]}...\n\nروی دکمه بزن تا ضربه بزنی:"
    
    await bot.send_message(player1, msg, reply_markup=keyboard)
    await bot.send_message(player2, msg, reply_markup=keyboard)

@bot.on_callback_query(lambda c: c.data.startswith("football_"))
async def football_kick(callback: CallbackQuery):
    parts = callback.data.split("_")
    room_code = parts[1]
    guid = callback.message.author_guid
    
    cursor = db.conn.cursor()
    cursor.execute("SELECT creator_guid, opponent_guid, bet_amount FROM rooms WHERE room_code = ?", (room_code,))
    room = cursor.fetchone()
    if not room:
        await callback.answer("❌ اتاق پیدا نشد!", show_alert=True)
        return
    
    creator, opponent, bet = room
    goal = random.choice([True, False])
    
    if guid == creator:
        cursor.execute("UPDATE rooms SET player1_choice = ? WHERE room_code = ?", ("goal" if goal else "miss", room_code))
    elif guid == opponent:
        cursor.execute("UPDATE rooms SET player2_choice = ? WHERE room_code = ?", ("goal" if goal else "miss", room_code))
    else:
        await callback.answer("❌ شما در این بازی نیستید!", show_alert=True)
        return
    
    db.conn.commit()
    await callback.answer(f"{'⚽ گل!' if goal else '❌ بیرون!'}")
    
    cursor.execute("SELECT player1_choice, player2_choice FROM rooms WHERE room_code = ?", (room_code,))
    choices = cursor.fetchone()
    
    if choices[0] and choices[1]:
        p1_result = choices[0]
        p2_result = choices[1]
        p1_goal = p1_result == "goal"
        p2_goal = p2_result == "goal"
        
        commission = int(bet * COMMISSION_RATE * 2)
        
        if p1_goal == p2_goal:
            result = "مساوی"
            winner = None
            db.update_coins(creator, bet)
            db.update_coins(opponent, bet)
            commission = 0
        elif p1_goal and not p2_goal:
            result = "برنده: سازنده اتاق"
            winner = creator
            prize = bet * 2 - commission
            db.update_coins(creator, prize)
            db.add_commission(ADMIN_USER_ID, commission)
        else:
            result = "برنده: حریف"
            winner = opponent
            prize = bet * 2 - commission
            db.update_coins(opponent, prize)
            db.add_commission(ADMIN_USER_ID, commission)
        
        db.save_game_history(room_code, creator, opponent, bet, "football", winner, commission)
        
        msg = f"⚽ نتیجه بازی فوتبال:\n\n"
        msg += f"👤 سازنده: {'⚽ گل' if p1_goal else '❌ بیرون'}\n"
        msg += f"👤 حریف: {'⚽ گل' if p2_goal else '❌ بیرون'}\n\n"
        msg += f"🏆 {result}\n"
        msg += f"💰 جایزه: {bet * 2 - commission if winner else bet} سکه\n"
        if commission > 0:
            msg += f"🔥 کمیسیون (۱۰٪): {commission} سکه به مالک ربات\n"
        
        for g in [creator, opponent]:
            await bot.send_message(g, msg, reply_markup=main_menu())
        
        cursor.execute("DELETE FROM rooms WHERE room_code = ?", (room_code,))
        db.conn.commit()

# ========== بازی حدس عدد ==========
async def start_guess(player1, player2, room_code, bet_amount):
    # عدد مخفی برای هر بازیکن
    secret1 = random.randint(1, 100)
    secret2 = random.randint(1, 100)
    
    temp_data[f"guess_{room_code}"] = {"p1": secret1, "p2": secret2}
    
    keyboard = InlineKeyboard()
    row = []
    for i in range(1, 11):
        row.append(InlineKeyboardButton(str(i*10), callback_data=f"guess_{room_code}_{i*10}"))
        if len(row) == 5:
            keyboard.row(*row)
            row = []
    if row:
        keyboard.row(*row)
    keyboard.row(InlineKeyboardButton("🎲 تصادفی!", callback_data=f"guess_{room_code}_random"))
    
    msg = f"🔢 بازی حدس عدد\n💰 شرط: {bet_amount} سکه\n🔥 کمیسیون: {int(bet_amount * COMMISSION_RATE * 2)} سکه\n👥 حریف: {player2[:8]}...\n\nیک عدد ۱۰ تا ۱۰۰ (با پله ۱۰) رو انتخاب کن:"
    
    await bot.send_message(player1, msg, reply_markup=keyboard)
    await bot.send_message(player2, msg, reply_markup=keyboard)

@bot.on_callback_query(lambda c: c.data.startswith("guess_"))
async def guess_choice(callback: CallbackQuery):
    parts = callback.data.split("_")
    room_code = parts[1]
    choice = parts[2]
    guid = callback.message.author_guid
    
    cursor = db.conn.cursor()
    cursor.execute("SELECT creator_guid, opponent_guid, bet_amount FROM rooms WHERE room_code = ?", (room_code,))
    room = cursor.fetchone()
    if not room:
        await callback.answer("❌ اتاق پیدا نشد!", show_alert=True)
        return
    
    creator, opponent, bet = room
    
    if choice == "random":
        number = random.choice(range(10, 101, 10))
    else:
        number = int(choice)
    
    if guid == creator:
        cursor.execute("UPDATE rooms SET player1_choice = ? WHERE room_code = ?", (str(number), room_code))
    elif guid == opponent:
        cursor.execute("UPDATE rooms SET player2_choice = ? WHERE room_code = ?", (str(number), room_code))
    else:
        await callback.answer("❌ شما در این بازی نیستید!", show_alert=True)
        return
    
    db.conn.commit()
    await callback.answer(f"✅ عدد شما: {number}")
    
    cursor.execute("SELECT player1_choice, player2_choice FROM rooms WHERE room_code = ?", (room_code,))
    choices = cursor.fetchone()
    
    if choices[0] and choices[1]:
        p1_num = int(choices[0])
        p2_num = int(choices[1])
        secret1 = temp_data.get(f"guess_{room_code}", {}).get("p1", random.randint(1, 100))
        secret2 = temp_data.get(f"guess_{room_code}", {}).get("p2", random.randint(1, 100))
        
        commission = int(bet * COMMISSION_RATE * 2)
        
        # هر کس به عدد مخفی خودش نزدیک‌تر باشه برنده است
        p1_diff = abs(p1_num - secret1)
        p2_diff = abs(p2_num - secret2)
        
        if p1_diff == p2_diff:
            result = "مساوی"
            winner = None
            db.update_coins(creator, bet)
            db.update_coins(opponent, bet)
            commission = 0
        elif p1_diff < p2_diff:
            result = "برنده: سازنده اتاق"
            winner = creator
            prize = bet * 2 - commission
            db.update_coins(creator, prize)
            db.add_commission(ADMIN_USER_ID, commission)
        else:
            result = "برنده: حریف"
            winner = opponent
            prize = bet * 2 - commission
            db.update_coins(opponent, prize)
            db.add_commission(ADMIN_USER_ID, commission)
        
        db.save_game_history(room_code, creator, opponent, bet, "guess", winner, commission)
        
        msg = f"🔢 نتیجه بازی حدس عدد:\n\n"
        msg += f"👤 سازنده: عدد {p1_num} (عدد مخفی: {secret1})\n"
        msg += f"👤 حریف: عدد {p2_num} (عدد مخفی: {secret2})\n\n"
        msg += f"🏆 {result}\n"
        msg += f"💰 جایزه: {bet * 2 - commission if winner else bet} سکه\n"
        if commission > 0:
            msg += f"🔥 کمیسیون (۱۰٪): {commission} سکه به مالک ربات\n"
        
        for g in [creator, opponent]:
            await bot.send_message(g, msg, reply_markup=main_menu())
        
        cursor.execute("DELETE FROM rooms WHERE room_code = ?", (room_code,))
        db.conn.commit()
        
        # پاک کردن داده موقت
        if f"guess_{room_code}" in temp_data:
            del temp_data[f"guess_{room_code}"]

# ========== بازی سریع ==========
@bot.on_callback_query("quick_game")
async def quick_game(callback: CallbackQuery):
    await callback.message.edit_text(
        "💰 مبلغ شرط رو انتخاب کن:",
        reply_markup=price_menu("quick_price")
    )
    await callback.answer()

@bot.on_callback_query(lambda c: c.data.startswith("quick_price_"))
async def quick_join(callback: CallbackQuery):
    bet_amount = int(callback.data.replace("quick_price_", ""))
    guid = callback.message.author_guid
    
    user = db.get_user(guid)
    if not user or user[2] < bet_amount:
        await callback.answer(f"❌ سکه کافی نیست!", show_alert=True)
        return
    
    cursor = db.conn.cursor()
    cursor.execute("SELECT guid, game_type FROM quick_queue WHERE bet_amount = ? ORDER BY joined_at ASC", (bet_amount,))
    queue = cursor.fetchone()
    
    if queue and queue[0] != guid:
        opponent = queue[0]
        game_type = queue[1] or "rps"
        
        cursor.execute("DELETE FROM quick_queue WHERE guid = ?", (opponent,))
        db.conn.commit()
        
        room_code = str(random.randint(100000, 999999))
        cursor.execute("""
            INSERT INTO rooms (room_code, creator_guid, opponent_guid, bet_amount, game_type, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (room_code, opponent, guid, bet_amount, game_type, "playing", datetime.now()))
        db.conn.commit()
        
        db.update_coins(opponent, -bet_amount)
        db.update_coins(guid, -bet_amount)
        
        db.add_daily_game(opponent)
        db.add_daily_game(guid)
        
        await callback.message.edit_text(
            f"✅ حریف پیدا شد!\n\n"
            f"💰 شرط: {bet_amount} سکه\n"
            f"👥 حریف: {opponent[:8]}...\n"
            f"🎮 بازی: {game_type}\n\n"
            f"🔥 کمیسیون: {int(bet_amount * COMMISSION_RATE * 2)} سکه\n\n"
            f"بازی شروع شد!",
            reply_markup=main_menu()
        )
        
        game_map = {
            "rps": start_rps,
            "dice": start_dice,
            "football": start_football,
            "guess": start_guess
        }
        await game_map.get(game_type, start_rps)(opponent, guid, room_code, bet_amount)
        
        await callback.answer()
    else:
        if queue and queue[0] == guid:
            await callback.answer("⏳ شما قبلاً در صف هستید!", show_alert=True)
            return
        
        cursor.execute("""
            INSERT OR REPLACE INTO quick_queue (guid, bet_amount, game_type, joined_at)
            VALUES (?, ?, ?, ?)
        """, (guid, bet_amount, "rps", datetime.now()))
        db.conn.commit()
        
        count = cursor.execute("SELECT COUNT(*) FROM quick_queue WHERE bet_amount = ?", (bet_amount,)).fetchone()[0]
        
        await callback.message.edit_text(
            f"⏳ شما به صف اضافه شدید!\n\n"
            f"💰 مبلغ شرط: {bet_amount} سکه\n"
            f"🔢 تعداد در صف: {count}\n\n"
            f"به محض پیدا شدن حریف، بازی شروع میشه!",
            reply_markup=InlineKeyboard([
                [InlineKeyboardButton("❌ خروج از صف", callback_data="leave_queue")],
                [InlineKeyboardButton("🔙 برگشت", callback_data="back_to_main")]
            ])
        )
        await callback.answer()

@bot.on_callback_query("leave_queue")
async def leave_queue(callback: CallbackQuery):
    guid = callback.message.author_guid
    cursor = db.conn.cursor()
    cursor.execute("DELETE FROM quick_queue WHERE guid = ?", (guid,))
    db.conn.commit()
    await callback.message.edit_text("✅ از صف خارج شدید.", reply_markup=main_menu())
    await callback.answer()

# ========== سکه‌ها ==========
@bot.on_callback_query("my_coins")
async def my_coins(callback: CallbackQuery):
    guid = callback.message.author_guid
    user = db.get_user(guid)
    if not user:
        await callback.answer("❌ کاربر پیدا نشد!", show_alert=True)
        return
    
    # محاسبه کمیسیون کل
    cursor = db.conn.cursor()
    cursor.execute("SELECT SUM(commission) FROM game_history WHERE winner_guid = ?", (guid,))
    total_commission = cursor.fetchone()[0] or 0
    
    await callback.message.edit_text(
        f"💰 موجودی شما:\n\n"
        f"🪙 سکه: {user[2]}\n"
        f"🎮 کل بازی‌ها: {user[3]}\n"
        f"🏆 کل بردها: {user[4]}\n"
        f"🔥 کمیسیون دریافتی: {total_commission}\n"
        f"📅 تاریخ عضویت: {user[6]}",
        reply_markup=InlineKeyboard([
            [InlineKeyboardButton("🔙 برگشت", callback_data="back_to_main")]
        ])
    )
    await callback.answer()

# ========== زیرمجموعه‌ها ==========
@bot.on_callback_query("referrals")
async def referrals_menu(callback: CallbackQuery):
    guid = callback.message.author_guid
    stats = db.get_referral_stats(guid)
    
    invite_link = f"https://rubika.ir/BOT_USERNAME?start=ref_{guid}"
    
    await callback.message.edit_text(
        f"👥 زیرمجموعه‌ها\n\n"
        f"📊 آمار:\n"
        f"• کل زیرمجموعه‌ها: {stats['total']}\n"
        f"• زیرمجموعه‌های فعال: {stats['active']}\n\n"
        f"🔗 لینک دعوت:\n"
        f"`{invite_link}`\n\n"
        f"💎 به ازای هر زیرمجموعه فعال ۱ الماس دریافت میکنی!",
        reply_markup=InlineKeyboard([
            [InlineKeyboardButton("📋 کپی لینک", callback_data="copy_link")],
            [InlineKeyboardButton("🔙 برگشت", callback_data="back_to_main")]
        ])
    )
    await callback.answer()

@bot.on_callback_query("copy_link")
async def copy_link(callback: CallbackQuery):
    guid = callback.message.author_guid
    invite_link = f"https://rubika.ir/BOT_USERNAME?start=ref_{guid}"
    await callback.answer(f"لینک: {invite_link}", show_alert=True)

# ========== ماموریت روزانه ==========
@bot.on_callback_query("daily_mission")
async def daily_mission(callback: CallbackQuery):
    guid = callback.message.author_guid
    progress = db.get_daily_progress(guid)
    
    played = progress["played"]
    claimed = progress["claimed"]
    
    if claimed:
        await callback.message.edit_text(
            f"✅ امروز جایزه رو گرفتی!\n"
            f"بازی‌های امروز: {played}/3\n\n"
            f"فردا دوباره امتحان کن.",
            reply_markup=InlineKeyboard([
                [InlineKeyboardButton("🔙 برگشت", callback_data="back_to_main")]
            ])
        )
        await callback.answer()
        return
    
    progress_bar = "█" * min(played, 3) + "░" * (3 - min(played, 3))
    
    text = (
        f"🎯 ماموریت روزانه\n\n"
        f"📋 امروز ۳ بازی انجام بده\n"
        f"🎁 جایزه: ۵۰ سکه\n\n"
        f"پیشرفت:\n"
        f"{progress_bar} {played}/3\n"
    )
    
    keyboard = InlineKeyboard()
    if played >= 3:
        keyboard.row(InlineKeyboardButton("🎁 دریافت جایزه", callback_data="claim_daily"))
    keyboard.row(InlineKeyboardButton("🔙 برگشت", callback_data="back_to_main"))
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@bot.on_callback_query("claim_daily")
async def claim_daily(callback: CallbackQuery):
    guid = callback.message.author_guid
    progress = db.get_daily_progress(guid)
    
    if progress["played"] < 3:
        await callback.answer("❌ هنوز کامل نشده!", show_alert=True)
        return
    
    if progress["claimed"]:
        await callback.answer("❌ امروز قبلاً گرفتی!", show_alert=True)
        return
    
    db.update_coins(guid, 50)
    cursor = db.conn.cursor()
    today = datetime.now().date()
    cursor.execute("""
        UPDATE daily_missions SET last_claimed = ? WHERE user_guid = ?
    """, (today, guid))
    db.conn.commit()
    
    await callback.message.edit_text(
        f"🎉 جایزه روزانه دریافت شد!\n\n"
        f"💰 ۵۰ سکه به حسابت اضافه شد.",
        reply_markup=main_menu()
    )
    await callback.answer()

# ========== برداشت ==========
@bot.on_callback_query("withdraw")
async def withdraw_menu(callback: CallbackQuery):
    guid = callback.message.author_guid
    user = db.get_user(guid)
    
    if not user or user[2] < MIN_WITHDRAW_COINS:
        await callback.answer(f"❌ حداقل برداشت {MIN_WITHDRAW_COINS} سکه است!", show_alert=True)
        return
    
    await callback.message.edit_text(
        f"💎 برداشت سکه\n\n"
        f"💰 سکه قابل برداشت: {user[2]}\n"
        f"💳 حداقل برداشت: {MIN_WITHDRAW_COINS} سکه\n"
        f"🏦 مبلغ قابل برداشت: {user[2] * COIN_TO_TOMAN:,} تومان\n\n"
        f"لطفاً شماره کارت ۱۶ رقمی و نام صاحب کارت رو وارد کن:\n"
        f"مثال: `/withdraw 6037997012345678 علی محمدی`",
        reply_markup=InlineKeyboard([
            [InlineKeyboardButton("🔙 برگشت", callback_data="back_to_main")]
        ])
    )
    await callback.answer()

@bot.on_message(filters.command("withdraw"))
async def process_withdraw(client, message: Message):
    guid = message.author_guid
    parts = message.text.split(maxsplit=2)
    
    if len(parts) < 3:
        await message.reply("❌ فرمت صحیح:\n/withdraw [شماره کارت] [نام صاحب کارت]")
        return
    
    card_number = parts[1]
    card_holder = parts[2]
    
    if not re.match(r"^\d{16}$", card_number):
        await message.reply("❌ شماره کارت باید ۱۶ رقم باشد!")
        return
    
    user = db.get_user(guid)
    if not user or user[2] < MIN_WITHDRAW_COINS:
        await message.reply(f"❌ حداقل برداشت {MIN_WITHDRAW_COINS} سکه است!")
        return
    
    coins = user[2]
    toman = coins * COIN_TO_TOMAN
    
    cursor = db.conn.cursor()
    cursor.execute("""
        INSERT INTO withdrawals (user_guid, coins, toman, card_number, card_holder, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (guid, coins, toman, card_number, card_holder, datetime.now(), datetime.now()))
    db.conn.commit()
    withdraw_id = cursor.lastrowid
    
    db.update_coins(guid, -coins)
    
    await message.reply(
        f"✅ درخواست برداشت ثبت شد!\n\n"
        f"🆔 شماره: {withdraw_id}\n"
        f"💰 سکه: {coins}\n"
        f"💳 مبلغ: {toman:,} تومان\n"
        f"🏦 شماره کارت: {card_number}\n"
        f"👤 صاحب کارت: {card_holder}\n\n"
        f"⏳ در انتظار تایید ادمین..."
    )

# ========== آمار ==========
@bot.on_callback_query("stats")
async def stats_menu(callback: CallbackQuery):
    guid = callback.message.author_guid
    user = db.get_user(guid)
    
    if not user:
        await callback.answer("❌ کاربر پیدا نشد!", show_alert=True)
        return
    
    # آمار دقیق‌تر
    cursor = db.conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM game_history WHERE player1_guid = ? OR player2_guid = ?", (guid, guid))
    total_games = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM game_history WHERE winner_guid = ?", (guid,))
    wins = cursor.fetchone()[0]
    
    await callback.message.edit_text(
        f"🏆 آمار شما\n\n"
        f"💰 سکه: {user[2]}\n"
        f"🎮 کل بازی‌ها: {total_games}\n"
        f"🏆 کل بردها: {wins}\n"
        f"📊 درصد برد: {round(wins/total_games*100, 1) if total_games > 0 else 0}%\n"
        f"📅 تاریخ عضویت: {user[6]}",
        reply_markup=InlineKeyboard([
            [InlineKeyboardButton("🔙 برگشت", callback_data="back_to_main")]
        ])
    )
    await callback.answer()

# ========== پنل ادمین ==========
@bot.on_message(filters.command("admin"))
async def admin_login(client, message: Message):
    guid = message.author_guid
    if guid != ADMIN_USER_ID:
        await message.reply("⛔ شما دسترسی ادمین ندارید!")
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("🔑 رمز عبور رو وارد کن: /admin [password]")
        return
    
    if parts[1] != "123456":
        await message.reply("❌ رمز عبور اشتباه است!")
        return
    
    keyboard = InlineKeyboard([
        [InlineKeyboardButton("📊 آمار کلی", callback_data="admin_stats")],
        [InlineKeyboardButton("💰 درآمد کمیسیون", callback_data="admin_commission")],
        [InlineKeyboardButton("💎 درخواست‌های برداشت", callback_data="admin_withdrawals")],
        [InlineKeyboardButton("📢 ارسال همگانی", callback_data="admin_broadcast")],
        [InlineKeyboardButton("📜 تاریخچه بازی‌ها", callback_data="admin_history")],
        [InlineKeyboardButton("🚪 خروج", callback_data="admin_logout")]
    ])
    
    await message.reply("📊 پنل مدیریت", reply_markup=keyboard)

@bot.on_callback_query("admin_stats")
async def admin_stats(callback: CallbackQuery):
    if callback.message.author_guid != ADMIN_USER_ID:
        await callback.answer("⛔ دسترسی غیرمجاز!", show_alert=True)
        return
    
    cursor = db.conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    
    cursor.execute("SELECT SUM(coins) FROM users")
    total_coins = cursor.fetchone()[0] or 0
    
    cursor.execute("SELECT COUNT(*) FROM withdrawals WHERE status = 'pending'")
    pending = cursor.fetchone()[0]
    
    cursor.execute("SELECT SUM(commission) FROM game_history")
    total_commission = cursor.fetchone()[0] or 0
    
    cursor.execute("SELECT COUNT(*) FROM game_history")
    total_games = cursor.fetchone()[0]
    
    await callback.message.edit_text(
        f"📊 آمار کلی\n\n"
        f"👥 کاربران: {total_users}\n"
        f"💰 کل سکه: {total_coins:,}\n"
        f"🔥 کل کمیسیون دریافتی: {total_commission}\n"
        f"🎮 کل بازی‌ها: {total_games}\n"
        f"💎 درخواست‌های در انتظار: {pending}",
        reply_markup=InlineKeyboard([
            [InlineKeyboardButton("🔙 برگشت", callback_data="admin_panel")]
        ])
    )
    await callback.answer()

@bot.on_callback_query("admin_commission")
async def admin_commission(callback: CallbackQuery):
    if callback.message.author_guid != ADMIN_USER_ID:
        await callback.answer("⛔ دسترسی غیرمجاز!", show_alert=True)
        return
    
    cursor = db.conn.cursor()
    cursor.execute("""
        SELECT game_type, COUNT(*), SUM(commission) 
        FROM game_history 
        GROUP BY game_type
    """)
    stats = cursor.fetchall()
    
    text = "🔥 درآمد کمیسیون بر اساس بازی:\n\n"
    total = 0
    for row in stats:
        game_type = row[0]
        count = row[1]
        commission = row[2] or 0
        text += f"🎮 {game_type}: {count} بازی | {commission} سکه\n"
        total += commission
    
    text += f"\n💰 مجموع کل: {total} سکه"
    text += f"\n💵 معادل تومان: {total * COIN_TO_TOMAN:,} تومان"
    
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboard([
            [InlineKeyboardButton("🔙 برگشت", callback_data="admin_panel")]
        ])
    )
    await callback.answer()

@bot.on_callback_query("admin_withdrawals")
async def admin_withdrawals(callback: CallbackQuery):
    if callback.message.author_guid != ADMIN_USER_ID:
        await callback.answer("⛔ دسترسی غیرمجاز!", show_alert=True)
        return
    
    cursor = db.conn.cursor()
    cursor.execute("""
        SELECT id, user_guid, coins, toman, card_number, card_holder, created_at
        FROM withdrawals WHERE status = 'pending'
    """)
    withdrawals = cursor.fetchall()
    
    if not withdrawals:
        await callback.answer("✅ هیچ درخواستی نیست!", show_alert=True)
        return
    
    text = "💎 درخواست‌های برداشت:\n\n"
    for w in withdrawals[:5]:
        text += (
            f"🆔 {w[0]} | {w[1][:8]}...\n"
            f"💰 {w[2]} سکه ({w[3]:,} تومان)\n"
            f"🏦 {w[4]} | {w[5]}\n"
            f"⏱️ {w[6]}\n"
            f"─────────────────\n"
        )
    
    keyboard = InlineKeyboard([
        [InlineKeyboardButton("✅ تایید", callback_data="approve_withdraw"),
         InlineKeyboardButton("❌ رد", callback_data="reject_withdraw")],
        [InlineKeyboardButton("🔙 برگشت", callback_data="admin_panel")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@bot.on_callback_query("admin_history")
async def admin_history(callback: CallbackQuery):
    if callback.message.author_guid != ADMIN_USER_ID:
        await callback.answer("⛔ دسترسی غیرمجاز!", show_alert=True)
        return
    
    cursor = db.conn.cursor()
    cursor.execute("""
        SELECT game_type, COUNT(*), SUM(bet_amount), SUM(commission)
        FROM game_history
        GROUP BY game_type
    """)
    stats = cursor.fetchall()
    
    text = "📜 تاریخچه بازی‌ها:\n\n"
    for row in stats:
        game_type = row[0]
        count = row[1]
        total_bet = row[2] or 0
        total_commission = row[3] or 0
        text += f"🎮 {game_type}: {count} بازی | شرط کل: {total_bet} | کمیسیون: {total_commission}\n"
    
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboard([
            [InlineKeyboardButton("🔙 برگشت", callback_data="admin_panel")]
        ])
    )
    await callback.answer()

@bot.on_callback_query("admin_broadcast")
async def admin_broadcast(callback: CallbackQuery):
    if callback.message.author_guid != ADMIN_USER_ID:
        await callback.answer("⛔ دسترسی غیرمجاز!", show_alert=True)
        return
    
    await callback.message.edit_text(
        "📢 ارسال همگانی\n\n"
        "پیام خود را به صورت /broadcast [متن] ارسال کنید.",
        reply_markup=InlineKeyboard([
            [InlineKeyboardButton("🔙 برگشت", callback_data="admin_panel")]
        ])
    )
    await callback.answer()

@bot.on_message(filters.command("broadcast") & filters.user(ADMIN_USER_ID))
async def broadcast(client, message: Message):
    text = message.text.replace("/broadcast", "").strip()
    if not text:
        await message.reply("❌ متن پیام رو وارد کن!")
        return
    
    cursor = db.conn.cursor()
    cursor.execute("SELECT guid FROM users")
    users = cursor.fetchall()
    
    sent = 0
    for user in users:
        try:
            await bot.send_message(user[0], f"📢 پیام همگانی:\n\n{text}")
            sent += 1
            await asyncio.sleep(0.1)
        except:
            pass
    
    await message.reply(f"✅ پیام به {sent} نفر ارسال شد.")

@bot.on_callback_query("admin_panel")
async def admin_panel(callback: CallbackQuery):
    if callback.message.author_guid != ADMIN_USER_ID:
        await callback.answer("⛔ دسترسی غیرمجاز!", show_alert=True)
        return
    
    keyboard = InlineKeyboard([
        [InlineKeyboardButton("📊 آمار کلی", callback_data="admin_stats")],
        [InlineKeyboardButton("💰 درآمد کمیسیون", callback_data="admin_commission")],
        [InlineKeyboardButton("💎 درخواست‌های برداشت", callback_data="admin_withdrawals")],
        [InlineKeyboardButton("📢 ارسال همگانی", callback_data="admin_broadcast")],
        [InlineKeyboardButton("📜 تاریخچه بازی‌ها", callback_data="admin_history")],
        [InlineKeyboardButton("🚪 خروج", callback_data="admin_logout")]
    ])
    
    await callback.message.edit_text("📊 پنل مدیریت", reply_markup=keyboard)
    await callback.answer()

@bot.on_callback_query("admin_logout")
async def admin_logout(callback: CallbackQuery):
    if callback.message.author_guid != ADMIN_USER_ID:
        await callback.answer("⛔ دسترسی غیرمجاز!", show_alert=True)
        return
    
    await callback.message.edit_text("🚪 خارج شدید.", reply_markup=main_menu())
    await callback.answer()

# ========== تابع اصلی ==========
if __name__ == "__main__":
    print("🎮 ربات حرفه‌ای بازی دو نفره روشن شد!")
    print(f"👤 ادمین: {ADMIN_USER_ID}")
    print(f"🔥 کمیسیون: {COMMISSION_RATE * 100}% از هر بازی")
    print("=" * 50)
    bot.run()
