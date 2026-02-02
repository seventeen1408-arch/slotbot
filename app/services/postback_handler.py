"""
Обработчик постбеков от 1Win казино.
S2S интеграция для отслеживания регистраций, депозитов, выводов и выигрышей.
"""

import hashlib
import hmac
from datetime import datetime
from typing import Optional, Dict, Any, Tuple
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from app.core.logger import get_logger
from app.core.config import config
from app.database.db import db
from app.locales.i18n import t

logger = get_logger(__name__)


class PostbackEvent:
    """Модель события постбека."""
    
    def __init__(self, event_type: str, user_id: str, amount: Optional[float] = None, **kwargs):
        self.event_type = event_type  # registration, deposit, withdrawal, win
        self.user_id = user_id  # ID игрока в казино
        self.amount = amount  # Сумма (для депозита, вывода, выигрыша)
        self.timestamp = datetime.now()
        self.extra = kwargs  # Дополнительные данные


class PostbackHandler:
    """Обработчик постбеков от 1Win."""
    
    # События
    EVENT_REGISTRATION = "registration"
    EVENT_DEPOSIT = "deposit"
    EVENT_WITHDRAWAL = "withdrawal"
    EVENT_WIN = "win"
    
    # Текстовые сообщения
    MESSAGES = {
        "ru": {
            "registration": (
                "🎉 <b>Добро пожаловать!</b>\n\n"
                "Спасибо за регистрацию в 1Win!\n\n"
                "Теперь ты получаешь доступ к нашим эксклюзивным сигналам. 📊"
            ),
            "deposit": (
                "💰 <b>Депозит получен!</b>\n\n"
                "Сумма: <b>{amount} ₽</b>\n\n"
                "Отличный выбор! Теперь ты готов к игре. 🎮\n\n"
                "Используй наши сигналы для максимального выигрыша! 🚀"
            ),
            "deposit_unlocked": (
                "✅ <b>Сигналы разблокированы!</b>\n\n"
                "Спасибо за депозит на сумму <b>{amount} ₽</b>\n\n"
                "Теперь ты получаешь доступ к премиум сигналам. 📊"
            ),
            "withdrawal": (
                "🎊 <b>Вывод средств!</b>\n\n"
                "Сумма: <b>{amount} ₽</b>\n\n"
                "Поздравляем с выигрышем! 🏆\n\n"
                "Продолжай использовать наши сигналы! 📈"
            ),
            "win": (
                "🏆 <b>Удачная игра!</b>\n\n"
                "Выигрыш: <b>{amount} ₽</b>\n\n"
                "Отлично! Ты на правильном пути! 💪\n\n"
                "Следи за нашими сигналами для еще больших выигрышей! 🚀"
            ),
        },
        "en": {
            "registration": (
                "🎉 <b>Welcome!</b>\n\n"
                "Thank you for registering at 1Win!\n\n"
                "Now you have access to our exclusive signals. 📊"
            ),
            "deposit": (
                "💰 <b>Deposit received!</b>\n\n"
                "Amount: <b>{amount} ₽</b>\n\n"
                "Great choice! You're ready to play. 🎮\n\n"
                "Use our signals for maximum winnings! 🚀"
            ),
            "deposit_unlocked": (
                "✅ <b>Signals unlocked!</b>\n\n"
                "Thank you for depositing <b>{amount} ₽</b>\n\n"
                "Now you have access to premium signals. 📊"
            ),
            "withdrawal": (
                "🎊 <b>Withdrawal!</b>\n\n"
                "Amount: <b>{amount} ₽</b>\n\n"
                "Congratulations on your winnings! 🏆\n\n"
                "Keep using our signals! 📈"
            ),
            "win": (
                "🏆 <b>Lucky game!</b>\n\n"
                "Winnings: <b>{amount} ₽</b>\n\n"
                "Excellent! You're on the right track! 💪\n\n"
                "Follow our signals for even bigger wins! 🚀"
            ),
        }
    }
    
    # Минимальная сумма выигрыша для уведомления (в $)
    MIN_WIN_AMOUNT = 15.0
    
    def __init__(self, bot: Bot, funnel_service=None):
        self.bot = bot
        self.funnel_service = funnel_service  # FunnelService для запуска воронки
        self.secret_key = config.POSTBACK_SECRET_KEY if hasattr(config, 'POSTBACK_SECRET_KEY') else None
    
    async def handle_postback(self, event: PostbackEvent) -> Tuple[bool, str]:
        """
        Обработать событие постбека.
        
        Args:
            event: Событие постбека
            
        Returns:
            (success, message)
        """
        try:
            logger.info(f"📨 Получен постбек: {event.event_type} от {event.user_id}")
            
            # Получить пользователя по ID казино
            user = await db.get_user_by_casino_id(event.user_id)
            if not user:
                logger.warning(f"⚠️ Пользователь с casino_id {event.user_id} не найден")
                return False, "User not found"
            
            # Обработать событие в зависимости от типа
            if event.event_type == self.EVENT_REGISTRATION:
                return await self._handle_registration(user, event)
            
            elif event.event_type == self.EVENT_DEPOSIT:
                return await self._handle_deposit(user, event)
            
            elif event.event_type == self.EVENT_WITHDRAWAL:
                return await self._handle_withdrawal(user, event)
            
            elif event.event_type == self.EVENT_WIN:
                return await self._handle_win(user, event)
            
            else:
                logger.warning(f"⚠️ Неизвестный тип события: {event.event_type}")
                return False, "Unknown event type"
        
        except Exception as e:
            logger.error(f"❌ Ошибка при обработке постбека: {e}", exc_info=True)
            return False, str(e)
    
    async def _handle_registration(self, user: Any, event: PostbackEvent) -> Tuple[bool, str]:
        """Обработать регистрацию."""
        try:
            user_id = user.id
            language = user.language or "ru"
            
            logger.info(f"✅ Регистрация пользователя {user_id}")
            
            # Обновить casino_id если не установлен
            if not user.casino_id:
                await db.update_user_casino_id(user_id, event.user_id)
            
            # Логировать событие
            await db.log_event(user_id, "casino_registration", {
                "casino_id": event.user_id,
                "timestamp": event.timestamp.isoformat()
            })
            
            # Отправить сообщение
            message = self.MESSAGES[language]["registration"]
            await self.bot.send_message(user_id, message, parse_mode="HTML")
            
            # Запустить Funnel если доступен
            if self.funnel_service:
                try:
                    await self.funnel_service.start_funnel(user_id, user)
                    logger.info(f"✅ Funnel запущен для пользователя {user_id}")
                except Exception as e:
                    logger.warning(f"⚠️ Ошибка при запуске Funnel: {e}")
            
            logger.info(f"✅ Сообщение о регистрации отправлено {user_id}")
            return True, "Registration processed"
        
        except Exception as e:
            logger.error(f"❌ Ошибка при обработке регистрации: {e}", exc_info=True)
            return False, str(e)
    
    async def _handle_deposit(self, user: Any, event: PostbackEvent) -> Tuple[bool, str]:
        """Обработать депозит."""
        try:
            user_id = user.id
            language = user.language or "ru"
            amount = event.amount or 0
            
            logger.info(f"💰 Депозит пользователя {user_id}: {amount} ₽")
            
            # Обновить casino_id если не установлен
            if not user.casino_id:
                await db.update_user_casino_id(user_id, event.user_id)
            
            # Обновить статус депозита в БД
            await db.update_user_deposited(user_id, True)
            
            # Логировать событие
            await db.log_event(user_id, "casino_deposit", {
                "casino_id": event.user_id,
                "amount": amount,
                "timestamp": event.timestamp.isoformat()
            })
            
            # Отправить сообщение о депозите
            message = self.MESSAGES[language]["deposit"].format(amount=amount)
            await self.bot.send_message(user_id, message, parse_mode="HTML")
            
            # Разблокировать сигналы
            await db.update_user_signals_unlocked(user_id, True)
            
            # Отправить сообщение о разблокировке сигналов
            message_unlocked = self.MESSAGES[language]["deposit_unlocked"].format(amount=amount)
            await self.bot.send_message(user_id, message_unlocked, parse_mode="HTML")
            
            logger.info(f"✅ Сигналы разблокированы для {user_id}")
            return True, "Deposit processed"
        
        except Exception as e:
            logger.error(f"❌ Ошибка при обработке депозита: {e}", exc_info=True)
            return False, str(e)
    
    async def _handle_withdrawal(self, user: Any, event: PostbackEvent) -> Tuple[bool, str]:
        """Обработать вывод средств."""
        try:
            user_id = user.id
            language = user.language or "ru"
            amount = event.amount or 0
            
            logger.info(f"🎊 Вывод пользователя {user_id}: {amount} ₽")
            
            # Логировать событие
            await db.log_event(user_id, "casino_withdrawal", {
                "casino_id": event.user_id,
                "amount": amount,
                "timestamp": event.timestamp.isoformat()
            })
            
            # Отправить сообщение
            message = self.MESSAGES[language]["withdrawal"].format(amount=amount)
            
            # Добавить кнопку с сигналами
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📊 Получить сигналы", callback_data="get_signals")],
                [InlineKeyboardButton(text="🎰 Вернуться в казино", url="https://1win.com")],
            ])
            
            await self.bot.send_message(user_id, message, reply_markup=keyboard, parse_mode="HTML")
            
            logger.info(f"✅ Сообщение о выводе отправлено {user_id}")
            return True, "Withdrawal processed"
        
        except Exception as e:
            logger.error(f"❌ Ошибка при обработке вывода: {e}", exc_info=True)
            return False, str(e)
    
    async def _handle_win(self, user: Any, event: PostbackEvent) -> Tuple[bool, str]:
        """Обработать выигрыш."""
        try:
            user_id = user.id
            language = user.language or "ru"
            amount = event.amount or 0
            
            logger.info(f"🏆 Выигрыш пользователя {user_id}: {amount} ₽")
            
            # Логировать событие
            await db.log_event(user_id, "casino_win", {
                "casino_id": event.user_id,
                "amount": amount,
                "timestamp": event.timestamp.isoformat()
            })
            
            # Отправить сообщение (не каждый раз, чтобы не спамить)
            # Проверить последнее сообщение о выигрыше
            last_win_log = await db.get_last_event(user_id, "casino_win")
            
            # Если последний выигрыш был менее 5 минут назад, не отправляем
            if last_win_log and (datetime.now() - last_win_log.get("timestamp")).total_seconds() < 300:
                logger.debug(f"⏭️ Пропуск сообщения о выигрыше для {user_id} (слишком частые выигрыши)")
                return True, "Win logged (no message)"
            
            # Отправить сообщение
            message = self.MESSAGES[language]["win"].format(amount=amount)
            await self.bot.send_message(user_id, message, parse_mode="HTML")
            
            logger.info(f"✅ Сообщение о выигрыше отправлено {user_id}")
            return True, "Win processed"
        
        except Exception as e:
            logger.error(f"❌ Ошибка при обработке выигрыша: {e}", exc_info=True)
            return False, str(e)
    
    def verify_signature(self, data: Dict[str, Any], signature: str) -> bool:
        """
        Проверить подпись постбека.
        
        Args:
            data: Данные постбека
            signature: Подпись
            
        Returns:
            True если подпись корректна
        """
        if not self.secret_key:
            logger.warning("⚠️ Secret key не установлен, пропуск проверки подписи")
            return True
        
        try:
            # Создать строку для подписи
            data_str = "&".join([f"{k}={v}" for k, v in sorted(data.items())])
            
            # Вычислить HMAC
            computed_signature = hmac.new(
                self.secret_key.encode(),
                data_str.encode(),
                hashlib.sha256
            ).hexdigest()
            
            # Сравнить подписи
            return hmac.compare_digest(computed_signature, signature)
        
        except Exception as e:
            logger.error(f"❌ Ошибка при проверке подписи: {e}", exc_info=True)
            return False
    
    @staticmethod
    def parse_postback_data(data: Dict[str, Any]) -> Optional[PostbackEvent]:
        """
        Парсить данные постбека от 1Win.
        
        Args:
            data: Данные из запроса
            
        Returns:
            PostbackEvent или None
        """
        try:
            # Определить тип события
            event_type = None
            if "registration" in data:
                event_type = PostbackHandler.EVENT_REGISTRATION
            elif "deposit" in data:
                event_type = PostbackHandler.EVENT_DEPOSIT
            elif "withdrawal" in data:
                event_type = PostbackHandler.EVENT_WITHDRAWAL
            elif "win" in data:
                event_type = PostbackHandler.EVENT_WIN
            else:
                logger.warning(f"⚠️ Неизвестный тип события: {data}")
                return None
            
            # Получить user_id
            user_id = data.get("user_id") or data.get("userId") or data.get("id")
            if not user_id:
                logger.warning("⚠️ user_id не найден в постбеке")
                return None
            
            # Получить сумму (если есть)
            amount = None
            if "amount" in data:
                try:
                    amount = float(data["amount"])
                except (ValueError, TypeError):
                    pass
            
            return PostbackEvent(
                event_type=event_type,
                user_id=str(user_id),
                amount=amount,
                **{k: v for k, v in data.items() if k not in ["user_id", "userId", "id", "amount"]}
            )
        
        except Exception as e:
            logger.error(f"❌ Ошибка при парсинге постбека: {e}", exc_info=True)
            return None
