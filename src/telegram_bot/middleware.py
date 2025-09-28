"""
Middleware для Telegram бота
"""
import time
import logging
from collections import defaultdict
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message

logger = logging.getLogger(__name__)

class LoggingMiddleware(BaseMiddleware):
    """Middleware для логирования всех команд"""
    
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        user_id = event.from_user.id if event.from_user else "Unknown"
        username = event.from_user.username if event.from_user else "Unknown"
        text = event.text or "No text"
        
        logger.info(f"Command from user {user_id} (@{username}): {text}")
        
        start_time = time.time()
        try:
            result = await handler(event, data)
            duration = time.time() - start_time
            logger.info(f"Command processed in {duration:.3f}s")
            return result
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Command failed after {duration:.3f}s: {e}")
            raise

class RateLimitMiddleware(BaseMiddleware):
    """Middleware для rate limiting"""
    
    def __init__(self):
        # Хранение времени последних запросов для каждого пользователя
        self.user_last_request: Dict[int, float] = {}
        # Хранение количества глобальных запросов /signal за минуту
        self.global_signal_requests: list = []
        
        # Настройки
        self.user_cooldown = 2.0  # 2 секунды между запросами /signal для пользователя
        self.global_limit = 10    # 10 запросов /signal в минуту глобально
        self.global_window = 60   # окно в секундах
    
    def _clean_global_requests(self):
        """Очистка старых глобальных запросов"""
        now = time.time()
        self.global_signal_requests = [
            req_time for req_time in self.global_signal_requests 
            if now - req_time < self.global_window
        ]
    
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        # Проверяем rate limit только для команды /signal
        if event.text and event.text.startswith('/signal'):
            user_id = event.from_user.id if event.from_user else 0
            now = time.time()
            
            # Проверка пользовательского лимита
            if user_id in self.user_last_request:
                time_since_last = now - self.user_last_request[user_id]
                if time_since_last < self.user_cooldown:
                    remaining = self.user_cooldown - time_since_last
                    await event.answer(
                        f"⏱ Слишком часто. Попробуй через {remaining:.1f} секунд."
                    )
                    return
            
            # Проверка глобального лимита
            self._clean_global_requests()
            if len(self.global_signal_requests) >= self.global_limit:
                await event.answer(
                    "🚫 Превышен глобальный лимит запросов /signal. "
                    "Попробуй через минуту."
                )
                return
            
            # Сохраняем время запроса
            self.user_last_request[user_id] = now
            self.global_signal_requests.append(now)
        
        return await handler(event, data)