"""
Планировщик задач для автоматической обработки сигналов
"""
import schedule
import time
import signal
import threading
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from ..utils.logger import get_logger
from ..signal_analyzer import SignalManager
from ..database.crud import ErrorLogCRUD
from ..database.connection import db_manager
from ..config import config

logger = get_logger(__name__)

class SignalScheduler:
    """Планировщик для автоматического запуска обработки сигналов"""
    
    def __init__(self):
        self.signal_manager = SignalManager()
        self.is_running = False
        self.shutdown_requested = False
        self.current_job = None
        self.job_thread = None
        self.last_run_time = None
        self.last_run_result = None
        self.total_runs = 0
        self.successful_runs = 0
        self.failed_runs = 0
        
        # Настраиваем graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def setup_schedule(self):
        """Настраивает расписание выполнения задач"""
        interval_minutes = config.FETCH_INTERVAL_MINUTES
        
        logger.info(f"Настройка расписания: каждые {interval_minutes} минут")
        
        # Очищаем существующие задачи
        schedule.clear()
        
        # Планируем выполнение каждые N минут
        schedule.every(interval_minutes).minutes.do(self._run_signal_processing_job)
        
        # Дополнительно планируем на времена кратные 15 минутам (как в ТЗ)
        if interval_minutes == 15:
            schedule.every().hour.at(":00").do(self._run_signal_processing_job)
            schedule.every().hour.at(":15").do(self._run_signal_processing_job)
            schedule.every().hour.at(":30").do(self._run_signal_processing_job)
            schedule.every().hour.at(":45").do(self._run_signal_processing_job)
        
        logger.info("Расписание настроено")
        return True
    
    def start(self, run_immediately: bool = True):
        """
        Запускает планировщик
        
        Args:
            run_immediately: Запустить первую обработку немедленно
        """
        if self.is_running:
            logger.warning("Планировщик уже запущен")
            return
        
        logger.info("=== Запуск планировщика сигналов ===")
        
        # Настраиваем расписание
        if not self.setup_schedule():
            logger.error("Не удалось настроить расписание")
            return
        
        self.is_running = True
        self.shutdown_requested = False
        
        # Запускаем первую обработку сразу если нужно
        if run_immediately:
            logger.info("Запуск первой обработки...")
            self._run_signal_processing_job()
        
        # Основной цикл планировщика
        logger.info("Планировщик запущен. Ожидание расписания...")
        self._print_next_run_time()
        
        try:
            last_countdown_minute = None
            
            while self.is_running and not self.shutdown_requested:
                schedule.run_pending()
                
                # Показываем счетчик каждую минуту
                if not (self.job_thread and self.job_thread.is_alive()):
                    self._show_countdown(last_countdown_minute)
                    last_countdown_minute = self._get_minutes_until_next_run()
                
                time.sleep(1)  # Проверяем каждую секунду
                
        except KeyboardInterrupt:
            logger.info("Получен сигнал прерывания")
        finally:
            self._cleanup()
        
        logger.info("Планировщик остановлен")
    
    def stop(self):
        """Останавливает планировщик"""
        logger.info("Запрос остановки планировщика...")
        print("🛑 Остановка планировщика...")
        self.shutdown_requested = True
        self.is_running = False
        
        # Ждем завершения текущей задачи
        if self.job_thread and self.job_thread.is_alive():
            logger.info("Ожидание завершения текущей задачи...")
            print("⏳ Ожидание завершения текущей обработки сигналов...")
            
            # Ждем с периодическими обновлениями
            import time
            max_wait = 240  # 4 минуты максимум
            waited = 0
            while self.job_thread.is_alive() and waited < max_wait:
                time.sleep(10)
                waited += 10
                if self.job_thread.is_alive():
                    print(f"⏳ Продолжаем ожидание... ({waited}с/{max_wait}с)")
            
            if self.job_thread.is_alive():
                print("⚠️  Время ожидания истекло, принудительное завершение...")
    
    def force_stop(self):
        """Принудительно останавливает планировщик без ожидания"""
        logger.info("🚨 Принудительная остановка планировщика")
        print("🚨 Принудительная остановка - немедленное завершение!")
        
        self.shutdown_requested = True
        self.is_running = False
        
        # Принудительно завершаем поток обработки
        if self.job_thread and self.job_thread.is_alive():
            print("💀 Принудительное завершение потока обработки...")
            try:
                # Пытаемся изящно остановить
                import threading
                import time
                
                # Даем 2 секунды на завершение
                self.job_thread.join(timeout=2)
                
                if self.job_thread.is_alive():
                    print("💀 Поток не отвечает, применяем жесткие меры...")
                    # В Python нет прямого способа убить поток, 
                    # поэтому просто помечаем что нужно остановиться
                    import os
                    print("💀 Выходим из процесса...")
                    os._exit(1)  # Жесткий выход
                    
            except Exception as e:
                logger.error(f"Ошибка принудительной остановки: {e}")
                print(f"💀 Ошибка: {e}")
        
        print("✅ Принудительная остановка завершена")
    
    def _run_signal_processing_job(self):
        """Выполняет задачу обработки сигналов в отдельном потоке"""
        if self.job_thread and self.job_thread.is_alive():
            logger.warning("Предыдущая задача еще выполняется, пропускаем")
            return
        
        # Запускаем в отдельном потоке чтобы не блокировать планировщик
        self.job_thread = threading.Thread(
            target=self._execute_signal_processing,
            name="SignalProcessingThread"
        )
        self.job_thread.start()
    
    def _execute_signal_processing(self):
        """Выполняет обработку сигналов с обработкой ошибок"""
        job_start = datetime.utcnow()
        self.last_run_time = job_start
        self.total_runs += 1
        
        print()  # Очищаем строку счетчика
        logger.info("🚀 Начало планового выполнения обработки сигналов")
        logger.info(f"   Время: {job_start.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"   Запуск №{self.total_runs}")
        
        try:
            # Выполняем полный цикл обработки
            results = self.signal_manager.fetch_and_process_all_signals()
            
            # Записываем результат
            self.last_run_result = {
                'success': True,
                'start_time': job_start,
                'end_time': datetime.utcnow(),
                'duration': results.get('processing_time', 0),
                'results': results
            }
            
            self.successful_runs += 1
            
            # Логируем успешное выполнение
            logger.info("✅ Плановое выполнение завершено успешно")
            logger.info(f"   🕐 Длительность: {results.get('processing_time', 0):.1f} сек")
            logger.info(f"   📊 Тикеров: {results.get('tickers_processed', 0)}/{results.get('tickers_total', 0)}")
            logger.info(f"   💾 Сигналов: {results.get('signals_saved', 0)} новых, {results.get('signals_updated', 0)} обновлений")
            logger.info(f"   🎯 Исполнений: {results.get('entry_hits', 0)} входов, {results.get('take_profit_hits', 0)} тейков, {results.get('stop_loss_hits', 0)} стопов")
            
        except Exception as e:
            # Записываем ошибку
            self.last_run_result = {
                'success': False,
                'start_time': job_start,
                'end_time': datetime.utcnow(),
                'error': str(e)
            }
            
            self.failed_runs += 1
            
            logger.error(f"❌ Ошибка планового выполнения: {e}")
            
            # Логируем в БД
            try:
                with db_manager.session_scope() as session:
                    ErrorLogCRUD.log_error(
                        session, 
                        'SignalScheduler', 
                        f"Ошибка планового выполнения: {e}"
                    )
            except Exception as db_error:
                logger.error(f"Не удалось записать ошибку в БД: {db_error}")
        
        finally:
            # Показываем время следующего запуска
            self._print_next_run_time()
    
    def _print_next_run_time(self):
        """Выводит время следующего запуска"""
        next_run = schedule.next_run()
        if next_run:
            from datetime import timezone
            
            # schedule.next_run() возвращает время в локальной зоне, 
            # нужно получить соответствующее UTC время
            now_local = datetime.now()
            now_utc = datetime.utcnow()
            
            # Вычисляем смещение локального времени от UTC
            local_utc_offset = now_local - now_utc
            
            # Преобразуем next_run из локального времени в UTC
            next_run_utc = next_run - local_utc_offset
            
            time_until = next_run_utc - now_utc
            minutes_until = int(time_until.total_seconds() / 60)
            next_run_str = next_run_utc.strftime('%H:%M:%S')
            
            logger.info(f"⏰ Следующий запуск: {next_run_str} UTC (через {minutes_until} мин)")
    
    def _get_minutes_until_next_run(self) -> Optional[int]:
        """Возвращает количество минут до следующего запуска"""
        next_run = schedule.next_run()
        if next_run:
            # Приводим к UTC как в _print_next_run_time()
            now_local = datetime.now()
            now_utc = datetime.utcnow()
            local_utc_offset = now_local - now_utc
            next_run_utc = next_run - local_utc_offset
            
            time_until = next_run_utc - now_utc
            return max(0, int(time_until.total_seconds() / 60))
        return None
    
    def _show_countdown(self, last_minute: Optional[int]):
        """Показывает счетчик времени до следующего запуска"""
        current_minute = self._get_minutes_until_next_run()
        
        if current_minute is not None and current_minute != last_minute:
            if current_minute > 0:
                print(f"\r⏰ До следующего батча: {current_minute} мин", end="", flush=True)
            else:
                print(f"\r⏰ Запуск батча через несколько секунд...", end="", flush=True)
    
    def _signal_handler(self, signum, frame):
        """Обработчик сигналов для graceful shutdown"""
        signal_name = signal.Signals(signum).name
        logger.info(f"Получен сигнал {signal_name}, завершение работы...")
        print(f"📡 Получен сигнал {signal_name}, начинаем graceful shutdown...")
        self.stop()
    
    def _cleanup(self):
        """Очистка ресурсов при завершении"""
        logger.info("Очистка ресурсов планировщика...")
        print("🧹 Очистка ресурсов планировщика...")
        
        # Очищаем расписание
        schedule.clear()
        
        # Ждем завершения потока
        if self.job_thread and self.job_thread.is_alive():
            logger.info("Ожидание завершения рабочего потока...")
            print("⏳ Завершение рабочего потока...")
            self.job_thread.join(timeout=60)  # Увеличиваем timeout
        
        # Закрываем API клиент
        try:
            self.signal_manager.api_client.close()
            print("🔌 API клиент закрыт")
        except:
            pass
        
        print("✅ Планировщик успешно остановлен")
    
    def get_status(self) -> Dict[str, Any]:
        """Возвращает текущий статус планировщика"""
        status = {
            'is_running': self.is_running,
            'total_runs': self.total_runs,
            'successful_runs': self.successful_runs,
            'failed_runs': self.failed_runs,
            'success_rate': 0.0,
            'last_run_time': None,
            'last_run_success': None,
            'next_run_time': None
        }
        
        if self.total_runs > 0:
            status['success_rate'] = (self.successful_runs / self.total_runs) * 100
        
        if self.last_run_time:
            status['last_run_time'] = self.last_run_time.isoformat()
        
        if self.last_run_result:
            status['last_run_success'] = self.last_run_result.get('success', False)
        
        next_run = schedule.next_run()
        if next_run:
            status['next_run_time'] = next_run.isoformat()
        
        return status
    
    def run_manual(self) -> Dict[str, Any]:
        """Запускает обработку вручную (не по расписанию)"""
        logger.info("Запуск обработки вручную...")
        
        if self.job_thread and self.job_thread.is_alive():
            return {
                'success': False, 
                'error': 'Уже выполняется другая задача'
            }
        
        try:
            results = self.signal_manager.fetch_and_process_all_signals()
            return {'success': True, 'results': results}
        except Exception as e:
            logger.error(f"Ошибка ручного запуска: {e}")
            return {'success': False, 'error': str(e)}