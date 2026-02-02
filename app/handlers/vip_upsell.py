"""
VIP Upsell Handler - кнопки и логика после истечения free access.

Функции:
- Обработка кнопок [Купить VIP] [Играть в казино] [Завтра снова]
- Создание счета для VIP
- Отправка ссылки на казино
- Логирование действий
"""

from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters.callback_data import CallbackData

from app.core.logger import get_logger
from app.database.db import db


logger = get_logger(__name__)
router = Router()


class VipUpsellCallback(CallbackData, prefix="vip_upsell"):
    """Callback для VIP Upsell кнопок."""
    action: str  # "buy_vip", "play_casino", "tomorrow"


@router.callback_query(VipUpsellCallback.filter(F.action == "buy_vip"))
async def handle_buy_vip(callback: CallbackQuery, callback_data: VipUpsellCallback, bot: Bot):
    """
    Обработать кнопку [💎 Купить VIP].
    """
    try:
        user_id = callback.from_user.id
        logger.info(f"🎯 Пользователь {user_id} нажал 'Купить VIP'")
        
        # Получить информацию о пользователе
        user = await db.get_user(user_id)
        if not user:
            await callback.answer("❌ User not found", show_alert=True)
            return
        
        # Создать счет для VIP (если есть VIP сервис)
        # Это должно быть реализовано в вашем VIP сервисе
        message = (
            "💎 <b>VIP Подписка</b>\n\n"
            "Получи неограниченный доступ к сигналам!\n\n"
            "✅ Эксклюзивные сигналы\n"
            "✅ Приоритетная поддержка\n"
            "✅ Без ограничений по времени\n\n"
            "Стоимость: $9.99/месяц\n\n"
            "Нажми кнопку ниже для оплаты:"
        )
        
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(
                    text="💳 Оплатить",
                    callback_data="vip_payment"  # Должно быть реализовано в VIP сервисе
                )],
                [InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data=VipUpsellCallback(action="tomorrow").pack()
                )]
            ]
        )
        
        await callback.message.edit_text(message, reply_markup=keyboard, parse_mode="HTML")
        await callback.answer()
        
        logger.info(f"✅ VIP предложение отправлено пользователю {user_id}")
    
    except Exception as e:
        logger.error(f"❌ Ошибка при обработке VIP покупки: {e}", exc_info=True)
        await callback.answer("❌ An error occurred", show_alert=True)


@router.callback_query(VipUpsellCallback.filter(F.action == "play_casino"))
async def handle_play_casino(callback: CallbackQuery, callback_data: VipUpsellCallback, bot: Bot):
    """
    Обработать кнопку [🎰 Играть в казино].
    """
    try:
        user_id = callback.from_user.id
        logger.info(f"🎮 Пользователь {user_id} нажал 'Играть в казино'")
        
        # Получить ссылку на казино
        user = await db.get_user(user_id)
        if not user:
            await callback.answer("❌ User not found", show_alert=True)
            return
        
        # Получить click_id для отслеживания
        click_id = user.get("click_id")
        
        # Формировать ссылку (пример для 1Win)
        casino_url = "https://1win.com"
        if click_id:
            casino_url += f"?subid={click_id}"
        
        message = (
            "🎰 <b>Переходи в казино!</b>\n\n"
            "Нажми кнопку ниже:"
        )
        
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(
                    text="🎰 Открыть казино",
                    url=casino_url
                )],
                [InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data=VipUpsellCallback(action="tomorrow").pack()
                )]
            ]
        )
        
        await callback.message.edit_text(message, reply_markup=keyboard, parse_mode="HTML")
        await callback.answer()
        
        logger.info(f"✅ Ссылка на казино отправлена пользователю {user_id}")
    
    except Exception as e:
        logger.error(f"❌ Ошибка при обработке казино ссылки: {e}", exc_info=True)
        await callback.answer("❌ An error occurred", show_alert=True)


@router.callback_query(VipUpsellCallback.filter(F.action == "tomorrow"))
async def handle_tomorrow(callback: CallbackQuery, callback_data: VipUpsellCallback, bot: Bot):
    """
    Обработать кнопку [⏳ Завтра снова].
    """
    try:
        user_id = callback.from_user.id
        logger.info(f"⏳ Пользователь {user_id} выбрал 'Завтра снова'")
        
        message = (
            "⏳ <b>До встречи завтра!</b>\n\n"
            "Завтра ты сможешь использовать бесплатный доступ снова.\n\n"
            "💡 Совет: Купи VIP и получи неограниченный доступ! 💎"
        )
        
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(
                    text="💎 Купить VIP",
                    callback_data=VipUpsellCallback(action="buy_vip").pack()
                )],
                [InlineKeyboardButton(
                    text="❌ Закрыть",
                    callback_data="close"
                )]
            ]
        )
        
        await callback.message.edit_text(message, reply_markup=keyboard, parse_mode="HTML")
        await callback.answer()
        
        logger.info(f"✅ Сообщение 'Завтра' отправлено пользователю {user_id}")
    
    except Exception as e:
        logger.error(f"❌ Ошибка при обработке 'Завтра': {e}", exc_info=True)
        await callback.answer("❌ An error occurred", show_alert=True)


# Глобальная функция для отправки VIP Upsell сообщения
async def send_vip_upsell_message(bot: Bot, user_id: int) -> None:
    """
    Отправить VIP Upsell сообщение с кнопками.
    """
    try:
        message = (
            "🔥 <b>Бесплатное время закончилось</b>\n\n"
            "⏳ Завтра откроется снова\n\n"
            "💎 Или купи VIP без ограничений!"
        )
        
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(
                    text="💎 Купить VIP",
                    callback_data=VipUpsellCallback(action="buy_vip").pack()
                )],
                [InlineKeyboardButton(
                    text="🎰 Играть в казино",
                    callback_data=VipUpsellCallback(action="play_casino").pack()
                )],
                [InlineKeyboardButton(
                    text="⏳ Завтра снова",
                    callback_data=VipUpsellCallback(action="tomorrow").pack()
                )]
            ]
        )
        
        await bot.send_message(
            user_id,
            message,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
        logger.info(f"✅ VIP Upsell сообщение отправлено пользователю {user_id}")
    
    except Exception as e:
        logger.error(f"❌ Ошибка при отправке VIP Upsell сообщения: {e}", exc_info=True)
