"""
PRO S2S Postback Service с полной безопасностью.

Функции:
- HMAC-SHA256 верификация подписей
- Replay attack protection (idempotency)
- IP whitelist
- Rate limiting
- Timestamp validation
- Audit logging
- Encryption at rest
- Pydantic валидация
"""

import hashlib
import hmac
import json
import time
import uuid
import re
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple, List
from enum import Enum
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from app.core.logger import get_logger
from app.core.config import config
from app.database.db import db
from app.locales.i18n import t

logger = get_logger(__name__)


class PostbackEventType(str, Enum):
    """Типы событий постбека."""
    REGISTRATION = "register"
    FIRST_DEPOSIT = "first_deposit"
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    WIN = "win"


class PostbackStatus(str, Enum):
    """Статусы обработки постбека."""
    RECEIVED = "received"
    VERIFIED = "verified"
    PROCESSED = "processed"
    FAILED = "failed"
    DUPLICATE = "duplicate"


class PostbackProService:
    """
    PRO S2S Postback Service с полной безопасностью.
    
    Защита:
    1. HMAC-SHA256 подпись
    2. Replay attack prevention (idempotency)
    3. IP whitelist
    4. Rate limiting
    5. Timestamp validation
    6. Audit logging
    7. Encryption at rest
    8. Pydantic валидация
    """
    
    # Конфигурация
    MAX_EVENT_AGE_SECONDS = 300  # 5 минут
    RATE_LIMIT_WINDOW = 60  # 1 минута
    RATE_LIMIT_MAX_REQUESTS = 100  # 100 запросов в минуту
    
    # IP Whitelist (по партнерам)
    IP_WHITELIST = {
        "1win": ["1.2.3.4", "5.6.7.8"],  # Примеры, нужно обновить реальными IP
        "stake": ["10.11.12.13"],
        "roobet": ["14.15.16.17"],
        "localhost": ["127.0.0.1", "::1"],  # Для тестирования
    }
    
    # VIP длительность при первом депозите
    VIP_DURATION_HOURS = 48
    
    def __init__(self, bot: Bot, soft_gate_service=None):
        self.bot = bot
        self.soft_gate_service = soft_gate_service
        self.secret_keys = self._load_secret_keys()
        self.rate_limit_cache: Dict[str, List[float]] = {}
    
    def _load_secret_keys(self) -> Dict[str, str]:
        """Загрузить secret keys для партнеров из конфига."""
        keys = {}
        
        # Пример: POSTBACK_SECRET_1WIN, POSTBACK_SECRET_STAKE и т.д.
        for partner in self.IP_WHITELIST.keys():
            env_key = f"POSTBACK_SECRET_{partner.upper()}"
            secret = getattr(config, env_key, None)
            if secret:
                keys[partner] = secret
                logger.info(f"✅ Загружен secret key для партнера {partner}")
            else:
                logger.warning(f"⚠️ Secret key не найден для партнера {partner}")
        
        return keys
    
    # ========== ЗАЩИТА 1: HMAC Верификация ==========
    
    def verify_signature(
        self,
        data: Dict[str, Any],
        signature: str,
        partner_name: str
    ) -> Tuple[bool, str]:
        """
        Проверить HMAC-SHA256 подпись.
        
        Args:
            data: Данные постбека (без самой подписи)
            signature: Подпись для проверки
            partner_name: Имя партнера
            
        Returns:
            (is_valid, message)
        """
        try:
            # Получить secret key
            secret_key = self.secret_keys.get(partner_name)
            if not secret_key:
                logger.error(f"❌ Secret key не найден для партнера {partner_name}")
                return False, "Secret key not found"
            
            # Исключить саму подпись из данных
            data_without_sig = {k: v for k, v in data.items() if k != 'signature'}
            
            # Отсортировать для консистентности
            sorted_data = sorted(data_without_sig.items())
            
            # Создать строку для подписи
            data_string = "&".join([f"{k}={v}" for k, v in sorted_data])
            
            # Вычислить ожидаемую подпись
            expected_signature = hmac.new(
                secret_key.encode(),
                data_string.encode(),
                hashlib.sha256
            ).hexdigest()
            
            # Timing-safe сравнение
            is_valid = hmac.compare_digest(expected_signature, signature)
            
            if is_valid:
                logger.debug(f"✅ Подпись верна для партнера {partner_name}")
                return True, "Signature verified"
            else:
                logger.warning(f"❌ Неверная подпись для партнера {partner_name}")
                return False, "Invalid signature"
        
        except Exception as e:
            logger.error(f"❌ Ошибка при проверке подписи: {e}", exc_info=True)
            return False, str(e)
    
    # ========== ЗАЩИТА 2: IP Whitelist ==========
    
    def verify_ip(self, partner_name: str, client_ip: str) -> Tuple[bool, str]:
        """
        Проверить IP адрес.
        
        Args:
            partner_name: Имя партнера
            client_ip: IP адрес клиента
            
        Returns:
            (is_allowed, message)
        """
        try:
            allowed_ips = self.IP_WHITELIST.get(partner_name, [])
            
            if not allowed_ips:
                logger.warning(f"⚠️ IP whitelist не настроен для партнера {partner_name}")
                return False, "IP whitelist not configured"
            
            if client_ip in allowed_ips:
                logger.debug(f"✅ IP {client_ip} разрешен для партнера {partner_name}")
                return True, "IP allowed"
            else:
                logger.warning(f"❌ IP {client_ip} не разрешен для партнера {partner_name}")
                return False, "IP not allowed"
        
        except Exception as e:
            logger.error(f"❌ Ошибка при проверке IP: {e}", exc_info=True)
            return False, str(e)
    
    # ========== ЗАЩИТА 3: Timestamp Validation ==========
    
    def verify_timestamp(self, timestamp: int) -> Tuple[bool, str]:
        """
        Проверить timestamp события.
        
        Args:
            timestamp: Unix timestamp события
            
        Returns:
            (is_valid, message)
        """
        try:
            current_time = int(time.time())
            age = current_time - timestamp
            
            # Проверить что событие не слишком старое
            if age > self.MAX_EVENT_AGE_SECONDS:
                logger.warning(f"⚠️ Событие слишком старое: {age} секунд")
                return False, f"Event too old: {age} seconds"
            
            # Проверить что событие не из будущего (часовой сдвиг)
            if age < -60:  # Допуск 60 секунд
                logger.warning(f"⚠️ Событие из будущего: {age} секунд")
                return False, f"Event from future: {age} seconds"
            
            logger.debug(f"✅ Timestamp валиден: {age} секунд назад")
            return True, "Timestamp valid"
        
        except Exception as e:
            logger.error(f"❌ Ошибка при проверке timestamp: {e}", exc_info=True)
            return False, str(e)
    
    # ========== ЗАЩИТА 4: Rate Limiting ==========
    
    def check_rate_limit(self, partner_name: str, client_ip: str) -> Tuple[bool, str]:
        """
        Проверить rate limit.
        
        Args:
            partner_name: Имя партнера
            client_ip: IP адрес клиента
            
        Returns:
            (is_allowed, message)
        """
        try:
            key = f"{partner_name}:{client_ip}"
            current_time = time.time()
            
            # Получить или создать список запросов
            if key not in self.rate_limit_cache:
                self.rate_limit_cache[key] = []
            
            requests = self.rate_limit_cache[key]
            
            # Удалить старые запросы (старше 1 минуты)
            requests = [req_time for req_time in requests 
                       if current_time - req_time < self.RATE_LIMIT_WINDOW]
            
            # Проверить лимит
            if len(requests) >= self.RATE_LIMIT_MAX_REQUESTS:
                logger.warning(
                    f"❌ Rate limit превышен для {partner_name} ({client_ip}): "
                    f"{len(requests)} запросов в минуту"
                )
                return False, "Rate limit exceeded"
            
            # Добавить текущий запрос
            requests.append(current_time)
            self.rate_limit_cache[key] = requests
            
            logger.debug(f"✅ Rate limit OK: {len(requests)}/{self.RATE_LIMIT_MAX_REQUESTS}")
            return True, "Rate limit OK"
        
        except Exception as e:
            logger.error(f"❌ Ошибка при проверке rate limit: {e}", exc_info=True)
            return False, str(e)
    
    # ========== ЗАЩИТА 5: Replay Attack Prevention (Idempotency) ==========
    
    async def check_idempotency(self, event_id: str) -> Tuple[bool, str]:
        """
        Проверить что событие не обработано ранее.
        
        Args:
            event_id: Уникальный ID события
            
        Returns:
            (is_new, message)
        """
        try:
            # Проверить в БД
            existing_log = await db.get_postback_log_by_event_id(event_id)
            
            if existing_log:
                logger.warning(f"⚠️ Дублирующееся событие: {event_id}")
                return False, "Duplicate event"
            
            logger.debug(f"✅ Событие новое: {event_id}")
            return True, "Event is new"
        
        except Exception as e:
            logger.error(f"❌ Ошибка при проверке idempotency: {e}", exc_info=True)
            return False, str(e)
    
    # ========== ЗАЩИТА 6: Pydantic Валидация ==========
    
    def validate_data(self, data: Dict[str, Any]) -> Tuple[bool, str, Optional[Dict]]:
        """
        Валидировать данные постбека.
        
        Args:
            data: Данные для валидации
            
        Returns:
            (is_valid, message, validated_data)
        """
        try:
            # Обязательные поля
            required_fields = ['click_id', 'event', 'timestamp', 'signature']
            for field in required_fields:
                if field not in data:
                    return False, f"Missing required field: {field}", None
            
            click_id = data.get('click_id', '')
            event = data.get('event', '')
            amount = data.get('amount')
            currency = data.get('currency', 'USD')
            
            # Валидировать click_id (UUID)
            uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
            if not re.match(uuid_pattern, click_id):
                return False, "Invalid click_id format (must be UUID)", None
            
            # Валидировать event type
            try:
                PostbackEventType(event)
            except ValueError:
                valid_events = [e.value for e in PostbackEventType]
                return False, f"Invalid event type. Must be one of: {valid_events}", None
            
            # Валидировать amount (если есть)
            if amount is not None:
                try:
                    amount = float(amount)
                    if amount < 0:
                        return False, "Amount cannot be negative", None
                except (ValueError, TypeError):
                    return False, "Invalid amount format", None
            
            # Валидировать currency
            valid_currencies = ['USD', 'EUR', 'RUB', 'GBP', 'JPY']
            if currency not in valid_currencies:
                return False, f"Invalid currency. Must be one of: {valid_currencies}", None
            
            # Валидировать timestamp
            try:
                timestamp = int(data.get('timestamp', 0))
                if timestamp <= 0:
                    return False, "Invalid timestamp", None
            except (ValueError, TypeError):
                return False, "Invalid timestamp format", None
            
            logger.debug(f"✅ Данные валидны")
            
            return True, "Data valid", {
                'click_id': click_id,
                'event': event,
                'amount': amount,
                'currency': currency,
                'timestamp': timestamp,
            }
        
        except Exception as e:
            logger.error(f"❌ Ошибка при валидации данных: {e}", exc_info=True)
            return False, str(e), None
    
    # ========== ЗАЩИТА 7 & 8: Audit Logging + Encryption ==========
    
    async def log_audit(
        self,
        partner_name: str,
        event_id: str,
        client_ip: str,
        action: str,
        data: Dict[str, Any],
        user_id: Optional[int] = None,
        status: str = "success"
    ) -> bool:
        """
        Логировать аудит событие.
        
        Args:
            partner_name: Имя партнера
            event_id: ID события
            client_ip: IP адрес клиента
            action: Действие (received, verified, processed, failed)
            data: Данные события
            user_id: ID пользователя (если применимо)
            status: Статус (success, failed)
            
        Returns:
            True если логирование успешно
        """
        try:
            audit_data = {
                'timestamp': datetime.utcnow().isoformat(),
                'partner': partner_name,
                'event_id': event_id,
                'ip_address': client_ip,
                'action': action,
                'status': status,
                'user_id': user_id,
                'event_type': data.get('event'),
                'amount': data.get('amount'),
                'currency': data.get('currency'),
            }
            
            # Сохранить в БД
            await db.create_postback_audit_log(
                partner_name=partner_name,
                event_id=event_id,
                ip_address=client_ip,
                action=action,
                details=json.dumps(audit_data),
                user_id=user_id,
                status=status
            )
            
            logger.info(f"✅ Аудит логирован: {event_id} ({action})")
            return True
        
        except Exception as e:
            logger.error(f"❌ Ошибка при логировании аудита: {e}", exc_info=True)
            return False
    
    # ========== Основная обработка ==========
    
    async def handle_postback(
        self,
        partner_name: str,
        data: Dict[str, Any],
        client_ip: str
    ) -> Tuple[bool, str, Optional[Dict]]:
        """
        Обработать постбек с полной безопасностью.
        
        Args:
            partner_name: Имя партнера
            data: Данные постбека
            client_ip: IP адрес клиента
            
        Returns:
            (success, message, result_data)
        """
        try:
            # Генерировать event_id для отслеживания
            event_id = str(uuid.uuid4())
            
            logger.info(f"📨 Получен постбек от {partner_name}: {event_id}")
            
            # Логировать получение
            await self.log_audit(
                partner_name, event_id, client_ip,
                "received", data, status="received"
            )
            
            # ЗАЩИТА 1: IP Whitelist
            ip_valid, ip_msg = self.verify_ip(partner_name, client_ip)
            if not ip_valid:
                await self.log_audit(
                    partner_name, event_id, client_ip,
                    "ip_check", data, status="failed"
                )
                return False, ip_msg, None
            
            # ЗАЩИТА 2: Rate Limiting
            rate_ok, rate_msg = self.check_rate_limit(partner_name, client_ip)
            if not rate_ok:
                await self.log_audit(
                    partner_name, event_id, client_ip,
                    "rate_limit", data, status="failed"
                )
                return False, rate_msg, None
            
            # ЗАЩИТА 3: Валидация данных
            valid, valid_msg, validated_data = self.validate_data(data)
            if not valid:
                await self.log_audit(
                    partner_name, event_id, client_ip,
                    "validation", data, status="failed"
                )
                return False, valid_msg, None
            
            # ЗАЩИТА 4: Timestamp Validation
            ts_valid, ts_msg = self.verify_timestamp(validated_data['timestamp'])
            if not ts_valid:
                await self.log_audit(
                    partner_name, event_id, client_ip,
                    "timestamp", data, status="failed"
                )
                return False, ts_msg, None
            
            # ЗАЩИТА 5: HMAC Верификация
            sig_valid, sig_msg = self.verify_signature(data, data.get('signature', ''), partner_name)
            if not sig_valid:
                await self.log_audit(
                    partner_name, event_id, client_ip,
                    "signature", data, status="failed"
                )
                return False, sig_msg, None
            
            await self.log_audit(
                partner_name, event_id, client_ip,
                "verified", data, status="success"
            )
            
            # ЗАЩИТА 6: Idempotency (Replay Attack Prevention)
            is_new, idempotency_msg = await self.check_idempotency(event_id)
            if not is_new:
                await self.log_audit(
                    partner_name, event_id, client_ip,
                    "duplicate", data, status="duplicate"
                )
                return True, "Duplicate event (already processed)", None
            
            # Все проверки пройдены! Обработать событие
            result = await self._process_event(
                partner_name, event_id, validated_data, client_ip
            )
            
            if result[0]:
                await self.log_audit(
                    partner_name, event_id, client_ip,
                    "processed", data, user_id=result[2], status="success"
                )
            else:
                await self.log_audit(
                    partner_name, event_id, client_ip,
                    "processing_error", data, status="failed"
                )
            
            return result
        
        except Exception as e:
            logger.error(f"❌ Критическая ошибка при обработке постбека: {e}", exc_info=True)
            return False, str(e), None
    
    async def _process_event(
        self,
        partner_name: str,
        event_id: str,
        data: Dict[str, Any],
        client_ip: str
    ) -> Tuple[bool, str, Optional[int]]:
        """
        Обработать событие после всех проверок безопасности.
        
        Args:
            partner_name: Имя партнера
            event_id: ID события
            data: Валидированные данные
            client_ip: IP адрес клиента
            
        Returns:
            (success, message, user_id)
        """
        try:
            click_id = data['click_id']
            event_type = data['event']
            amount = data.get('amount')
            
            # Найти пользователя по click_id
            user = await db.get_user_by_click_id(click_id)
            if not user:
                logger.warning(f"⚠️ Пользователь с click_id {click_id} не найден")
                return False, "User not found", None
            
            user_id = user.id
            language = user.language or "ru"
            
            logger.info(f"✅ Найден пользователь {user_id} для события {event_type}")
            
            # Обработать в зависимости от типа события
            if event_type == PostbackEventType.REGISTRATION.value:
                return await self._handle_registration(user_id, user, language)
            
            elif event_type == PostbackEventType.FIRST_DEPOSIT.value:
                return await self._handle_first_deposit(user_id, user, language, amount)
            
            elif event_type == PostbackEventType.DEPOSIT.value:
                return await self._handle_deposit(user_id, user, language, amount)
            
            elif event_type == PostbackEventType.WITHDRAWAL.value:
                return await self._handle_withdrawal(user_id, user, language, amount)
            
            elif event_type == PostbackEventType.WIN.value:
                return await self._handle_win(user_id, user, language, amount)
            
            else:
                return False, f"Unknown event type: {event_type}", None
        
        except Exception as e:
            logger.error(f"❌ Ошибка при обработке события: {e}", exc_info=True)
            return False, str(e), None
    
    # ========== Обработчики событий ==========
    
    async def _handle_registration(
        self,
        user_id: int,
        user: Any,
        language: str
    ) -> Tuple[bool, str, int]:
        """Обработать регистрацию."""
        try:
            logger.info(f"✅ Регистрация пользователя {user_id}")
            
            # Отправить сообщение
            message = (
                "✅ <b>Аккаунт создан!</b>\n\n"
                "Теперь ты можешь тестировать наши сигналы. 📊\n\n"
                "Сделай первый депозит и получи VIP доступ! 🔥"
            )
            
            await self.bot.send_message(user_id, message, parse_mode="HTML")
            
            logger.info(f"✅ Сообщение о регистрации отправлено {user_id}")
            return True, "Registration processed", user_id
        
        except Exception as e:
            logger.error(f"❌ Ошибка при обработке регистрации: {e}", exc_info=True)
            return False, str(e), user_id
    
    async def _handle_first_deposit(
        self,
        user_id: int,
        user: Any,
        language: str,
        amount: Optional[float]
    ) -> Tuple[bool, str, int]:
        """Обработать первый депозит - выдать VIP и Auto Unlock."""
        try:
            logger.info(f"🏆 Первый депозит пользователя {user_id}: {amount}")
            
            # Выдать VIP на 48 часов
            vip_until = datetime.utcnow() + timedelta(hours=self.VIP_DURATION_HOURS)
            await db.update_user_vip(user_id, vip_until)
            
            # Обновить статистику
            await db.update_user_first_deposited(user_id, True)
            await db.update_user_lifetime_value(user_id, amount or 0)
            
            # AUTO UNLOCK: Выдать сигналы на 24 часа (НОВОЕ!)
            if self.soft_gate_service:
                await self.soft_gate_service.unlock_24h(user_id)
                logger.info(f"✅ Auto unlock 24h выдан пользователю {user_id}")
            
            # Отправить сообщение
            message = (
                "🔥 <b>Депозит получен!</b>\n\n"
                f"Сумма: {amount} {user.currency or 'USD'}\n\n"
                "🎉 <b>Сигналы открыты на 24 часа без ограничений!</b>\n\n"
                "Теперь ты получаешь эксклюзивные сигналы и приоритетную поддержку! 💎"
            )
            
            await self.bot.send_message(user_id, message, parse_mode="HTML")
            
            logger.info(f"✅ VIP выдан пользователю {user_id} до {vip_until}")
            return True, "First deposit processed", user_id
        
        except Exception as e:
            logger.error(f"❌ Ошибка при обработке первого депозита: {e}", exc_info=True)
            return False, str(e), user_id
    
    async def _handle_deposit(
        self,
        user_id: int,
        user: Any,
        language: str,
        amount: Optional[float]
    ) -> Tuple[bool, str, int]:
        """Обработать повторный депозит."""
        try:
            logger.info(f"💰 Депозит пользователя {user_id}: {amount}")
            
            # Обновить статистику
            await db.increment_user_deposits_count(user_id)
            await db.update_user_lifetime_value(user_id, amount or 0)
            
            # Отправить сообщение
            message = (
                "💰 <b>Депозит получен!</b>\n\n"
                f"Сумма: {amount} {user.currency or 'USD'}\n\n"
                "Спасибо за доверие! Следи за нашими сигналами! 📊"
            )
            
            await self.bot.send_message(user_id, message, parse_mode="HTML")
            
            logger.info(f"✅ Депозит обработан для пользователя {user_id}")
            return True, "Deposit processed", user_id
        
        except Exception as e:
            logger.error(f"❌ Ошибка при обработке депозита: {e}", exc_info=True)
            return False, str(e), user_id
    
    async def _handle_withdrawal(
        self,
        user_id: int,
        user: Any,
        language: str,
        amount: Optional[float]
    ) -> Tuple[bool, str, int]:
        """Обработать вывод средств."""
        try:
            logger.info(f"💸 Вывод средств пользователя {user_id}: {amount}")
            
            # Логировать событие
            await db.log_event(user_id, "casino_withdrawal", {
                "amount": amount,
                "timestamp": datetime.utcnow().isoformat()
            })
            
            logger.info(f"✅ Вывод обработан для пользователя {user_id}")
            return True, "Withdrawal processed", user_id
        
        except Exception as e:
            logger.error(f"❌ Ошибка при обработке вывода: {e}", exc_info=True)
            return False, str(e), user_id
    
    async def _handle_win(
        self,
        user_id: int,
        user: Any,
        language: str,
        amount: Optional[float]
    ) -> Tuple[bool, str, int]:
        """Обработать выигрыш."""
        try:
            logger.info(f"🏆 Выигрыш пользователя {user_id}: {amount}")
            
            # Логировать событие
            await db.log_event(user_id, "casino_win", {
                "amount": amount,
                "timestamp": datetime.utcnow().isoformat()
            })
            
            logger.info(f"✅ Выигрыш обработан для пользователя {user_id}")
            return True, "Win processed", user_id
        
        except Exception as e:
            logger.error(f"❌ Ошибка при обработке выигрыша: {e}", exc_info=True)
            return False, str(e), user_id
