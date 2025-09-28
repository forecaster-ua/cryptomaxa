"""
Подключение к базе данных
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
import logging

from ..config import config
from .models import Base

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Менеджер подключения к базе данных"""
    
    def __init__(self):
        self.engine = None
        self.SessionLocal = None
        
    def init_connection(self):
        """Инициализация подключения к БД"""
        try:
            self.engine = create_engine(
                config.DATABASE_URL,
                echo=False,  # Установить True для отладки SQL запросов
                pool_pre_ping=True,
                pool_recycle=3600
            )
            self.SessionLocal = sessionmaker(
                autocommit=False, 
                autoflush=False, 
                bind=self.engine
            )
            logger.info("Подключение к базе данных установлено")
            return True
        except Exception as e:
            logger.error(f"Ошибка подключения к БД: {e}")
            return False
    
    def create_tables(self):
        """Создание таблиц в базе данных"""
        try:
            Base.metadata.create_all(bind=self.engine)
            logger.info("Таблицы успешно созданы")
            return True
        except Exception as e:
            logger.error(f"Ошибка создания таблиц: {e}")
            return False
    
    def get_session(self) -> Session:
        """Получение сессии для работы с БД"""
        if not self.SessionLocal:
            raise RuntimeError("База данных не инициализирована")
        return self.SessionLocal()
    
    @contextmanager
    def session_scope(self):
        """Контекстный менеджер для безопасной работы с сессией"""
        session = self.get_session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Ошибка при работе с БД: {e}")
            raise
        finally:
            session.close()

# Глобальный экземпляр менеджера БД
db_manager = DatabaseManager()

def get_db_session():
    """Функция для получения сессии БД (совместимость с новым кодом)"""
    return db_manager.session_scope()