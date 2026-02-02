"""
Сервис умного автоответчика (AutoResponder).
Отвечает на текстовые сообщения пользователя локально (без AI).
"""

import re
import time
from typing import Optional, Dict, Tuple
from aiogram import Bot
from aiogram.types import User as TgUser, InlineKeyboardMarkup, InlineKeyboardButton
from app.core.logger import get_logger
from app.core.config import config
from app.locales.i18n import I18n
from app.database.models import User
from app.database.db import db

logger = get_logger(__name__)


class AutoResponderService:
    """Умный автоответчик на текстовые сообщения."""
    
    # Минимальный интервал между ответами (10 сек)
    MIN_RESPONSE_INTERVAL = 10
    
    # Ключевые слова для разных категорий ответов
    KEYWORDS_SIGNALS = {
        "ru": ["сигнал", "сигналы", "сигналы?", "какой сигнал", "когда сигнал"],
        "en": ["signal", "signals", "when signal", "what signal", "get signal"]
    }
    
    KEYWORDS_CASINO = {
        "ru": ["казино", "играть", "игра", "ставка", "депозит", "вывод"],
        "en": ["casino", "play", "game", "bet", "deposit", "withdraw"]
    }
    
    KEYWORDS_VIP = {
        "ru": ["вип", "vip", "премиум", "premium", "подписка", "членство"],
        "en": ["vip", "premium", "subscription", "membership"]
    }
    
    KEYWORDS_HELP = {
        "ru": ["помощь", "как", "что", "помоги", "объясни", "инструкция"],
        "en": ["help", "how", "what", "explain", "instruction", "guide"]
    }
    
    # Кэш времени последнего ответа (user_id -> timestamp)
    _response_cache: Dict[int, float] = {}
    
    def __init__(self, bot: Bot):
        """Инициализировать сервис."""
        self.bot = bot
        self.i18n = I18n()
    
    async def handle_text(self, user_id: int, user: User, message_text: str) -> Optional[str]:
        """
        Обработать текстовое сообщение пользователя.
        
        Args:
            user_id: ID пользователя
            user: Объект пользователя из БД
            message_text: Текст сообщения
            
        Returns:
            Ответ (если нужно отправить) или None
        """
        try:
            # Проверить антиспам (не более 1 ответа в 10 сек)
            if not self._check_rate_limit(user_id):
                logger.debug(f"⏱️ Антиспам: пропускаю ответ для {user_id}")
                return None
            
            # Нормализовать текст
            normalized_text = self._normalize_text(message_text)
            
            # Определить категорию и получить ответ
            response, response_type = await self._get_response(
                user_id, user, normalized_text
            )
            
            if response:
                # Логировать событие
                await db.log_event(
                    user_id,
                    "autoresponder_response",
                    {"type": response_type, "text": message_text[:50]}
                )
                
                logger.info(f"✅ AutoResponder для {user_id}: тип={response_type}")
                return response
            
            return None
        
        except Exception as e:
            logger.error(f"❌ Ошибка в AutoResponder для {user_id}: {e}", exc_info=True)
            return None
    
    def _check_rate_limit(self, user_id: int) -> bool:
        """
        Проверить антиспам (не более 1 ответа в 10 сек).
        
        Args:
            user_id: ID пользователя
            
        Returns:
            True если можно отвечать, False если нужно ждать
        """
        now = time.time()
        last_response = self._response_cache.get(user_id, 0)
        
        if now - last_response < self.MIN_RESPONSE_INTERVAL:
            return False
        
        # Обновить кэш
        self._response_cache[user_id] = now
        return True
    
    def _normalize_text(self, text: str) -> str:
        """
        Нормализовать текст (нижний регистр, убрать спецсимволы).
        
        Args:
            text: Исходный текст
            
        Returns:
            Нормализованный текст
        """
        # Нижний регистр
        text = text.lower()
        
        # Убрать спецсимволы (кроме букв, цифр, пробелов)
        text = re.sub(r'[^а-яa-z0-9\s]', '', text)
        
        # Убрать лишние пробелы
        text = ' '.join(text.split())
        
        return text
    
    async def _get_response(
        self, user_id: int, user: User, normalized_text: str
    ) -> Tuple[Optional[str], str]:
        """
        Определить категорию и получить ответ.
        
        Args:
            user_id: ID пользователя
            user: Объект пользователя из БД
            normalized_text: Нормализованный текст
            
        Returns:
            Кортеж (ответ, тип_ответа) или (None, "")
        """
        language = user.language or "ru"
        
        # Проверить ключевые слова для каждой категории
        if self._match_keywords(normalized_text, self.KEYWORDS_SIGNALS, language):
            return await self._response_signals(user_id, user, language), "signals"
        
        if self._match_keywords(normalized_text, self.KEYWORDS_CASINO, language):
            return await self._response_casino(user_id, user, language), "casino"
        
        if self._match_keywords(normalized_text, self.KEYWORDS_VIP, language):
            return await self._response_vip(user_id, user, language), "vip"
        
        if self._match_keywords(normalized_text, self.KEYWORDS_HELP, language):
            return await self._response_help(user_id, user, language), "help"
        
        # Fallback ответ
        return await self._response_fallback(user_id, user, language), "fallback"
    
    def _match_keywords(
        self, text: str, keywords_dict: Dict[str, list], language: str
    ) -> bool:
        """
        Проверить совпадение с ключевыми словами.
        
        Args:
            text: Текст для проверки
            keywords_dict: Словарь ключевых слов по языкам
            language: Язык
            
        Returns:
            True если есть совпадение
        """
        keywords = keywords_dict.get(language, [])
        
        for keyword in keywords:
            # Проверить полное совпадение слова
            if re.search(r'\b' + re.escape(keyword) + r'\b', text):
                return True
        
        return False
    
    async def _response_signals(self, user_id: int, user: User, language: str) -> str:
        """Ответ на вопрос о сигналах."""
        response = (
            "📊 <b>Сигналы</b>\n\n"
            if language == "ru"
            else "📊 <b>Signals</b>\n\n"
        )
        
        if language == "ru":
            response += (
                "Я отправляю точные сигналы на игры каждый день.\n\n"
                "Для получения сигналов:\n"
                "1️⃣ Убедись что ты подписан на канал\n"
                "2️⃣ Нажми кнопку ниже\n"
                "3️⃣ Следуй рекомендациям\n\n"
                "Средняя точность: 75% ✅"
            )
        else:
            response += (
                "I send accurate game signals every day.\n\n"
                "To get signals:\n"
                "1️⃣ Make sure you're subscribed to the channel\n"
                "2️⃣ Click the button below\n"
                "3️⃣ Follow the recommendations\n\n"
                "Average accuracy: 75% ✅"
            )
        
        return response
    
    async def _response_casino(self, user_id: int, user: User, language: str) -> str:
        """Ответ на вопрос о казино."""
        response = (
            "🎰 <b>Казино</b>\n\n"
            if language == "ru"
            else "🎰 <b>Casino</b>\n\n"
        )
        
        if language == "ru":
            response += (
                "Я помогу тебе выбрать лучшее казино и получить максимум прибыли.\n\n"
                "Популярные казино:\n"
                "✅ 1Win - лучшие коэффициенты\n"
                "✅ Vavada - быстрые выводы\n"
                "✅ Mostbet - большой выбор игр\n\n"
                "Нажми кнопку ниже чтобы перейти 👇"
            )
        else:
            response += (
                "I'll help you choose the best casino and maximize your profits.\n\n"
                "Popular casinos:\n"
                "✅ 1Win - best odds\n"
                "✅ Vavada - fast withdrawals\n"
                "✅ Mostbet - wide game selection\n\n"
                "Click the button below to go 👇"
            )
        
        return response
    
    async def _response_vip(self, user_id: int, user: User, language: str) -> str:
        """Ответ на вопрос о VIP."""
        response = (
            "👑 <b>VIP Членство</b>\n\n"
            if language == "ru"
            else "👑 <b>VIP Membership</b>\n\n"
        )
        
        if language == "ru":
            response += (
                "VIP дает тебе эксклюзивные преимущества:\n\n"
                "✨ Приватные сигналы\n"
                "✨ Консультации трейдеров\n"
                "✨ Приоритетная поддержка\n"
                "✨ Скидки на услуги\n\n"
                "Стоимость: от 500 руб/месяц\n\n"
                "Нажми кнопку ниже чтобы узнать больше 👇"
            )
        else:
            response += (
                "VIP gives you exclusive benefits:\n\n"
                "✨ Private signals\n"
                "✨ Trader consultations\n"
                "✨ Priority support\n"
                "✨ Service discounts\n\n"
                "Starting from $5/month\n\n"
                "Click the button below to learn more 👇"
            )
        
        return response
    
    async def _response_help(self, user_id: int, user: User, language: str) -> str:
        """Ответ на вопрос помощи."""
        response = (
            "❓ <b>Справка</b>\n\n"
            if language == "ru"
            else "❓ <b>Help</b>\n\n"
        )
        
        if language == "ru":
            response += (
                "<b>Как это работает:</b>\n\n"
                "1️⃣ <b>Подписка</b> - подпишись на канал\n"
                "2️⃣ <b>Сигналы</b> - получай сигналы каждый день\n"
                "3️⃣ <b>Казино</b> - используй сигналы в казино\n"
                "4️⃣ <b>Прибыль</b> - получай деньги 💰\n\n"
                "Нужна помощь? Напиши нам в поддержку!"
            )
        else:
            response += (
                "<b>How it works:</b>\n\n"
                "1️⃣ <b>Subscribe</b> - subscribe to the channel\n"
                "2️⃣ <b>Signals</b> - get signals every day\n"
                "3️⃣ <b>Casino</b> - use signals in the casino\n"
                "4️⃣ <b>Profit</b> - make money 💰\n\n"
                "Need help? Write to our support!"
            )
        
        return response
    
    async def _response_fallback(self, user_id: int, user: User, language: str) -> str:
        """Fallback ответ."""
        if language == "ru":
            return (
                "😊 Я помогу тебе 👇\n\n"
                "Выбери действие в меню или напиши:\n"
                "• <b>Сигналы</b> - получить сигналы\n"
                "• <b>Казино</b> - перейти в казино\n"
                "• <b>ВИП</b> - узнать о VIP\n"
                "• <b>Помощь</b> - справка"
            )
        else:
            return (
                "😊 I'll help you 👇\n\n"
                "Choose an action from the menu or write:\n"
                "• <b>Signals</b> - get signals\n"
                "• <b>Casino</b> - go to casino\n"
                "• <b>VIP</b> - learn about VIP\n"
                "• <b>Help</b> - help"
            )
    
    def clear_cache(self) -> None:
        """Очистить кэш (для тестирования)."""
        self._response_cache.clear()
        logger.info("✅ Кэш AutoResponder очищен")
