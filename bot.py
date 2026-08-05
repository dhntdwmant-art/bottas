# ============================================================
# bot.py - ربات کامل تاس روبیکا (نسخه نهایی)
# کتابخانه: rubpy - روش Polling (نیاز به Webhook ندارد)
# توجه: در روبیکا user_id از نوع رشته (string) است، نه عدد!
# ============================================================

import os
import sqlite3
import random
import logging
import asyncio
from datetime import datetime
from typing import Optional, Dict, List

# =========================== نصب خودکار کتابخانه ===========================
try:
    from rubpy import Client, filters
    from rubpy.types import Message, CallbackQuery
    from rubpy.keyboard import InlineKeyboard, InlineKeyboardButton
except ImportError:
    import subprocess
    subprocess.check_call(['pip', 'install', 'rubpy'])
    from rubpy import Client, filters
    from rubpy.types import Message, CallbackQuery
    from rubpy.keyboard import InlineKeyboard, InlineKeyboardButton

# =========================== تنظیمات اولیه ===========================
# متغیرهای محیطی (در Railway تنظیم کنید)
BOT_TOKEN = os.environ.get("CBBJGB0XOTDMCTHQTFDUFZOVJJRVDVAFTCLZKGGQWAOIRCJSDIVPMKOWTUKURONM")
PORT = int(os.environ.get("PORT", 5000))
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "09158029769")

# آیدی ادمین اصلی - در روبیکا به صورت رشته است
MAIN_ADMIN_ID = os.environ.get("MAIN_ADMIN_ID", "u0If7GJ01a6b90d62c1ac6f0162a465e")

if not BOT_TOKEN:
    print("❌ خطا: متغیر BOT_TOKEN تنظیم نشده است!")
    print("لطفاً در Railway Variables مقدار BOT_TOKEN را قرار دهید.")
    exit(1)

# =========================== راه‌اندازی لاگ ===========================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# =========================== دیتابیس ===========================
DB_PATH = "bot_database.db"

def init_db():
    """ایجاد جداول دیتابیس"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # کاربران - user_id از نوع TEXT (رشته)
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            invited_by TEXT,
            balance INTEGER DEFAULT 0,
            total_games INTEGER DEFAULT 0,
            wins INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0,
            total_fee_paid INTEGER DEFAULT 0,
            join_date TEXT,
            is_banned BOOLEAN DEFAULT 0,
            is_admin BOOLEAN DEFAULT 0,
            has_played BOOLEAN DEFAULT 0
        )
    ''')

    # تراکنش‌ها
    c.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            amount INTEGER,
            type TEXT,
            description TEXT,
            timestamp TEXT
        )
    ''')

    # تاریخچه بازی
    c.execute('''
        CREATE TABLE IF NOT EXISTS game_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            bet_amount INTEGER,
            win_amount INTEGER,
            fee INTEGER,
            result TEXT,
            timestamp TEXT
        )
    ''')

    # قفل بازی
    c.execute('''
        CREATE TABLE IF NOT EXISTS game_locks (
            user_id TEXT PRIMARY KEY,
            lock_time TEXT
        )
    ''')

    # درخواست‌های برداشت
    c.execute('''
        CREATE TABLE IF NOT EXISTS withdraw_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            amount INTEGER,
            card_number TEXT,
            card_holder TEXT,
            status TEXT,
            request_time TEXT,
            processed_time TEXT
        )
    ''')

    # ماموریت روزانه
    c.execute('''
        CREATE TABLE IF NOT EXISTS daily_missions (
            user_id TEXT,
            date TEXT,
            games_played INTEGER DEFAULT 0,
            claimed BOOLEAN DEFAULT 0,
            PRIMARY KEY (user_id, date)
        )
    ''')

    # تنظیمات
    c.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')

    # تنظیمات پیش‌فرض
    defaults = {
        "card_number": "6062561009737464",
        "card_holder": "مجاور",
        "min_withdraw": "100000",
        "fee_percent": "10",
        "dice_win_chance": "16",
        "bet_amounts": "10000,50000,100000,500000,1000000",
        "daily_mission_required": "3",
        "daily_mission_reward": "50000",
        "invite_reward": "20000"
    }
    for key, val in defaults.items():
        c.execute('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)', (key, val))

    conn.commit()
    conn.close()
    logger.info("✅ دیتابیس مقداردهی شد.")

# =========================== توابع دیتابیس ===========================
def get_setting(key: str) -> str:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT value FROM settings WHERE key = ?', (key,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def get_user(user_id: str) -> Optional[Dict]:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    row = c.fetchone()
    conn.close()
    if row:
        cols = ['user_id', 'username', 'first_name', 'last_name', 'invited_by',
                'balance', 'total_games', 'wins', 'losses', 'total_fee_paid',
                'join_date', 'is_banned', 'is_admin', 'has_played']
        return dict(zip(cols, row))
    return None

def get_all_users() -> List[Dict]:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT * FROM users ORDER BY join_date DESC')
    rows = c.fetchall()
    conn.close()
    cols = ['user_id', 'username', 'first_name', 'last_name', 'invited_by',
            'balance', 'total_games', 'wins', 'losses', 'total_fee_paid',
            'join_date', 'is_banned', 'is_admin', 'has_played']
    return [dict(zip(cols, row)) for row in rows]

def create_user(user_id: str, username: str = "", first_name: str = "", last_name: str = "", invited_by: str = None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        INSERT OR IGNORE INTO users (user_id, username, first_name, last_name, invited_by, join_date)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, username, first_name, last_name, invited_by, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def update_balance(user_id: str, amount: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
    conn.commit()
    conn.close()

def add_transaction(user_id: str, amount: int, trans_type: str, desc: str = ""):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT INTO transactions (user_id, amount, type, description, timestamp) VALUES (?, ?, ?, ?, ?)',
              (user_id, amount, trans_type, desc, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def increment_games(user_id: str, won: bool, fee: int = 0):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if won:
        c.execute('UPDATE users SET total_games = total_games + 1, wins = wins + 1, total_fee_paid = total_fee_paid + ? WHERE user_id = ?', (fee, user_id))
    else:
        c.execute('UPDATE users SET total_games = total_games + 1, losses = losses + 1 WHERE user_id = ?', (user_id,))
    c.execute('UPDATE users SET has_played = 1 WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

def get_game_lock(user_id: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT 1 FROM game_locks WHERE user_id = ?', (user_id,))
    exists = c.fetchone() is not None
    conn.close()
    return exists

def set_game_lock(user_id: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO game_locks (user_id, lock_time) VALUES (?, ?)', (user_id, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def release_game_lock(user_id: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM game_locks WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

def get_daily_mission(user_id: str) -> Dict:
    today = datetime.now().date().isoformat()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT * FROM daily_missions WHERE user_id = ? AND date = ?', (user_id, today))
    row = c.fetchone()
    if not row:
        c.execute('INSERT INTO daily_missions (user_id, date, games_played, claimed) VALUES (?, ?, 0, 0)', (user_id, today))
        conn.commit()
        c.execute('SELECT * FROM daily_missions WHERE user_id = ? AND date = ?', (user_id, today))
        row = c.fetchone()
    conn.close()
    return {'user_id': row[0], 'date': row[1], 'games_played': row[2], 'claimed': bool(row[3])}

def update_daily_mission(user_id: str, games_played: int = None, claimed: bool = None):
    today = datetime.now().date().isoformat()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if games_played is not None:
        c.execute('UPDATE daily_missions SET games_played = games_played + ? WHERE user_id = ? AND date = ?', (games_played, user_id, today))
    if claimed is not None:
        c.execute('UPDATE daily_missions SET claimed = ? WHERE user_id = ? AND date = ?', (1 if claimed else 0, user_id, today))
    conn.commit()
    conn.close()

def save_withdraw_request(user_id: str, amount: int, card_number: str, card_holder: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        INSERT INTO withdraw_requests (user_id, amount, card_number, card_holder, status, request_time)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, amount, card_number, card_holder, 'pending', datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_pending_withdrawals() -> List[Dict]:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT id, user_id, amount, card_number, card_holder FROM withdraw_requests WHERE status = "pending"')
    rows = c.fetchall()
    conn.close()
    return [{'id': r[0], 'user_id': r[1], 'amount': r[2], 'card_number': r[3], 'card_holder': r[4]} for r in rows]

def process_withdraw(req_id: int, approve: bool):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if approve:
        c.execute('UPDATE withdraw_requests SET status = "approved", processed_time = ? WHERE id = ?', (datetime.now().isoformat(), req_id))
    else:
        c.execute('UPDATE withdraw_requests SET status = "rejected", processed_time = ? WHERE id = ?', (datetime.now().isoformat(), req_id))
    conn.commit()
    conn.close()

# =========================== کلاینت ربات ===========================
client = Client(BOT_TOKEN)

# =========================== توابع کمکی ===========================
def format_number(num: int) -> str:
    return f"{num:,}"

def get_bet_amounts() -> List[int]:
    amounts_str = get_setting('bet_amounts') or "10000,50000,100000,500000,1000000"
    return [int(x.strip()) for x in amounts_str.split(',') if x.strip().isdigit()]

def is_admin(user_id: str) -> bool:
    if user_id == MAIN_ADMIN_ID:
        return True
    user = get_user(user_id)
    return user.get('is_admin', False) if user else False

def get_invite_link(user_id: str) -> str:
    # نام کاربری ربات را از BotFather ببینید
    return f"https://rubika.ir/YourBotUsername?start={user_id}"

# =========================== کیبوردها ===========================
def main_menu(user_id: str) -> InlineKeyboard:
    return InlineKeyboard([
        [InlineKeyboardButton("🎮 بازی تاس", callback_data=f"dice_{user_id}")],
        [InlineKeyboardButton("💰 خرید اعتبار", callback_data=f"buy_{user_id}")],
        [InlineKeyboardButton("👤 پروفایل", callback_data=f"profile_{user_id}")],
        [InlineKeyboardButton("👥 دعوت دوستان", callback_data=f"invite_{user_id}")],
        [InlineKeyboardButton("🎯 ماموریت روزانه", callback_data=f"mission_{user_id}")],
        [InlineKeyboardButton("💎 برداشت", callback_data=f"withdraw_{user_id}")],
        [InlineKeyboardButton("📞 پشتیبانی", callback_data=f"support_{user_id}")],
        [InlineKeyboardButton("❓ راهنما", callback_data=f"help_{user_id}")]
    ])

def dice_keyboard(user_id: str) -> InlineKeyboard:
    amounts = get_bet_amounts()
    buttons = []
    row = []
    for i, amt in enumerate(amounts):
        row.append(InlineKeyboardButton(f"{format_number(amt)} تومان", callback_data=f"bet_{user_id}_{amt}"))
        if (i + 1) % 2 == 0:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("❌ انصراف", callback_data=f"cancel_{user_id}")])
    return InlineKeyboard(buttons)

def result_keyboard(user_id: str) -> InlineKeyboard:
    return InlineKeyboard([
        [InlineKeyboardButton("🎲 بازی دوباره", callback_data=f"dice_{user_id}")],
        [InlineKeyboardButton("🏠 منوی اصلی", callback_data=f"menu_{user_id}")]
    ])

def admin_menu() -> InlineKeyboard:
    return InlineKeyboard([
        [InlineKeyboardButton("📊 آمار کلی", callback_data="admin_stats")],
        [InlineKeyboardButton("👥 لیست کاربران", callback_data="admin_users")],
        [InlineKeyboardButton("💎 درخواست‌های برداشت", callback_data="admin_withdrawals")],
        [InlineKeyboardButton("📢 ارسال همگانی", callback_data="admin_broadcast")],
        [InlineKeyboardButton("🔒 رفع قفل همه", callback_data="admin_unlock")],
        [InlineKeyboardButton("🚪 خروج", callback_data="admin_logout")]
    ])

# =========================== دیکشنری وضعیت‌ها ===========================
admin_sessions = {}  # {'user_id': 'waiting_pass' | 'logged_in'}
user_steps = {}      # {'user_id': {'step': 'withdraw_card', 'card_number': '...'}}

# =========================== هندلر پیام‌های متنی ===========================
@client.on_message(filters.text & filters.private)
async def handle_message(message: Message):
    user_id = message.author_id
    text = message.text.strip()

    # ثبت کاربر جدید
    if not get_user(user_id):
        invited_by = None
        if text.startswith('/start') and len(text.split()) > 1:
            invited_by = text.split()[1]
        create_user(user_id, message.chat.username or "", message.chat.first_name or "", message.chat.last_name or "", invited_by)
        await message.reply("✅ ثبت نام شما با موفقیت انجام شد!")

    user = get_user(user_id)
    if not user:
        await message.reply("❌ خطا در ثبت نام.")
        return

    if user.get('is_banned', False):
        await message.reply("⛔ شما مسدود هستید.")
        return

    # ====== پردازش مراحل مختلف ======
    # مرحله برداشت - وارد کردن شماره کارت
    if user_id in user_steps and user_steps[user_id].get('step') == 'withdraw_card':
        if len(text) == 16 and text.isdigit():
            user_steps[user_id]['card_number'] = text
            user_steps[user_id]['step'] = 'withdraw_holder'
            await message.reply("✅ شماره کارت ثبت شد. لطفاً نام صاحب کارت را وارد کنید:")
        else:
            await message.reply("❌ شماره کارت باید ۱۶ رقم باشد. دوباره وارد کنید:")
        return

    # مرحله برداشت - وارد کردن نام صاحب کارت
    if user_id in user_steps and user_steps[user_id].get('step') == 'withdraw_holder':
        holder = text.strip()
        if len(holder) < 3:
            await message.reply("❌ نام صاحب کارت معتبر نیست. دوباره وارد کنید:")
            return
        card_number = user_steps[user_id].get('card_number')
        if not card_number:
            await message.reply("❌ خطا: شماره کارت ثبت نشده.")
            return
        
        # ثبت درخواست برداشت
        amount = user['balance']
        min_wd = int(get_setting('min_withdraw') or 100000)
        if amount < min_wd:
            await message.reply(f"⛔ حداقل برداشت {format_number(min_wd)} تومان است.")
            return
        
        save_withdraw_request(user_id, amount, card_number, holder)
        user_steps.pop(user_id, None)
        await message.reply(f"✅ درخواست برداشت {format_number(amount)} تومان ثبت شد. منتظر تأیید ادمین باشید.", reply_markup=main_menu(user_id))
        
        # اطلاع به ادمین
        if MAIN_ADMIN_ID:
            await client.send_message(MAIN_ADMIN_ID, f"🔔 درخواست برداشت جدید:\n👤 {user_id}\n💰 {format_number(amount)} تومان\n💳 {card_number}\n👤 {holder}")
        return

    # ====== ورود به پنل مدیریت ======
    if text == '/admin':
        if is_admin(user_id):
            admin_sessions[user_id] = 'waiting_pass'
            await message.reply("🔐 رمز پنل را وارد کنید:")
        else:
            await message.reply("⛔ شما دسترسی ندارید.")
        return

    # بررسی رمز پنل
    if user_id in admin_sessions and admin_sessions[user_id] == 'waiting_pass':
        if text == ADMIN_PASSWORD:
            admin_sessions[user_id] = 'logged_in'
            await message.reply("✅ ورود موفق! به پنل مدیریت خوش آمدید.", reply_markup=admin_menu())
        else:
            await message.reply("❌ رمز اشتباه است.")
        return

    # ====== دستورات عادی ======
    if text == '/start':
        await message.reply(f"🎉 به ربات تاس خوش آمدید!\n💰 موجودی: {format_number(user['balance'])} تومان", reply_markup=main_menu(user_id))
    else:
        await message.reply("لطفاً از دکمه‌های زیر استفاده کنید:", reply_markup=main_menu(user_id))

# =========================== هندلر Callback ===========================
@client.on_callback_query()
async def handle_callback(callback: CallbackQuery):
    user_id = callback.from_id
    data = callback.data
    msg = callback.message

    user = get_user(user_id)
    if user and user.get('is_banned', False):
        await callback.answer("⛔ شما مسدود هستید.", show_alert=True)
        return

    # ====== منوی اصلی ======
    if data.startswith("dice_") and data.split('_')[1] == user_id:
        await callback.answer("")
        await msg.edit_text("🎲 مبلغ شرط را انتخاب کنید:", reply_markup=dice_keyboard(user_id))

    elif data.startswith("bet_") and data.split('_')[1] == user_id:
        bet = int(data.split('_')[2])
        await callback.answer("")
        if get_game_lock(user_id):
            await msg.edit_text("⏳ در حال انجام بازی هستید...")
            return
        set_game_lock(user_id)
        await play_dice(msg, user_id, bet)

    elif data.startswith("cancel_") and data.split('_')[1] == user_id:
        await callback.answer("بازی لغو شد.")
        await msg.edit_text("❌ لغو شد.", reply_markup=main_menu(user_id))

    elif data.startswith("menu_") and data.split('_')[1] == user_id:
        await callback.answer("")
        await msg.edit_text("🏠 منوی اصلی:", reply_markup=main_menu(user_id))

    # ====== پروفایل ======
    elif data.startswith("profile_") and data.split('_')[1] == user_id:
        await callback.answer("")
        u = get_user(user_id)
        txt = f"""
👤 **پروفایل شما**

🆔 {user_id}
💰 موجودی: {format_number(u['balance'])} تومان
🎮 بازی: {u['total_games']} (برد: {u['wins']} | باخت: {u['losses']})
💸 کارمزد: {format_number(u['total_fee_paid'])} تومان
        """
        await msg.edit_text(txt, reply_markup=InlineKeyboard([[InlineKeyboardButton("🔙 بازگشت", callback_data=f"menu_{user_id}")]]))

    # ====== دعوت ======
    elif data.startswith("invite_") and data.split('_')[1] == user_id:
        await callback.answer("")
        link = get_invite_link(user_id)
        txt = f"👥 **لینک دعوت شما**\n\n`{link}`\n\n🎁 هر کاربر فعال ۲۰,۰۰۰ تومان پاداش!"
        await msg.edit_text(txt, reply_markup=InlineKeyboard([[InlineKeyboardButton("🔙 بازگشت", callback_data=f"menu_{user_id}")]]))

    # ====== ماموریت روزانه ======
    elif data.startswith("mission_") and data.split('_')[1] == user_id:
        await callback.answer("")
        m = get_daily_mission(user_id)
        req = int(get_setting('daily_mission_required') or 3)
        reward = int(get_setting('daily_mission_reward') or 50000)
        progress = min(m['games_played'], req)
        bar = "█" * progress + "░" * (req - progress)
        txt = f"🎯 **ماموریت روزانه**\n\n{bar} {progress}/{req}\nجایزه: {format_number(reward)} تومان\nوضعیت: {'✅ دریافت شد' if m['claimed'] else '⏳ در حال انجام'}"
        kb = InlineKeyboard([[InlineKeyboardButton("🔙 بازگشت", callback_data=f"menu_{user_id}")]])
        if progress >= req and not m['claimed']:
            kb = InlineKeyboard([
                [InlineKeyboardButton("🎁 دریافت جایزه", callback_data=f"claim_{user_id}")],
                [InlineKeyboardButton("🔙 بازگشت", callback_data=f"menu_{user_id}")]
            ])
        await msg.edit_text(txt, reply_markup=kb)

    elif data.startswith("claim_") and data.split('_')[1] == user_id:
        await callback.answer("")
        m = get_daily_mission(user_id)
        req = int(get_setting('daily_mission_required') or 3)
        reward = int(get_setting('daily_mission_reward') or 50000)
        if m['games_played'] >= req and not m['claimed']:
            update_balance(user_id, reward)
            update_daily_mission(user_id, claimed=True)
            add_transaction(user_id, reward, 'daily_mission', 'جایزه ماموریت روزانه')
            await msg.edit_text(f"✅ {format_number(reward)} تومان به حساب شما واریز شد!", reply_markup=main_menu(user_id))
        else:
            await msg.edit_text("⛔ قبلاً دریافت کردید یا کامل نشده.", reply_markup=main_menu(user_id))

    # ====== خرید ======
    elif data.startswith("buy_") and data.split('_')[1] == user_id:
        await callback.answer("")
        card = get_setting('card_number') or "6037-9975-1234-5678"
        holder = get_setting('card_holder') or "علی رضایی"
        txt = f"💰 **خرید اعتبار**\n\nشماره کارت: `{card}`\nصاحب: {holder}\n\nمبلغ را به کارت واریز کرده و رسید را به ادمین ارسال کنید."
        await msg.edit_text(txt, reply_markup=InlineKeyboard([[InlineKeyboardButton("🔙 بازگشت", callback_data=f"menu_{user_id}")]]))

    # ====== برداشت ======
    elif data.startswith("withdraw_") and data.split('_')[1] == user_id:
        await callback.answer("")
        min_wd = int(get_setting('min_withdraw') or 100000)
        if user['balance'] < min_wd:
            await msg.edit_text(f"⛔ حداقل برداشت {format_number(min_wd)} تومان است.", reply_markup=main_menu(user_id))
            return
        user_steps[user_id] = {'step': 'withdraw_card'}
        await msg.edit_text("💳 شماره کارت ۱۶ رقمی خود را وارد کنید:", reply_markup=InlineKeyboard([[InlineKeyboardButton("🔙 انصراف", callback_data=f"menu_{user_id}")]]))

    # ====== پشتیبانی ======
    elif data.startswith("support_") and data.split('_')[1] == user_id:
        await callback.answer("")
        await msg.edit_text("📞 پشتیبانی: با ادمین تماس بگیرید.", reply_markup=main_menu(user_id))

    # ====== راهنما ======
    elif data.startswith("help_") and data.split('_')[1] == user_id:
        await callback.answer("")
        txt = "❓ **راهنما**\n\n🎮 بازی تاس: شرط بندی و برد ۴ برابری\n💰 خرید: کارت به کارت\n👥 دعوت: ۲۰,۰۰۰ تومان پاداش\n🎯 ماموریت: ۳ بازی روزانه\n💎 برداشت: حداقل ۱۰۰,۰۰۰ تومان"
        await msg.edit_text(txt, reply_markup=InlineKeyboard([[InlineKeyboardButton("🔙 بازگشت", callback_data=f"menu_{user_id}")]]))

    # ====== پنل مدیریت ======
    elif data.startswith("admin_"):
        if not is_admin(user_id):
            await callback.answer("⛔ شما ادمین نیستید.", show_alert=True)
            return
        
        if admin_sessions.get(user_id) != 'logged_in':
            await callback.answer("⛔ ابتدا وارد پنل شوید. /admin", show_alert=True)
            return

        # خروج از پنل
        if data == "admin_logout":
            admin_sessions.pop(user_id, None)
            await callback.answer("")
            await msg.edit_text("🚪 از پنل خارج شدید.", reply_markup=main_menu(user_id))
            return

        # آمار کلی
        if data == "admin_stats":
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute('SELECT COUNT(*) FROM users')
            total = c.fetchone()[0]
            c.execute('SELECT SUM(balance) FROM users')
            balance = c.fetchone()[0] or 0
            c.execute('SELECT COUNT(*) FROM users WHERE is_banned = 1')
            banned = c.fetchone()[0]
            conn.close()
            txt = f"📊 **آمار کلی**\n\n👥 کاربران: {total}\n💰 مجموع موجودی: {format_number(balance)} تومان\n🚫 مسدود: {banned}"
            await msg.edit_text(txt, reply_markup=InlineKeyboard([[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back")]]))

        # لیست کاربران
        elif data == "admin_users":
            users = get_all_users()
            txt = "👥 **لیست کاربران**\n\n"
            for i, u in enumerate(users[:20], 1):
                txt += f"{i}. {u['first_name']} ({u['user_id']}) - {format_number(u['balance'])} تومان\n"
            if len(users) > 20:
                txt += f"\n... و {len(users)-20} کاربر دیگر"
            await msg.edit_text(txt, reply_markup=InlineKeyboard([[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back")]]))

        # درخواست‌های برداشت
        elif data == "admin_withdrawals":
            pending = get_pending_withdrawals()
            if not pending:
                await msg.edit_text("💎 هیچ درخواست برداشت معلقی وجود ندارد.", reply_markup=InlineKeyboard([[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back")]]))
                return
            for req in pending:
                txt = f"💎 درخواست برداشت\n👤 {req['user_id']}\n💰 {format_number(req['amount'])} تومان\n💳 {req['card_number']}\n👤 {req['card_holder']}"
                kb = InlineKeyboard([
                    [InlineKeyboardButton("✅ تایید", callback_data=f"approve_{req['id']}"),
                     InlineKeyboardButton("❌ رد", callback_data=f"reject_{req['id']}")]
                ])
                await client.send_message(user_id, txt, reply_markup=kb)
            await msg.edit_text("✅ درخواست‌ها ارسال شدند.", reply_markup=admin_menu())

        # تایید/رد برداشت
        elif data.startswith("approve_") or data.startswith("reject_"):
            parts = data.split('_')
            action = parts[0]
            req_id = int(parts[1])
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute('SELECT user_id, amount FROM withdraw_requests WHERE id = ?', (req_id,))
            row = c.fetchone()
            conn.close()
            if row:
                uid, amount = row
                if action == "approve":
                    update_balance(uid, -amount)
                    add_transaction(uid, -amount, 'withdraw', f'برداشت تایید شده - مبلغ {amount}')
                    await client.send_message(uid, f"✅ درخواست برداشت {format_number(amount)} تومانی شما تایید شد.")
                else:
                    await client.send_message(uid, f"❌ درخواست برداشت {format_number(amount)} تومانی شما رد شد.")
                process_withdraw(req_id, action == "approve")
                await callback.answer(f"برداشت {action} شد.")
                await msg.edit_text("✅ عملیات انجام شد.", reply_markup=admin_menu())

        # ارسال همگانی
        elif data == "admin_broadcast":
            await msg.edit_text("📢 متن پیام همگانی را ارسال کنید:", reply_markup=InlineKeyboard([[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back")]]))
            user_steps[user_id] = {'step': 'admin_broadcast'}

        # رفع قفل همه
        elif data == "admin_unlock":
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute('DELETE FROM game_locks')
            conn.commit()
            conn.close()
            await msg.edit_text("✅ تمام قفل‌های بازی آزاد شدند.", reply_markup=admin_menu())

        # بازگشت به منوی ادمین
        elif data == "admin_back":
            await msg.edit_text("🏠 پنل مدیریت:", reply_markup=admin_menu())

    # ====== پردازش پیام همگانی ======
    if user_id in user_steps and user_steps[user_id].get('step') == 'admin_broadcast':
        text = data if data else "پیام"
        users = get_all_users()
        count = 0
        for u in users:
            try:
                await client.send_message(u['user_id'], text)
                count += 1
                await asyncio.sleep(0.1)
            except:
                pass
        await msg.edit_text(f"✅ پیام به {count} کاربر ارسال شد.", reply_markup=admin_menu())
        user_steps.pop(user_id, None)

# =========================== بازی تاس ===========================
async def play_dice(msg: Message, user_id: str, bet: int):
    user = get_user(user_id)
    if user['balance'] < bet:
        await msg.edit_text(f"⛔ موجودی کافی نیست. موجودی: {format_number(user['balance'])} تومان", reply_markup=main_menu(user_id))
        release_game_lock(user_id)
        return

    win_chance = int(get_setting('dice_win_chance') or 16)
    fee_percent = int(get_setting('fee_percent') or 10)

    # کسر شرط
    update_balance(user_id, -bet)
    add_transaction(user_id, -bet, 'game_bet', f'شرط بازی تاس - {bet} تومان')

    # انداختن تاس
    user_roll = random.randint(1, 6)
    bot_roll = random.randint(1, 6)
    is_win = user_roll > bot_roll

    # اعمال شانس
    if random.randint(1, 100) > win_chance:
        is_win = False

    if is_win:
        gross_win = bet * 4
        fee = int(gross_win * fee_percent / 100)
        net_win = gross_win - fee
        update_balance(user_id, net_win)
        add_transaction(user_id, net_win, 'game_win', f'برد در بازی تاس - {net_win} تومان')
        add_transaction(MAIN_ADMIN_ID, fee, 'fee', f'کارمزد از {user_id}')
        increment_games(user_id, True, fee)
        result_text = f"🎉 **تبریک! برنده شدید!**\n\nشرط: {format_number(bet)} تومان\nجایزه ناخالص: {format_number(gross_win)} تومان\nکارمزد ({fee_percent}%): {format_number(fee)} تومان\nجایزه نهایی: {format_number(net_win)} تومان\nموجودی جدید: {format_number(get_user(user_id)['balance'])} تومان"
    else:
        increment_games(user_id, False, 0)
        result_text = f"😞 **باختید!**\n\nشرط: {format_number(bet)} تومان\nموجودی جدید: {format_number(get_user(user_id)['balance'])} تومان"

    # ماموریت روزانه
    update_daily_mission(user_id, games_played=1)

    # جایزه دعوت (اگر اولین بازی باشد)
    invited = get_user(user_id)
    if invited and invited.get('has_played') and invited.get('invited_by'):
        inviter_id = invited['invited_by']
        reward = int(get_setting('invite_reward') or 20000)
        # بررسی اینکه قبلاً جایزه داده نشده
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('SELECT 1 FROM transactions WHERE user_id = ? AND type = ? AND description LIKE ?', 
                  (inviter_id, 'invite_reward', f'%{user_id}%'))
        exists = c.fetchone()
        conn.close()
        if not exists:
            update_balance(inviter_id, reward)
            add_transaction(inviter_id, reward, 'invite_reward', f'جایزه دعوت {user_id}')
            try:
                await client.send_message(inviter_id, f"🎁 {format_number(reward)} تومان پاداش دعوت {user_id} به حساب شما واریز شد!")
            except:
                pass

    await msg.edit_text(f"🎲 **نتیجه بازی**\nتاس شما: {user_roll}\nتاس ربات: {bot_roll}\n\n{result_text}", reply_markup=result_keyboard(user_id))
    release_game_lock(user_id)

# =========================== اجرای ربات ===========================
async def main():
    init_db()
    logger.info("🤖 ربات تاس روبیکا در حال اجراست...")
    await client.start()
    await client.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
