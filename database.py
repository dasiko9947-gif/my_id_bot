"""
Асинхронная работа с SQLite базой данных
"""
import aiosqlite
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from contextlib import asynccontextmanager
from pathlib import Path

from models import User, Chat, Message
from logger_config import logger

class Database:
    """Класс для работы с базой данных"""
    
    def __init__(self, db_path: str = "data/bot_database.sqlite"):
        self.db_path = db_path
        # Создаем директорию для БД, если её нет
        Path("data").mkdir(exist_ok=True)
    
    @asynccontextmanager
    async def get_connection(self):
        """Контекстный менеджер для соединения с БД"""
        conn = await aiosqlite.connect(self.db_path)
        conn.row_factory = aiosqlite.Row  # Возвращаем строки как словари
        try:
            yield conn
            await conn.commit()
        finally:
            await conn.close()
    
    async def init_db(self):
        """Инициализация таблиц в базе данных"""
        async with self.get_connection() as conn:
            # Таблица пользователей
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT NOT NULL,
                    last_name TEXT,
                    language_code TEXT,
                    is_bot INTEGER DEFAULT 0,
                    first_seen TIMESTAMP NOT NULL,
                    last_seen TIMESTAMP NOT NULL,
                    is_active INTEGER DEFAULT 1,
                    additional_data TEXT
                )
            ''')
            
            # Таблица чатов
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS chats (
                    id INTEGER PRIMARY KEY,
                    type TEXT NOT NULL,
                    title TEXT,
                    first_seen TIMESTAMP NOT NULL,
                    last_used TIMESTAMP NOT NULL
                )
            ''')
            
            # Таблица сообщений
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id INTEGER,
                    user_id INTEGER NOT NULL,
                    chat_id INTEGER NOT NULL,
                    text TEXT,
                    date TIMESTAMP NOT NULL,
                    is_forward INTEGER DEFAULT 0,
                    is_reply INTEGER DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users (id),
                    FOREIGN KEY (chat_id) REFERENCES chats (id)
                )
            ''')
            
            # Индексы
            await conn.execute('CREATE INDEX IF NOT EXISTS idx_users_active ON users(is_active)')
            await conn.execute('CREATE INDEX IF NOT EXISTS idx_users_last_seen ON users(last_seen)')
            await conn.execute('CREATE INDEX IF NOT EXISTS idx_messages_date ON messages(date)')
            
            # Таблица для рассылок
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS broadcasts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    text TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL,
                    sent_count INTEGER DEFAULT 0,
                    failed_count INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'pending'
                )
            ''')
            
            logger.info("База данных инициализирована")
    
    # ========== РАБОТА С ПОЛЬЗОВАТЕЛЯМИ ==========
    
    async def add_or_update_user(self, user: User) -> None:
        """
        Добавление или обновление пользователя
        
        Args:
            user: Объект пользователя
        """
        async with self.get_connection() as conn:
            # Проверяем, существует ли пользователь
            cursor = await conn.execute(
                'SELECT * FROM users WHERE id = ?',
                (user.id,)
            )
            existing = await cursor.fetchone()
            
            if existing:
                # Обновляем существующего пользователя
                await conn.execute('''
                    UPDATE users 
                    SET username = ?, first_name = ?, last_name = ?,
                        language_code = ?, last_seen = ?, is_active = ?
                    WHERE id = ?
                ''', (
                    user.username, user.first_name, user.last_name,
                    user.language_code, user.last_seen.isoformat(), 
                    1 if user.is_active else 0,
                    user.id
                ))
                logger.debug(f"Обновлен пользователь {user.id}")
            else:
                # Добавляем нового пользователя
                await conn.execute('''
                    INSERT INTO users 
                    (id, username, first_name, last_name, language_code, 
                     is_bot, first_seen, last_seen, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    user.id, user.username, user.first_name, user.last_name,
                    user.language_code, 1 if user.is_bot else 0,
                    user.first_seen.isoformat(), user.last_seen.isoformat(),
                    1 if user.is_active else 0
                ))
                logger.info(f"Добавлен новый пользователь {user.id}")
    
    async def get_user(self, user_id: int) -> Optional[User]:
        """
        Получение пользователя по ID
        
        Args:
            user_id: ID пользователя
        
        Returns:
            Optional[User]: Объект пользователя или None
        """
        async with self.get_connection() as conn:
            cursor = await conn.execute(
                'SELECT * FROM users WHERE id = ?',
                (user_id,)
            )
            row = await cursor.fetchone()
            
            if row:
                return User(
                    id=row['id'],
                    username=row['username'],
                    first_name=row['first_name'],
                    last_name=row['last_name'],
                    language_code=row['language_code'],
                    is_bot=bool(row['is_bot']),
                    first_seen=datetime.fromisoformat(row['first_seen']),
                    last_seen=datetime.fromisoformat(row['last_seen']),
                    is_active=bool(row['is_active'])
                )
            return None
    
    async def get_users_count(self, active_only: bool = True) -> int:
        """
        Получение количества пользователей
        
        Args:
            active_only: Только активные пользователи
        
        Returns:
            int: Количество пользователей
        """
        async with self.get_connection() as conn:
            if active_only:
                cursor = await conn.execute(
                    'SELECT COUNT(*) as count FROM users WHERE is_active = 1'
                )
            else:
                cursor = await conn.execute(
                    'SELECT COUNT(*) as count FROM users'
                )
            
            row = await cursor.fetchone()
            return row['count'] if row else 0
    
    async def deactivate_user(self, user_id: int) -> None:
        """Деактивация пользователя"""
        async with self.get_connection() as conn:
            await conn.execute(
                'UPDATE users SET is_active = 0 WHERE id = ?',
                (user_id,)
            )
            logger.info(f"Пользователь {user_id} деактивирован")
    
    # ========== НОВЫЕ МЕТОДЫ ДЛЯ АДМИНКИ ==========
    
    async def get_users_by_status(self) -> Dict[str, int]:
        """
        Получение статистики по статусам пользователей
        
        Returns:
            Dict[str, int]: Словарь со статистикой
        """
        async with self.get_connection() as conn:
            stats = {}
            
            # Все пользователи
            cursor = await conn.execute('SELECT COUNT(*) as count FROM users')
            row = await cursor.fetchone()
            stats['total'] = row['count'] if row else 0
            
            # Активные
            cursor = await conn.execute('SELECT COUNT(*) as count FROM users WHERE is_active = 1')
            row = await cursor.fetchone()
            stats['active'] = row['count'] if row else 0
            
            # Неактивные
            cursor = await conn.execute('SELECT COUNT(*) as count FROM users WHERE is_active = 0')
            row = await cursor.fetchone()
            stats['inactive'] = row['count'] if row else 0
            
            # Боты
            cursor = await conn.execute('SELECT COUNT(*) as count FROM users WHERE is_bot = 1')
            row = await cursor.fetchone()
            stats['bots'] = row['count'] if row else 0
            
            # За последние 24 часа
            cursor = await conn.execute('''
                SELECT COUNT(*) as count FROM users 
                WHERE datetime(last_seen) > datetime('now', '-1 day')
            ''')
            row = await cursor.fetchone()
            stats['last_24h'] = row['count'] if row else 0
            
            # За последнюю неделю
            cursor = await conn.execute('''
                SELECT COUNT(*) as count FROM users 
                WHERE datetime(last_seen) > datetime('now', '-7 days')
            ''')
            row = await cursor.fetchone()
            stats['last_week'] = row['count'] if row else 0
            
            # За последний месяц
            cursor = await conn.execute('''
                SELECT COUNT(*) as count FROM users 
                WHERE datetime(last_seen) > datetime('now', '-30 days')
            ''')
            row = await cursor.fetchone()
            stats['last_month'] = row['count'] if row else 0
            
            return stats
    
    async def get_users_with_pagination(self, page: int = 1, per_page: int = 10) -> Dict[str, Any]:
        """
        Получение пользователей с пагинацией
        
        Args:
            page: Номер страницы
            per_page: Пользователей на странице
        
        Returns:
            Dict: Словарь с пользователями и информацией о пагинации
        """
        offset = (page - 1) * per_page
        
        async with self.get_connection() as conn:
            # Получаем общее количество
            cursor = await conn.execute('SELECT COUNT(*) as count FROM users')
            total_row = await cursor.fetchone()
            total_count = total_row['count'] if total_row else 0
            
            # Получаем пользователей для текущей страницы
            cursor = await conn.execute('''
                SELECT id, username, first_name, last_name, language_code, 
                       is_bot, first_seen, last_seen, is_active 
                FROM users 
                ORDER BY last_seen DESC 
                LIMIT ? OFFSET ?
            ''', (per_page, offset))
            
            rows = await cursor.fetchall()
            users = []
            
            for row in rows:
                users.append({
                    'id': row['id'],
                    'username': row['username'],
                    'first_name': row['first_name'],
                    'last_name': row['last_name'],
                    'language_code': row['language_code'],
                    'is_bot': bool(row['is_bot']),
                    'first_seen': row['first_seen'],
                    'last_seen': row['last_seen'],
                    'is_active': bool(row['is_active'])
                })
            
            total_pages = (total_count + per_page - 1) // per_page if total_count > 0 else 1
            
            return {
                'users': users,
                'total': total_count,
                'page': page,
                'per_page': per_page,
                'total_pages': total_pages
            }
    
    async def get_all_active_users_for_broadcast(self) -> List[int]:
        """Получение всех активных пользователей для рассылки"""
        async with self.get_connection() as conn:
            cursor = await conn.execute('''
                SELECT id FROM users 
                WHERE is_active = 1 AND is_bot = 0
                ORDER BY last_seen DESC
            ''')
            rows = await cursor.fetchall()
            return [row['id'] for row in rows]
    
    # ========== РАБОТА С ЧАТАМИ ==========
    
    async def add_or_update_chat(self, chat) -> None:
        """
        Добавление или обновление чата
        
        Args:
            chat: Объект чата из Telegram
        """
        now = datetime.now().isoformat()
        
        async with self.get_connection() as conn:
            cursor = await conn.execute(
                'SELECT * FROM chats WHERE id = ?',
                (chat.id,)
            )
            existing = await cursor.fetchone()
            
            if existing:
                await conn.execute('''
                    UPDATE chats 
                    SET title = ?, last_used = ?
                    WHERE id = ?
                ''', (chat.title, now, chat.id))
            else:
                await conn.execute('''
                    INSERT INTO chats (id, type, title, first_seen, last_used)
                    VALUES (?, ?, ?, ?, ?)
                ''', (chat.id, chat.type, chat.title, now, now))
    
    # ========== РАБОТА С СООБЩЕНИЯМИ ==========
    
    async def save_message(self, message, user_id: int, chat_id: int) -> None:
        """
        Сохранение сообщения в БД
        
        Args:
            message: Объект сообщения из Telegram
            user_id: ID пользователя
            chat_id: ID чата
        """
        async with self.get_connection() as conn:
            await conn.execute('''
                INSERT INTO messages 
                (message_id, user_id, chat_id, text, date, is_forward, is_reply)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                message.message_id,
                user_id,
                chat_id,
                message.text or message.caption,
                datetime.now().isoformat(),
                1 if message.forward_from or message.forward_from_chat else 0,
                1 if message.reply_to_message else 0
            ))
    
    # ========== СТАТИСТИКА ==========
    
    async def get_statistics(self) -> Dict[str, int]:
        """
        Получение статистики по базе данных
        
        Returns:
            Dict[str, int]: Словарь со статистикой
        """
        async with self.get_connection() as conn:
            stats = {}
            
            # Активные пользователи
            cursor = await conn.execute('SELECT COUNT(*) as count FROM users WHERE is_active = 1')
            row = await cursor.fetchone()
            stats['active_users'] = row['count'] if row else 0
            
            # Всего пользователей
            cursor = await conn.execute('SELECT COUNT(*) as count FROM users')
            row = await cursor.fetchone()
            stats['total_users'] = row['count'] if row else 0
            
            # Всего чатов
            cursor = await conn.execute('SELECT COUNT(*) as count FROM chats')
            row = await cursor.fetchone()
            stats['total_chats'] = row['count'] if row else 0
            
            # Всего сообщений
            cursor = await conn.execute('SELECT COUNT(*) as count FROM messages')
            row = await cursor.fetchone()
            stats['total_messages'] = row['count'] if row else 0
            
            # Пользователи за последние 24 часа
            cursor = await conn.execute('''
                SELECT COUNT(*) as count FROM users 
                WHERE datetime(last_seen) > datetime('now', '-1 day')
            ''')
            row = await cursor.fetchone()
            stats['users_last_24h'] = row['count'] if row else 0
            
            return stats

# Создаем глобальный экземпляр базы данных
db = Database()