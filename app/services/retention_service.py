"""
Сервис удержания пользователей (Retention Service).
Проверяет подписку перед доступом к сигналам, VIP, казино.
Показывает "Goodbye Screen" при потере подписки.
"""

from typing import Optional, Tuple
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, User as TgUser
from app.core.logger import get_logger
from app.core.config import config

from app.database.models import User
from app.database.db import db
from app.services.subscription_checker import SubscriptionChecker

logger = get_logger(__name__)


class RetentionService:
    """Сервис удержания пользователей (проверка подписки)."""
    
    def __init__(self, bot: Bot):
        """Инициализировать сервис."""
        self.bot = bot
        self.subscription_checker = SubscriptionChecker(bot)
    
    async def check_before_signals(
        self, user_id: int, user: User
    ) -> Tuple[bool, Optional[str]]:
        """
        Проверить подписку перед доступом к сигналам.
        
        Args:
            user_id: ID пользователя
            user: Объект пользователя из БД
            
        Returns:
            Кортеж (разрешен ли доступ, сообщение об ошибке если есть)
        """
        return await self._check_subscription(user_id, user, "signals")
    
    async def check_before_vip(
        self, user_id: int, user: User
    ) -> Tuple[bool, Optional[str]]:
        """
        Проверить подписку перед доступом к VIP.
        
        Args:
            user_id: ID пользователя
            user: Объект пользователя из БД
            
        Returns:
            Кортеж (разрешен ли доступ, сообщение об ошибке если есть)
        """
        return await self._check_subscription(user_id, user, "vip")
    
    async def check_before_casino(
        self, user_id: int, user: User
    ) -> Tuple[bool, Optional[str]]:
        """
        Проверить подписку перед доступом к казино.
        
        Args:
            user_id: ID пользователя
            user: Объект пользователя из БД
            
        Returns:
            Кортеж (разрешен ли доступ, сообщение об ошибке если есть)
        """
        return await self._check_subscription(user_id, user, "casino")
    
    async def _check_subscription(
        self, user_id: int, user: User, action: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Проверить подписку и показать Goodbye Screen если нужно.
        
        Args:
            user_id: ID пользователя
            user: Объект пользователя из БД
            action: Тип действия (signals, vip, casino)
            
        Returns:
            Кортеж (разрешен ли доступ, сообщение об ошибке если есть)
        """
        try:
            language = user.language or "ru"
            
            # Проверить подписку через API
            is_subscribed = await self.subscription_checker.check_subscription(user_id)
            
            if is_subscribed:
                # Пользователь подписан - разрешить доступ
                logger.info(f"✅ Пользователь {user_id} подписан, доступ к {action} разрешен")
                
                # Если ранее был отписан, логировать переподписку
                if not user.is_subscribed:
                    await db.log_event(user_id, "user_resubscribed", {"action": action})
                    logger.info(f"🔄 Пользователь {user_id} переподписался")
                
                return True, None
            
            else:
                # Пользователь НЕ подписан - показать Goodbye Screen
                logger.warning(f"❌ Пользователь {user_id} НЕ подписан на канал")
                
                # Логировать отписку
                if user.is_subscribed:
                    await db.log_event(user_id, "user_unsubscribed", {"action": action})
                    logger.info(f"👋 Пользователь {user_id} отписался от канала")
                
                # Получить сообщение Goodbye Screen
                goodbye_message = self._get_goodbye_message(language)
                
                return False, goodbye_message
        
        except Exception as e:
            logger.error(f"❌ Ошибка при проверке подписки для {user_id}: {e}", exc_info=True)
            # В случае ошибки считаем, что пользователь не подписан (безопасно)
            goodbye_message = self._get_goodbye_message(user.language or "ru")
            return False, goodbye_message
    
    def _get_goodbye_message(self, language: str) -> str:
        """
        Получить сообщение Goodbye Screen.
        
        Args:
            language: Язык
            
        Returns:
            Текст сообщения
        """
        if language == "ru":
            return (
                "😢 <b>Ты вышел из канала</b>\n\n"
                "Сигналы доступны только подписчикам канала.\n\n"
                "Вернись в канал и продолжай играть! 🎰"
            )
        else:
            return (
                "😢 <b>You left the channel</b>\n\n"
                "Signals are only available to channel subscribers.\n\n"
                "Come back to the channel and keep playing! 🎰"
            )
    
    def _get_goodbye_keyboard(self, language: str) -> InlineKeyboardMarkup:
        """
        Получить клавиатуру Goodbye Screen.
        
        Args:
            language: Язык
            
        Returns:
            Клавиатура
        """
        if language == "ru":
            btn_subscribed = "✅ Я подписался"
            btn_open_channel = "📢 Открыть канал"
        else:
            btn_subscribed = "✅ I subscribed"
            btn_open_channel = "📢 Open channel"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=btn_subscribed,
                    callback_data="retention_check_subscription"
                ),
                InlineKeyboardButton(
                    text=btn_open_channel,
                    callback_data="retention_open_channel"
                )
            ]
        ])
        
        return keyboard
    
    async def show_goodbye_screen(
        self, user_id: int, user: User, action: str
    ) -> None:
        """
        Показать Goodbye Screen пользователю.
        
        Args:
            user_id: ID пользователя
            user: Объект пользователя из БД
            action: Тип действия (signals, vip, casino)
        """
        try:
            language = user.language or "ru"
            
            # Получить сообщение и клавиатуру
            message = self._get_goodbye_message(language)
            keyboard = self._get_goodbye_keyboard(language)
            
            # Отправить сообщение
            await self.bot.send_message(
                chat_id=user_id,
                text=message,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            
            # Логировать событие
            await db.log_event(
                user_id,
                "goodbye_screen_shown",
                {"action": action}
            )
            
            logger.info(f"📬 Goodbye Screen показан пользователю {user_id}")
        
        except Exception as e:
            logger.error(f"❌ Ошибка при показе Goodbye Screen для {user_id}: {e}", exc_info=True)
    
    async def handle_subscription_check(self, user_id: int, user: User) -> bool:
        """
        Обработать нажатие кнопки "Я подписался".
        Повторно проверить подписку.
        
        Args:
            user_id: ID пользователя
            user: Объект пользователя из БД
            
        Returns:
            True если пользователь подписан, False если нет
        """
        try:
            language = user.language or "ru"
            
            # Повторно проверить подписку
            is_subscribed = await self.subscription_checker.check_subscription(user_id)
            
            if is_subscribed:
                # Успех - пользователь подписан
                if language == "ru":
                    success_message = "✅ <b>Спасибо за подписку!</b>\n\nТеперь ты можешь использовать все функции бота."
                else:
                    success_message = "✅ <b>Thank you for subscribing!</b>\n\nNow you can use all bot features."
                
                await self.bot.send_message(
                    chat_id=user_id,
                    text=success_message,
                    parse_mode="HTML"
                )
                
                # Логировать событие
                await db.log_event(user_id, "retention_check_success")
                logger.info(f"✅ Проверка подписки успешна для {user_id}")
                
                return True
            
            else:
                # Пользователь все еще не подписан
                if language == "ru":
                    error_message = "❌ <b>Ты все еще не подписан на канал</b>\n\nПожалуйста, подпишись и попробуй снова."
                else:
                    error_message = "❌ <b>You are still not subscribed to the channel</b>\n\nPlease subscribe and try again."
                
                await self.bot.send_message(
                    chat_id=user_id,
                    text=error_message,
                    parse_mode="HTML"
                )
                
                # Логировать событие
                await db.log_event(user_id, "retention_check_failed")
                logger.warning(f"❌ Проверка подписки не пройдена для {user_id}")
                
                return False
        
        except Exception as e:
            logger.error(f"❌ Ошибка при проверке подписки для {user_id}: {e}", exc_info=True)
            return False
    
    async def handle_open_channel(self, user_id: int, user: User) -> None:
        """
        Обработать нажатие кнопки "Открыть канал".
        
        Args:
            user_id: ID пользователя
            user: Объект пользователя из БД
        """
        try:
            language = user.language or "ru"
            
            # Получить ID канала
            channel_id = config.REQUIRED_CHANNEL_ID
            
            # Преобразовать ID канала в username или ссылку
            # Формат: -1001234567890 -> @channel_name или https://t.me/channel_name
            channel_link = self._get_channel_link(channel_id)
            
            if language == "ru":
                message = f"📢 <b>Перейди в канал:</b>\n\n{channel_link}"
            else:
                message = f"📢 <b>Go to the channel:</b>\n\n{channel_link}"
            
            # Отправить сообщение с ссылкой
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔗 " + ("Перейти в канал" if language == "ru" else "Go to channel"),
                        url=channel_link
                    )
                ]
            ])
            
            await self.bot.send_message(
                chat_id=user_id,
                text=message,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            
            # Логировать событие
            await db.log_event(user_id, "retention_open_channel_clicked")
            logger.info(f"🔗 Пользователь {user_id} открыл ссылку на канал")
        
        except Exception as e:
            logger.error(f"❌ Ошибка при открытии канала для {user_id}: {e}", exc_info=True)
    
    def _get_channel_link(self, channel_id: int) -> str:
        """
        Получить ссылку на канал.
        
        Args:
            channel_id: ID канала
            
        Returns:
            Ссылка на канал
        """
        # Если ID канала начинается с -100, это приватный канал
        # Нужно использовать t.me/joinchat/ ссылку
        # Для простоты используем формат: https://t.me/c/{channel_id}
        
        if str(channel_id).startswith("-100"):
            # Приватный канал: -1001234567890 -> 1234567890
            channel_num = str(channel_id)[4:]
            return f"https://t.me/c/{channel_num}"
        else:
            # Публичный канал
            return f"https://t.me/{channel_id}"
