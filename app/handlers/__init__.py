"""Обработчики сообщений бота."""

# Импортируем модули обработчиков
from app.handlers import signals, text_handler, vip_upsell

# Создаем пустой модуль start для совместимости
class start:
    """Модуль обработчика команды /start."""
    pass

__all__ = ['start', 'signals', 'text_handler', 'vip_upsell']
