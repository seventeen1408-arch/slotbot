"""
Обработчик сигналов.
"""

from aiogram import Router, types
from aiogram.filters import Command

from app.core.logger import get_logger
from app.database.db import db

from app.services.soft_gate_service import SoftGateService
from app.services.retention_service import RetentionService

logger = get_logger(__name__)

router = Router()


@router.message(Command("signals"))
async def signals_command(
    message: types.Message,
    soft_gate_service: SoftGateService,
    retention_service: RetentionService
) -> None:
    """Обработчик команды /signals."""
    try:
        user_id = message.from_user.id
        
        # Получить пользователя из БД
        user = await db.get_user(user_id)
        if not user:
            await message.answer("❌ Пользователь не найден")
            return
        
        # Обновить время активности
        await db.update_last_active(user_id)
        
        # Проверить подписку перед доступом к сигналам
        is_allowed, error_message = await retention_service.check_before_signals(user_id, user)
        if not is_allowed:
            # Показать Goodbye Screen
            await retention_service.show_goodbye_screen(user_id, user, "signals")
            return
        
        # Проверить, разблокированы ли сигналы
        if user.signals_unlocked:
            # Сигналы разблокированы
            text = (
                "📊 <b>Сигналы</b>\n\n"
                "🎮 Игры:\n"
                "1️⃣ Мины\n"
                "2️⃣ Черепа\n"
                "3️⃣ Пенальти\n\n"
                "Выберите игру для получения сигнала."
            )
            
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🎮 Мины", callback_data="signal_mines")],
                [InlineKeyboardButton(text="💀 Черепа", callback_data="signal_skulls")],
                [InlineKeyboardButton(text="⚽ Пенальти", callback_data="signal_penalties")],
            ])
            
            await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        else:
            # Сигналы заблокированы
            await soft_gate_service.send_gate_locked_message(user_id)
    
    except Exception as e:
        logger.error(f"❌ Ошибка в обработчике /signals: {e}", exc_info=True)
        await message.answer("❌ Произошла ошибка. Попробуйте позже.")


@router.callback_query(lambda c: c.data == "open_casino")
async def open_casino_callback(
    callback_query: types.CallbackQuery,
    soft_gate_service: SoftGateService
) -> None:
    """Обработчик открытия казино."""
    try:
        user_id = callback_query.from_user.id
        
        # Обработать клик на казино
        unlock_after = await soft_gate_service.handle_casino_click(user_id)
        
        if unlock_after > 0:
            # Отправить сообщение о таймере
            from datetime import datetime
            unlock_time = datetime.fromtimestamp(unlock_after).strftime("%H:%M:%S")
            
            text = (
                f"⏱️ <b>Таймер запущен</b>\n\n"
                f"Сигналы будут доступны в {unlock_time}\n\n"
                f"Перейдите в казино и сделайте ставку!"
            )
            
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🎰 Перейти в казино", url="https://1win.com")],
            ])
            
            await callback_query.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
            await callback_query.answer("✅ Таймер запущен!", show_alert=False)
        else:
            await callback_query.answer("❌ Произошла ошибка", show_alert=True)
    
    except Exception as e:
        logger.error(f"❌ Ошибка в обработчике открытия казино: {e}", exc_info=True)
        await callback_query.answer("❌ Произошла ошибка", show_alert=True)


@router.callback_query(lambda c: c.data.startswith("signal_"))
async def signal_callback(callback_query: types.CallbackQuery) -> None:
    """Обработчик выбора сигнала."""
    try:
        user_id = callback_query.from_user.id
        signal_type = callback_query.data.replace("signal_", "")
        
        # Логировать событие
        await db.log_event(user_id, "signal_requested", {"signal_type": signal_type})
        
        # Отправить сигнал
        signals = {
            "mines": "🎮 <b>Мины</b>\n\n💡 Рекомендация: Выбрать 2 клетки\n💰 Коэффициент: 1.5x",
            "skulls": "💀 <b>Черепа</b>\n\n💡 Рекомендация: Ставить на красное\n💰 Коэффициент: 2x",
            "penalties": "⚽ <b>Пенальти</b>\n\n💡 Рекомендация: Угадать сторону\n💰 Коэффициент: 1.8x",
        }
        
        text = signals.get(signal_type, "❌ Неизвестный сигнал")
        
        await callback_query.message.edit_text(text, parse_mode="HTML")
        await callback_query.answer("✅ Сигнал отправлен!", show_alert=False)
    
    except Exception as e:
        logger.error(f"❌ Ошибка в обработчике сигнала: {e}", exc_info=True)
        await callback_query.answer("❌ Произошла ошибка", show_alert=True)
