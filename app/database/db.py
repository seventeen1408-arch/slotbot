"""
Слой работы с БД.
"""

import sqlite3
import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.core.logger import get_logger
from app.database.models import User, Event

logger = get_logger(__name__)


class Database:
    """Работа с БД."""
    
    def __init__(self, db_path: str = "bot.db"):
        """Инициализировать БД."""
        self.db_path = db_path
        self.loop = asyncio.get_event_loop()
    
    async def init(self) -> None:
        """Инициализировать таблицы БД."""
        try:
            await self.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    language TEXT DEFAULT 'ru',
                    is_subscribed BOOLEAN DEFAULT 0,
                    signals_unlocked BOOLEAN DEFAULT 0,
                    casino_clicked BOOLEAN DEFAULT 0,
                    casino_click_time INTEGER,
                    unlock_after INTEGER,
                    funnel_stage INTEGER DEFAULT 0,
                    last_active INTEGER,
                    casino_clicks_count INTEGER DEFAULT 0,
                    subscription_checked_at INTEGER,
                    casino_id TEXT,
                    is_deposited BOOLEAN DEFAULT 0,
                    created_at INTEGER
                )
            """)
            
            await self.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    event_type TEXT,
                    details TEXT,
                    created_at INTEGER,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            """)
            
            logger.info("✅ Таблицы БД инициализированы")
        except Exception as e:
            logger.error(f"❌ Ошибка при инициализации БД: {e}", exc_info=True)
    
    async def execute(self, query: str, params: tuple = ()) -> None:
        """Выполнить запрос."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"❌ Ошибка при выполнении запроса: {e}", exc_info=True)
    
    async def fetch_one(self, query: str, params: tuple = ()) -> Optional[tuple]:
        """Получить одну строку."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(query, params)
            result = cursor.fetchone()
            conn.close()
            return result
        except Exception as e:
            logger.error(f"❌ Ошибка при получении данных: {e}", exc_info=True)
            return None
    
    async def fetch_all(self, query: str, params: tuple = ()) -> List[tuple]:
        """Получить все строки."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(query, params)
            result = cursor.fetchall()
            conn.close()
            return result
        except Exception as e:
            logger.error(f"❌ Ошибка при получении данных: {e}", exc_info=True)
            return []
    
    # ========================================================================
    # USER OPERATIONS
    # ========================================================================
    
    async def add_user(self, user_id: int, username: Optional[str] = None, language: str = "ru") -> None:
        """Добавить пользователя."""
        try:
            now = int(datetime.now().timestamp())
            await self.execute(
                """
                INSERT OR IGNORE INTO users 
                (user_id, username, language, created_at, last_active)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, username, language, now, now)
            )
            logger.info(f"✅ Пользователь {user_id} добавлен")
        except Exception as e:
            logger.error(f"❌ Ошибка при добавлении пользователя: {e}", exc_info=True)
    
    async def get_user(self, user_id: int) -> Optional[User]:
        """Получить пользователя."""
        try:
            row = await self.fetch_one(
                "SELECT * FROM users WHERE user_id = ?",
                (user_id,)
            )
            if row:
                return User(
                    user_id=row[0],
                    username=row[1],
                    language=row[2],
                    is_subscribed=bool(row[3]),
                    signals_unlocked=bool(row[4]),
                    casino_clicked=bool(row[5]),
                    casino_click_time=row[6],
                    unlock_after=row[7],
                    funnel_stage=row[8],
                    last_active=row[9],
                    casino_clicks_count=row[10],
                    subscription_checked_at=row[11],
                    casino_id=row[12],
                    is_deposited=bool(row[13]),
                    created_at=row[14],
                )
            return None
        except Exception as e:
            logger.error(f"❌ Ошибка при получении пользователя: {e}", exc_info=True)
            return None
    
    async def update_subscription(self, user_id: int, is_subscribed: bool) -> None:
        """Обновить статус подписки."""
        try:
            now = int(datetime.now().timestamp())
            await self.execute(
                "UPDATE users SET is_subscribed = ?, subscription_checked_at = ? WHERE user_id = ?",
                (int(is_subscribed), now, user_id)
            )
            logger.info(f"✅ Статус подписки пользователя {user_id} обновлен: {is_subscribed}")
        except Exception as e:
            logger.error(f"❌ Ошибка при обновлении подписки: {e}", exc_info=True)
    
    async def is_user_subscribed(self, user_id: int) -> bool:
        """Проверить, подписан ли пользователь."""
        try:
            row = await self.fetch_one(
                "SELECT is_subscribed FROM users WHERE user_id = ?",
                (user_id,)
            )
            if row:
                return bool(row[0])
            return False
        except Exception as e:
            logger.error(f"❌ Ошибка при проверке подписки: {e}", exc_info=True)
            return False
    
    async def update_language(self, user_id: int, language: str) -> None:
        """Обновить язык пользователя."""
        try:
            await self.execute(
                "UPDATE users SET language = ? WHERE user_id = ?",
                (language, user_id)
            )
            logger.info(f"✅ Язык пользователя {user_id} обновлен: {language}")
        except Exception as e:
            logger.error(f"❌ Ошибка при обновлении языка: {e}", exc_info=True)
    
    async def update_last_active(self, user_id: int) -> None:
        """Обновить время последней активности."""
        try:
            now = int(datetime.now().timestamp())
            await self.execute(
                "UPDATE users SET last_active = ? WHERE user_id = ?",
                (now, user_id)
            )
        except Exception as e:
            logger.error(f"❌ Ошибка при обновлении времени активности: {e}", exc_info=True)
    
    # ========================================================================
    # SOFT GATE OPERATIONS
    # ========================================================================
    
    async def set_casino_clicked(self, user_id: int, unlock_after: int) -> None:
        """Установить, что пользователь кликнул на казино."""
        try:
            now = int(datetime.now().timestamp())
            await self.execute(
                """
                UPDATE users 
                SET casino_clicked = 1, casino_click_time = ?, unlock_after = ?, casino_clicks_count = casino_clicks_count + 1
                WHERE user_id = ?
                """,
                (now, unlock_after, user_id)
            )
            logger.info(f"✅ Клик на казино зафиксирован для пользователя {user_id}")
        except Exception as e:
            logger.error(f"❌ Ошибка при установке клика на казино: {e}", exc_info=True)
    
    async def unlock_signals(self, user_id: int) -> None:
        """Разблокировать сигналы."""
        try:
            await self.execute(
                "UPDATE users SET signals_unlocked = 1 WHERE user_id = ?",
                (user_id,)
            )
            logger.info(f"✅ Сигналы разблокированы для пользователя {user_id}")
        except Exception as e:
            logger.error(f"❌ Ошибка при разблокировке сигналов: {e}", exc_info=True)
    
    async def lock_signals(self, user_id: int) -> None:
        """Заблокировать сигналы."""
        try:
            await self.execute(
                "UPDATE users SET signals_unlocked = 0, casino_clicked = 0 WHERE user_id = ?",
                (user_id,)
            )
            logger.info(f"✅ Сигналы заблокированы для пользователя {user_id}")
        except Exception as e:
            logger.error(f"❌ Ошибка при блокировке сигналов: {e}", exc_info=True)
    
    async def get_users_to_unlock(self) -> List[int]:
        """Получить пользователей, которых нужно разблокировать."""
        try:
            now = int(datetime.now().timestamp())
            rows = await self.fetch_all(
                """
                SELECT user_id FROM users 
                WHERE signals_unlocked = 0 AND unlock_after IS NOT NULL AND unlock_after <= ?
                """,
                (now,)
            )
            return [row[0] for row in rows]
        except Exception as e:
            logger.error(f"❌ Ошибка при получении пользователей для разблокировки: {e}", exc_info=True)
            return []
    
    # ========================================================================
    # EVENT OPERATIONS
    # ========================================================================
    
    async def log_event(self, user_id: int, event_type: str, details: Optional[str] = None) -> None:
        """Логировать событие."""
        try:
            now = int(datetime.now().timestamp())
            await self.execute(
                """
                INSERT INTO events (user_id, event_type, details, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, event_type, details, now)
            )
            logger.info(f"✅ Событие логировано: {event_type} для пользователя {user_id}")
        except Exception as e:
            logger.error(f"❌ Ошибка при логировании события: {e}", exc_info=True)
    
    async def get_user_events(self, user_id: int) -> List[Event]:
        """Получить события пользователя."""
        try:
            rows = await self.fetch_all(
                "SELECT id, user_id, event_type, details, created_at FROM events WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,)
            )
            return [
                Event(
                    id=row[0],
                    user_id=row[1],
                    event_type=row[2],
                    details=row[3],
                    created_at=row[4],
                )
                for row in rows
            ]
        except Exception as e:
            logger.error(f"❌ Ошибка при получении событий: {e}", exc_info=True)
            return []
    
    # ========================================================================
    # STATISTICS
    # ========================================================================
    
    async def get_stats(self) -> Dict[str, int]:
        """Получить статистику."""
        try:
            total = await self.fetch_one("SELECT COUNT(*) FROM users")
            subscribed = await self.fetch_one("SELECT COUNT(*) FROM users WHERE is_subscribed = 1")
            signals_unlocked = await self.fetch_one("SELECT COUNT(*) FROM users WHERE signals_unlocked = 1")
            deposited = await self.fetch_one("SELECT COUNT(*) FROM users WHERE is_deposited = 1")
            
            return {
                "total_users": total[0] if total else 0,
                "subscribed_users": subscribed[0] if subscribed else 0,
                "signals_unlocked_users": signals_unlocked[0] if signals_unlocked else 0,
                "deposited_users": deposited[0] if deposited else 0,
            }
        except Exception as e:
            logger.error(f"❌ Ошибка при получении статистики: {e}", exc_info=True)
            return {}


# Глобальный экземпляр БД
db = Database("bot.db")
