"""
SoftGate Service - управление доступом к сигналам.

Функции:
- Управление доступом (2 часа бесплатно)
- Daily free limit (1 раз в 24 часа)
- Auto unlock при депозите (24 часа)
- FOMO countdown с напоминаниями
- VIP игнорирует лимиты
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from app.core.logger import get_logger
from app.core.config import config
from app.database.db import db


logger = get_logger(__name__)

# Константы
FREE_ACCESS_DURATION_MINUTES = 120  # 2 часа
FREE_ACCESS_LIMIT_HOURS = 24  # 1 раз в 24 часа
AUTO_UNLOCK_DURATION_HOURS = 24  # После депозита
FOMO_REMINDERS = [30, 10, 5, 1]  # Напоминания за N минут до конца


class SoftGateService:
    """Сервис управления доступом к сигналам."""

    def __init__(self, bot: Bot):
        self.bot = bot
        self.countdown_tasks: Dict[int, asyncio.Task] = {}

    # ========== BASIC METHODS ==========

    async def is_signals_unlocked(self, user_id: int) -> Tuple[bool, str]:
        """
        Проверить есть ли доступ к сигналам.

        Returns:
            (has_access, reason)
        """
        user = await db.get_user(user_id)
        if not user:
            return False, "user_not_found"

        # VIP игнорирует лимиты
        if user.get("is_vip"):
            return True, "vip_access"

        # Проверить auto_unlock (после депозита)
        if user.get("signals_unlocked_until"):
            unlock_until = user["signals_unlocked_until"]
            if isinstance(unlock_until, str):
                unlock_until = datetime.fromisoformat(unlock_until)
            
            if datetime.now() < unlock_until:
                return True, "auto_unlocked"
            else:
                # Истекло - очистить
                await db.update_user(user_id, {"signals_unlocked_until": None})

        # Проверить free_access (2 часа)
        if user.get("free_access_until"):
            free_until = user["free_access_until"]
            if isinstance(free_until, str):
                free_until = datetime.fromisoformat(free_until)
            
            if datetime.now() < free_until:
                return True, "free_access"
            else:
                # Истекло - очистить
                await db.update_user(user_id, {"free_access_until": None})

        return False, "no_access"

    async def can_use_free_access(self, user_id: int) -> Tuple[bool, str]:
        """
        Проверить можно ли использовать бесплатный доступ.

        Returns:
            (can_use, reason)
        """
        user = await db.get_user(user_id)
        if not user:
            return False, "user_not_found"

        # VIP игнорирует лимит
        if user.get("is_vip"):
            return True, "vip_no_limit"

        # Проверить last_free_access_at
        last_free = user.get("last_free_access_at")
        if last_free:
            if isinstance(last_free, str):
                last_free = datetime.fromisoformat(last_free)
            
            hours_since = (datetime.now() - last_free).total_seconds() / 3600
            if hours_since < FREE_ACCESS_LIMIT_HOURS:
                hours_left = FREE_ACCESS_LIMIT_HOURS - hours_since
                return False, f"limit_active_{int(hours_left)}"

        return True, "can_use"

    # ========== FREE ACCESS (2 HOURS) ==========

    async def grant_free_access(self, user_id: int) -> bool:
        """
        Выдать бесплатный доступ на 2 часа.
        """
        try:
            now = datetime.now()
            free_until = now + timedelta(minutes=FREE_ACCESS_DURATION_MINUTES)
            
            await db.update_user(user_id, {
                "free_access_until": free_until,
                "last_free_access_at": now
            })

            logger.info(f"Free access granted to user {user_id} until {free_until}")
            
            # Запустить countdown
            await self._start_countdown(user_id, "free_access", free_until)
            
            return True
        except Exception as e:
            logger.error(f"Error granting free access to {user_id}: {e}")
            return False

    # ========== AUTO UNLOCK (24 HOURS AFTER DEPOSIT) ==========

    async def unlock_24h(self, user_id: int) -> bool:
        """
        Автоматически открыть сигналы на 24 часа (при депозите).
        """
        try:
            now = datetime.now()
            unlock_until = now + timedelta(hours=AUTO_UNLOCK_DURATION_HOURS)
            
            await db.update_user(user_id, {
                "signals_unlocked_until": unlock_until,
                "free_access_until": None,  # Снять таймер free access
                "last_free_access_at": None  # Снять лимит
            })

            logger.info(f"Auto unlock 24h for user {user_id} until {unlock_until}")
            
            # Запустить countdown
            await self._start_countdown(user_id, "auto_unlock", unlock_until)
            
            # Отправить сообщение
            await self._send_unlock_message(user_id)
            
            return True
        except Exception as e:
            logger.error(f"Error auto unlocking user {user_id}: {e}")
            return False

    # ========== FOMO COUNTDOWN ==========

    async def _start_countdown(
        self,
        user_id: int,
        access_type: str,  # "free_access" или "auto_unlock"
        until_time: datetime
    ) -> None:
        """
        Запустить FOMO countdown с напоминаниями.
        """
        # Отменить старый таск если есть
        if user_id in self.countdown_tasks:
            self.countdown_tasks[user_id].cancel()

        # Создать новый таск
        task = asyncio.create_task(
            self._countdown_loop(user_id, access_type, until_time)
        )
        self.countdown_tasks[user_id] = task

    async def _countdown_loop(
        self,
        user_id: int,
        access_type: str,
        until_time: datetime
    ) -> None:
        """
        Основной loop для countdown с напоминаниями.
        """
        try:
            while True:
                now = datetime.now()
                time_left = (until_time - now).total_seconds()

                if time_left <= 0:
                    # Время истекло
                    await self._send_expire_message(user_id, access_type)
                    break

                # Проверить напоминания
                minutes_left = time_left / 60
                
                for reminder_minutes in FOMO_REMINDERS:
                    # Отправить напоминание за N минут
                    if reminder_minutes * 60 <= time_left < (reminder_minutes + 1) * 60:
                        await self._send_fomo_reminder(
                            user_id,
                            access_type,
                            reminder_minutes
                        )
                        # Подождать чтобы не отправить дважды
                        await asyncio.sleep(61)
                        break

                # Проверить каждые 30 секунд
                await asyncio.sleep(30)

        except asyncio.CancelledError:
            logger.debug(f"Countdown cancelled for user {user_id}")
        except Exception as e:
            logger.error(f"Error in countdown loop for {user_id}: {e}")
        finally:
            # Очистить таск
            if user_id in self.countdown_tasks:
                del self.countdown_tasks[user_id]

    async def _send_fomo_reminder(
        self,
        user_id: int,
        access_type: str,
        minutes_left: int
    ) -> None:
        """
        Отправить FOMO напоминание.
        """
        try:
            text = f"⏰ Your access expires in {minutes_left} minutes! View signals now."
            
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(
                        text="📊 View Signals",
                        callback_data="signals_list"
                    )]
                ]
            )
            
            await self.bot.send_message(
                user_id,
                text,
                reply_markup=keyboard
            )
            
            logger.info(f"FOMO reminder sent to {user_id}: {minutes_left} min left")
        except Exception as e:
            logger.error(f"Error sending FOMO reminder to {user_id}: {e}")

    async def _send_expire_message(
        self,
        user_id: int,
        access_type: str
    ) -> None:
        """
        Отправить сообщение об истечении доступа с VIP Upsell.
        """
        try:
            # Импортировать здесь чтобы избежать циклических импортов
            from app.handlers.vip_upsell import send_vip_upsell_message
            
            # Отправить VIP Upsell сообщение
            await send_vip_upsell_message(self.bot, user_id)
            
            logger.info(f"Access expired message with VIP Upsell sent to {user_id}")
        except Exception as e:
            logger.error(f"Error sending expire message to {user_id}: {e}")

    async def _send_unlock_message(self, user_id: int) -> None:
        """
        Отправить сообщение об автоматическом разблокировании.
        """
        try:
            text = "🎉 Your signals access has been unlocked for 24 hours! Start viewing signals now."
            
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(
                        text="📊 View Signals",
                        callback_data="signals_list"
                    )]
                ]
            )
            
            await self.bot.send_message(
                user_id,
                text,
                reply_markup=keyboard
            )
            
            logger.info(f"Auto unlock message sent to {user_id}")
        except Exception as e:
            logger.error(f"Error sending unlock message to {user_id}: {e}")

    # ========== CLEANUP ==========

    async def cleanup(self) -> None:
        """
        Очистить все countdown таски.
        """
        for task in self.countdown_tasks.values():
            task.cancel()
        self.countdown_tasks.clear()
        logger.info("SoftGateService cleanup completed")
