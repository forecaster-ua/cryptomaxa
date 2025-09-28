"""
CRUD операции для работы с базой данных
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_, or_

from .models import User, Subscription, Signal, ErrorLog


class UserCRUD:
    """CRUD операции для пользователей"""
    
    @staticmethod
    def create_user(session: Session, telegram_id: int, username: str = None) -> User:
        """Создание нового пользователя"""
        user = User(telegram_id=telegram_id, username=username)
        session.add(user)
        session.flush()
        return user
    
    @staticmethod
    def get_user_by_telegram_id(session: Session, telegram_id: int) -> Optional[User]:
        """Получение пользователя по Telegram ID"""
        return session.query(User).filter(User.telegram_id == telegram_id).first()
    
    @staticmethod
    def get_or_create_user(session: Session, telegram_id: int, username: str = None) -> User:
        """Получение существующего или создание нового пользователя"""
        user = UserCRUD.get_user_by_telegram_id(session, telegram_id)
        if not user:
            user = UserCRUD.create_user(session, telegram_id, username)
        elif username and user.username != username:
            user.username = username
        return user
    
    @staticmethod
    def update_subscribed_all(session: Session, telegram_id: int, subscribed_all: bool):
        """Обновление флага подписки на все тикеры"""
        user = UserCRUD.get_user_by_telegram_id(session, telegram_id)
        if user:
            user.subscribed_all = subscribed_all


class SubscriptionCRUD:
    """CRUD операции для подписок"""
    
    @staticmethod
    def add_subscription(session: Session, user_id: int, ticker: str) -> bool:
        """Добавление подписки"""
        existing = session.query(Subscription).filter(
            and_(Subscription.user_id == user_id, Subscription.ticker == ticker)
        ).first()
        
        if not existing:
            subscription = Subscription(user_id=user_id, ticker=ticker)
            session.add(subscription)
            return True
        return False
    
    @staticmethod
    def remove_subscription(session: Session, user_id: int, ticker: str) -> bool:
        """Удаление подписки"""
        subscription = session.query(Subscription).filter(
            and_(Subscription.user_id == user_id, Subscription.ticker == ticker)
        ).first()
        
        if subscription:
            session.delete(subscription)
            return True
        return False
    
    @staticmethod
    def get_user_subscriptions(session: Session, user_id: int) -> List[str]:
        """Получение списка подписок пользователя"""
        subscriptions = session.query(Subscription.ticker).filter(
            Subscription.user_id == user_id
        ).all()
        return [sub.ticker for sub in subscriptions]
    
    @staticmethod
    def clear_user_subscriptions(session: Session, user_id: int):
        """Очистка всех подписок пользователя"""
        session.query(Subscription).filter(Subscription.user_id == user_id).delete()


class SignalCRUD:
    """CRUD операции для сигналов"""
    
    @staticmethod
    def create_signal(session: Session, **kwargs) -> Signal:
        """Создание нового сигнала"""
        signal = Signal(**kwargs)
        session.add(signal)
        session.flush()
        return signal
    
    @staticmethod
    def get_latest_signal(session: Session, ticker: str, timeframe: str = None) -> Optional[Signal]:
        """Получение последнего сигнала по тикеру"""
        query = session.query(Signal).filter(Signal.ticker == ticker)
        if timeframe:
            query = query.filter(Signal.timeframe == timeframe)
        return query.order_by(desc(Signal.created_at)).first()
    
    @staticmethod
    def get_signals_history(session: Session, ticker: str, limit: int = 10) -> List[Signal]:
        """Получение истории сигналов по тикеру"""
        return session.query(Signal).filter(
            Signal.ticker == ticker
        ).order_by(desc(Signal.created_at)).limit(limit).all()
    
    @staticmethod
    def get_active_signals(session: Session) -> List[Signal]:
        """Получение активных сигналов для проверки исполнения"""
        return session.query(Signal).filter(
            Signal.status.in_(['new', 'entry_hit', 'active'])
        ).all()
    
    @staticmethod
    def update_signal_status(session: Session, signal_id: int, status: str, current_price: float = None):
        """Обновление статуса сигнала"""
        signal = session.query(Signal).filter(Signal.id == signal_id).first()
        if signal:
            signal.status = status
            if current_price is not None:
                signal.current_price = current_price


class ErrorLogCRUD:
    """CRUD операции для логов ошибок"""
    
    @staticmethod
    def log_error(session: Session, source: str, message: str):
        """Запись ошибки в лог"""
        error_log = ErrorLog(source=source, message=message)
        session.add(error_log)