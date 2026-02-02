"""
Webhook обработчик для постбеков от 1Win.
Endpoint для приема S2S событий от казино.
"""

from typing import Dict, Any
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import JSONResponse

from app.core.logger import get_logger
from app.core.config import config
from app.services.postback_handler import PostbackHandler, PostbackEvent

logger = get_logger(__name__)

router = APIRouter(prefix="/postback", tags=["postback"])


async def get_postback_handler(request: Request) -> PostbackHandler:
    """Получить PostbackHandler из контекста приложения."""
    try:
        return request.app.state.postback_handler
    except AttributeError:
        logger.error("❌ PostbackHandler не инициализирован")
        raise HTTPException(status_code=500, detail="PostbackHandler not initialized")


@router.post("/1win")
async def handle_1win_postback(
    request: Request,
    postback_handler: PostbackHandler = Depends(get_postback_handler)
) -> Dict[str, Any]:
    """
    Webhook endpoint для постбеков от 1Win.
    
    Поддерживаемые события:
    - registration: Регистрация пользователя
    - deposit: Депозит пользователя
    - withdrawal: Вывод средств
    - win: Выигрыш
    
    Примеры URL:
    - https://your-bot.com/postback/1win?user_id=123&event=registration
    - https://your-bot.com/postback/1win?user_id=123&event=deposit&amount=1000
    - https://your-bot.com/postback/1win?user_id=123&event=withdrawal&amount=500
    - https://your-bot.com/postback/1win?user_id=123&event=win&amount=250
    """
    try:
        # Получить данные из query параметров
        query_params = dict(request.query_params)
        
        # Получить данные из тела запроса (если есть)
        try:
            body_data = await request.json()
            data = {**query_params, **body_data}
        except:
            data = query_params
        
        logger.info(f"📨 Получен постбек: {data}")
        
        # Проверить обязательные параметры
        user_id = data.get("user_id") or data.get("userId")
        event_type = data.get("event") or data.get("type")
        
        if not user_id:
            logger.warning("⚠️ user_id не найден в постбеке")
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "user_id is required"}
            )
        
        if not event_type:
            logger.warning("⚠️ event type не найден в постбеке")
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "event type is required"}
            )
        
        # Проверить подпись (если включена)
        signature = data.get("signature")
        if signature and not postback_handler.verify_signature(data, signature):
            logger.warning(f"❌ Неверная подпись для постбека от {user_id}")
            return JSONResponse(
                status_code=403,
                content={"success": False, "error": "Invalid signature"}
            )
        
        # Парсить данные постбека
        postback_event = PostbackHandler.parse_postback_data(data)
        if not postback_event:
            logger.warning(f"⚠️ Не удалось парсить постбек: {data}")
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "Invalid postback data"}
            )
        
        # Обработать постбек
        success, message = await postback_handler.handle_postback(postback_event)
        
        if success:
            logger.info(f"✅ Постбек обработан: {event_type} для {user_id}")
            return JSONResponse(
                status_code=200,
                content={"success": True, "message": message}
            )
        else:
            logger.error(f"❌ Ошибка при обработке постбека: {message}")
            return JSONResponse(
                status_code=500,
                content={"success": False, "error": message}
            )
    
    except Exception as e:
        logger.error(f"❌ Ошибка в webhook обработчике: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )


@router.get("/health")
async def postback_health() -> Dict[str, str]:
    """Проверка здоровья webhook endpoint."""
    return {"status": "ok", "service": "postback"}


@router.post("/test")
async def test_postback(
    request: Request,
    postback_handler: PostbackHandler = Depends(get_postback_handler)
) -> Dict[str, Any]:
    """
    Тестовый endpoint для проверки постбеков.
    
    Пример:
    curl -X POST "http://localhost:3000/postback/test?user_id=123&event=registration"
    """
    try:
        query_params = dict(request.query_params)
        logger.info(f"🧪 Тестовый постбек: {query_params}")
        
        # Парсить данные
        postback_event = PostbackHandler.parse_postback_data(query_params)
        if not postback_event:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "Invalid test data"}
            )
        
        # Обработать
        success, message = await postback_handler.handle_postback(postback_event)
        
        return JSONResponse(
            status_code=200,
            content={
                "success": success,
                "message": message,
                "event": {
                    "type": postback_event.event_type,
                    "user_id": postback_event.user_id,
                    "amount": postback_event.amount
                }
            }
        )
    
    except Exception as e:
        logger.error(f"❌ Ошибка в тестовом endpoint: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )
