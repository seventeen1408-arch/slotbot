"""Обработчики сообщений бота."""

# Импортируем модули обработчиков
from app.handlers import start, signals, text_handler, vip_upsell

__all__ = ['start', 'signals', 'text_handler', 'vip_upsell']
