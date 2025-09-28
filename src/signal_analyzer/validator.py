"""
Валидатор и анализатор исполнения сигналов
"""
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from decimal import Decimal

from ..database.connection import db_manager
from ..database.crud import SignalCRUD, ErrorLogCRUD
from ..database.models import Signal

logger = logging.getLogger(__name__)

class SignalValidator:
    """Класс для проверки исполнения сигналов и обновления их статусов"""
    
    def __init__(self):
        self.validation_count = 0
    
    def validate_active_signals(self, current_prices: Dict[str, float] = None) -> Dict[str, Any]:
        """
        Проверяет исполнение активных сигналов
        
        Args:
            current_prices: Словарь текущих цен по тикерам
            
        Returns:
            Dict с результатами проверки
        """
        results = {
            'checked_signals': 0,
            'entry_hits': 0,
            'take_profit_hits': 0,
            'stop_loss_hits': 0,
            'still_active': 0,
            'errors': 0
        }
        
        logger.info("🎯 Начало проверки активных сигналов")
        
        try:
            with db_manager.session_scope() as session:
                
                # Получаем все активные сигналы
                active_signals = SignalCRUD.get_active_signals(session)
                logger.info(f"🎯 Найдено {len(active_signals)} активных сигналов для проверки")
                
                signal_count = 0
                for signal in active_signals:
                    signal_count += 1
                    
                    if signal_count % 10 == 0 or signal_count == len(active_signals):
                        print(f"\r🎯 Проверка исполнений: {signal_count}/{len(active_signals)}", end="", flush=True)
                    results['checked_signals'] += 1
                    
                    try:
                        # Используем текущую цену из сигнала или переданную
                        current_price = None
                        if current_prices and signal.ticker in current_prices:
                            current_price = current_prices[signal.ticker]
                        elif signal.current_price:
                            current_price = float(signal.current_price)
                        
                        if current_price is None:
                            logger.warning(f"Нет текущей цены для {signal.ticker}")
                            continue
                        
                        # Проверяем исполнение сигнала
                        new_status = self._check_signal_execution(signal, current_price)
                        
                        if new_status != signal.status:
                            old_status = signal.status
                            SignalCRUD.update_signal_status(
                                session, signal.id, new_status, current_price
                            )
                            
                            # Увеличиваем счетчики
                            if new_status == 'entry_hit':
                                results['entry_hits'] += 1
                                logger.info(f"🎯 ВХОД: {signal.ticker} {signal.timeframe} по цене {current_price}")
                            elif new_status == 'tp_hit':
                                results['take_profit_hits'] += 1
                                logger.info(f"🎯 ТЕЙК: {signal.ticker} {signal.timeframe} по цене {current_price}")
                            elif new_status == 'sl_hit':
                                results['stop_loss_hits'] += 1
                                logger.info(f"🎯 СТОП: {signal.ticker} {signal.timeframe} по цене {current_price}")
                            
                            logger.info(f"Обновлен статус {signal.ticker} {signal.timeframe}: "
                                      f"{old_status} → {new_status}")
                        else:
                            results['still_active'] += 1
                            
                    except Exception as e:
                        results['errors'] += 1
                        error_msg = f"💥 Ошибка проверки сигнала {signal.ticker} {signal.id}: {e}"
                        logger.error(error_msg)
                        print(f"\n💥 Ошибка валидации: {signal.ticker} - {str(e)[:100]}")
                        ErrorLogCRUD.log_error(session, 'SignalValidator', error_msg)
                
                print()  # Переход на новую строку после прогресса
                self.validation_count += results['checked_signals']
                
                logger.info(f"✅ Проверка завершена: {results['entry_hits']} входов, "
                           f"{results['take_profit_hits']} тейков, "
                           f"{results['stop_loss_hits']} стопов")
                
        except Exception as e:
            logger.error(f"Критическая ошибка проверки сигналов: {e}")
            results['errors'] += 1
        
        return results
    
    def _check_signal_execution(self, signal: Signal, current_price: float) -> str:
        """
        Проверяет исполнение конкретного сигнала
        
        Args:
            signal: Объект сигнала из БД
            current_price: Текущая цена
            
        Returns:
            str: Новый статус сигнала
        """
        entry_price = float(signal.entry_price)
        signal_type = signal.signal_type.upper()
        
        # Преобразуем цены для сравнения
        take_profit = float(signal.take_profit) if signal.take_profit else None
        stop_loss = float(signal.stop_loss) if signal.stop_loss else None
        
        # Логика согласно ТЗ
        if signal.status == 'new':
            # Проверяем вход
            if self._check_entry_execution(signal_type, current_price, entry_price):
                return 'entry_hit'
            return 'new'
            
        elif signal.status == 'entry_hit' or signal.status == 'active':
            # Проверяем исполнение стопа и тейка
            stop_hit = False
            take_hit = False
            
            if stop_loss:
                stop_hit = self._check_stop_loss_execution(signal_type, current_price, stop_loss)
            
            if take_profit:
                take_hit = self._check_take_profit_execution(signal_type, current_price, take_profit)
            
            # Приоритет у стоп-лосса
            if stop_hit:
                return 'sl_hit'
            elif take_hit:
                return 'tp_hit'
            else:
                return 'active'
        
        return signal.status
    
    def _check_entry_execution(self, signal_type: str, current_price: float, entry_price: float) -> bool:
        """Проверяет исполнение входа согласно логике из ТЗ"""
        if signal_type == 'LONG':
            # LONG: вход исполнен при current_price ≤ entry
            return current_price <= entry_price
        elif signal_type == 'SHORT':
            # SHORT: вход исполнен при current_price ≥ entry
            return current_price >= entry_price
        return False
    
    def _check_take_profit_execution(self, signal_type: str, current_price: float, take_profit: float) -> bool:
        """Проверяет исполнение тейк-профита"""
        if signal_type == 'LONG':
            # LONG: тейк при price ≥ take_profit
            return current_price >= take_profit
        elif signal_type == 'SHORT':
            # SHORT: тейк при price ≤ take_profit  
            return current_price <= take_profit
        return False
    
    def _check_stop_loss_execution(self, signal_type: str, current_price: float, stop_loss: float) -> bool:
        """Проверяет исполнение стоп-лосса"""
        if signal_type == 'LONG':
            # LONG: стоп при price ≤ stop_loss
            return current_price <= stop_loss
        elif signal_type == 'SHORT':
            # SHORT: стоп при price ≥ stop_loss
            return current_price >= stop_loss
        return False

class ConfidenceAnalyzer:
    """Анализатор уровня confidence и предупреждений"""
    
    HIGH_CONFIDENCE_THRESHOLD = 90.0
    LOW_CONFIDENCE_THRESHOLD = 50.0
    TREND_ANALYSIS_HOURS = 12
    
    def analyze_confidence_warnings(self, signals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Анализирует сигналы на предмет предупреждений по confidence
        
        Args:
            signals: Список сигналов для анализа
            
        Returns:
            List[Dict]: Список сигналов с добавленными предупреждениями
        """
        analyzed_signals = []
        
        for signal in signals:
            analyzed_signal = signal.copy()
            warnings = []
            
            confidence = signal.get('confidence')
            if confidence is not None:
                
                # Проверка высокого confidence
                if confidence >= self.HIGH_CONFIDENCE_THRESHOLD:
                    warnings.append({
                        'type': 'high_confidence',
                        'message': f'⚠️ Высокий confidence: {confidence}% (опасность)',
                        'severity': 'warning'
                    })
                
                # Проверка низкого confidence
                elif confidence < self.LOW_CONFIDENCE_THRESHOLD:
                    warnings.append({
                        'type': 'low_confidence', 
                        'message': f'⚠️ Слабый сигнал: {confidence}%',
                        'severity': 'info'
                    })
                
                # Проверка сигнала против тренда (требует исторических данных)
                trend_warning = self._check_trend_conflict(signal)
                if trend_warning:
                    warnings.append(trend_warning)
            
            analyzed_signal['warnings'] = warnings
            analyzed_signals.append(analyzed_signal)
        
        return analyzed_signals
    
    def _check_trend_conflict(self, signal: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Проверяет конфликт сигнала с трендом (упрощенная версия)
        
        В реальной реализации здесь нужно анализировать исторические сигналы
        за последние 12 часов и определять доминирующий тренд
        """
        confidence = signal.get('confidence', 0)
        
        # Пока что простая логика - если очень высокий confidence и это может быть разворот
        if confidence > 95.0:
            return {
                'type': 'potential_trend_conflict',
                'message': '⚠️ Возможный сигнал против тренда (требует проверки)',
                'severity': 'warning'
            }
        
        return None
    
    def get_confidence_summary(self, signals: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Возвращает сводку по уровням confidence"""
        if not signals:
            return {}
        
        confidences = [s.get('confidence', 0) for s in signals if s.get('confidence') is not None]
        
        if not confidences:
            return {}
        
        return {
            'avg_confidence': sum(confidences) / len(confidences),
            'max_confidence': max(confidences),
            'min_confidence': min(confidences),
            'high_confidence_count': sum(1 for c in confidences if c >= self.HIGH_CONFIDENCE_THRESHOLD),
            'low_confidence_count': sum(1 for c in confidences if c < self.LOW_CONFIDENCE_THRESHOLD),
            'total_signals': len(confidences)
        }