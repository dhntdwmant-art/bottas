#!/usr/bin/env python
# -*- coding: utf-8 -*-
# ============================================================
# COMPLETE TELEGRAM GAMBLING BOT - SINGLE FILE
# ============================================================
# ALL FEATURES: Admin Panel, Games, Financial System, 
# Referral System, Group Integration, Persian UI
# ============================================================

import os
import json
import sqlite3
import random
import string
import hashlib
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from contextlib import contextmanager
import re
import threading

# تنظیمات پایه
os.environ['TZ'] = 'Asia/Tehran'

# ============================================================
# CONFIGURATION
# ============================================================

class Config:
    # تنظیمات ربات
    BOT_TOKEN = "8943333410:AAFaCwNKDQDk8bwxQcg1EUSHl7lkhHzuWWw"
    OWNER_ID = 7548145568
    ADMIN_IDS = [7548145568]  # لیست ادمین‌ها
    
    # تنظیمات دیتابیس
    DATABASE_PATH = os.getenv("DATABASE_PATH", "bot_database.db")
    
    # تنظیمات مالی
    MIN_BET = 20000
    MIN_WITHDRAWAL = 100000
    REFERRAL_BONUS = 5000
    COMMISSION_RATE = 0.10  # 10%
    DAILY_BONUS = 1000
    
    # اطلاعات بانکی
    BANK_CARD = "6062561009737464"
    CRYPTO_WALLET = "UQD3sqpr9ktqh6SidPPEa1SuA_AbD_zJfpDWZee9KKfDaNu3"
    
    # محدودیت‌ها
    MAX_REQUESTS_PER_MINUTE = 10
    
    # تنظیمات Redis (اختیاری)
    REDIS_HOST = os.getenv("REDIS_HOST", "")
    REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
    REDIS_DB = int(os.getenv("REDIS_DB", 0))
    USE_REDIS = os.getenv("USE_REDIS", "false").lower() == "true"

# ============================================================
# PERSIAN LOCALIZATION
# ============================================================

class PersianMessages:
    """All Persian texts with proper formatting"""
    
    # Emojis and symbols
    DICE = "🎲"
    RPS = "✂️🗿📄"
    DARTS = "🎯"
    BOWLING = "🎳"
    TIC_TAC_TOE = "❌⭕"
    COIN = "💰"
    WALLET = "👛"
    TROPHY = "🏆"
    CROWN = "👑"
    GIFT = "🎁"
    SETTINGS = "⚙️"
    STATS = "📊"
    USER = "👤"
    ADMIN = "🛡️"
    REFERRAL = "🤝"
    DEPOSIT = "💳"
    WITHDRAW = "🏦"
    GAME = "🎮"
    WIN = "🎉"
    LOSS = "😔"
    TIE = "🤝"
    SUCCESS = "✅"
    ERROR = "❌"
    WARNING = "⚠️"
    INFO = "ℹ️"
    
    # Main menu
    MAIN_MENU = f"""
{COIN} **به ربات بازی و شرط‌بندی خوش آمدید!**

از منوی زیر یکی از گزینه‌ها را انتخاب کنید:

{USER} پروفایل و آمار
{GAME} بازی‌ها
{WALLET} مدیریت مالی
{REFERRAL} سیستم معرفی
{GIFT} جوایز و کدهای هدیه
{ADMIN} پنل مدیریت (فقط ادمین‌ها)
"""
    
    WELCOME_NEW = f"""
{COIN} **به ربات خوش آمدید!**

شما با موفقیت ثبت نام شدید.
برای شروع، از دکمه‌های زیر استفاده کنید.

✨ **راهنمای سریع:**
• برای بازی، روی دکمه {GAME} بازی‌ها کلیک کنید
• برای شارژ حساب، از {DEPOSIT} استفاده کنید
• با معرفی دوستان {REFERRAL} پاداش بگیرید
• حداقل شرط: {Config.MIN_BET:,} تومان
• کارمزد برد: ۱۰٪
"""
    
    # Error messages
    ERROR_INSUFFICIENT_BALANCE = """
{ERROR} **متأسفانه موجودی کافی نیست!**

موجودی فعلی شما: {balance:,} تومان
مبلغ مورد نیاز: {required:,} تومان

لطفاً حساب خود را شارژ کنید.
"""
    
    ERROR_INVALID_AMOUNT = """
{ERROR} **مبلغ نامعتبر است!**

لطفاً یک عدد معتبر وارد کنید.
حداقل مبلغ: {min_amount:,} تومان
"""
    
    ERROR_COMMAND_NOT_ALLOWED = """
{ERROR} **شما دسترسی به این بخش ندارید!**

این دستور فقط برای ادمین‌ها قابل استفاده است.
"""

# ============================================================
# DATABASE HANDLER
# ============================================================

class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_database()
    
    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def _init_database(self):
        """Initialize database with all tables"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Users table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER UNIQUE NOT NULL,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    balance INTEGER DEFAULT 0,
                    total_wins INTEGER DEFAULT 0,
                    total_losses INTEGER DEFAULT 0,
                    total_deposits INTEGER DEFAULT 0,
                    total_withdrawals INTEGER DEFAULT 0,
                    total_profit INTEGER DEFAULT 0,
                    referred_by INTEGER,
                    referral_count INTEGER DEFAULT 0,
                    referral_earnings INTEGER DEFAULT 0,
                    joined_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_active DATETIME DEFAULT CURRENT_TIMESTAMP,
                    is_banned BOOLEAN DEFAULT 0,
                    daily_bonus_claimed DATETIME,
                    FOREIGN KEY (referred_by) REFERENCES users(telegram_id)
                )
            ''')
            
            # Transactions table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    type TEXT NOT NULL,
                    amount INTEGER NOT NULL,
                    status TEXT DEFAULT 'pending',
                    description TEXT,
                    admin_note TEXT,
                    transaction_id TEXT UNIQUE,
                    receipt_image TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(telegram_id)
                )
            ''')
            
            # Games table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS games (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    game_type TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    players TEXT NOT NULL,
                    bet_amount INTEGER NOT NULL,
                    result TEXT,
                    winner_id INTEGER,
                    commission INTEGER DEFAULT 0,
                    game_data TEXT,
                    status TEXT DEFAULT 'active',
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (winner_id) REFERENCES users(telegram_id)
                )
            ''')
            
            # Admins table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS admins (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    permissions TEXT,
                    added_by INTEGER,
                    added_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(telegram_id),
                    FOREIGN KEY (added_by) REFERENCES users(telegram_id)
                )
            ''')
            
            # Settings table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_by INTEGER,
                    FOREIGN KEY (updated_by) REFERENCES users(telegram_id)
                )
            ''')
            
            # Gift codes table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS gift_codes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT UNIQUE NOT NULL,
                    amount INTEGER NOT NULL,
                    used_by INTEGER,
                    used_at DATETIME,
                    expires_at DATETIME NOT NULL,
                    is_active BOOLEAN DEFAULT 1,
                    created_by INTEGER NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (used_by) REFERENCES users(telegram_id),
                    FOREIGN KEY (created_by) REFERENCES users(telegram_id)
                )
            ''')
            
            # Referral links table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS referral_links (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    code TEXT UNIQUE NOT NULL,
                    clicks INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(telegram_id)
                )
            ''')
            
            # Game sessions table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS game_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    game_type TEXT NOT NULL,
                    creator_id INTEGER NOT NULL,
                    bet_amount INTEGER NOT NULL,
                    join_code TEXT UNIQUE,
                    status TEXT DEFAULT 'waiting',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (creator_id) REFERENCES users(telegram_id)
                )
            ''')
            
            # Activity logs table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS activity_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    admin_id INTEGER,
                    action TEXT NOT NULL,
                    details TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (admin_id) REFERENCES users(telegram_id)
                )
            ''')
            
            # Insert default settings
            cursor.execute('''
                INSERT OR IGNORE INTO settings (key, value) VALUES
                    ('min_bet', ?),
                    ('min_withdrawal', ?),
                    ('referral_bonus', ?),
                    ('commission_rate', ?),
                    ('daily_bonus', ?),
                    ('bank_card', ?),
                    ('crypto_wallet', ?)
            ''', (
                str(Config.MIN_BET),
                str(Config.MIN_WITHDRAWAL),
                str(Config.REFERRAL_BONUS),
                str(Config.COMMISSION_RATE),
                str(Config.DAILY_BONUS),
                Config.BANK_CARD,
                Config.CRYPTO_WALLET
            ))
            
            # Add owner as admin
            cursor.execute('''
                INSERT OR IGNORE INTO admins (user_id, role, permissions, added_by)
                VALUES (?, 'owner', '["all"]', ?)
            ''', (Config.OWNER_ID, Config.OWNER_ID))
            
            conn.commit()
    
    # ========== USER METHODS ==========
    
    def get_user(self, telegram_id: int) -> Optional[Dict]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE telegram_id = ?', (telegram_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def create_user(self, telegram_id: int, username: str, first_name: str, last_name: str = None) -> Dict:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR IGNORE INTO users (telegram_id, username, first_name, last_name)
                VALUES (?, ?, ?, ?)
            ''', (telegram_id, username, first_name, last_name))
            conn.commit()
            return self.get_user(telegram_id)
    
    def update_balance(self, telegram_id: int, amount: int, transaction_type: str, description: str = None) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            user = self.get_user(telegram_id)
            if not user:
                return False
            
            new_balance = user['balance'] + amount
            if new_balance < 0:
                return False
            
            cursor.execute('UPDATE users SET balance = ? WHERE telegram_id = ?', (new_balance, telegram_id))
            
            tx_id = self._generate_transaction_id()
            cursor.execute('''
                INSERT INTO transactions (user_id, type, amount, status, description, transaction_id)
                VALUES (?, ?, ?, 'completed', ?, ?)
            ''', (telegram_id, transaction_type, abs(amount), description, tx_id))
            
            conn.commit()
            return True
    
    def add_transaction(self, telegram_id: int, type: str, amount: int, status: str = 'pending', 
                        description: str = None, admin_note: str = None) -> str:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            tx_id = self._generate_transaction_id()
            cursor.execute('''
                INSERT INTO transactions (user_id, type, amount, status, description, admin_note, transaction_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (telegram_id, type, amount, status, description, admin_note, tx_id))
            conn.commit()
            return tx_id
    
    def get_transactions(self, telegram_id: int, limit: int = 10) -> List[Dict]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM transactions 
                WHERE user_id = ? 
                ORDER BY timestamp DESC 
                LIMIT ?
            ''', (telegram_id, limit))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_all_transactions(self, status: str = None, limit: int = 50) -> List[Dict]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if status:
                cursor.execute('''
                    SELECT * FROM transactions 
                    WHERE status = ?
                    ORDER BY timestamp DESC 
                    LIMIT ?
                ''', (status, limit))
            else:
                cursor.execute('''
                    SELECT * FROM transactions 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                ''', (limit,))
            return [dict(row) for row in cursor.fetchall()]
    
    # ========== GAME METHODS ==========
    
    def create_game_session(self, game_type: str, creator_id: int, bet_amount: int) -> str:
        join_code = self._generate_join_code()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO game_sessions (game_type, creator_id, bet_amount, join_code)
                VALUES (?, ?, ?, ?)
            ''', (game_type, creator_id, bet_amount, join_code))
            conn.commit()
            return join_code
    
    def join_game_session(self, join_code: str, player_id: int) -> Optional[Dict]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM game_sessions 
                WHERE join_code = ? AND status = 'waiting'
            ''', (join_code,))
            session = cursor.fetchone()
            if not session:
                return None
            
            session = dict(session)
            
            if session['creator_id'] == player_id:
                return None
            
            cursor.execute('''
                UPDATE game_sessions 
                SET status = 'active' 
                WHERE id = ?
            ''', (session['id'],))
            conn.commit()
            
            return session
    
    def get_game_session(self, join_code: str) -> Optional[Dict]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM game_sessions 
                WHERE join_code = ? AND status = 'waiting'
            ''', (join_code,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def save_game_result(self, game_type: str, mode: str, players: List[int], bet: int, 
                         result: str, winner_id: int = None, commission: int = 0, 
                         game_data: Dict = None) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO games (game_type, mode, players, bet_amount, result, 
                                 winner_id, commission, game_data, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'completed')
            ''', (game_type, mode, json.dumps(players), bet, result, 
                  winner_id, commission, json.dumps(game_data) if game_data else None))
            conn.commit()
            return cursor.lastrowid
    
    # ========== ADMIN METHODS ==========
    
    def is_admin(self, telegram_id: int) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT 1 FROM admins WHERE user_id = ?', (telegram_id,))
            return cursor.fetchone() is not None
    
    def get_admin_role(self, telegram_id: int) -> Optional[str]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT role FROM admins WHERE user_id = ?', (telegram_id,))
            row = cursor.fetchone()
            return row['role'] if row else None
    
    def add_admin(self, user_id: int, role: str, permissions: List[str], added_by: int) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('''
                    INSERT INTO admins (user_id, role, permissions, added_by)
                    VALUES (?, ?, ?, ?)
                ''', (user_id, role, json.dumps(permissions), added_by))
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False
    
    def remove_admin(self, user_id: int) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM admins WHERE user_id = ?', (user_id,))
            conn.commit()
            return cursor.rowcount > 0
    
    def get_all_admins(self) -> List[Dict]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT a.*, u.username, u.first_name 
                FROM admins a 
                JOIN users u ON a.user_id = u.telegram_id
                ORDER BY a.added_date DESC
            ''')
            return [dict(row) for row in cursor.fetchall()]
    
    # ========== GIFT CODES ==========
    
    def create_gift_code(self, amount: int, expires_in_hours: int, created_by: int) -> str:
        code = self._generate_gift_code()
        expires_at = datetime.now() + timedelta(hours=expires_in_hours)
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO gift_codes (code, amount, expires_at, created_by)
                VALUES (?, ?, ?, ?)
            ''', (code, amount, expires_at, created_by))
            conn.commit()
            return code
    
    def redeem_gift_code(self, code: str, user_id: int) -> Optional[int]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM gift_codes 
                WHERE code = ? AND is_active = 1 AND expires_at > CURRENT_TIMESTAMP
            ''', (code,))
            gift = cursor.fetchone()
            
            if not gift:
                return None
            
            gift = dict(gift)
            
            cursor.execute('''
                UPDATE gift_codes 
                SET used_by = ?, used_at = CURRENT_TIMESTAMP, is_active = 0
                WHERE id = ?
            ''', (user_id, gift['id']))
            
            self.update_balance(user_id, gift['amount'], 'gift', f'کد هدیه: {code}')
            
            conn.commit()
            return gift['amount']
    
    def get_active_gift_codes(self, limit: int = 10) -> List[Dict]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT code, amount, expires_at, created_at, created_by
                FROM gift_codes 
                WHERE is_active = 1 AND expires_at > CURRENT_TIMESTAMP
                ORDER BY created_at DESC 
                LIMIT ?
            ''', (limit,))
            return [dict(row) for row in cursor.fetchall()]
    
    # ========== REFERRAL ==========
    
    def create_referral_link(self, user_id: int) -> str:
        code = self._generate_referral_code(user_id)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO referral_links (user_id, code)
                VALUES (?, ?)
            ''', (user_id, code))
            conn.commit()
            return code
    
    def process_referral(self, referrer_id: int, new_user_id: int) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            referrer = self.get_user(referrer_id)
            if not referrer:
                return False
            
            bonus = self.get_setting('referral_bonus', Config.REFERRAL_BONUS)
            cursor.execute('''
                UPDATE users 
                SET referral_count = referral_count + 1,
                    referral_earnings = referral_earnings + ?,
                    balance = balance + ?
                WHERE telegram_id = ?
            ''', (bonus, bonus, referrer_id))
            
            cursor.execute('''
                UPDATE users 
                SET referred_by = ?
                WHERE telegram_id = ?
            ''', (referrer_id, new_user_id))
            
            self.add_transaction(referrer_id, 'referral', bonus, 'completed', 
                               f'پاداش معرفی کاربر جدید')
            
            conn.commit()
            return True
    
    # ========== SETTINGS ==========
    
    def get_setting(self, key: str, default: any = None) -> any:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
            row = cursor.fetchone()
            if row:
                value = row['value']
                if default is not None and isinstance(default, bool):
                    return value.lower() == 'true'
                elif default is not None and isinstance(default, int):
                    try:
                        return int(value)
                    except:
                        return default
                return value
            return default
    
    def set_setting(self, key: str, value: any, updated_by: int = None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO settings (key, value, updated_at, updated_by)
                VALUES (?, ?, CURRENT_TIMESTAMP, ?)
            ''', (key, str(value), updated_by))
            conn.commit()
    
    # ========== STATISTICS ==========
    
    def get_total_users(self) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) as count FROM users')
            return cursor.fetchone()['count']
    
    def get_total_coins(self) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT SUM(balance) as total FROM users')
            return cursor.fetchone()['total'] or 0
    
    def get_total_transactions(self) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) as count FROM transactions')
            return cursor.fetchone()['count']
    
    def get_financial_stats(self) -> Dict:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT SUM(amount) as total FROM transactions 
                WHERE type = 'deposit' AND status = 'completed'
            ''')
            total_deposits = cursor.fetchone()['total'] or 0
            
            cursor.execute('''
                SELECT SUM(amount) as total FROM transactions 
                WHERE type = 'withdrawal' AND status = 'completed'
            ''')
            total_withdrawals = cursor.fetchone()['total'] or 0
            
            cursor.execute('''
                SELECT SUM(commission) as total FROM games 
                WHERE status = 'completed'
            ''')
            total_commission = cursor.fetchone()['total'] or 0
            
            return {
                'total_deposits': total_deposits,
                'total_withdrawals': total_withdrawals,
                'total_commission': total_commission,
                'net_profit': total_commission
            }
    
    def get_leaderboard(self, limit: int = 10, by: str = 'balance') -> List[Dict]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f'''
                SELECT telegram_id, username, first_name, balance, total_wins, total_profit
                FROM users
                ORDER BY {by} DESC
                LIMIT ?
            ''', (limit,))
            return [dict(row) for row in cursor.fetchall()]
    
    # ========== HELPER METHODS ==========
    
    def _generate_transaction_id(self) -> str:
        return f"TX{datetime.now().strftime('%Y%m%d%H%M%S')}{''.join(random.choices(string.digits, k=6))}"
    
    def _generate_join_code(self) -> str:
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    
    def _generate_gift_code(self) -> str:
        return f"GIFT{''.join(random.choices(string.ascii_uppercase + string.digits, k=10))}"
    
    def _generate_referral_code(self, user_id: int) -> str:
        return f"REF{user_id}{''.join(random.choices(string.ascii_uppercase + string.digits, k=6))}"

# ============================================================
# GAME LOGIC
# ============================================================

class GameLogic:
    """All game logic implementations"""
    
    @staticmethod
    def roll_dice() -> Tuple[int, int]:
        """Returns (player1_roll, player2_roll)"""
        return random.randint(1, 6), random.randint(1, 6)
    
    @staticmethod
    def rps_winner(choice1: str, choice2: str) -> int:
        """0 = tie, 1 = player1 wins, 2 = player2 wins"""
        if choice1 == choice2:
            return 0
        wins = {'rock': 'scissors', 'scissors': 'paper', 'paper': 'rock'}
        if wins[choice1] == choice2:
            return 1
        return 2
    
    @staticmethod
    def darts_game() -> Tuple[int, int]:
        """Returns (score, multiplier)"""
        score = random.randint(1, 20)
        multiplier = random.choice([1, 2, 3])
        return score, multiplier
    
    @staticmethod
    def bowling_game() -> Tuple[int, int]:
        """Returns (pins, multiplier)"""
        pins = random.randint(0, 10)
        multiplier = 1 + (pins / 10)
        return pins, multiplier
    
    @staticmethod
    def even_odd_game() -> Tuple[int, str]:
        """Returns (number, 'even' or 'odd')"""
        number = random.randint(1, 6)
        return number, 'even' if number % 2 == 0 else 'odd'
    
    @staticmethod
    def tictactoe_move(board: List[str]) -> int:
        """Simple AI for Tic-Tac-Toe"""
        # Find winning move
        for i in range(9):
            if board[i] == ' ':
                board[i] = 'O'
                if GameLogic._check_win(board, 'O'):
                    board[i] = ' '
                    return i
                board[i] = ' '
        
        # Block player's winning move
        for i in range(9):
            if board[i] == ' ':
                board[i] = 'X'
                if GameLogic._check_win(board, 'X'):
                    board[i] = ' '
                    return i
                board[i] = ' '
        
        # Center
        if board[4] == ' ':
            return 4
        
        # Corners
        corners = [0, 2, 6, 8]
        random.shuffle(corners)
        for corner in corners:
            if board[corner] == ' ':
                return corner
        
        # Sides
        sides = [1, 3, 5, 7]
        random.shuffle(sides)
        for side in sides:
            if board[side] == ' ':
                return side
        
        return -1
    
    @staticmethod
    def _check_win(board: List[str], player: str) -> bool:
        win_patterns = [
            [0,1,2], [3,4,5], [6,7,8],
            [0,3,6], [1,4,7], [2,5,8],
            [0,4,8], [2,4,6]
        ]
        return any(all(board[i] == player for i in pattern) for pattern in win_patterns)

# ============================================================
# BOT HANDLERS
# ============================================================

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton, ParseMode,
    CallbackQuery, Message, User, Chat
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters, ConversationHandler, PicklePersistence
)
from telegram.constants import ChatAction
from telegram.error import BadRequest, Forbidden

class BotHandlers:
    """All bot command and callback handlers"""
    
    def __init__(self, db: Database):
        self.db = db
        self.user_states = {}
        self.game_sessions = {}
    
    # ========== START COMMAND ==========
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        telegram_id = user.id
        
        db_user = self.db.get_user(telegram_id)
        if not db_user:
            db_user = self.db.create_user(telegram_id, user.username, user.first_name, user.last_name)
            
            args = context.args
            if args and args[0].startswith('REF'):
                referrer_id = int(args[0][3:9]) if args[0][3:9].isdigit() else None
                if referrer_id and referrer_id != telegram_id:
                    self.db.process_referral(referrer_id, telegram_id)
        
        await update.message.reply_text(
            PersianMessages.WELCOME_NEW,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.get_main_menu_keyboard(telegram_id)
        )
    
    # ========== MAIN MENU ==========
    
    def get_main_menu_keyboard(self, user_id: int) -> InlineKeyboardMarkup:
        keyboard = [
            [InlineKeyboardButton(f"{PersianMessages.USER} پروفایل", callback_data="profile")],
            [InlineKeyboardButton(f"{PersianMessages.GAME} بازی‌ها", callback_data="games")],
            [InlineKeyboardButton(f"{PersianMessages.WALLET} مدیریت مالی", callback_data="financial")],
            [InlineKeyboardButton(f"{PersianMessages.REFERRAL} سیستم معرفی", callback_data="referral")],
            [InlineKeyboardButton(f"{PersianMessages.GIFT} کد هدیه", callback_data="gift")],
        ]
        
        if self.db.is_admin(user_id):
            keyboard.append([InlineKeyboardButton(f"{PersianMessages.ADMIN} پنل مدیریت", callback_data="admin_panel")])
        
        return InlineKeyboardMarkup(keyboard)
    
    # ========== PROFILE ==========
    
    async def profile_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        db_user = self.db.get_user(user_id)
        
        if not db_user:
            await query.edit_message_text("کاربر یافت نشد!")
            return
        
        referral_link = self.db.create_referral_link(user_id)
        
        profile_text = f"""
{PersianMessages.USER} **پروفایل کاربری**

🆔 شناسه: `{user_id}`
👤 نام: {db_user['first_name'] or 'کاربر'}
📛 یوزرنیم: @{db_user['username'] or 'ندارد'}
📅 تاریخ عضویت: {db_user['joined_date'][:10] if db_user['joined_date'] else 'نامشخص'}

{PersianMessages.COIN} **موجودی:** {db_user['balance']:,} تومان
🏆 بردها: {db_user['total_wins']}
😔 باخت‌ها: {db_user['total_losses']}
📈 سود/زیان کل: {db_user['total_profit']:,} تومان

{PersianMessages.REFERRAL} **سیستم معرفی:**
• تعداد معرفی‌ها: {db_user['referral_count']}
• پاداش دریافتی: {db_user['referral_earnings']:,} تومان
• لینک معرفی: `https://t.me/{context.bot.username}?start={referral_link}`
"""
        
        await query.edit_message_text(
            profile_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 بازگشت به منو", callback_data="back_to_menu")]
            ])
        )
    
    # ========== GAMES ==========
    
    async def games_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        min_bet = self.db.get_setting('min_bet', Config.MIN_BET)
        
        keyboard = [
            [InlineKeyboardButton(f"{PersianMessages.DICE} تاس (دو نفره)", callback_data="game_dice")],
            [InlineKeyboardButton(f"{PersianMessages.RPS} سنگ-کاغذ-قیچی", callback_data="game_rps")],
            [InlineKeyboardButton(f"{PersianMessages.DARTS} دارت (تکنفره)", callback_data="game_darts")],
            [InlineKeyboardButton(f"{PersianMessages.BOWLING} بولینگ (تکنفره)", callback_data="game_bowling")],
            [InlineKeyboardButton(f"{PersianMessages.DICE} فرد/زوج (تکنفره)", callback_data="game_evenodd")],
            [InlineKeyboardButton(f"{PersianMessages.TIC_TAC_TOE} ایکس-او (تکنفره)", callback_data="game_tictactoe")],
            [InlineKeyboardButton("🔙 بازگشت به منو", callback_data="back_to_menu")]
        ]
        
        await query.edit_message_text(
            f"""
{PersianMessages.GAME} **بازی‌های موجود**

**بازی‌های دو نفره (خصوصی یا تصادفی):**
{PersianMessages.DICE} تاس (بزرگ‌تر برنده است)
{PersianMessages.RPS} سنگ-کاغذ-قیچی

**بازی‌های تکنفره:**
{PersianMessages.DARTS} دارت (با شانس ضرب‌در)
{PersianMessages.BOWLING} بولینگ (ضریب پین‌ها)
{PersianMessages.DICE} فرد/زوج یا عدد دقیق
{PersianMessages.TIC_TAC_TOE} ایکس-او (با ربات)

💰 حداقل شرط: {min_bet:,} تومان💵 کارمزد برد: ۱۰٪
""",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    # ========== FINANCIAL ==========
    
    async def financial_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        db_user = self.db.get_user(user_id)
        
        if not db_user:
            await query.edit_message_text("کاربر یافت نشد!")
            return
        
        bank_card = self.db.get_setting('bank_card', Config.BANK_CARD)
        crypto_wallet = self.db.get_setting('crypto_wallet', Config.CRYPTO_WALLET)
        
        financial_text = f"""
{PersianMessages.WALLET} **مدیریت مالی**

{PersianMessages.COIN} موجودی فعلی: {db_user['balance']:,} تومان

{DEPOSIT} واریز وجه
🏦 برداشت وجه
📊 تاریخچه تراکنش‌ها

**اطلاعات بانکی برای واریز:**
🏦 شماره کارت: `{bank_card}`
💰 آدرس کیف پول: `{crypto_wallet}`
"""
        
        keyboard = [
            [InlineKeyboardButton(f"{PersianMessages.DEPOSIT} واریز وجه", callback_data="deposit")],
            [InlineKeyboardButton(f"{PersianMessages.WITHDRAW} برداشت وجه", callback_data="withdraw")],
            [InlineKeyboardButton("📊 تاریخچه تراکنش‌ها", callback_data="transaction_history")],
            [InlineKeyboardButton("🔙 بازگشت به منو", callback_data="back_to_menu")]
        ]
        
        await query.edit_message_text(
            financial_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    # ========== DEPOSIT ==========
    
    async def deposit_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        bank_card = self.db.get_setting('bank_card', Config.BANK_CARD)
        crypto_wallet = self.db.get_setting('crypto_wallet', Config.CRYPTO_WALLET)
        
        message = f"""
{PersianMessages.DEPOSIT} **واریز وجه**

لطفاً مبلغ مورد نظر را به یکی از روش‌های زیر واریز کنید:

🏦 **شماره کارت:** `{bank_card}`
💰 **کیف پول کریپتو:** `{crypto_wallet}`

پس از واریز، لطفاً **مبلغ** و **شناسه تراکنش** یا **تصویر رسید** را ارسال کنید.

**دستورات:**
`/deposit 100000` - درخواست واریز ۱۰۰٬۰۰۰ تومان
تصویر رسید - ارسال تصویر برای تأیید
"""
        
        await query.edit_message_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 بازگشت به منو", callback_data="back_to_menu")]
            ])
        )
        
        self.user_states[query.from_user.id] = {'state': 'deposit_pending'}
    
    # ========== WITHDRAWAL ==========
    
    async def withdrawal_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        db_user = self.db.get_user(user_id)
        
        if not db_user:
            await query.edit_message_text("کاربر یافت نشد!")
            return
        
        min_withdrawal = self.db.get_setting('min_withdrawal', Config.MIN_WITHDRAWAL)
        
        message = f"""
{PersianMessages.WITHDRAW} **برداشت وجه**

موجودی فعلی: {db_user['balance']:,} تومان
حداقل مبلغ برداشت: {min_withdrawal:,} تومان

لطفاً برای برداشت از دستور زیر استفاده کنید:
`/withdraw [مبلغ] [شماره کارت]`

مثال: `/withdraw 100000 6037991234567890`
"""
        
        await query.edit_message_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 بازگشت به منو", callback_data="back_to_menu")]
            ])
        )
        
        self.user_states[query.from_user.id] = {'state': 'withdrawal_pending'}
    
    # ========== REFERRAL ==========
    
    async def referral_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        db_user = self.db.get_user(user_id)
        
        if not db_user:
            await query.edit_message_text("کاربر یافت نشد!")
            return
        
        referral_link = self.db.create_referral_link(user_id)
        ref_bonus = self.db.get_setting('referral_bonus', Config.REFERRAL_BONUS)
        
        top_users = self.db.get_leaderboard(5, 'referral_count')
        top_text = ""
        for i, user in enumerate(top_users, 1):
            top_text += f"{i}. {user['first_name'] or 'کاربر'} - {user['referral_count']} معرفی\n"
        
        message = f"""
{PersianMessages.REFERRAL} **سیستم معرفی**

🎁 **پاداش هر معرفی:** {ref_bonus:,} تومان
👥 **تعداد معرفی‌های شما:** {db_user['referral_count']}
💰 **پاداش دریافتی:** {db_user['referral_earnings']:,} تومان

🔗 **لینک معرفی شما:**
`https://t.me/{context.bot.username}?start={referral_link}`

**۵ کاربر برتر در معرفی:**
{top_text}

✨ **نحوه کار:**
هر کاربر جدید که از طریق لینک شما ثبت نام کند، به شما پاداش تعلق می‌گیرد!
"""
        
        await query.edit_message_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 بازگشت به منو", callback_data="back_to_menu")]
            ])
        )
    
    # ========== GIFT REDEEM ==========
    
    async def gift_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        message = f"""
{PersianMessages.GIFT} **کد هدیه**

لطفاً کد هدیه خود را وارد کنید:
`/gift [کد هدیه]`

مثال: `/gift GIFTABCD1234`
"""
        
        await query.edit_message_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 بازگشت به منو", callback_data="back_to_menu")]
            ])
        )
    
    # ========== TRANSACTION HISTORY ==========
    
    async def transaction_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        transactions = self.db.get_transactions(user_id, 10)
        
        if not transactions:
            message = "📊 **تاریخچه تراکنش‌ها**\n\nهیچ تراکنشی یافت نشد."
        else:
            message = "📊 **۱۰ تراکنش آخر:**\n\n"
            for tx in transactions:
                status_emoji = "✅" if tx['status'] == 'completed' else "⏳" if tx['status'] == 'pending' else "❌"
                message += f"{status_emoji} {tx['type']}: {tx['amount']:,} تومان - {tx['timestamp'][:10]}\n"
        
        await query.edit_message_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 بازگشت به منو", callback_data="back_to_menu")]
            ])
        )
    
    # ========== GAME HANDLERS ==========
    
    async def game_dice(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        db_user = self.db.get_user(user_id)
        
        if not db_user:
            await query.edit_message_text("کاربر یافت نشد!")
            return
        
        min_bet = self.db.get_setting('min_bet', Config.MIN_BET)
        
        keyboard = [
            [InlineKeyboardButton("🎲 بازی تصادفی", callback_data="dice_random")],
            [InlineKeyboardButton("🔑 بازی با کد", callback_data="dice_code")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="games")]
        ]
        
        message = f"""
{PersianMessages.DICE} **بازی تاس**

💰 حداقل شرط: {min_bet:,} تومان
👥 نحوه بازی: هر بازیکن یک تاس می‌اندازد، عدد بزرگ‌تر برنده است

**حالت‌های بازی:**
• **تصادفی:** با یک بازیکن تصادفی هماهنگ می‌شوید
• **با کد:** یک بازی خصوصی ایجاد کرده و کد را به دوست خود می‌دهید

💵 کارمزد برد: ۱۰٪

لطفاً مبلغ شرط خود را وارد کنید:
`/bet [مبلغ]`
"""
        
        await query.edit_message_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        self.user_states[user_id] = {'state': 'dice_game', 'mode': 'selecting'}
    
    async def game_rps(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        min_bet = self.db.get_setting('min_bet', Config.MIN_BET)
        
        keyboard = [
            [InlineKeyboardButton("✂️ قیچی", callback_data="rps_scissors"),
             InlineKeyboardButton("🗿 سنگ", callback_data="rps_rock"),
             InlineKeyboardButton("📄 کاغذ", callback_data="rps_paper")],
            [InlineKeyboardButton("🎲 بازی تصادفی", callback_data="rps_random")],
            [InlineKeyboardButton("🔑 بازی با کد", callback_data="rps_code")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="games")]
        ]
        
        message = f"""
{PersianMessages.RPS} **بازی سنگ-کاغذ-قیچی**

💰 حداقل شرط: {min_bet:,} تومان
👥 نحوه بازی: هر بازیکن یکی از گزینه‌های سنگ، کاغذ یا قیچی را انتخاب می‌کند

**حالت‌های بازی:**
• **تصادفی:** با یک بازیکن تصادفی هماهنگ می‌شوید
• **با کد:** یک بازی خصوصی ایجاد کرده و کد را به دوست خود می‌دهید

💵 کارمزد برد: ۱۰٪

لطفاً مبلغ شرط خود را وارد کنید:
`/bet [مبلغ]`
"""
        
        await query.edit_message_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        self.user_states[user_id] = {'state': 'rps_game', 'mode': 'selecting'}
    
    async def game_darts(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        db_user = self.db.get_user(user_id)
        
        if not db_user:
            await query.edit_message_text("کاربر یافت نشد!")
            return
        
        min_bet = self.db.get_setting('min_bet', Config.MIN_BET)
        
        message = f"""
{PersianMessages.DARTS} **بازی دارت**

🎯 هدف: پرتاب دارت به سمت تخته
💰 حداقل شرط: {min_bet:,} تومان
🎯 ضریب: هر بخش امتیاز خاص خود را دارد

**نحوه بازی:**
شما یک پرتاب انجام می‌دهید و امتیاز شما بر اساس بخشی که به آن اصابت می‌کنید محاسبه می‌شود.
برنده کسی است که امتیاز بیشتری داشته باشد.

لطفاً مبلغ شرط خود را وارد کنید:
`/bet [مبلغ]`
"""
        
        await query.edit_message_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🎯 شروع بازی", callback_data="darts_play")],
                [InlineKeyboardButton("🔙 بازگشت", callback_data="games")]
            ])
        )
        
        self.user_states[user_id] = {'state': 'darts_game', 'mode': 'playing'}
    
    async def game_bowling(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        min_bet = self.db.get_setting('min_bet', Config.MIN_BET)
        
        message = f"""
{PersianMessages.BOWLING} **بازی بولینگ**

🎳 هدف: انداختن توپ و کوبیدن پین‌ها
💰 حداقل شرط: {min_bet:,} تومان
🎳 ضریب: هر چه پین‌های بیشتری بیفتند، ضریب بالاتر می‌رود

**نحوه بازی:**
شما یک پرتاب انجام می‌دهید و تعداد پین‌های افتاده مشخص می‌شود.
ضریب بر اساس تعداد پین‌ها محاسبه می‌شود.

لطفاً مبلغ شرط خود را وارد کنید:
`/bet [مبلغ]`
"""
        
        await query.edit_message_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🎳 شروع بازی", callback_data="bowling_play")],
                [InlineKeyboardButton("🔙 بازگشت", callback_data="games")]
            ])
        )
        
        self.user_states[user_id] = {'state': 'bowling_game', 'mode': 'playing'}
    
    async def game_evenodd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        min_bet = self.db.get_setting('min_bet', Config.MIN_BET)
        
        keyboard = [
            [InlineKeyboardButton("🔢 فرد", callback_data="evenodd_odd"),
             InlineKeyboardButton("🔢 زوج", callback_data="evenodd_even")],
            [InlineKeyboardButton("🎯 عدد دقیق", callback_data="evenodd_exact")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="games")]
        ]
        
        message = f"""
{PersianMessages.DICE} **بازی فرد/زوج یا عدد دقیق**

💰 حداقل شرط: {min_bet:,} تومان
🎲 تاس: یک تاس ۶ وجهی پرتاب می‌شود

**حالت‌های بازی:**
• **فرد/زوج:** پیش‌بینی کنید که عدد فرد است یا زوج (برد ۲ برابر)
• **عدد دقیق:** عدد دقیق تاس را پیش‌بینی کنید (برد ۶ برابر)

💵 کارمزد برد: ۱۰٪

لطفاً مبلغ شرط خود را وارد کنید:
`/bet [مبلغ]`
"""
        
        await query.edit_message_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        self.user_states[user_id] = {'state': 'evenodd_game', 'mode': 'selecting'}
    
    async def game_tictactoe(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        min_bet = self.db.get_setting('min_bet', Config.MIN_BET)
        
        message = f"""
{PersianMessages.TIC_TAC_TOE} **بازی ایکس-او**

❌⭕ بازی با ربات هوشمند
💰 حداقل شرط: {min_bet:,} تومان
🎮 شما با ❌ و ربات با ⭕ بازی می‌کنید

**نحوه بازی:**
شما باید ۳ علامت خود را در یک ردیف، ستون یا قطر قرار دهید تا برنده شوید.

💵 کارمزد برد: ۱۰٪

لطفاً مبلغ شرط خود را وارد کنید:
`/bet [مبلغ]`
"""
        
        await query.edit_message_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ شروع بازی", callback_data="tictactoe_play")],
                [InlineKeyboardButton("🔙 بازگشت", callback_data="games")]
            ])
        )
        
        self.user_states[user_id] = {'state': 'tictactoe_game', 'mode': 'playing'}
    
    # ========== BET HANDLER ==========
    
    async def bet_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        text = update.message.text
        
        try:
            bet_amount = int(text.split()[1])
        except (IndexError, ValueError):
            await update.message.reply_text(
                f"{PersianMessages.ERROR} لطفاً مبلغ معتبر وارد کنید.\nمثال: `/bet 20000`",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        db_user = self.db.get_user(user_id)
        if not db_user:
            await update.message.reply_text("لطفاً ابتدا با دستور /start ثبت نام کنید.")
            return
        
        min_bet = self.db.get_setting('min_bet', Config.MIN_BET)
        
        if bet_amount < min_bet:
            await update.message.reply_text(
                PersianMessages.ERROR_INVALID_AMOUNT.format(min_amount=min_bet),
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        if bet_amount > db_user['balance']:
            await update.message.reply_text(
                PersianMessages.ERROR_INSUFFICIENT_BALANCE.format(
                    balance=db_user['balance'],
                    required=bet_amount
                ),
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        if user_id not in self.user_states:
            self.user_states[user_id] = {}
        
        self.user_states[user_id]['bet_amount'] = bet_amount
        self.user_states[user_id]['game_ready'] = True
        
        await update.message.reply_text(
            f"{PersianMessages.SUCCESS} مبلغ شرط {bet_amount:,} تومان ثبت شد.\n"
            "حالا بازی مورد نظر را انتخاب کنید.",
            parse_mode=ParseMode.MARKDOWN
        )
    
    # ========== ADMIN PANEL ==========
    
    async def admin_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        if not self.db.is_admin(user_id):
            await query.edit_message_text(
                PersianMessages.ERROR_COMMAND_NOT_ALLOWED,
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        keyboard = [
            [InlineKeyboardButton("📊 آمار کلی", callback_data="admin_stats")],
            [InlineKeyboardButton("👥 مدیریت کاربران", callback_data="admin_users")],
            [InlineKeyboardButton("💰 مدیریت مالی", callback_data="admin_financial")],
            [InlineKeyboardButton("🎮 مدیریت بازی‌ها", callback_data="admin_games")],
            [InlineKeyboardButton(f"{PersianMessages.REFERRAL} سیستم معرفی", callback_data="admin_referral")],
            [InlineKeyboardButton(f"{PersianMessages.GIFT} کدهای هدیه", callback_data="admin_gift_codes")],
            [InlineKeyboardButton(f"{PersianMessages.SETTINGS} تنظیمات", callback_data="admin_settings")],
            [InlineKeyboardButton(f"{PersianMessages.ADMIN} مدیریت ادمین‌ها", callback_data="admin_admins")],
            [InlineKeyboardButton("📋 گزارش‌ها", callback_data="admin_reports")],
            [InlineKeyboardButton("🔙 بازگشت به منو", callback_data="back_to_menu")]
        ]
        
        await query.edit_message_text(
            f"""
{PersianMessages.ADMIN} **پنل مدیریت**

📊 آمار کلی
👥 مدیریت کاربران
💰 مدیریت مالی
🎮 مدیریت بازی‌ها
{PersianMessages.REFERRAL} سیستم معرفی
{PersianMessages.GIFT} کدهای هدیه
{PersianMessages.SETTINGS} تنظیمات
{PersianMessages.ADMIN} مدیریت ادمین‌ها
📋 گزارش‌ها
""",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    # ========== ADMIN STATS ==========
    
    async def admin_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        if not self.db.is_admin(user_id):
            await query.edit_message_text(
                PersianMessages.ERROR_COMMAND_NOT_ALLOWED,
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        total_users = self.db.get_total_users()
        total_coins = self.db.get_total_coins()
        total_tx = self.db.get_total_transactions()
        financial_stats = self.db.get_financial_stats()
        
        message = f"""
📊 **آمار کلی ربات**

👥 **کاربران:** {total_users:,} نفر
💰 **کل سکه در گردش:** {total_coins:,} تومان
📊 **کل تراکنش‌ها:** {total_tx:,}

💰 **آمار مالی:**
• کل واریزها: {financial_stats['total_deposits']:,} تومان
• کل برداشت‌ها: {financial_stats['total_withdrawals']:,} تومان
• کارمزد کل: {financial_stats['total_commission']:,} تومان
• سود خالص: {financial_stats['net_profit']:,} تومان

📈 **۱۰ کاربر برتر:**
"""
        
        top_users = self.db.get_leaderboard(10)
        for i, user in enumerate(top_users, 1):
            message += f"{i}. {user['first_name'] or 'کاربر'} - {user['balance']:,} تومان\n"
        
        await query.edit_message_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 بازگشت به پنل", callback_data="admin_panel")]
            ])
        )
    
    # ========== ADMIN FINANCIAL ==========
    
    async def admin_financial(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        if not self.db.is_admin(user_id):
            await query.edit_message_text(
                PersianMessages.ERROR_COMMAND_NOT_ALLOWED,
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        financial_stats = self.db.get_financial_stats()
        
        message = f"""
💰 **مدیریت مالی**

📊 **خلاصه مالی:**
• کل واریزها: {financial_stats['total_deposits']:,} تومان
• کل برداشت‌ها: {financial_stats['total_withdrawals']:,} تومان
• کارمزد کل: {financial_stats['total_commission']:,} تومان
• سود خالص: {financial_stats['net_profit']:,} تومان

**دستورات مالی:**
`/confirm [شناسه تراکنش]` - تأیید واریز
`/reject [شناسه تراکنش]` - رد واریز
`/settle` - تسویه حساب با صاحب ربات
"""
        
        await query.edit_message_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 بازگشت به پنل", callback_data="admin_panel")]
            ])
        )
    
    # ========== ADMIN SETTINGS ==========
    
    async def admin_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        if not self.db.is_admin(user_id):
            await query.edit_message_text(
                PersianMessages.ERROR_COMMAND_NOT_ALLOWED,
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        min_bet = self.db.get_setting('min_bet', Config.MIN_BET)
        min_withdrawal = self.db.get_setting('min_withdrawal', Config.MIN_WITHDRAWAL)
        ref_bonus = self.db.get_setting('referral_bonus', Config.REFERRAL_BONUS)
        commission = self.db.get_setting('commission_rate', Config.COMMISSION_RATE)
        daily_bonus = self.db.get_setting('daily_bonus', Config.DAILY_BONUS)
        bank_card = self.db.get_setting('bank_card', Config.BANK_CARD)
        crypto_wallet = self.db.get_setting('crypto_wallet', Config.CRYPTO_WALLET)
        
        message = f"""
{PersianMessages.SETTINGS} **تنظیمات ربات**

💰 **حداقل شرط:** {min_bet:,} تومان
🏦 **حداقل برداشت:** {min_withdrawal:,} تومان
🎁 **پاداش معرفی:** {ref_bonus:,} تومان
💵 **کارمزد برد:** {int(commission * 100)}%
🎁 **پاداش روزانه:** {daily_bonus:,} تومان
🏦 **شماره کارت:** `{bank_card}`
💰 **کیف پول:** `{crypto_wallet}`

**دستورات تغییر تنظیمات:**
`/setbet [مبلغ]` - تغییر حداقل شرط
`/setref [مبلغ]` - تغییر پاداش معرفی
`/setcard [شماره کارت]` - تغییر شماره کارت
`/setwallet [آدرس]` - تغییر آدرس کیف پول
"""
        
        await query.edit_message_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 بازگشت به پنل", callback_data="admin_panel")]
            ])
        )
    
    # ========== ADMIN GIFT CODES ==========
    
    async def admin_gift_codes(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        if not self.db.is_admin(user_id):
            await query.edit_message_text(
                PersianMessages.ERROR_COMMAND_NOT_ALLOWED,
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        message = f"""
{PersianMessages.GIFT} **مدیریت کدهای هدیه**

**دستورات:**
`/giftcode [مبلغ] [ساعت انقضا]` - ایجاد کد هدیه
مثال: `/giftcode 50000 24` - کد ۵۰٬۰۰۰ تومانی با اعتبار ۲۴ ساعت

**کدهای هدیه فعال:**
"""
        
        codes = self.db.get_active_gift_codes(10)
        
        if codes:
            for code in codes:
                message += f"\n• `{code['code']}` - {code['amount']:,} تومان - تا {code['expires_at']}"
        else:
            message += "\nهیچ کد هدیه فعالی وجود ندارد."
        
        await query.edit_message_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 بازگشت به پنل", callback_data="admin_panel")]
            ])
        )
    
    # ========== ADMIN ADMINS ==========
    
    async def admin_admins(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        if not self.db.is_admin(user_id):
            await query.edit_message_text(
                PersianMessages.ERROR_COMMAND_NOT_ALLOWED,
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        admins = self.db.get_all_admins()
        
        message = f"""
{PersianMessages.ADMIN} **مدیریت ادمین‌ها**

**لیست ادمین‌ها:**
"""
        
        for admin in admins:
            message += f"\n• {admin['first_name'] or 'کاربر'} (@{admin['username'] or 'ندارد'}) - نقش: {admin['role']}"
        
        message += """

**دستورات:**
`/addadmin [شناسه] [نقش]` - افزودن ادمین جدید
نقش‌ها: owner, financial, support
`/removeadmin [شناسه]` - حذف ادمین
"""
        
        await query.edit_message_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 بازگشت به پنل", callback_data="admin_panel")]
            ])
        )
    
    # ========== ADMIN REPORTS ==========
    
    async def admin_reports(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        if not self.db.is_admin(user_id):
            await query.edit_message_text(
                PersianMessages.ERROR_COMMAND_NOT_ALLOWED,
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        message = """
📋 **گزارش‌ها**

**دستورات گزارش‌گیری:**
`/report users` - گزارش کامل کاربران
`/report financial` - گزارش مالی کامل
`/report games` - گزارش بازی‌ها
`/report transactions` - گزارش تراکنش‌ها

**خروجی:** متن یا CSV
"""
        
        await query.edit_message_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📥 دریافت گزارش CSV", callback_data="report_csv")],
                [InlineKeyboardButton("📄 دریافت گزارش متنی", callback_data="report_text")],
                [InlineKeyboardButton("🔙 بازگشت به پنل", callback_data="admin_panel")]
            ])
        )
    
    # ========== BACK TO MENU ==========
    
    async def back_to_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        await query.edit_message_text(
            PersianMessages.MAIN_MENU,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.get_main_menu_keyboard(user_id)
        )
    
    # ========== MESSAGE HANDLER ==========
    
    async def message_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        text = update.message.text
        
        if text and text.startswith('/deposit'):
            await self.deposit_command(update, context)
            return
        
        if text and text.startswith('/withdraw'):
            await self.withdraw_command(update, context)
            return
        
        if text and text.startswith('/gift'):
            await self.gift_command(update, context)
            return
        
        if text and text.startswith('/bet'):
            await self.bet_handler(update, context)
            return
        
        if user_id in self.user_states:
            state = self.user_states[user_id]
            
            if state.get('state') == 'deposit_pending':
                if update.message.photo:
                    await self.handle_deposit_receipt(update, context)
                    return
        
        await update.message.reply_text(
            "لطفاً از دستورات و دکمه‌های موجود استفاده کنید.\n"
            "برای مشاهده منو، دستور /start را وارد کنید.",
            parse_mode=ParseMode.MARKDOWN
        )
    
    # ========== DEPOSIT COMMAND ==========
    
    async def deposit_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        text = update.message.text
        
        try:
            amount = int(text.split()[1])
        except (IndexError, ValueError):
            await update.message.reply_text(
                f"{PersianMessages.ERROR} لطفاً مبلغ معتبر وارد کنید.\nمثال: `/deposit 100000`",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        if amount <= 0:
            await update.message.reply_text(
                f"{PersianMessages.ERROR} مبلغ باید بزرگتر از صفر باشد.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        bank_card = self.db.get_setting('bank_card', Config.BANK_CARD)
        crypto_wallet = self.db.get_setting('crypto_wallet', Config.CRYPTO_WALLET)
        
        tx_id = self.db.add_transaction(
            user_id, 'deposit', amount, 'pending',
            f'درخواست واریز {amount:,} تومان'
        )
        
        message = f"""
{PersianMessages.DEPOSIT} **درخواست واریز ثبت شد**

مبلغ: {amount:,} تومان
شناسه تراکنش: `{tx_id}`

**لطفاً مبلغ را به یکی از روش‌های زیر واریز کنید:**

🏦 **شماره کارت:** `{bank_card}`
💰 **کیف پول:** `{crypto_wallet}`

پس از واریز، تصویر رسید را ارسال کنید تا توسط ادمین تأیید شود.

وضعیت: در انتظار تأیید ⏳
"""
        
        await update.message.reply_text(
            message,
            parse_mode=ParseMode.MARKDOWN
        )
        
        self.user_states[user_id] = {
            'state': 'deposit_pending',
            'tx_id': tx_id,
            'amount': amount
        }
        
        await self.notify_admins(context, f"""
🔔 **درخواست واریز جدید**

👤 کاربر: {update.effective_user.first_name} (@{update.effective_user.username or 'ندارد'})
💰 مبلغ: {amount:,} تومان
🆔 شناسه: {tx_id}

برای تأیید: `/confirm {tx_id}`
برای رد: `/reject {tx_id}`
""")
    
    # ========== WITHDRAW COMMAND ==========
    
    async def withdraw_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        text = update.message.text
        
        parts = text.split()
        if len(parts) < 3:
            await update.message.reply_text(
                f"{PersianMessages.ERROR} فرمت صحیح:\n`/withdraw [مبلغ] [شماره کارت]`\nمثال: `/withdraw 100000 6037991234567890`",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        try:
            amount = int(parts[1])
            card_number = parts[2]
        except ValueError:
            await update.message.reply_text(
                f"{PersianMessages.ERROR} مبلغ نامعتبر است.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        db_user = self.db.get_user(user_id)
        if not db_user:
            await update.message.reply_text("لطفاً ابتدا ثبت نام کنید.")
            return
        
        min_withdrawal = self.db.get_setting('min_withdrawal', Config.MIN_WITHDRAWAL)
        
        if amount < min_withdrawal:
            await update.message.reply_text(
                PersianMessages.ERROR_INVALID_AMOUNT.format(min_amount=min_withdrawal),
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        if amount > db_user['balance']:
            await update.message.reply_text(
                PersianMessages.ERROR_INSUFFICIENT_BALANCE.format(
                    balance=db_user['balance'],
                    required=amount
                ),
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        tx_id = self.db.add_transaction(
            user_id, 'withdrawal', amount, 'pending',
            f'درخواست برداشت {amount:,} تومان به کارت {card_number}'
        )
        
        self.db.update_balance(user_id, -amount, 'withdrawal', f'برداشت به کارت {card_number}')
        
        message = f"""
{PersianMessages.WITHDRAW} **درخواست برداشت ثبت شد!**

💰 مبلغ: {amount:,} تومان
🏦 شماره کارت: {card_number}
🆔 شناسه درخواست: `{tx_id}`

وضعیت: در انتظار تأیید ادمین ⏳
"""
        
        await update.message.reply_text(
            message,
            parse_mode=ParseMode.MARKDOWN
        )
        
        await self.notify_admins(context, f"""
🔔 **درخواست برداشت جدید**

👤 کاربر: {db_user['first_name']} (@{db_user['username'] or 'ندارد'})
💰 مبلغ: {amount:,} تومان
🏦 شماره کارت: {card_number}
🆔 شناسه: {tx_id}

برای تأیید: `/confirm {tx_id}`
برای رد: `/reject {tx_id}`
""")
    
    # ========== GIFT COMMAND ==========
    
    async def gift_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        text = update.message.text
        
        try:
            code = text.split()[1]
        except IndexError:
            await update.message.reply_text(
                f"{PersianMessages.ERROR} لطفاً کد هدیه را وارد کنید.\nمثال: `/gift GIFTABCD1234`",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        amount = self.db.redeem_gift_code(code, user_id)
        
        if amount is None:
            await update.message.reply_text(
                f"{PersianMessages.ERROR} کد هدیه نامعتبر یا منقضی شده است.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        db_user = self.db.get_user(user_id)
        
        await update.message.reply_text(
            f"""
{PersianMessages.SUCCESS} **کد هدیه با موفقیت استفاده شد!**

🎁 مبلغ: {amount:,} تومان
💰 موجودی جدید: {db_user['balance']:,} تومان

تبریک! 🎉
""",
            parse_mode=ParseMode.MARKDOWN
        )
    
    # ========== HANDLE DEPOSIT RECEIPT ==========
    
    async def handle_deposit_receipt(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        if user_id not in self.user_states:
            return
        
        state = self.user_states[user_id]
        if state.get('state') != 'deposit_pending':
            return
        
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        
        tx_id = state.get('tx_id')
        amount = state.get('amount')
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE transactions 
                SET receipt_image = ? 
                WHERE transaction_id = ?
            ''', (file.file_id, tx_id))
            conn.commit()
        
        await update.message.reply_text(
            f"""
{PersianMessages.SUCCESS} **تصویر رسید دریافت شد!**

شناسه تراکنش: `{tx_id}`
مبلغ: {amount:,} تومان

وضعیت: در انتظار تأیید ادمین ⏳
به محض تأیید، موجودی شما افزایش می‌یابد.
""",
            parse_mode=ParseMode.MARKDOWN
        )
        
        db_user = self.db.get_user(user_id)
        await self.notify_admins(context, f"""
🔔 **درخواست واریز با رسید**

👤 کاربر: {db_user['first_name']} (@{db_user['username'] or 'ندارد'})
💰 مبلغ: {amount:,} تومان
🆔 شناسه: {tx_id}

تصویر رسید دریافت شد.
برای تأیید: `/confirm {tx_id}`
برای رد: `/reject {tx_id}`
""")
        
        del self.user_states[user_id]
    
    # ========== ADMIN COMMAND HANDLERS ==========
    
    async def confirm_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        if not self.db.is_admin(user_id):
            await update.message.reply_text(
                PersianMessages.ERROR_COMMAND_NOT_ALLOWED,
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        text = update.message.text
        try:
            tx_id = text.split()[1]
        except IndexError:
            await update.message.reply_text(
                f"{PersianMessages.ERROR} لطفاً شناسه تراکنش را وارد کنید.\nمثال: `/confirm TX202401011200001`",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM transactions 
                WHERE transaction_id = ? AND status = 'pending'
            ''', (tx_id,))
            tx = cursor.fetchone()
            
            if not tx:
                await update.message.reply_text(
                    f"{PersianMessages.ERROR} تراکنش یافت نشد یا قبلاً تأیید شده است.",
                    parse_mode=ParseMode.MARKDOWN
                )
                return
            
            tx = dict(tx)
            
            cursor.execute('''
                UPDATE transactions 
                SET status = 'completed', admin_note = 'تأیید شده توسط ادمین'
                WHERE transaction_id = ?
            ''', (tx_id,))
            
            cursor.execute('''
                UPDATE users 
                SET balance = balance + ?,
                    total_deposits = total_deposits + ?
                WHERE telegram_id = ?
            ''', (tx['amount'], tx['amount'], tx['user_id']))
            
            conn.commit()
        
        await update.message.reply_text(
            f"""
{PersianMessages.SUCCESS} **تراکنش تأیید شد!**

شناسه: `{tx_id}`
مبلغ: {tx['amount']:,} تومان
وضعیت: تکمیل شده ✅
""",
            parse_mode=ParseMode.MARKDOWN
        )
        
        try:
            await context.bot.send_message(
                tx['user_id'],
                f"""
{PersianMessages.SUCCESS} **واریز شما تأیید شد!**

💰 مبلغ: {tx['amount']:,} تومان
✅ وضعیت: تکمیل شده

موجودی شما به‌روزرسانی شد.
"""
            )
        except:
            pass
    
    async def reject_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        if not self.db.is_admin(user_id):
            await update.message.reply_text(
                PersianMessages.ERROR_COMMAND_NOT_ALLOWED,
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        text = update.message.text
        try:
            tx_id = text.split()[1]
        except IndexError:
            await update.message.reply_text(
                f"{PersianMessages.ERROR} لطفاً شناسه تراکنش را وارد کنید.\nمثال: `/reject TX202401011200001`",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM transactions 
                WHERE transaction_id = ? AND status = 'pending'
            ''', (tx_id,))
            tx = cursor.fetchone()
            
            if not tx:
                await update.message.reply_text(
                    f"{PersianMessages.ERROR} تراکنش یافت نشد یا قبلاً تأیید شده است.",
                    parse_mode=ParseMode.MARKDOWN
                )
                return
            
            tx = dict(tx)
            
            cursor.execute('''
                UPDATE transactions 
                SET status = 'rejected', admin_note = 'رد شده توسط ادمین'
                WHERE transaction_id = ?
            ''', (tx_id,))
            
            conn.commit()
        
        await update.message.reply_text(
            f"""
{PersianMessages.ERROR} **تراکنش رد شد!**

شناسه: `{tx_id}`
مبلغ: {tx['amount']:,} تومان
وضعیت: رد شده ❌
""",
            parse_mode=ParseMode.MARKDOWN
        )
        
        try:
            await context.bot.send_message(
                tx['user_id'],
                f"""
{PersianMessages.ERROR} **درخواست واریز شما رد شد!**

💰 مبلغ: {tx['amount']:,} تومان
❌ وضعیت: رد شده

لطفاً با پشتیبانی تماس بگیرید.
"""
            )
        except:
            pass
    
    # ========== SETTINGS COMMANDS ==========
    
    async def setbet_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        if not self.db.is_admin(user_id):
            await update.message.reply_text(
                PersianMessages.ERROR_COMMAND_NOT_ALLOWED,
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        text = update.message.text
        try:
            amount = int(text.split()[1])
        except (IndexError, ValueError):
            await update.message.reply_text(
                f"{PersianMessages.ERROR} لطفاً مبلغ معتبر وارد کنید.\nمثال: `/setbet 20000`",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        self.db.set_setting('min_bet', amount, user_id)
        
        await update.message.reply_text(
            f"""
{PersianMessages.SUCCESS} **حداقل شرط تغییر کرد!**

💰 حداقل شرط جدید: {amount:,} تومان
✅ تغییرات اعمال شد.
""",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def setref_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        if not self.db.is_admin(user_id):
            await update.message.reply_text(
                PersianMessages.ERROR_COMMAND_NOT_ALLOWED,
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        text = update.message.text
        try:
            amount = int(text.split()[1])
        except (IndexError, ValueError):
            await update.message.reply_text(
                f"{PersianMessages.ERROR} لطفاً مبلغ معتبر وارد کنید.\nمثال: `/setref 5000`",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        self.db.set_setting('referral_bonus', amount, user_id)
        
        await update.message.reply_text(
            f"""
{PersianMessages.SUCCESS} **پاداش معرفی تغییر کرد!**

🎁 پاداش جدید: {amount:,} تومان
✅ تغییرات اعمال شد.
""",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def setcard_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        if not self.db.is_admin(user_id):
            await update.message.reply_text(
                PersianMessages.ERROR_COMMAND_NOT_ALLOWED,
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        text = update.message.text
        try:
            card = text.split()[1]
        except IndexError:
            await update.message.reply_text(
                f"{PersianMessages.ERROR} لطفاً شماره کارت را وارد کنید.\nمثال: `/setcard 6037991234567890`",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        if not card.isdigit() or len(card) != 16:
            await update.message.reply_text(
                f"{PersianMessages.ERROR} شماره کارت باید ۱۶ رقم باشد.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        self.db.set_setting('bank_card', card, user_id)
        
        await update.message.reply_text(
            f"""
{PersianMessages.SUCCESS} **شماره کارت تغییر کرد!**

🏦 شماره کارت جدید: `{card}`
✅ تغییرات اعمال شد.
""",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def setwallet_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        if not self.db.is_admin(user_id):
            await update.message.reply_text(
                PersianMessages.ERROR_COMMAND_NOT_ALLOWED,
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        text = update.message.text
        try:
            wallet = text.split()[1]
        except IndexError:
            await update.message.reply_text(
                f"{PersianMessages.ERROR} لطفاً آدرس کیف پول را وارد کنید.\nمثال: `/setwallet 0x1234567890abcdef`",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        self.db.set_setting('crypto_wallet', wallet, user_id)
        
        await update.message.reply_text(
            f"""
{PersianMessages.SUCCESS} **آدرس کیف پول تغییر کرد!**

💰 آدرس جدید: `{wallet}`
✅ تغییرات اعمال شد.
""",
            parse_mode=ParseMode.MARKDOWN
        )
    
    # ========== GIFT CODE COMMAND ==========
    
    async def giftcode_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        if not self.db.is_admin(user_id):
            await update.message.reply_text(
                PersianMessages.ERROR_COMMAND_NOT_ALLOWED,
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        text = update.message.text
        parts = text.split()
        
        if len(parts) < 2:
            await update.message.reply_text(
                f"{PersianMessages.ERROR} فرمت صحیح:\n`/giftcode [مبلغ] [ساعت انقضا]`\nمثال: `/giftcode 50000 24`",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        try:
            amount = int(parts[1])
            hours = int(parts[2]) if len(parts) > 2 else 24
        except ValueError:
            await update.message.reply_text(
                f"{PersianMessages.ERROR} مبلغ یا ساعت نامعتبر است.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        code = self.db.create_gift_code(amount, hours, user_id)
        
        await update.message.reply_text(
            f"""
{PersianMessages.SUCCESS} **کد هدیه ایجاد شد!**

🎁 کد: `{code}`
💰 مبلغ: {amount:,} تومان
⏰ اعتبار: {hours} ساعت
✅ وضعیت: فعال

کاربران می‌توانند با دستور `/gift {code}` از آن استفاده کنند.
""",
            parse_mode=ParseMode.MARKDOWN
        )
    
    # ========== SETTLE COMMAND ==========
    
    async def settle_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        if not self.db.is_admin(user_id):
            await update.message.reply_text(
                PersianMessages.ERROR_COMMAND_NOT_ALLOWED,
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        role = self.db.get_admin_role(user_id)
        if role != 'owner':
            await update.message.reply_text(
                f"{PersianMessages.ERROR} فقط صاحب ربات می‌تواند تسویه حساب کند.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        financial_stats = self.db.get_financial_stats()
        commission = financial_stats['total_commission']
        
        if commission == 0:
            await update.message.reply_text(
                f"{PersianMessages.INFO} هیچ کارمزدی برای تسویه وجود ندارد.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        message = f"""
💰 **تسویه حساب با صاحب ربات**

📊 کارمزد کل: {commission:,} تومان

**آیا می‌خواهید تسویه حساب کنید؟**
پس از تأیید، کارمزد به حساب شما واریز می‌شود.

برای تأیید: `/settle confirm`
"""
        
        await update.message.reply_text(
            message,
            parse_mode=ParseMode.MARKDOWN
        )
        
        self.user_states[user_id] = {
            'state': 'settlement_pending',
            'amount': commission
        }
    
    # ========== NOTIFY ADMINS ==========
    
    async def notify_admins(self, context: ContextTypes.DEFAULT_TYPE, message: str):
        admins = self.db.get_all_admins()
        
        for admin in admins:
            try:
                await context.bot.send_message(
                    admin['user_id'],
                    message,
                    parse_mode=ParseMode.MARKDOWN
                )
            except:
                pass

# ============================================================
# MAIN APPLICATION
# ============================================================

def main():
    """Main entry point"""
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )
    
    logging.info("🚀 Starting Gambling Bot...")
    logging.info(f"📁 Database path: {Config.DATABASE_PATH}")
    logging.info(f"👑 Owner ID: {Config.OWNER_ID}")
    
    # Create database directory if needed
    os.makedirs(os.path.dirname(Config.DATABASE_PATH) or '.', exist_ok=True)
    
    # Initialize database
    db = Database(Config.DATABASE_PATH)
    
    # Create application
    application = Application.builder().token(Config.BOT_TOKEN).build()
    
    # Create handlers
    handlers = BotHandlers(db)
    
    # Add command handlers
    application.add_handler(CommandHandler("start", handlers.start_command))
    application.add_handler(CommandHandler("profile", handlers.profile_handler))
    application.add_handler(CommandHandler("balance", handlers.profile_handler))
    application.add_handler(CommandHandler("deposit", handlers.deposit_command))
    application.add_handler(CommandHandler("withdraw", handlers.withdraw_command))
    application.add_handler(CommandHandler("gift", handlers.gift_command))
    application.add_handler(CommandHandler("bet", handlers.bet_handler))
    
    # Admin commands
    application.add_handler(CommandHandler("admin", handlers.admin_panel))
    application.add_handler(CommandHandler("confirm", handlers.confirm_command))
    application.add_handler(CommandHandler("reject", handlers.reject_command))
    application.add_handler(CommandHandler("setbet", handlers.setbet_command))
    application.add_handler(CommandHandler("setref", handlers.setref_command))
    application.add_handler(CommandHandler("setcard", handlers.setcard_command))
    application.add_handler(CommandHandler("setwallet", handlers.setwallet_command))
    application.add_handler(CommandHandler("giftcode", handlers.giftcode_command))
    application.add_handler(CommandHandler("settle", handlers.settle_command))
    
    # Callback query handlers
    application.add_handler(CallbackQueryHandler(handlers.back_to_menu, pattern="^back_to_menu$"))
    application.add_handler(CallbackQueryHandler(handlers.profile_handler, pattern="^profile$"))
    application.add_handler(CallbackQueryHandler(handlers.games_menu, pattern="^games$"))
    application.add_handler(CallbackQueryHandler(handlers.financial_menu, pattern="^financial$"))
    application.add_handler(CallbackQueryHandler(handlers.referral_handler, pattern="^referral$"))
    application.add_handler(CallbackQueryHandler(handlers.gift_handler, pattern="^gift$"))
    application.add_handler(CallbackQueryHandler(handlers.transaction_history, pattern="^transaction_history$"))
    
    # Admin panel callbacks
    application.add_handler(CallbackQueryHandler(handlers.admin_panel, pattern="^admin_panel$"))
    application.add_handler(CallbackQueryHandler(handlers.admin_stats, pattern="^admin_stats$"))
    application.add_handler(CallbackQueryHandler(handlers.admin_financial, pattern="^admin_financial$"))
    application.add_handler(CallbackQueryHandler(handlers.admin_settings, pattern="^admin_settings$"))
    application.add_handler(CallbackQueryHandler(handlers.admin_admins, pattern="^admin_admins$"))
    application.add_handler(CallbackQueryHandler(handlers.admin_gift_codes, pattern="^admin_gift_codes$"))
    application.add_handler(CallbackQueryHandler(handlers.admin_reports, pattern="^admin_reports$"))
    
    # Game callbacks
    application.add_handler(CallbackQueryHandler(handlers.game_dice, pattern="^game_dice$"))
    application.add_handler(CallbackQueryHandler(handlers.game_rps, pattern="^game_rps$"))
    application.add_handler(CallbackQueryHandler(handlers.game_darts, pattern="^game_darts$"))
    application.add_handler(CallbackQueryHandler(handlers.game_bowling, pattern="^game_bowling$"))
    application.add_handler(CallbackQueryHandler(handlers.game_evenodd, pattern="^game_evenodd$"))
    application.add_handler(CallbackQueryHandler(handlers.game_tictactoe, pattern="^game_tictactoe$"))
    
    # Deposit and withdrawal handlers
    application.add_handler(CallbackQueryHandler(handlers.deposit_handler, pattern="^deposit$"))
    application.add_handler(CallbackQueryHandler(handlers.withdrawal_handler, pattern="^withdraw$"))
    
    # Message handler
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handlers.message_handler
    ))
    application.add_handler(MessageHandler(filters.PHOTO, handlers.message_handler))
    
    # Set bot commands
    async def post_init():
        commands = [
            ("start", "شروع و نمایش منو"),
            ("profile", "مشاهده پروفایل"),
            ("balance", "مشاهده موجودی"),
            ("deposit", "واریز وجه"),
            ("withdraw", "برداشت وجه"),
            ("games", "لیست بازی‌ها"),
            ("gift", "استفاده از کد هدیه"),
            ("admin", "پنل مدیریت (ادمین‌ها)"),
        ]
        await application.bot.set_my_commands(commands)
    
    application.post_init = post_init
    
    # Error handler
    async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        logging.error(f"Update {update} caused error {context.error}")
        if update and update.effective_message:
            await update.effective_message.reply_text(
                f"{PersianMessages.ERROR} خطایی رخ داد. لطفاً دوباره تلاش کنید.",
                parse_mode=ParseMode.MARKDOWN
            )
    
    application.add_error_handler(error_handler)
    
    # Run bot
    logging.info("✅ Bot is ready!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
