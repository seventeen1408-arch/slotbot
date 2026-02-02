"""Логирование."""

import logging
import sys
from app.core.config import config


def get_logger(name: str) -> logging.Logger:
    """Получить логгер."""
    logger = logging.getLogger(name)
    logger.setLevel(config.LOG_LEVEL)
    
    # Консольный обработчик
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(config.LOG_LEVEL)
    
    # Формат логирования
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    
    if not logger.handlers:
        logger.addHandler(handler)
    
    return logger
