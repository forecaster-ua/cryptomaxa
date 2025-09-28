"""
Основной модуль для обработки сигналов - интеграция API, БД и анализа
"""
import logging
from typing import Dict, Any, List, Optional

from ..api_client import TickersParser, SignalAPIClient, SignalDataParser
from ..signal_analyzer import SignalProcessor, SignalValidator, ConfidenceAnalyzer
from ..utils.exceptions import APIError, DatabaseError

logger = logging.getLogger(__name__)

class SignalManager:
    """Главный класс для управления жизненным циклом сигналов"""
    
    def __init__(self):
        self.tickers_parser = TickersParser()
        self.api_client = SignalAPIClient()
        self.signal_processor = SignalProcessor()
        self.signal_validator = SignalValidator()
        self.confidence_analyzer = ConfidenceAnalyzer()
    
    def fetch_and_process_all_signals(self) -> Dict[str, Any]:
        """
        Полный цикл: получение данных по всем тикерам, обработка и сохранение
        
        Returns:
            Dict с результатами обработки
        """
        results = {
            'tickers_total': 0,
            'tickers_processed': 0,
            'api_errors': 0,
            'signals_saved': 0,
            'signals_updated': 0,
            'warnings_found': 0,
            'processing_time': 0
        }
        
        logger.info("=== Начало полного цикла обработки сигналов ===")
        
        from datetime import datetime
        start_time = datetime.utcnow()
        
        try:
            # 1. Получаем список тикеров
            tickers = self.tickers_parser.parse_tickers()
            results['tickers_total'] = len(tickers)
            logger.info(f"Получен список из {len(tickers)} тикеров")
            
            # 2. Получаем данные с API
            logger.info(f"Получение сигналов для {len(tickers)} тикеров")
            raw_signals_data = self.api_client.get_signals_batch(tickers, delay=0.1)
            
            # 3. Парсим и анализируем сигналы
            processed_signals = {}
            total_signals = 0
            ticker_count = 0
            
            print(f"📊 Обработка тикеров: 0/{len(tickers)}", end="", flush=True)
            
            for ticker, api_data in raw_signals_data.items():
                ticker_count += 1
                
                # Обновляем прогресс
                print(f"\r📊 Обработка тикеров: {ticker_count}/{len(tickers)} ({ticker})", end="", flush=True)
                
                if api_data is None:
                    results['api_errors'] += 1
                    continue
                
                try:
                    # Парсим сигналы
                    signals = SignalDataParser.parse_signal_response(api_data, ticker)
                    
                    if signals:
                        # Анализируем confidence
                        analyzed_signals = self.confidence_analyzer.analyze_confidence_warnings(signals)
                        processed_signals[ticker] = analyzed_signals
                        
                        total_signals += len(signals)
                        results['tickers_processed'] += 1
                        
                        # Подсчитываем предупреждения
                        for signal in analyzed_signals:
                            if signal.get('warnings'):
                                results['warnings_found'] += len(signal['warnings'])
                    
                except Exception as e:
                    logger.error(f"Ошибка обработки сигналов для {ticker}: {e}")
                    results['api_errors'] += 1
            
            print()  # Переход на новую строку после прогресса
            logger.info(f"Обработано {total_signals} сигналов для {results['tickers_processed']} тикеров")
            
            # 4. Сохраняем в базу данных
            if processed_signals:
                print(f"💾 Сохранение {total_signals} сигналов в БД...")
                save_results = self.signal_processor.save_signals_batch(processed_signals)
                
                results['signals_saved'] = save_results['saved_signals']
                results['signals_updated'] = save_results['updated_signals']
            
            # 5. Проверяем исполнение активных сигналов
            print("🎯 Проверка исполнения активных сигналов...")
            
            # Собираем текущие цены из полученных данных
            current_prices = {}
            for ticker, signals in processed_signals.items():
                if signals:
                    # Берем current_price из любого сигнала (они одинаковые для тикера)
                    current_price = signals[0].get('current_price')
                    if current_price:
                        current_prices[ticker] = current_price
            
            validation_results = self.signal_validator.validate_active_signals(current_prices)
            results.update({
                'entry_hits': validation_results.get('entry_hits', 0),
                'take_profit_hits': validation_results.get('take_profit_hits', 0),
                'stop_loss_hits': validation_results.get('stop_loss_hits', 0)
            })
            
        except Exception as e:
            logger.error(f"Критическая ошибка в цикле обработки: {e}")
            raise
        finally:
            # Закрываем API клиент
            self.api_client.close()
        
        # Подсчитываем время выполнения
        end_time = datetime.utcnow()
        results['processing_time'] = (end_time - start_time).total_seconds()
        
        logger.info("=== Цикл обработки завершен ===")
        logger.info(f"Сохранено: {results['signals_saved']} новых, "
                   f"{results['signals_updated']} обновлений")
        logger.info(f"Исполнения: {results['entry_hits']} входов, "
                   f"{results['take_profit_hits']} тейков, "
                   f"{results['stop_loss_hits']} стопов")
        logger.info(f"Время выполнения: {results['processing_time']:.1f} сек")
        
        # 6. Отправляем уведомления подписчикам (для всех обработанных сигналов)
        if processed_signals and (results['signals_saved'] > 0 or results['signals_updated'] > 0):
            try:
                import asyncio
                from ..telegram_bot.notifications import NotificationService
                
                # Подготавливаем данные для уведомлений
                notifications_data = {}
                for ticker, signals in processed_signals.items():
                    if signals:
                        # Формируем данные в формате для format_signal_frames
                        signal_data = {
                            'pair': f"{ticker}USDT",
                            'frames': [],
                            'source': "Новый сигнал"
                        }
                        
                        for signal in signals:
                            frame = {
                                'tf': signal.get('timeframe'),
                                'direction': signal.get('signal_type', '').upper(),
                                'entry': signal.get('entry_price'),
                                'tp': signal.get('take_profit_list', []),
                                'sl': signal.get('stop_loss'),
                                'confidence': signal.get('confidence', 0),
                                'warnings': signal.get('warnings', [])
                            }
                            signal_data['frames'].append(frame)
                        
                        notifications_data[ticker] = signal_data
                
                # Отправляем уведомления асинхронно
                logger.info(f"📢 Отправка уведомлений для {len(notifications_data)} тикеров")
                
                # Запускаем в новом event loop, так как планировщик синхронный
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(NotificationService.send_batch_notifications(notifications_data))
                    results['notifications_sent'] = len(notifications_data)
                finally:
                    loop.close()
                
            except Exception as e:
                logger.error(f"❌ Ошибка отправки уведомлений: {e}")
                results['notification_errors'] = 1
        
        return results
    
    def process_single_ticker(self, ticker: str) -> Dict[str, Any]:
        """
        Обрабатывает сигналы для одного тикера
        
        Args:
            ticker: Тикер для обработки
            
        Returns:
            Dict с результатами обработки
        """
        logger.info(f"Обработка сигналов для {ticker}")
        
        try:
            # Получаем данные
            api_data = self.api_client.get_multi_signal(ticker)
            
            if not api_data:
                return {'success': False, 'error': 'Нет данных от API'}
            
            # Парсим сигналы
            signals = SignalDataParser.parse_signal_response(api_data, ticker)
            
            if not signals:
                return {'success': False, 'error': 'Не удалось извлечь сигналы'}
            
            # Анализируем confidence
            analyzed_signals = self.confidence_analyzer.analyze_confidence_warnings(signals)
            
            # Сохраняем в БД
            save_results = self.signal_processor.save_signals_batch({ticker: analyzed_signals})
            
            return {
                'success': True,
                'signals_count': len(analyzed_signals),
                'saved': save_results['saved_signals'],
                'updated': save_results['updated_signals'],
                'warnings': sum(len(s.get('warnings', [])) for s in analyzed_signals)
            }
            
        except Exception as e:
            logger.error(f"Ошибка обработки {ticker}: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_recent_signals_summary(self, hours: int = 24) -> Dict[str, Any]:
        """
        Возвращает сводку по недавним сигналам
        
        Args:
            hours: Количество часов для анализа
            
        Returns:
            Dict со сводкой
        """
        from datetime import datetime, timedelta
        from ..database.connection import db_manager
        from ..database.models import Signal
        from sqlalchemy import and_
        
        try:
            with db_manager.session_scope() as session:
                time_threshold = datetime.utcnow() - timedelta(hours=hours)
                
                # Получаем сигналы за период
                recent_signals = session.query(Signal).filter(
                    Signal.created_at >= time_threshold
                ).all()
                
                if not recent_signals:
                    return {'total_signals': 0}
                
                # Группируем по статусам
                status_counts = {}
                confidence_values = []
                tickers = set()
                
                for signal in recent_signals:
                    status = signal.status
                    status_counts[status] = status_counts.get(status, 0) + 1
                    
                    if signal.confidence:
                        confidence_values.append(float(signal.confidence))
                    
                    tickers.add(signal.ticker)
                
                # Формируем сводку
                summary = {
                    'total_signals': len(recent_signals),
                    'unique_tickers': len(tickers),
                    'status_breakdown': status_counts,
                    'timeframe': f'{hours}h'
                }
                
                if confidence_values:
                    summary['confidence_stats'] = {
                        'avg': sum(confidence_values) / len(confidence_values),
                        'max': max(confidence_values),
                        'min': min(confidence_values),
                        'high_confidence_count': sum(1 for c in confidence_values if c >= 90)
                    }
                
                return summary
                
        except Exception as e:
            logger.error(f"Ошибка получения сводки: {e}")
            return {'error': str(e)}