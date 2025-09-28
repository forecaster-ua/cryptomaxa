"""
Парсер и валидатор ответов API
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from ..utils.exceptions import ValidationError

logger = logging.getLogger(__name__)

class SignalDataParser:
    """Класс для парсинга и валидации данных сигналов"""
    
    @staticmethod
    def parse_signal_response(data: Any, ticker: str) -> List[Dict[str, Any]]:
        """
        Парсит ответ API и извлекает сигналы для всех таймфреймов
        
        Args:
            data: Данные от API (может быть список или объект)
            ticker: Тикер для которого получены данные
            
        Returns:
            List[Dict]: Список сигналов для разных таймфреймов
            
        Raises:
            ValidationError: При некорректной структуре данных
        """
        if not data:
            raise ValidationError("Пустой ответ от API")
        
        signals = []
        
        try:
            # Вариант 1: API возвращает список объектов (наш случай)
            if isinstance(data, list):
                logger.debug(f"Обрабатываем список из {len(data)} элементов")
                
                for item in data:
                    if isinstance(item, dict):
                        timeframe = item.get('timeframe', '1h')
                        
                        # Обрабатываем разные форматы сигналов в элементе
                        parsed_signals = SignalDataParser._parse_timeframe_item(item, ticker, timeframe)
                        signals.extend(parsed_signals)
            
            # Вариант 2: API возвращает объект с данными по таймфреймам
            elif isinstance(data, dict):
                logger.debug("Обрабатываем объект с данными")
                
                # Прямые ключи таймфреймов
                timeframes = ['15m', '1h', '4h', '1d']
                for timeframe in timeframes:
                    if timeframe in data:
                        signal_data = data[timeframe]
                        if signal_data and isinstance(signal_data, dict):
                            parsed_signal = SignalDataParser._parse_single_signal(
                                signal_data, ticker, timeframe
                            )
                            if parsed_signal:
                                signals.append(parsed_signal)
                
                # Массив в поле signals
                if 'signals' in data and isinstance(data['signals'], list):
                    for signal_item in data['signals']:
                        if isinstance(signal_item, dict):
                            timeframe = signal_item.get('timeframe', '1h')
                            parsed_signal = SignalDataParser._parse_single_signal(
                                signal_item, ticker, timeframe
                            )
                            if parsed_signal:
                                signals.append(parsed_signal)
            
            else:
                raise ValidationError(f"Неподдерживаемый тип ответа API: {type(data)}")
            
            logger.debug(f"Извлечено {len(signals)} сигналов для {ticker}")
            return signals
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Ошибка парсинга сигналов для {ticker}: {e}")
            raise ValidationError(f"Ошибка парсинга данных: {e}")
    
    @staticmethod
    def _parse_timeframe_item(item: Dict[str, Any], ticker: str, timeframe: str) -> List[Dict[str, Any]]:
        """
        Парсит элемент таймфрейма, который может содержать несколько сигналов
        
        Args:
            item: Элемент данных для таймфрейма
            ticker: Тикер
            timeframe: Таймфрейм
            
        Returns:
            List[Dict]: Список обработанных сигналов
        """
        signals = []
        
        try:
            # Проверяем наличие main_signal и correction_signal (формат 15m)
            if 'main_signal' in item:
                main_signal_data = item['main_signal'].copy()
                main_signal_data['current_price'] = item.get('current_price')
                
                parsed_signal = SignalDataParser._parse_single_signal(
                    main_signal_data, ticker, timeframe
                )
                if parsed_signal:
                    parsed_signal['signal_category'] = 'main'
                    signals.append(parsed_signal)
            
            if 'correction_signal' in item:
                correction_signal_data = item['correction_signal'].copy()  
                correction_signal_data['current_price'] = item.get('current_price')
                
                parsed_signal = SignalDataParser._parse_single_signal(
                    correction_signal_data, ticker, timeframe
                )
                if parsed_signal:
                    parsed_signal['signal_category'] = 'correction'
                    signals.append(parsed_signal)
            
            # Обычный формат сигнала (1h, 4h, 1d)
            if not signals:  # Если не нашли main/correction сигналы
                parsed_signal = SignalDataParser._parse_single_signal(item, ticker, timeframe)
                if parsed_signal:
                    parsed_signal['signal_category'] = 'main'
                    signals.append(parsed_signal)
            
            return signals
            
        except Exception as e:
            logger.error(f"Ошибка обработки элемента таймфрейма {timeframe}: {e}")
            return []
    
    @staticmethod
    def _parse_single_signal(data: Dict[str, Any], ticker: str, timeframe: str) -> Optional[Dict[str, Any]]:
        """
        Парсит данные одного сигнала
        
        Args:
            data: Данные сигнала
            ticker: Тикер
            timeframe: Таймфрейм
            
        Returns:
            Dict с нормализованными данными сигнала или None при ошибке
        """
        try:
            # Извлекаем основные поля с учетом реальной структуры API
            signal_type = SignalDataParser._extract_field(
                data, ['type', 'signal', 'signal_type', 'direction', 'side'], 'HOLD'
            )
            
            entry_price = SignalDataParser._extract_numeric_field(
                data, ['entry', 'entry_price', 'price']
            )
            
            take_profit = SignalDataParser._extract_numeric_field(
                data, ['tp', 'take_profit', 'target', 'take']
            )
            
            stop_loss = SignalDataParser._extract_numeric_field(
                data, ['sl', 'stop_loss', 'stop', 'stoploss']
            )
            
            confidence = SignalDataParser._extract_numeric_field(
                data, ['confidence', 'prob', 'probability', 'conf']
            )
            
            current_price = SignalDataParser._extract_numeric_field(
                data, ['current_price', 'price', 'current', 'last_price']
            )
            
            risk_reward = SignalDataParser._extract_numeric_field(
                data, ['risk_reward', 'rr', 'risk_to_reward', 'r_r']
            )
            
            # Нормализуем тип сигнала
            signal_type = SignalDataParser._normalize_signal_type(signal_type)
            
            # Проверяем обязательные поля
            if not entry_price:
                logger.warning(f"Отсутствует entry_price для {ticker} {timeframe}")
                return None
            
            if signal_type not in ['LONG', 'SHORT', 'HOLD']:
                logger.warning(f"Неизвестный тип сигнала '{signal_type}' для {ticker} {timeframe}")
                return None
            
            # Формируем результат
            result = {
                'ticker': ticker,
                'timeframe': timeframe,
                'signal_type': signal_type,
                'entry_price': float(entry_price),
                'take_profit': float(take_profit) if take_profit else None,
                'stop_loss': float(stop_loss) if stop_loss else None,
                'confidence': float(confidence) if confidence else None,
                'risk_reward': float(risk_reward) if risk_reward else None,
                'current_price': float(current_price) if current_price else float(entry_price),
                'status': 'new',
                'created_at': datetime.utcnow()
            }
            
            logger.debug(f"Обработан сигнал {ticker} {timeframe}: {signal_type}")
            return result
            
        except Exception as e:
            logger.error(f"Ошибка обработки сигнала {ticker} {timeframe}: {e}")
            return None
    
    @staticmethod
    def _extract_field(data: Dict, possible_keys: List[str], default: Any = None) -> Any:
        """Извлекает поле по списку возможных ключей"""
        for key in possible_keys:
            if key in data and data[key] is not None:
                return data[key]
        return default
    
    @staticmethod
    def _extract_numeric_field(data: Dict, possible_keys: List[str]) -> Optional[float]:
        """Извлекает числовое поле"""
        value = SignalDataParser._extract_field(data, possible_keys)
        if value is not None:
            try:
                return float(value)
            except (ValueError, TypeError):
                pass
        return None
    
    @staticmethod
    def _normalize_signal_type(signal_type: str) -> str:
        """Нормализует тип сигнала к стандартному формату"""
        if not signal_type:
            return 'HOLD'
        
        signal_type = str(signal_type).upper().strip()
        
        # Возможные варианты для LONG
        if signal_type in ['LONG', 'BUY', '1', 'UP', 'BULL', 'BULLISH']:
            return 'LONG'
        
        # Возможные варианты для SHORT
        if signal_type in ['SHORT', 'SELL', '-1', 'DOWN', 'BEAR', 'BEARISH']:
            return 'SHORT'
        
        # По умолчанию HOLD
        return 'HOLD'