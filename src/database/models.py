"""
SQLAlchemy модели для базы данных
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, BigInteger, Boolean, 
    Numeric, DateTime, Text, ForeignKey, Index, create_engine
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

Base = declarative_base()

class User(Base):
    """Пользователи Telegram бота"""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    username = Column(String(255))
    subscribed_all = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Связь с подписками
    subscriptions = relationship("Subscription", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User(telegram_id={self.telegram_id}, username='{self.username}')>"

class Subscription(Base):
    """Подписки пользователей на тикеры"""
    __tablename__ = 'subscriptions'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    ticker = Column(String(20), nullable=False)
    frequency = Column(String(10), nullable=False, default='15m')  # Частота получения сигналов
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Связь с пользователем
    user = relationship("User", back_populates="subscriptions")
    
    # Уникальная пара пользователь-тикер
    __table_args__ = (
        Index('idx_user_ticker', 'user_id', 'ticker', unique=True),
    )
    
    def __repr__(self):
        return f"<Subscription(user_id={self.user_id}, ticker='{self.ticker}', frequency='{self.frequency}')>"

class Signal(Base):
    """Торговые сигналы"""
    __tablename__ = 'signals'
    
    id = Column(Integer, primary_key=True)
    ticker = Column(String(20), nullable=False)
    timeframe = Column(String(10), nullable=False)
    signal_type = Column(String(10), nullable=False)  # LONG или SHORT
    entry_price = Column(Numeric(18, 8), nullable=False)
    take_profit = Column(Numeric(18, 8))
    stop_loss = Column(Numeric(18, 8))
    confidence = Column(Numeric(5, 2))
    risk_reward = Column(Numeric(6, 2))
    current_price = Column(Numeric(18, 8))
    status = Column(String(20), default='new')  # new, entry_hit, tp_hit, sl_hit, active, closed
    
    # Correction signal fields
    is_main_signal = Column(Boolean, default=True)  # True для основного сигнала, False для коррекционного
    correction_type = Column(String(10))  # LONG или SHORT для коррекционного сигнала
    correction_entry = Column(Numeric(18, 8))
    correction_tp = Column(Numeric(18, 8))  
    correction_sl = Column(Numeric(18, 8))
    correction_confidence = Column(Numeric(5, 2))
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Индексы
    __table_args__ = (
        Index('idx_signals_ticker_tf', 'ticker', 'timeframe'),
        Index('idx_signals_status', 'status'),
        Index('idx_signals_created_at', 'created_at'),
    )
    
    def __repr__(self):
        return f"<Signal(ticker='{self.ticker}', timeframe='{self.timeframe}', type='{self.signal_type}', status='{self.status}')>"

class ErrorLog(Base):
    """Логи ошибок"""
    __tablename__ = 'error_logs'
    
    id = Column(Integer, primary_key=True)
    source = Column(String(50))  # API, Telegram, Database, etc.
    message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<ErrorLog(source='{self.source}', created_at='{self.created_at}')>"