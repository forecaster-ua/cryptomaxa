#!/usr/bin/env python3
"""
Миграция для добавления полей correction сигналов
"""
import sys
import os
sys.path.append('/home/hydrabot/hydrabot-fetcher')

from sqlalchemy import text
from src.database.connection import db_manager

def add_correction_fields():
    """Добавляем поля для correction сигналов"""
    db_manager.init_connection()
    
    migration_sql = """
    -- Добавляем новые поля для correction сигналов
    ALTER TABLE signals 
    ADD COLUMN IF NOT EXISTS is_main_signal BOOLEAN DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS correction_type VARCHAR(10),
    ADD COLUMN IF NOT EXISTS correction_entry NUMERIC(18, 8),
    ADD COLUMN IF NOT EXISTS correction_tp NUMERIC(18, 8),
    ADD COLUMN IF NOT EXISTS correction_sl NUMERIC(18, 8),
    ADD COLUMN IF NOT EXISTS correction_confidence NUMERIC(5, 2);
    
    -- Устанавливаем значения по умолчанию для существующих записей
    UPDATE signals SET is_main_signal = TRUE WHERE is_main_signal IS NULL;
    """
    
    try:
        with db_manager.get_session() as session:
            # Выполняем миграцию
            session.execute(text(migration_sql))
            session.commit()
            print("✅ Миграция выполнена успешно - добавлены поля для correction сигналов")
            
            # Проверяем результат
            result = session.execute(text("SELECT COUNT(*) FROM signals WHERE is_main_signal = TRUE")).scalar()
            print(f"📊 Основных сигналов в БД: {result}")
            
    except Exception as e:
        print(f"❌ Ошибка миграции: {e}")
        return False
    
    return True

if __name__ == "__main__":
    print("🔧 Запуск миграции для correction сигналов...")
    success = add_correction_fields()
    if success:
        print("🎉 Миграция завершена успешно!")
    else:
        print("💥 Миграция не выполнена!")
        sys.exit(1)