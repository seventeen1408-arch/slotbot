"""
Обработчик команды /start.
"""

from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

router = Router()


@router.message(Command("start"))
async def start_command(message: types.Message, state: FSMContext) -> None:
    """
    Обработчик команды /start.
    
    Отправляет приветственное сообщение пользователю.
    """
    try:
        welcome_text = (
            "🎰 **Добро пожаловать в SlotSignalsBot!**\n\n"
            "Я помогу вам получать сигналы для игры в слоты.\n\n"
            "Команды:\n"
            "/signals - Получить сигналы\n"
            "/vip - Информация о VIP подписке\n"
            "/help - Справка\n"
        )
        
        await message.answer(welcome_text, parse_mode="Markdown")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")


@router.message(Command("help"))
async def help_command(message: types.Message) -> None:
    """Обработчик команды /help."""
    try:
        help_text = (
            "📖 **Справка по командам:**\n\n"
            "/start - Главное меню\n"
            "/signals - Получить сигналы\n"
            "/vip - VIP подписка\n"
            "/help - Эта справка\n"
        )
        
        await message.answer(help_text, parse_mode="Markdown")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
