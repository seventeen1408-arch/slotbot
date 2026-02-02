"""
FastAPI endpoints для PRO S2S постбек системы.

Routes:
- POST /api/postback/{partner_name} - основной endpoint
- GET /api/postback/health - проверка здоровья
- POST /api/postback/test - тестирование
"""

from fastapi import APIRouter, Request, HTTPException, Query
from typing import Dict, Any, Optional
from aiogram import Bot

from app.core.logger import get_logger
from app.services.postback_pro_service import PostbackProService

logger = get_logger(__name__)

# Инициализировать сервис (будет передан из main.py)
postback_service: Optional[PostbackProService] = None
bot: Optional[Bot] = None

router = APIRouter(prefix="/api/postback", tags=["postback"])


def init_postback_router(service: PostbackProService, telegram_bot: Bot):
    """Инициализировать router с сервисом."""
    global postback_service, bot
    postback_service = service
    bot = telegram_bot


@router.post("/{partner_name}")
async def handle_postback(
    partner_name: str,
    request: Request,
    data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Основной endpoint для приема постбеков от партнеров.
    
    Args:
        partner_name: Имя партнера (1win, stake, roobet и т.д.)
        request: Request объект
        data: Данные постбека
        
    Returns:
        JSON ответ с результатом обработки
    """
    try:
        if not postback_service:
            logger.error("❌ PostbackProService не инициализирован")
            raise HTTPException(status_code=500, detail="Service not initialized")
        
        # Получить IP адрес клиента
        client_ip = request.client.host if request.client else "unknown"
        
        logger.info(f"📨 Получен постбек от {partner_name} с IP {client_ip}")
        
        # Обработать постбек со всеми проверками безопасности
        success, message, result = await postback_service.handle_postback(
            partner_name=partner_name,
            data=data,
            client_ip=client_ip
        )
        
        if success:
            return {
                "status": "success",
                "message": message,
                "partner": partner_name,
            }
        else:
            logger.warning(f"⚠️ Ошибка при обработке постбека: {message}")
            raise HTTPException(status_code=400, detail=message)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check() -> Dict[str, str]:
    """
    Проверка здоровья сервиса.
    
    Returns:
        JSON с статусом
    """
    try:
        if not postback_service:
            return {"status": "error", "message": "Service not initialized"}
        
        return {
            "status": "healthy",
            "service": "PostbackProService",
            "version": "1.0.0"
        }
    
    except Exception as e:
        logger.error(f"❌ Ошибка при проверке здоровья: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


@router.post("/test")
async def test_postback(
    partner_name: str = Query("1win", description="Имя партнера"),
    event: str = Query("register", description="Тип события"),
    user_id: Optional[str] = Query(None, description="ID пользователя в казино"),
    click_id: Optional[str] = Query(None, description="Click ID"),
    amount: Optional[float] = Query(None, description="Сумма"),
    request: Request = None
) -> Dict[str, Any]:
    """
    Тестовый endpoint для проверки постбеков.
    
    Примеры:
    - /api/postback/test?partner_name=1win&event=register
    - /api/postback/test?partner_name=1win&event=first_deposit&amount=100
    - /api/postback/test?partner_name=1win&event=deposit&amount=50
    
    Args:
        partner_name: Имя партнера
        event: Тип события
        user_id: ID пользователя
        click_id: Click ID
        amount: Сумма
        request: Request объект
        
    Returns:
        JSON ответ
    """
    try:
        if not postback_service:
            raise HTTPException(status_code=500, detail="Service not initialized")
        
        # Для тестирования используем фиксированный click_id
        if not click_id:
            click_id = "550e8400-e29b-41d4-a716-446655440000"
        
        # Построить тестовые данные
        import time
        import uuid
        import hmac
        import hashlib
        
        test_data = {
            'click_id': click_id,
            'event': event,
            'timestamp': int(time.time()),
        }
        
        if amount is not None:
            test_data['amount'] = amount
        
        if user_id:
            test_data['user_id'] = user_id
        
        # Генерировать подпись (для тестирования)
        # В реальности подпись должна быть от партнера
        secret_key = "test-secret-key"  # Для тестирования
        sorted_data = sorted(test_data.items())
        data_string = "&".join([f"{k}={v}" for k, v in sorted_data])
        signature = hmac.new(
            secret_key.encode(),
            data_string.encode(),
            hashlib.sha256
        ).hexdigest()
        
        test_data['signature'] = signature
        
        client_ip = request.client.host if request and request.client else "127.0.0.1"
        
        logger.info(f"🧪 Тестовый постбек: {partner_name} - {event}")
        
        # Обработать
        success, message, result = await postback_service.handle_postback(
            partner_name=partner_name,
            data=test_data,
            client_ip=client_ip
        )
        
        return {
            "status": "success" if success else "failed",
            "message": message,
            "partner": partner_name,
            "event": event,
            "test_data": test_data,
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Ошибка при тестировании: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/audit")
async def get_audit_logs(
    partner_name: Optional[str] = Query(None, description="Фильтр по партнеру"),
    limit: int = Query(100, description="Максимум записей"),
    offset: int = Query(0, description="Смещение")
) -> Dict[str, Any]:
    """
    Получить логи аудита.
    
    Args:
        partner_name: Фильтр по партнеру
        limit: Максимум записей
        offset: Смещение
        
    Returns:
        JSON с логами
    """
    try:
        from app.database.db import db
        
        logs = await db.get_postback_audit_logs(
            partner_name=partner_name,
            limit=limit,
            offset=offset
        )
        
        return {
            "status": "success",
            "count": len(logs),
            "logs": logs
        }
    
    except Exception as e:
        logger.error(f"❌ Ошибка при получении логов: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_postback_stats(
    partner_name: Optional[str] = Query(None, description="Фильтр по партнеру"),
    days: int = Query(7, description="Количество дней")
) -> Dict[str, Any]:
    """
    Получить статистику постбеков.
    
    Args:
        partner_name: Фильтр по партнеру
        days: Количество дней
        
    Returns:
        JSON со статистикой
    """
    try:
        from app.database.db import db
        from datetime import datetime, timedelta
        
        since = datetime.utcnow() - timedelta(days=days)
        
        stats = await db.get_postback_stats(
            partner_name=partner_name,
            since=since
        )
        
        return {
            "status": "success",
            "period_days": days,
            "partner": partner_name or "all",
            "stats": stats
        }
    
    except Exception as e:
        logger.error(f"❌ Ошибка при получении статистики: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
