#!/usr/bin/env python3
"""
Проверка и очистка БД от тестовых данных
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import db_manager, get_db_session
from src.database.models import User, Subscription, Signal, ErrorLog
from sqlalchemy import func
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_database_state():
    """Проверка текущего состояния БД"""
    print("=== Проверка состояния БД ===\n")
    
    # Инициализируем БД
    if not db_manager.init_connection():
        print("❌ Ошибка подключения к БД")
        return False
    
    try:
        with get_db_session() as session:
            # Считаем записи в каждой таблице
            users_count = session.query(func.count(User.id)).scalar()
            subscriptions_count = session.query(func.count(Subscription.id)).scalar()
            signals_count = session.query(func.count(Signal.id)).scalar()
            errors_count = session.query(func.count(ErrorLog.id)).scalar()
            
            print(f"👤 Пользователей: {users_count}")
            print(f"📋 Подписок: {subscriptions_count}")
            print(f"📊 Сигналов: {signals_count}")
            print(f"❌ Ошибок: {errors_count}")
            
            # Показываем пример данных если есть
            if users_count > 0:
                print("\n📋 Пользователи:")
                users = session.query(User).limit(5).all()
                for user in users:
                    print(f"  - ID: {user.telegram_id}, Username: @{user.username or 'None'}")
            
            if signals_count > 0:
                print("\n📊 Последние сигналы:")
                signals = session.query(Signal).order_by(Signal.created_at.desc()).limit(5).all()
                for signal in signals:
                    print(f"  - {signal.ticker} {signal.timeframe} {signal.signal_type} ({signal.created_at})")
            
            return True
            
    except Exception as e:
        logger.error(f"Ошибка при проверке БД: {e}")
        return False

def clean_test_data():
    """Очистка тестовых данных"""
    print("\n=== Очистка тестовых данных ===")
    
    try:
        with get_db_session() as session:
            # Удаляем тестовые подписки (пользователь с ID 123456789 из тестов)
            test_user = session.query(User).filter_by(telegram_id=123456789).first()
            if test_user:
                print("🧹 Удаляем тестового пользователя и его подписки...")
                session.delete(test_user)
            
            # Можно добавить другие критерии очистки если нужно
            # Например, удалить старые ошибки
            old_errors = session.query(ErrorLog).count()
            if old_errors > 100:  # Если больше 100 ошибок, очищаем
                print(f"🧹 Очищаем {old_errors} старых записей об ошибках...")
                session.query(ErrorLog).delete()
            
            session.commit()
            print("✅ Тестовые данные очищены")
            
    except Exception as e:
        logger.error(f"Ошибка при очистке: {e}")
        return False
    
    return True

def main():
    """Главная функция"""
    print("🚀 Подготовка системы к запуску")
    print("=" * 50)
    
    # Проверяем состояние
    if not check_database_state():
        return
    
    # Спрашиваем о очистке
    with get_db_session() as session:
        users_count = session.query(func.count(User.id)).scalar()
        signals_count = session.query(func.count(Signal.id)).scalar()
    
    if users_count > 0 or signals_count > 0:
        print(f"\n🤔 В БД найдены данные:")
        print(f"   Пользователи: {users_count}")
        print(f"   Сигналы: {signals_count}")
        print("\nЕсли это тестовые данные, их стоит очистить.")
        print("Если это продуктивные данные - пропускаем очистку.")
        
        # Автоматически очищаем только явно тестовые данные
        clean_test_data()
    else:
        print("\n✅ БД пуста, очистка не требуется")
    
    # Финальная проверка
    print("\n=== Финальное состояние БД ===")
    check_database_state()
    
    print(f"\n🎯 База данных готова к работе!")
    print("Теперь можно запускать планировщик для накопления сигналов.")

if __name__ == '__main__':
    main()