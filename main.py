"""
PRO-бот для арбитража трафика - точка входа.
Production-ready версия.
"""

import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core import config, get_logger
from app.database.db import db
from app.services.soft_gate_service import SoftGateService
from app.services.autoresponder_service import AutoResponderService
from app.services.retention_service import RetentionService
from app.services.postback_pro_service import PostbackProService
from app.handlers import start, signals, text_handler, vip_upsell

logger = get_logger(__name__)


async def on_startup(bot: Bot, dispatcher: Dispatcher) -> None:
    """Инициализация при запуске бота."""
    try:
        logger.info("🚀 Запуск PRO-бота для арбитража трафика...")
        
        # Инициализировать БД
        await db.init()
        logger.info("✅ БД инициализирована")
        
        # Создать сервисы
        subscription_service = SubscriptionService(bot)
        soft_gate_service = SoftGateService(bot)
        autoresponder_service = AutoResponderService(bot)
        retention_service = RetentionService(bot)
        postback_pro_service = PostbackProService(bot, soft_gate_service=soft_gate_service)
        
        # Сохранить сервисы в контекст
        dispatcher.workflow_data["subscription_service"] = subscription_service
        dispatcher.workflow_data["soft_gate_service"] = soft_gate_service
        dispatcher.workflow_data["autoresponder_service"] = autoresponder_service
        dispatcher.workflow_data["retention_service"] = retention_service
        dispatcher.workflow_data["postback_pro_service"] = postback_pro_service
        
        logger.info("✅ Сервисы инициализированы")
        
        # Запустить фоновые задачи
        scheduler = AsyncIOScheduler()
        
        # Задача проверки и разблокировки сигналов (каждые 10 сек)
        scheduler.add_job(
            soft_gate_service.check_and_unlock_signals,
            "interval",
            seconds=config.SOFT_GATE_CHECK_INTERVAL,
            id="check_unlock_signals"
        )
        
        scheduler.start()
        dispatcher.workflow_data["scheduler"] = scheduler
        
        logger.info("✅ Фоновые задачи запущены")
        logger.info("✅ Бот готов к работе!")
    
    except Exception as e:
        logger.error(f"❌ Ошибка при инициализации: {e}", exc_info=True)
        raise


async def on_shutdown(bot: Bot, dispatcher: Dispatcher) -> None:
    """Завершение при остановке бота."""
    try:
        logger.info("🛑 Остановка бота...")
        
        # Остановить планировщик
        if "scheduler" in dispatcher.workflow_data:
            scheduler = dispatcher.workflow_data["scheduler"]
            scheduler.shutdown()
            logger.info("✅ Планировщик остановлен")
        
        logger.info("✅ Бот остановлен корректно")
    
    except Exception as e:
        logger.error(f"❌ Ошибка при остановке: {e}", exc_info=True)


async def main() -> None:
    """Главная функция."""
    try:
        # Инициализировать бота
        bot = Bot(token=config.BOT_TOKEN)
        storage = MemoryStorage()
        dp = Dispatcher(storage=storage)
        
        # Регистрировать роутеры
        dp.include_router(start.router)
        dp.include_router(signals.router)
        dp.include_router(text_handler.router)
        dp.include_router(vip_upsell.router)
        
        logger.info("✅ Роутеры зарегистрированы")
        
        # Регистрировать обработчики жизненного цикла
        dp.startup.register(on_startup)
        dp.shutdown.register(on_shutdown)
        
        # Запустить polling
        logger.info("📡 Запуск polling...")
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
            skip_updates=True
        )
    
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}", exc_info=True)
    
    finally:
        logger.info("🛑 Бот завершил работу")


if __name__ == "__main__":
    try:
        # Валидировать конфигурацию
        config.validate()
        
        # Запустить бота
        asyncio.run(main())
    
    except KeyboardInterrupt:
        logger.info("⏹️ Бот остановлен пользователем")
    
    except Exception as e:
        logger.error(f"❌ Неожиданная ошибка: {e}", exc_info=True)
