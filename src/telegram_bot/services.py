"""
Сервисы для работы с данными Telegram бота
"""
import os
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
import requests
from sqlalchemy.orm import Session
from sqlalchemy import desc

from ..database import get_db_session, db_manager
from ..database.models import User, Subscription, Signal

logger = logging.getLogger(__name__)

# Инициализируем БД при импорте модуля
def _init_db():
    """Инициализация БД для телеграм-бота"""
    if not db_manager.engine:
        success = db_manager.init_connection()
        if not success:
            logger.error("Не удалось инициализировать БД для телеграм-бота")
        else:
            logger.info("БД успешно инициализирована для телеграм-бота")

_init_db()

class UserService:
    """Сервис для работы с пользователями"""
    
    @staticmethod
    def get_or_create_user(telegram_id: int, username: str = None) -> User:
        """Получить или создать пользователя"""
        with get_db_session() as session:
            user = session.query(User).filter_by(telegram_id=telegram_id).first()
            
            if not user:
                user = User(
                    telegram_id=telegram_id,
                    username=username
                )
                session.add(user)
                session.commit()
                session.refresh(user)
                logger.info(f"Создан новый пользователь: {telegram_id} (@{username})")
                
                # Создаем новый объект с данными для возврата
                return User(
                    id=user.id,
                    telegram_id=user.telegram_id,
                    username=user.username
                )
            elif user.username != username and username:
                # Обновляем username если изменился
                user.username = username
                session.commit()
            
            # Возвращаем объект с данными
            return User(
                id=user.id,
                telegram_id=user.telegram_id,
                username=user.username
            )

class SubscriptionService:
    """Сервис для работы с подписками"""
    
    @staticmethod
    def subscribe_user(telegram_id: int, ticker: str, frequency: str = '15m') -> bool:
        """Подписать пользователя на тикер"""
        try:
            with get_db_session() as session:
                user = session.query(User).filter_by(telegram_id=telegram_id).first()
                if not user:
                    return False
                
                # Проверяем, есть ли уже подписка
                existing = session.query(Subscription).filter_by(
                    user_id=user.id, 
                    ticker=ticker
                ).first()
                
                if existing:
                    # Обновляем частоту если подписка уже есть
                    existing.frequency = frequency
                    session.commit()
                    logger.info(f"Обновлена подписка пользователя {telegram_id} на {ticker} с частотой {frequency}")
                    return True
                else:
                    # Создаем новую подписку
                    subscription = Subscription(
                        user_id=user.id,
                        ticker=ticker,
                        frequency=frequency
                    )
                    session.add(subscription)
                    session.commit()
                    logger.info(f"Создана подписка пользователя {telegram_id} на {ticker} с частотой {frequency}")
                    return True
                    
        except Exception as e:
            logger.error(f"Ошибка при создании подписки: {e}")
            return False
    
    @staticmethod
    def unsubscribe_user(telegram_id: int, ticker: str) -> bool:
        """Отписать пользователя от тикера"""
        try:
            with get_db_session() as session:
                user = session.query(User).filter_by(telegram_id=telegram_id).first()
                if not user:
                    return False
                
                subscription = session.query(Subscription).filter_by(
                    user_id=user.id, 
                    ticker=ticker
                ).first()
                
                if subscription:
                    session.delete(subscription)
                    session.commit()
                    logger.info(f"Удалена подписка пользователя {telegram_id} на {ticker}")
                    return True
                return False
                
        except Exception as e:
            logger.error(f"Ошибка при удалении подписки: {e}")
            return False
    
    @staticmethod
    def get_user_subscriptions(telegram_id: int) -> List[Dict[str, str]]:
        """Получить все подписки пользователя"""
        try:
            with get_db_session() as session:
                user = session.query(User).filter_by(telegram_id=telegram_id).first()
                if not user:
                    return []
                
                subscriptions = session.query(Subscription).filter_by(user_id=user.id).all()
                return [
                    {
                        'ticker': sub.ticker,
                        'frequency': sub.frequency,
                        'created_at': sub.created_at.strftime('%d.%m.%Y %H:%M')
                    }
                    for sub in subscriptions
                ]
                
        except Exception as e:
            logger.error(f"Ошибка при получении подписок: {e}")
            return []

class SignalService:
    """Сервис для работы с сигналами"""
    
    @staticmethod
    def get_online_signal(ticker: str) -> Optional[Dict[str, Any]]:
        """Получить онлайн сигнал по тикеру без записи в БД"""
        try:
            # Настройки API
            api_base = os.getenv('API_BASE', 'http://194.135.94.212:8001')
            lang = os.getenv('LANG', 'uk')
            model_type = os.getenv('MODEL_TYPE', 'xgb')
            
            pair = f"{ticker.upper()}USDT"
            url = f"{api_base}/multi_signal"
            
            params = {
                'pair': pair,
                'timeframes': ['15m', '1h', '4h', '1d'],
                'lang': lang,
                'model_type': model_type
            }
            
            logger.info(f"Запрос онлайн сигнала для {pair}")
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            logger.debug(f"API ответ для {pair}: {data}")
            
            # Преобразуем в унифицированную структуру
            result = {
                'pair': pair,
                'generated_at': datetime.now(timezone.utc).isoformat(),
                'frames': [],
                'source': f"API ({model_type}, lang={lang})"
            }
            
            # Парсим ответ - должен быть массив
            if isinstance(data, list):
                # Формат массива объектов
                for item in data:
                    if isinstance(item, dict):
                        tf = item.get('timeframe')
                        if not tf:
                            continue
                        
                        # Получаем сигнал - может быть в разных полях
                        signal_type = None
                        entry = None
                        tp = None
                        sl = None
                        confidence = 0
                        
                        if 'signal' in item:
                            # Формат для 1h, 4h, 1d
                            signal_type = item['signal']
                            entry = item.get('entry_price')
                            tp = item.get('take_profit')
                            sl = item.get('stop_loss')
                            confidence = item.get('confidence', 0)
                        elif 'main_signal' in item:
                            # Формат с main_signal и correction_signal
                            # Обрабатываем main signal
                            main_signal = item['main_signal']
                            main_frame = {
                                'tf': tf,
                                'category': 'main',
                                'direction': main_signal.get('type', '').upper(),
                                'entry': float(main_signal.get('entry')) if main_signal.get('entry') else None,
                                'tp': [float(main_signal.get('tp'))] if main_signal.get('tp') else [],
                                'sl': float(main_signal.get('sl')) if main_signal.get('sl') else None,
                                'confidence': float(main_signal.get('confidence', 0)),
                                'current_price': float(item.get('current_price', 0)) if item.get('current_price') else None
                            }
                            if main_frame['direction'] and main_frame['entry']:
                                result['frames'].append(main_frame)
                            
                            # Обрабатываем correction signal если есть
                            if 'correction_signal' in item:
                                correction_signal = item['correction_signal']
                                correction_frame = {
                                    'tf': tf,
                                    'category': 'correction',
                                    'direction': correction_signal.get('type', '').upper(),
                                    'entry': float(correction_signal.get('entry')) if correction_signal.get('entry') else None,
                                    'tp': [float(correction_signal.get('tp'))] if correction_signal.get('tp') else [],
                                    'sl': float(correction_signal.get('sl')) if correction_signal.get('sl') else None,
                                    'confidence': float(correction_signal.get('confidence', 0)),
                                    'current_price': float(item.get('current_price', 0)) if item.get('current_price') else None
                                }
                                if correction_frame['direction'] and correction_frame['entry']:
                                    result['frames'].append(correction_frame)
                        
                        if signal_type and entry:
                            frame = {
                                'tf': tf,
                                'category': 'main',
                                'direction': signal_type.upper(),
                                'entry': float(entry) if entry else None,
                                'tp': [float(tp)] if tp else [],
                                'sl': float(sl) if sl else None,
                                'confidence': float(confidence) if confidence else 0,
                                'current_price': float(item.get('current_price', 0)) if item.get('current_price') else None
                            }
                            result['frames'].append(frame)
            elif isinstance(data, dict):
                # Если API вернул словарь вместо массива
                logger.warning(f"API вернул dict вместо list для {pair}: {data}")
                return None
            else:
                logger.warning(f"Неожиданная структура API ответа для {pair}: {type(data)} - {data}")
                return None
            
            return result
            
        except requests.RequestException as e:
            logger.error(f"Ошибка API запроса для {ticker}: {e}")
            return None
        except Exception as e:
            logger.error(f"Ошибка при обработке онлайн сигнала для {ticker}: {e}")
            return None
    
    @staticmethod
    def get_last_signals_from_db(ticker: str) -> Optional[Dict[str, Any]]:
        """Получить последние сигналы по тикеру из БД"""
        try:
            with get_db_session() as session:
                # В БД тикеры хранятся без USDT (только базовый тикер)
                base_ticker = ticker.upper()
                if base_ticker.endswith('USDT'):
                    base_ticker = base_ticker[:-4]
                
                pair = f"{base_ticker}USDT"  # Для отображения пользователю
                
                result = {
                    'pair': pair,
                    'frames': [],
                    'source': "БД (последний fetcher)"
                }
                
                # Получаем последние сигналы для каждого таймфрейма
                for tf in ['15m', '1h', '4h', '1d']:
                    signal = session.query(Signal).filter_by(
                        ticker=base_ticker,  # Ищем по базовому тикеру
                        timeframe=tf
                    ).order_by(desc(Signal.created_at)).first()
                    
                    if signal:
                        frame = {
                            'tf': tf,
                            'direction': signal.signal_type.upper(),
                            'entry': float(signal.entry_price) if signal.entry_price else None,
                            'tp': [float(signal.take_profit)] if signal.take_profit else [],
                            'sl': float(signal.stop_loss) if signal.stop_loss else None,
                            'confidence': float(signal.confidence) if signal.confidence else 0,
                            'created_at': signal.created_at,
                            'status': signal.status
                        }
                        
                        # Добавляем correction сигнал если есть
                        if hasattr(signal, 'correction_type') and signal.correction_type:
                            frame['correction'] = {
                                'direction': signal.correction_type.upper(),
                                'entry': float(signal.correction_entry) if signal.correction_entry else None,
                                'tp': [float(signal.correction_tp)] if signal.correction_tp else [],
                                'sl': float(signal.correction_sl) if signal.correction_sl else None,
                                'confidence': float(signal.correction_confidence) if signal.correction_confidence else 0
                            }
                        
                        result['frames'].append(frame)
                        
                        # Сохраняем время создания самого свежего сигнала
                        if not result.get('stored_at'):
                            result['stored_at'] = signal.created_at
                
                return result if result['frames'] else None
                
        except Exception as e:
            logger.error(f"Ошибка при получении сигналов из БД для {ticker}: {e}")
            return None
    
    @staticmethod
    def get_signal_history(ticker: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Получить историю сигналов по тикеру"""
        try:
            with get_db_session() as session:
                # В БД тикеры хранятся без USDT (только базовый тикер)
                base_ticker = ticker.upper()
                if base_ticker.endswith('USDT'):
                    base_ticker = base_ticker[:-4]
                
                signals = session.query(Signal).filter_by(
                    ticker=base_ticker
                ).order_by(desc(Signal.created_at)).limit(limit).all()
                
                result = []
                for signal in signals:
                    # Основной сигнал
                    signal_data = {
                        'timeframe': signal.timeframe,
                        'signal_type': signal.signal_type.upper(),
                        'entry_price': float(signal.entry_price) if signal.entry_price else None,
                        'take_profit': float(signal.take_profit) if signal.take_profit else None,
                        'stop_loss': float(signal.stop_loss) if signal.stop_loss else None,
                        'confidence': float(signal.confidence) if signal.confidence else 0,
                        'status': signal.status,
                        'created_at': signal.created_at
                    }
                    
                    # Добавляем correction сигнал если есть
                    if hasattr(signal, 'correction_type') and signal.correction_type:
                        signal_data['correction'] = {
                            'type': signal.correction_type.upper(),
                            'entry': float(signal.correction_entry) if signal.correction_entry else None,
                            'tp': float(signal.correction_tp) if signal.correction_tp else None,
                            'sl': float(signal.correction_sl) if signal.correction_sl else None,
                            'confidence': float(signal.correction_confidence) if signal.correction_confidence else 0
                        }
                    
                    result.append(signal_data)
                
                return result
                
        except Exception as e:
            logger.error(f"Ошибка при получении истории сигналов для {ticker}: {e}")
            return []