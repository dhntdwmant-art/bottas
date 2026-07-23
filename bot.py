# ==============================
# 🎲 Telegram Dice Game Bot
# Version 1.0
# ==============================

import sqlite3
import random
import time

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton
)

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)


# ==============================
# ⚙️ تنظیمات ربات
# ==============================

BOT_TOKEN = "8713972741:AAFGtBrrjMa9nkeu2EuhoaJA6UMy9rCLx2s"

# آیدی عددی مالک ربات
ADMIN_ID = 7548145568


# تنظیمات بازی
GAME_ENTRY = 200       # ورودی بازی
OWNER_PERCENT = 10     # درصد کارمزد مالک
INVITE_REWARD = 20     # جایزه دعوت


# ==============================
# 🗄 دیتابیس
# ==============================

db = sqlite3.connect(
    "dice_bot.db",
    check_same_thread=False
)

cursor = db.cursor()


# ساخت جدول کاربران
cursor.execute("""
CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY,
    username TEXT,
    name TEXT,
    coins INTEGER DEFAULT 0,
    games INTEGER DEFAULT 0,
    wins INTEGER DEFAULT 0,
    loses INTEGER DEFAULT 0,
    inviter INTEGER DEFAULT 0,
    invite_reward INTEGER DEFAULT 0
)
""")


# جدول بازی‌ها
cursor.execute("""
CREATE TABLE IF NOT EXISTS games(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player1 INTEGER,
    player2 INTEGER,
    turn INTEGER,
    p1_dices TEXT,
    p2_dices TEXT,
    status TEXT
)
""")


# درآمد مالک
cursor.execute("""
CREATE TABLE IF NOT EXISTS owner(
    id INTEGER PRIMARY KEY,
    coins INTEGER DEFAULT 0
)
""")


db.commit()


# ==============================
# 🔧 توابع دیتابیس
# ==============================

def add_user(user):
    cursor.execute(
        "SELECT id FROM users WHERE id=?",
        (user.id,)
    )

    if cursor.fetchone() is None:
        cursor.execute("""
        INSERT INTO users
        (id, username, name)
        VALUES (?,?,?)
        """,
        (
            user.id,
            user.username or "",
            user.first_name or ""
        ))

        db.commit()



def get_coins(user_id):
    cursor.execute(
        "SELECT coins FROM users WHERE id=?",
        (user_id,)
    )

    result = cursor.fetchone()

    if result:
        return result[0]

    return 0



def change_coin(user_id, amount):
    cursor.execute("""
    UPDATE users
    SET coins = coins + ?
    WHERE id=?
    """,
    (amount,user_id))

    db.commit()



# ==============================
# 🚀 شروع ربات
# ==============================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user

    add_user(user)


    keyboard = [
        [
            KeyboardButton("🎲 شروع بازی"),
            KeyboardButton("👤 حساب من")
        ],
        [
            KeyboardButton("💳 عابر بانک"),
            KeyboardButton("👥 دعوت دوستان")
        ],
        [
            KeyboardButton("🏆 رتبه بندی"),
            KeyboardButton("📜 قوانین")
        ]
    ]


    await update.message.reply_text(
        "🎲 به ربات بازی تاس خوش آمدید\n\n"
        "برای شروع بازی از منو استفاده کنید.",
        reply_markup=ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True
        )
    )



# ==============================
# اجرا
# ==============================

def main():

    app = Application.builder()\
        .token(BOT_TOKEN)\
        .build()


    app.add_handler(
        CommandHandler(
            "start",
            start
        )
    )


    print("Bot Started...")


    app.run_polling()



if __name__ == "__main__":
    main()