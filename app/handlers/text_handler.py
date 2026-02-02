"""
Обработчик текстовых сообщений для AutoResponder и Retention.
Интегрирует AutoResponder и Retention Service.
"""

from aiogram import Router, types
from aiogram.filters import Command

from app.core.logger import get_logger
from app.database.db import db
from app.services.autoresponder_service import AutoResponderService
from app.services.retention_service import RetentionService

logger = get_logger(__name__)

router = Router()


@router.message()
async def handle_text_message(
    message: types.Message,
    autoresponder_service: AutoResponderService,
    retention_service: RetentionService
) -> None:
    """
    Обработчик всех текстовых сообщений.
    Использует AutoResponder для ответа на вопросы.
    """
    try:
        user_id = message.from_user.id
        message_text = message.text or ""
        
        # Пропустить пустые сообщения
        if not message_text.strip():
            return
        
        # Пропустить команды (они обрабатываются отдельно)
        if message_text.startswith("/"):
            return
        
        logger.debug(f"📝 Текстовое сообщение от {user_id}: {message_text[:50]}")
        
        # Получить пользователя из БД
        user = await db.get_user(user_id)
        if not user:
            logger.warning(f"⚠️ Пользователь {user_id} не найден в БД")
            return
        
        # Обновить время активности
        await db.update_last_active(user_id)
        
        # Обработать текст через AutoResponder
        response = await autoresponder_service.handle_text(user_id, user, message_text)
        
        if response:
            # Отправить ответ
            await message.answer(response, parse_mode="HTML")
            logger.info(f"✅ AutoResponder ответил пользователю {user_id}")
        else:
            logger.debug(f"⏭️ AutoResponder пропустил сообщение {user_id}")
    
    except Exception as e:
        logger.error(f"❌ Ошибка в обработчике текста для {message.from_user.id}: {e}", exc_info=True)


@router.callback_query(lambda c: c.data == "retention_check_subscription")
async def retention_check_subscription_callback(
    callback_query: types.CallbackQuery,
    retention_service: RetentionService
) -> None:
    """Обработчик кнопки 'Я подписался' в Goodbye Screen."""
    try:
        user_id = callback_query.from_user.id
        
        logger.info(f"🔄 Пользователь {user_id} нажал 'Я подписался'")
        
        # Получить пользователя из БД
        user = await db.get_user(user_id)
        if not user:
            await callback_query.answer("❌ Пользователь не найден", show_alert=True)
            return
        
        # Повторно проверить подписку
        is_subscribed = await retention_service.handle_subscription_check(user_id, user)
        
        if is_subscribed:
            # Удалить сообщение с Goodbye Screen
            try:
                await callback_query.message.delete()
            except Exception as e:
                logger.debug(f"⚠️ Не удалось удалить сообщение: {e}")
            
            await callback_query.answer("✅ Спасибо за подписку!", show_alert=False)
        else:
            await callback_query.answer("❌ Ты все еще не подписан на канал", show_alert=True)
    
    except Exception as e:
        logger.error(f"❌ Ошибка в retention_check_subscription для {callback_query.from_user.id}: {e}", exc_info=True)
        await callback_query.answer("❌ Произошла ошибка", show_alert=True)


@router.callback_query(lambda c: c.data == "retention_open_channel")
async def retention_open_channel_callback(
    callback_query: types.CallbackQuery,
    retention_service: RetentionService
) -> None:
    """Обработчик кнопки 'Открыть канал' в Goodbye Screen."""
    try:
        user_id = callback_query.from_user.id
        
        logger.info(f"🔗 Пользователь {user_id} нажал 'Открыть канал'")
        
        # Получить пользователя из БД
        user = await db.get_user(user_id)
        if not user:
            await callback_query.answer("❌ Пользователь не найден", show_alert=True)
            return
        
        # Обработать открытие канала
        await retention_service.handle_open_channel(user_id, user)
        
        await callback_query.answer("✅ Ссылка отправлена", show_alert=False)
    
    except Exception as e:
        logger.error(f"❌ Ошибка в retention_open_channel для {callback_query.from_user.id}: {e}", exc_info=True)
        await callback_query.answer("❌ Произошла ошибка", show_alert=True)
