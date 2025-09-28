"""
Настройка логирования для приложения
"""
import logging
import os
from logging.handlers import RotatingFileHandler
from datetime import datetime

from ..config import config


def setup_logging():
    """Настройка системы логирования"""
    
    # Создаем директорию для логов если её нет
    log_dir = os.path.dirname(config.LOG_FILE)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Настраиваем основной логгер
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, config.LOG_LEVEL))
    
    # Очищаем существующие handlers
    logger.handlers.clear()
    
    # Формат логов
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Handler для файла с ротацией
    if config.LOG_FILE:
        file_handler = RotatingFileHandler(
            config.LOG_FILE,
            maxBytes=10*1024*1024,  # 10 MB
            backupCount=5
        )
        file_handler.setLevel(getattr(logging, config.LOG_LEVEL))
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    # Handler для консоли
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Настройка логгеров для внешних библиотек
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
    logging.getLogger('aiogram').setLevel(logging.INFO)
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    
    logger.info("Система логирования инициализирована")


def get_logger(name: str = None) -> logging.Logger:
    """Получение логгера с указанным именем"""
    return logging.getLogger(name)