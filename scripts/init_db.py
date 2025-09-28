#!/usr/bin/env python3
"""
Скрипт для инициализации базы данных
"""
import sys
import os

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.logger import setup_logging, get_logger
from src.database.connection import db_manager
from src.config import config

def init_database():
    """Инициализация базы данных"""
    setup_logging()
    logger = get_logger(__name__)
    
    logger.info("Начало инициализации базы данных...")
    
    # Проверяем настройки БД
    if not config.DB_PASSWORD:
        logger.error("Не указан пароль для базы данных в .env файле")
        return False
    
    # Инициализируем подключение
    if not db_manager.init_connection():
        logger.error("Не удалось установить соединение с базой данных")
        return False
    
    # Создаем таблицы
    if not db_manager.create_tables():
        logger.error("Не удалось создать таблицы")
        return False
    
    logger.info("База данных успешно инициализирована!")
    return True

if __name__ == "__main__":
    success = init_database()
    sys.exit(0 if success else 1)