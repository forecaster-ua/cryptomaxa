"""
Telegram Bot Configuration and Setup
"""
import os
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from .handlers import register_handlers
from .middleware import RateLimitMiddleware, LoggingMiddleware

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Глобальный экземпляр бота для уведомлений
bot = None

def get_bot() -> Bot:
    """Получить глобальный экземпляр бота"""
    global bot
    if bot is None:
        bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        if not bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN не найден в переменных окружения")
        
        bot = Bot(
            token=bot_token,
            default=DefaultBotProperties(
                parse_mode=ParseMode.HTML
            )
        )
        logger.info("Создан глобальный экземпляр бота для уведомлений")
    
    return bot

def create_bot() -> tuple[Bot, Dispatcher]:
    """Создание и настройка бота"""
    
    # Токен бота
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not bot_token:
        raise ValueError("TELEGRAM_BOT_TOKEN не найден в переменных окружения")
    
    # Создание бота с HTML parse_mode по умолчанию
    bot = Bot(
        token=bot_token,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML
        )
    )
    
    # Создание диспетчера
    dp = Dispatcher(storage=MemoryStorage())
    
    # Подключение middleware
    dp.message.middleware(LoggingMiddleware())
    dp.message.middleware(RateLimitMiddleware())
    
    # Регистрация обработчиков
    register_handlers(dp)
    
    logger.info("Бот создан и настроен")
    return bot, dp

async def start_bot():
    """Запуск бота"""
    bot, dp = create_bot()
    
    try:
        # Получение информации о боте
        bot_info = await bot.get_me()
        logger.info(f"Бот @{bot_info.username} запущен")
        
        # Удаление webhook (если был установлен)
        await bot.delete_webhook(drop_pending_updates=True)
        
        # Запуск поллинга
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
        raise
    finally:
        await bot.session.close()