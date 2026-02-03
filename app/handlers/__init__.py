"""Обработчики сообщений бота."""

# Импортируем модули обработчиков
from app.handlers import signals, text_handler, vip_upsell

# Создаем пустой модуль start для совместимости
from aiogram import Router
class start:
    """Модуль обработчика команды /start."""
    router = Router()

__all__ = ['start', 'signals', 'text_handler', 'vip_upsell']
