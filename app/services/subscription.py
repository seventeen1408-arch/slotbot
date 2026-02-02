"""Сервис управления подписками пользователей."""

import logging
from datetime import datetime, timedelta
from aiogram import Bot
from app.database.db import db

logger = logging.getLogger(__name__)


class SubscriptionService:
    """Сервис управления подписками."""
    
    def __init__(self, bot: Bot):
        """Инициализация сервиса."""
        self.bot = bot
    
    async def check_subscription(self, user_id: int) -> bool:
        """Проверить активна ли подписка пользователя."""
        try:
            user = await db.get_user(user_id)
            if not user:
                return False
            
            # Проверить срок действия подписки
            if user.get('subscription_expires'):
                expires = datetime.fromisoformat(user['subscription_expires'])
                return expires > datetime.now()
            
            return False
        except Exception as e:
            logger.error(f"Ошибка при проверке подписки: {e}")
            return False
    
    async def activate_subscription(self, user_id: int, days: int = 30) -> bool:
        """Активировать подписку пользователю."""
        try:
            expires = datetime.now() + timedelta(days=days)
            await db.update_user(user_id, {
                'subscription_active': True,
                'subscription_expires': expires.isoformat()
            })
            logger.info(f"✅ Подписка активирована для пользователя {user_id}")
            return True
        except Exception as e:
            logger.error(f"Ошибка при активации подписки: {e}")
            return False
    
    async def cancel_subscription(self, user_id: int) -> bool:
        """Отменить подписку пользователю."""
        try:
            await db.update_user(user_id, {
                'subscription_active': False,
                'subscription_expires': None
            })
            logger.info(f"✅ Подписка отменена для пользователя {user_id}")
            return True
        except Exception as e:
            logger.error(f"Ошибка при отмене подписки: {e}")
            return False
