"""
Процессор сигналов - сохранение и обработка данных сигналов
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from ..database.connection import db_manager
from ..database.crud import SignalCRUD, ErrorLogCRUD
from ..utils.exceptions import DatabaseError, ValidationError

logger = logging.getLogger(__name__)

class SignalProcessor:
    """Класс для обработки и сохранения сигналов в базе данных"""
    
    def __init__(self):
        self.processed_count = 0
        self.error_count = 0
    
    def save_signals_batch(self, signals_data: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
        """
        Сохраняет пакет сигналов в базу данных
        
        Args:
            signals_data: Dict где ключ - тикер, значение - список сигналов
            
        Returns:
            Dict с результатами обработки
        """
        results = {
            'total_signals': 0,
            'saved_signals': 0,
            'updated_signals': 0,
            'errors': 0,
            'tickers_processed': 0
        }
        
        logger.info(f"💾 Начало сохранения сигналов для {len(signals_data)} тикеров")
        
        try:
            with db_manager.session_scope() as session:
                ticker_count = 0
                
                for ticker, signals_list in signals_data.items():
                    if not signals_list:
                        continue
                    
                    ticker_count += 1
                    results['tickers_processed'] += 1
                    
                    print(f"\r💾 Сохранение: {ticker_count}/{len(signals_data)} тикеров ({ticker}: {len(signals_list)} сигналов)", end="", flush=True)
                    
                    for signal_data in signals_list:
                        results['total_signals'] += 1
                        
                        try:
                            # Проверяем существующий сигнал
                            existing_signal = self._find_existing_signal(
                                session, signal_data
                            )
                            
                            if existing_signal:
                                # Обновляем существующий сигнал
                                updated = self._update_existing_signal(
                                    session, existing_signal, signal_data
                                )
                                if updated:
                                    results['updated_signals'] += 1
                                    logger.info(f"🔄 Обновлен: {ticker} {signal_data.get('timeframe')}")
                            else:
                                # Создаем новый сигнал
                                new_signal = self._create_new_signal(session, signal_data)
                                if new_signal:
                                    results['saved_signals'] += 1
                                    logger.info(f"💾 Создан: {ticker} {signal_data.get('timeframe')}")
                                    
                        except Exception as e:
                            results['errors'] += 1
                            error_msg = f"💥 Ошибка сигнала {ticker} {signal_data.get('timeframe', 'unknown')}: {e}"
                            logger.error(error_msg)
                            print(f"\n💥 Ошибка: {ticker} - {str(e)[:100]}")
                            
                            # Логируем ошибку в БД
                            ErrorLogCRUD.log_error(session, 'SignalProcessor', error_msg)
                
                print()  # Переход на новую строку после прогресса
                logger.info(f"✅ Сохранение завершено: {results['saved_signals']} новых, "
                           f"{results['updated_signals']} обновлений, {results['errors']} ошибок")
                
        except Exception as e:
            logger.error(f"Критическая ошибка при сохранении сигналов: {e}")
            raise DatabaseError(f"Ошибка сохранения в БД: {e}")
        
        return results
    
    def _find_existing_signal(self, session, signal_data: Dict[str, Any]):
        """Ищет существующий сигнал по тикеру, таймфрейму и времени"""
        ticker = signal_data.get('ticker')
        timeframe = signal_data.get('timeframe')
        signal_category = signal_data.get('signal_category', 'main')
        
        # Ищем сигналы за последние 30 минут для этого тикера и таймфрейма
        time_threshold = datetime.utcnow() - timedelta(minutes=30)
        
        from ..database.models import Signal
        from sqlalchemy import and_
        
        existing = session.query(Signal).filter(
            and_(
                Signal.ticker == ticker,
                Signal.timeframe == timeframe,
                Signal.created_at >= time_threshold,
                Signal.status.in_(['new', 'entry_hit', 'active'])
            )
        ).first()
        
        return existing
    
    def _update_existing_signal(self, session, existing_signal, signal_data: Dict[str, Any]) -> bool:
        """Обновляет существующий сигнал новыми данными"""
        try:
            updated = False
            
            # Обновляем current_price
            new_current_price = signal_data.get('current_price')
            if new_current_price and new_current_price != existing_signal.current_price:
                existing_signal.current_price = new_current_price
                updated = True
            
            # Обновляем confidence если изменилась
            new_confidence = signal_data.get('confidence')
            if new_confidence and new_confidence != existing_signal.confidence:
                existing_signal.confidence = new_confidence
                updated = True
            
            # Обновляем correction данные
            correction_data = signal_data.get('correction')
            if correction_data:
                if hasattr(existing_signal, 'correction_type'):
                    new_corr_type = correction_data.get('direction')
                    new_corr_entry = correction_data.get('entry')
                    new_corr_confidence = correction_data.get('confidence')
                    
                    if new_corr_type != existing_signal.correction_type:
                        existing_signal.correction_type = new_corr_type
                        updated = True
                    if new_corr_entry != existing_signal.correction_entry:
                        existing_signal.correction_entry = new_corr_entry
                        updated = True
                    if correction_data.get('tp') and len(correction_data['tp']) > 0:
                        new_tp = correction_data['tp'][0]
                        if new_tp != existing_signal.correction_tp:
                            existing_signal.correction_tp = new_tp
                            updated = True
                    if correction_data.get('sl') != existing_signal.correction_sl:
                        existing_signal.correction_sl = correction_data.get('sl')
                        updated = True
                    if new_corr_confidence != existing_signal.correction_confidence:
                        existing_signal.correction_confidence = new_corr_confidence
                        updated = True
            
            # Обновляем время последнего обновления
            if updated:
                from datetime import datetime
                # В SQLAlchemy модели нет поля updated_at для signals, но можно добавить логику
                pass
            
            return updated
            
        except Exception as e:
            logger.error(f"Ошибка обновления сигнала: {e}")
            return False
    
    def _create_new_signal(self, session, signal_data: Dict[str, Any]):
        """Создает новый сигнал в базе данных"""
        try:
            # Подготавливаем данные для создания
            create_data = {
                'ticker': signal_data.get('ticker'),
                'timeframe': signal_data.get('timeframe'),
                'signal_type': signal_data.get('signal_type'),
                'entry_price': signal_data.get('entry_price'),
                'take_profit': signal_data.get('take_profit'),
                'stop_loss': signal_data.get('stop_loss'),
                'confidence': signal_data.get('confidence'),
                'risk_reward': signal_data.get('risk_reward'),
                'current_price': signal_data.get('current_price'),
                'status': 'new',
                'is_main_signal': True
            }
            
            # Добавляем correction данные если есть
            correction_data = signal_data.get('correction')
            if correction_data:
                create_data.update({
                    'correction_type': correction_data.get('direction'),
                    'correction_entry': correction_data.get('entry'),
                    'correction_tp': correction_data.get('tp')[0] if correction_data.get('tp') else None,
                    'correction_sl': correction_data.get('sl'),
                    'correction_confidence': correction_data.get('confidence')
                })
            
            # Удаляем None значения
            create_data = {k: v for k, v in create_data.items() if v is not None}
            
            new_signal = SignalCRUD.create_signal(session, **create_data)
            
            return new_signal
            
        except Exception as e:
            logger.error(f"Ошибка создания сигнала: {e}")
            return None
    
    def get_processing_stats(self) -> Dict[str, int]:
        """Возвращает статистику обработки"""
        return {
            'processed_count': self.processed_count,
            'error_count': self.error_count
        }