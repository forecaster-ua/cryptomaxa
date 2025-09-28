"""
Миграция базы данных для добавления поля frequency в subscriptions
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import get_db_session, db_manager
from sqlalchemy import text

def migrate_subscriptions_table():
    """Добавить поле frequency в таблицу subscriptions"""
    
    # Инициализируем подключение к БД
    if not db_manager.init_connection():
        print("Ошибка подключения к базе данных")
        return
    
    with get_db_session() as session:
        try:
            # Проверяем, есть ли уже поле frequency
            result = session.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'subscriptions' 
                AND column_name = 'frequency'
            """))
            
            if result.fetchone():
                print("Поле frequency уже существует в таблице subscriptions")
                return
            
            # Добавляем поле frequency
            session.execute(text("""
                ALTER TABLE subscriptions 
                ADD COLUMN frequency VARCHAR(10) DEFAULT '15m' 
                CHECK (frequency IN ('15m', '1h'))
            """))
            
            # Добавляем поле created_at если его нет
            result = session.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'subscriptions' 
                AND column_name = 'created_at'
            """))
            
            if not result.fetchone():
                session.execute(text("""
                    ALTER TABLE subscriptions 
                    ADD COLUMN created_at TIMESTAMP DEFAULT NOW()
                """))
                print("Добавлено поле created_at в таблицу subscriptions")
            
            session.commit()
            print("Миграция успешно выполнена: добавлено поле frequency")
            
        except Exception as e:
            session.rollback()
            print(f"Ошибка миграции: {e}")
            raise

if __name__ == '__main__':
    migrate_subscriptions_table()