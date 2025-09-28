"""
Конфигурация приложения
"""
import os
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

class Config:
    """Основные настройки приложения"""
    
    # База данных
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = int(os.getenv('DB_PORT', 5432))
    DB_NAME = os.getenv('DB_NAME', 'hydra_signals')
    DB_USER = os.getenv('DB_USER', 'hydra_user')
    DB_PASSWORD = os.getenv('DB_PASSWORD', '')
    
    # Формируем строку подключения к БД
    DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    
    # API настройки
    API_BASE_URL = os.getenv('API_BASE_URL', 'http://194.135.94.212:8001')
    API_TIMEOUT = int(os.getenv('API_TIMEOUT', 30))
    
    # Telegram Bot
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
    TELEGRAM_ADMIN_ID = os.getenv('TELEGRAM_ADMIN_ID', '')
    
    # Планировщик
    FETCH_INTERVAL_MINUTES = int(os.getenv('FETCH_INTERVAL_MINUTES', 15))
    
    # Логирование
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = os.getenv('LOG_FILE', 'logs/app.log')
    
    # Таймфреймы для запросов к API
    TIMEFRAMES = ['15m', '1h', '4h', '1d']
    
    # Путь к файлу с тикерами
    TICKERS_FILE = 'tickers.txt'

config = Config()