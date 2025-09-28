"""
Система отправки уведомлений подписчикам
"""
import asyncio
import logging
from typing import List, Dict, Any
from datetime import datetime

from src.database.connection import db_manager
from src.database.models import User, Subscription, Signal
from src.telegram_bot.formatting import format_signal_frames
from src.telegram_bot.bot import get_bot

logger = logging.getLogger(__name__)

class NotificationService:
    """Сервис для отправки уведомлений подписчикам"""
    
    @staticmethod
    async def send_signal_notifications(ticker: str, signals_data: Dict[str, Any]):
        """
        Отправляет уведомления подписчикам о новых сигналах
        
        Args:
            ticker: Тикер (например, 'AVAX')  
            signals_data: Данные сигналов в формате как для format_signal_frames
        """
        try:
            db_manager.init_connection()
            
            with db_manager.get_session() as session:
                # Ищем подписки на этот тикер
                ticker_pair = f"{ticker}USDT"
                subscriptions = session.query(Subscription).filter_by(
                    ticker=ticker_pair
                ).join(User).all()
                
                if not subscriptions:
                    logger.debug(f"Нет подписчиков на {ticker_pair}")
                    return
                
                logger.info(f"📢 Отправка уведомлений {len(subscriptions)} подписчикам на {ticker_pair}")
                
                # Форматируем сообщение
                message_text = format_signal_frames(signals_data, "Уведомление")
                
                # Отправляем каждому подписчику
                sent_count = 0
                error_count = 0
                
                # Получаем экземпляр бота
                bot = get_bot()
                
                for sub in subscriptions:
                    try:
                        await bot.send_message(
                            chat_id=sub.user.telegram_id,
                            text=message_text,
                            parse_mode='HTML'
                        )
                        sent_count += 1
                        logger.debug(f"✅ Отправлено пользователю {sub.user.telegram_id}")
                        
                        # Небольшая задержка между отправками
                        await asyncio.sleep(0.1)
                        
                    except Exception as e:
                        error_count += 1
                        logger.error(f"❌ Ошибка отправки пользователю {sub.user.telegram_id}: {e}")
                
                logger.info(f"📊 Уведомления {ticker_pair}: отправлено {sent_count}, ошибок {error_count}")
                
        except Exception as e:
            logger.error(f"💥 Ошибка в send_signal_notifications для {ticker}: {e}")
    
    @staticmethod
    async def send_batch_notifications(signals_batch: Dict[str, Dict[str, Any]]):
        """
        Отправляет уведомления по пакету сигналов (для всех тикеров)
        
        Args:
            signals_batch: {ticker: signals_data} для всех тикеров
        """
        logger.info(f"📢 Начало отправки пакета уведомлений для {len(signals_batch)} тикеров")
        
        for ticker, signals_data in signals_batch.items():
            if signals_data and signals_data.get('frames'):
                await NotificationService.send_signal_notifications(ticker, signals_data)
                
        logger.info("📢 Пакет уведомлений обработан")
    
    @staticmethod
    def get_subscribers_count() -> Dict[str, int]:
        """Получить статистику подписчиков"""
        try:
            db_manager.init_connection()
            
            with db_manager.get_session() as session:
                # Всего подписок
                total_subs = session.query(Subscription).count()
                
                # Уникальных пользователей
                unique_users = session.query(User).join(Subscription).distinct().count()
                
                # Топ тикеров по подпискам
                top_tickers = session.query(
                    Subscription.ticker, 
                    session.query(Subscription.id).filter_by(ticker=Subscription.ticker).count().label('count')
                ).group_by(Subscription.ticker).order_by(session.text('count DESC')).limit(5).all()
                
                return {
                    'total_subscriptions': total_subs,
                    'unique_users': unique_users,
                    'top_tickers': [{'ticker': t.ticker, 'count': t.count} for t in top_tickers]
                }
                
        except Exception as e:
            logger.error(f"Ошибка получения статистики подписчиков: {e}")
            return {
                'total_subscriptions': 0,
                'unique_users': 0,
                'top_tickers': []
            }