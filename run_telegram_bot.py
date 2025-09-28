#!/usr/bin/env python3
"""
Главный файл для запуска Telegram бота Hydra Static
"""
import asyncio
import logging
import sys
from pathlib import Path

# Добавляем src в путь для импортов
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.telegram_bot.bot import start_bot

def main():
    """Главная функция"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('logs/telegram_bot.log'),
            logging.StreamHandler()
        ]
    )
    
    logger = logging.getLogger(__name__)
    logger.info("Запуск Telegram бота Hydra Static")
    
    try:
        asyncio.run(start_bot())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()