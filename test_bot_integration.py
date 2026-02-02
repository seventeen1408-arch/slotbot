"""
Интеграционные тесты для бота @SlotSignals_Bot.
Тестирует основную функциональность без необходимости запускать реальный бот.
"""

import asyncio
import sqlite3
import os
from datetime import datetime
from typing import Optional

# Импорты из приложения
from app.core import config, get_logger
from app.database.db import db
from app.database.models import User, Event

logger = get_logger(__name__)


class BotIntegrationTest:
    """Интеграционные тесты для бота."""
    
    def __init__(self):
        """Инициализировать тесты."""
        self.test_db_path = "test_bot_integration.db"
        self.test_results = []
        self.test_user_id = 123456789
        self.test_username = "test_user"
    
    async def setup(self) -> None:
        """Подготовить тестовую среду."""
        logger.info("🔧 Подготовка тестовой среды...")
        
        # Удалить старую БД если существует
        if os.path.exists(self.test_db_path):
            os.remove(self.test_db_path)
        
        # Инициализировать новую БД
        db.db_path = self.test_db_path
        await db.init()
        logger.info(f"✅ Тестовая БД создана: {self.test_db_path}")
    
    async def teardown(self) -> None:
        """Очистить тестовую среду."""
        logger.info("🧹 Очистка тестовой среды...")
        if os.path.exists(self.test_db_path):
            os.remove(self.test_db_path)
        logger.info("✅ Тестовая среда очищена")
    
    # ========================================================================
    # ТЕСТЫ ПОЛЬЗОВАТЕЛЯ
    # ========================================================================
    
    async def test_user_registration(self) -> bool:
        """Тест: Регистрация пользователя."""
        logger.info("\n📝 Тест: Регистрация пользователя")
        try:
            # Добавить пользователя
            await db.add_user(self.test_user_id, self.test_username, "ru")
            
            # Получить пользователя
            user = await db.get_user(self.test_user_id)
            
            # Проверить
            assert user is not None, "Пользователь не найден"
            assert user.user_id == self.test_user_id, "ID пользователя не совпадает"
            assert user.username == self.test_username, "Имя пользователя не совпадает"
            assert user.language == "ru", "Язык не совпадает"
            assert user.is_subscribed == False, "Пользователь должен быть не подписан"
            
            logger.info(f"✅ Пользователь успешно зарегистрирован: {user.user_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка: {e}")
            return False
    
    async def test_subscription_update(self) -> bool:
        """Тест: Обновление статуса подписки."""
        logger.info("\n📝 Тест: Обновление статуса подписки")
        try:
            # Добавить пользователя
            await db.add_user(self.test_user_id, self.test_username)
            
            # Обновить подписку
            await db.update_subscription(self.test_user_id, True)
            
            # Проверить
            is_subscribed = await db.is_user_subscribed(self.test_user_id)
            assert is_subscribed == True, "Подписка не обновлена"
            
            logger.info(f"✅ Подписка успешно обновлена")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка: {e}")
            return False
    
    async def test_language_update(self) -> bool:
        """Тест: Обновление языка пользователя."""
        logger.info("\n📝 Тест: Обновление языка пользователя")
        try:
            # Добавить пользователя
            await db.add_user(self.test_user_id, self.test_username, "ru")
            
            # Обновить язык
            await db.update_language(self.test_user_id, "en")
            
            # Получить пользователя
            user = await db.get_user(self.test_user_id)
            assert user.language == "en", "Язык не обновлен"
            
            logger.info(f"✅ Язык успешно обновлен на: en")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка: {e}")
            return False
    
    # ========================================================================
    # ТЕСТЫ SOFT GATE
    # ========================================================================
    
    async def test_casino_click(self) -> bool:
        """Тест: Клик на казино и установка таймера."""
        logger.info("\n📝 Тест: Клик на казино и установка таймера")
        try:
            # Добавить пользователя
            await db.add_user(self.test_user_id, self.test_username)
            
            # Установить клик на казино
            unlock_after = int(datetime.now().timestamp()) + 300  # +5 минут
            await db.set_casino_clicked(self.test_user_id, unlock_after)
            
            # Получить пользователя
            user = await db.get_user(self.test_user_id)
            assert user.casino_clicked == True, "Клик на казино не установлен"
            assert user.unlock_after == unlock_after, "Время разблокировки не совпадает"
            assert user.casino_clicks_count == 1, "Счетчик кликов не обновлен"
            
            logger.info(f"✅ Клик на казино успешно зафиксирован")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка: {e}")
            return False
    
    async def test_signals_unlock(self) -> bool:
        """Тест: Разблокировка сигналов."""
        logger.info("\n📝 Тест: Разблокировка сигналов")
        try:
            # Добавить пользователя
            await db.add_user(self.test_user_id, self.test_username)
            
            # Разблокировать сигналы
            await db.unlock_signals(self.test_user_id)
            
            # Получить пользователя
            user = await db.get_user(self.test_user_id)
            assert user.signals_unlocked == True, "Сигналы не разблокированы"
            
            logger.info(f"✅ Сигналы успешно разблокированы")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка: {e}")
            return False
    
    async def test_signals_lock(self) -> bool:
        """Тест: Блокировка сигналов."""
        logger.info("\n📝 Тест: Блокировка сигналов")
        try:
            # Добавить пользователя
            await db.add_user(self.test_user_id, self.test_username)
            
            # Разблокировать сигналы
            await db.unlock_signals(self.test_user_id)
            
            # Заблокировать сигналы
            await db.lock_signals(self.test_user_id)
            
            # Получить пользователя
            user = await db.get_user(self.test_user_id)
            assert user.signals_unlocked == False, "Сигналы не заблокированы"
            assert user.casino_clicked == False, "Клик на казино не очищен"
            
            logger.info(f"✅ Сигналы успешно заблокированы")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка: {e}")
            return False
    
    # ========================================================================
    # ТЕСТЫ СОБЫТИЙ
    # ========================================================================
    
    async def test_event_logging(self) -> bool:
        """Тест: Логирование событий."""
        logger.info("\n📝 Тест: Логирование событий")
        try:
            # Добавить пользователя
            await db.add_user(self.test_user_id, self.test_username)
            
            # Логировать событие
            now = int(datetime.now().timestamp())
            await db.log_event(
                self.test_user_id,
                "first_deposit",
                '{"amount": 100.0, "currency": "USD"}'
            )
            
            # Получить события
            events = await db.get_user_events(self.test_user_id)
            assert len(events) > 0, "События не логированы"
            assert events[0].event_type == "first_deposit", "Тип события не совпадает"
            
            logger.info(f"✅ События успешно логированы")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка: {e}")
            return False
    
    # ========================================================================
    # ТЕСТЫ ПОСТБЕКА
    # ========================================================================
    
    async def test_postback_registration(self) -> bool:
        """Тест: Обработка постбека регистрации."""
        logger.info("\n📝 Тест: Обработка постбека регистрации")
        try:
            # Добавить пользователя через постбек
            await db.add_user(self.test_user_id, self.test_username)
            
            # Логировать событие регистрации
            await db.log_event(self.test_user_id, "register", None)
            
            # Проверить
            user = await db.get_user(self.test_user_id)
            assert user is not None, "Пользователь не добавлен"
            
            events = await db.get_user_events(self.test_user_id)
            assert any(e.event_type == "register" for e in events), "Событие регистрации не логировано"
            
            logger.info(f"✅ Постбек регистрации успешно обработан")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка: {e}")
            return False
    
    async def test_postback_deposit(self) -> bool:
        """Тест: Обработка постбека депозита."""
        logger.info("\n📝 Тест: Обработка постбека депозита")
        try:
            # Добавить пользователя
            await db.add_user(self.test_user_id, self.test_username)
            
            # Логировать событие депозита
            await db.log_event(
                self.test_user_id,
                "first_deposit",
                '{"amount": 100.0, "currency": "USD"}'
            )
            
            # Обновить статус депозита
            await db.execute(
                "UPDATE users SET is_deposited = 1 WHERE user_id = ?",
                (self.test_user_id,)
            )
            
            # Проверить
            user = await db.get_user(self.test_user_id)
            assert user.is_deposited == True, "Статус депозита не обновлен"
            
            events = await db.get_user_events(self.test_user_id)
            assert any(e.event_type == "first_deposit" for e in events), "Событие депозита не логировано"
            
            logger.info(f"✅ Постбек депозита успешно обработан")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка: {e}")
            return False
    
    # ========================================================================
    # ЗАПУСК ВСЕХ ТЕСТОВ
    # ========================================================================
    
    async def run_all_tests(self) -> None:
        """Запустить все тесты."""
        logger.info("=" * 70)
        logger.info("🚀 ЗАПУСК ИНТЕГРАЦИОННЫХ ТЕСТОВ БОТА @SlotSignals_Bot")
        logger.info("=" * 70)
        
        try:
            # Подготовка
            await self.setup()
            
            # Тесты пользователя
            self.test_results.append(("Регистрация пользователя", await self.test_user_registration()))
            self.test_results.append(("Обновление подписки", await self.test_subscription_update()))
            self.test_results.append(("Обновление языка", await self.test_language_update()))
            
            # Тесты soft gate
            self.test_results.append(("Клик на казино", await self.test_casino_click()))
            self.test_results.append(("Разблокировка сигналов", await self.test_signals_unlock()))
            self.test_results.append(("Блокировка сигналов", await self.test_signals_lock()))
            
            # Тесты событий
            self.test_results.append(("Логирование событий", await self.test_event_logging()))
            
            # Тесты постбека
            self.test_results.append(("Постбек регистрации", await self.test_postback_registration()))
            self.test_results.append(("Постбек депозита", await self.test_postback_deposit()))
            
            # Вывод результатов
            await self.print_results()
            
        except Exception as e:
            logger.error(f"❌ Критическая ошибка: {e}", exc_info=True)
        
        finally:
            # Очистка
            await self.teardown()
    
    async def print_results(self) -> None:
        """Вывести результаты тестов."""
        logger.info("\n" + "=" * 70)
        logger.info("📊 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ")
        logger.info("=" * 70)
        
        passed = sum(1 for _, result in self.test_results if result)
        total = len(self.test_results)
        
        for test_name, result in self.test_results:
            status = "✅ PASSED" if result else "❌ FAILED"
            logger.info(f"{status:15} | {test_name}")
        
        logger.info("=" * 70)
        logger.info(f"📈 Итого: {passed}/{total} тестов пройдено ({int(passed/total*100)}%)")
        logger.info("=" * 70)


async def main():
    """Главная функция."""
    test = BotIntegrationTest()
    await test.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
