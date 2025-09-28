#!/usr/bin/env python3
"""
Основной скрипт для запуска планировщика сигналов
"""
import sys
import os
import argparse
from datetime import datetime

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.logger import setup_logging, get_logger
from src.scheduler import SignalScheduler
from src.database.connection import db_manager

def force_stop_scheduler():
    """Принудительно останавливает планировщик через systemctl или PID"""
    import subprocess
    import psutil
    
    try:
        # Сначала пробуем остановить systemd сервис
        try:
            result = subprocess.run(['sudo', 'systemctl', 'is-active', 'hydra-scheduler'], 
                                  capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip() == 'active':
                print("🛑 Принудительная остановка systemd сервиса...")
                subprocess.run(['sudo', 'systemctl', 'kill', '--signal=SIGKILL', 'hydra-scheduler'], 
                             check=True)
                subprocess.run(['sudo', 'systemctl', 'reset-failed', 'hydra-scheduler'], 
                             check=False)  # Игнорируем ошибки
                print("✅ Systemd сервис принудительно остановлен")
                return True
        except subprocess.CalledProcessError:
            pass
        
        # Если systemd не помог, ищем процессы по имени
        processes_killed = 0
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.info['cmdline'] and any('run_scheduler.py' in cmd for cmd in proc.info['cmdline']):
                    print(f"🔥 Убиваем процесс планировщика PID: {proc.info['pid']}")
                    proc.kill()
                    processes_killed += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        if processes_killed > 0:
            print(f"✅ Убито {processes_killed} процесс(ов) планировщика")
            return True
        else:
            print("ℹ️  Процессы планировщика не найдены")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка принудительной остановки: {e}")
        return False

def main():
    """Основная функция запуска планировщика"""
    
    # Парсинг аргументов командной строки
    parser = argparse.ArgumentParser(description='Планировщик обработки торговых сигналов')
    parser.add_argument('--no-immediate', action='store_true', 
                       help='Не запускать первую обработку сразу')
    parser.add_argument('--manual', action='store_true',
                       help='Запустить обработку один раз и выйти')
    parser.add_argument('--status', action='store_true',
                       help='Показать статус и выйти')
    parser.add_argument('--force-stop', action='store_true',
                       help='Принудительно остановить работающий планировщик')
    
    args = parser.parse_args()
    
    # Инициализируем логирование
    setup_logging()
    logger = get_logger(__name__)
    
    logger.info("=" * 60)
    logger.info("🚀 HYDRA SIGNALS SCHEDULER")
    logger.info("=" * 60)
    from datetime import timezone
    logger.info(f"Время запуска: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
    
    # Проверяем подключение к БД
    if not db_manager.init_connection():
        logger.error("❌ Не удалось подключиться к базе данных")
        return 1
    
    logger.info("✅ Подключение к базе данных установлено")
    
    # Создаем планировщик
    scheduler = SignalScheduler()
    
    try:
        if args.force_stop:
            # Принудительная остановка
            logger.info("🚨 Принудительная остановка планировщика")
            print("🚨 Принудительная остановка планировщика...")
            result = force_stop_scheduler()
            if result:
                logger.info("✅ Планировщик принудительно остановлен")
                print("✅ Планировщик принудительно остановлен")
            else:
                logger.info("ℹ️  Планировщик не был запущен")
                print("ℹ️  Планировщик не был запущен")
            
        elif args.status:
            # Показываем статус
            status = scheduler.get_status()
            logger.info("📊 Статус планировщика:")
            logger.info(f"   Запущен: {status['is_running']}")
            logger.info(f"   Всего запусков: {status['total_runs']}")
            logger.info(f"   Успешных: {status['successful_runs']}")
            logger.info(f"   Неудачных: {status['failed_runs']}")
            if status['total_runs'] > 0:
                logger.info(f"   Процент успеха: {status['success_rate']:.1f}%")
            if status['last_run_time']:
                logger.info(f"   Последний запуск: {status['last_run_time']}")
            if status['next_run_time']:
                logger.info(f"   Следующий запуск: {status['next_run_time']}")
            
        elif args.manual:
            # Ручной запуск
            logger.info("🔧 Ручной запуск обработки сигналов")
            result = scheduler.run_manual()
            
            if result['success']:
                results = result['results']
                logger.info("✅ Ручная обработка завершена:")
                logger.info(f"   📊 Тикеров: {results.get('tickers_processed', 0)}")
                logger.info(f"   💾 Сохранено: {results.get('signals_saved', 0)}")
                logger.info(f"   🔄 Обновлено: {results.get('signals_updated', 0)}")
                logger.info(f"   🕐 Время: {results.get('processing_time', 0):.1f} сек")
                return 0
            else:
                logger.error(f"❌ Ошибка ручной обработки: {result['error']}")
                return 1
        
        else:
            # Обычный режим планировщика
            run_immediately = not args.no_immediate
            
            logger.info("⏰ Запуск планировщика в режиме демона")
            logger.info(f"   Первый запуск: {'сразу' if run_immediately else 'по расписанию'}")
            logger.info("   Для остановки нажмите Ctrl+C")
            
            # Запускаем планировщик
            scheduler.start(run_immediately=run_immediately)
            
        return 0
        
    except KeyboardInterrupt:
        logger.info("\n🛑 Получен сигнал прерывания")
        scheduler.stop()
        return 0
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        return 1
    
    finally:
        logger.info("👋 Работа планировщика завершена")
        logger.info("=" * 60)

if __name__ == "__main__":
    sys.exit(main())