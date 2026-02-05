"""Конфигурация бота."""

import os
from dotenv import load_dotenv

# Загрузить переменные окружения
load_dotenv()


class Config:
    """Конфигурация приложения."""
    
    # Bot settings
    BOT_TOKEN = os.getenv("BOT_TOKEN", "8159090114:AAF1oDAOZ-dYKrS-ue-1cgBo1uBFzkc0Gps")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "534928819")
    
    # Database
    DATABASE_PATH = os.getenv("DATABASE_PATH", "test_bot.db")
    
    # Soft gate settings
    SOFT_GATE_UNLOCK_TIME = int(os.getenv("SOFT_GATE_UNLOCK_TIME", "25"))  # 25 секунд
    SOFT_GATE_CHECK_INTERVAL = int(os.getenv("SOFT_GATE_CHECK_INTERVAL", "10"))  # 10 секунд
    
    # Postback settings
    ENABLE_POSTBACK = os.getenv("ENABLE_POSTBACK", "true").lower() == "true"
    POSTBACK_SECRET_KEY = os.getenv("POSTBACK_SECRET_KEY", "")
    
    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    
    def validate(self) -> None:
        """Валидировать конфигурацию."""
        if not self.BOT_TOKEN:
            raise ValueError("BOT_TOKEN не установлен")
        if not self.TELEGRAM_CHAT_ID:
            raise ValueError("TELEGRAM_CHAT_ID не установлен")


config = Config()
