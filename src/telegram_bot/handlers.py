"""
Обработчики команд Telegram бота
"""
import logging
from typing import Optional
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command, CommandStart

from .services import UserService, SubscriptionService, SignalService
from .formatting import (
    START_MESSAGE, ERROR_MESSAGES,
    format_signal_frames, format_signal_history, format_subscriptions
)

logger = logging.getLogger(__name__)

# Создаем роутер для обработчиков
router = Router()

def parse_ticker_and_frequency(args: str) -> tuple[Optional[str], Optional[str]]:
    """Парсинг тикера и частоты из аргументов команды"""
    if not args:
        return None, None
    
    parts = args.strip().upper().split()
    raw_ticker = parts[0] if parts else None
    
    # Нормализуем тикер - убираем USDT если есть, так как мы добавим его позже
    ticker = None
    if raw_ticker:
        if raw_ticker.endswith('USDT'):
            ticker = raw_ticker[:-4]  # Убираем USDT
        else:
            ticker = raw_ticker
    
    frequency = None
    
    if len(parts) > 1:
        freq = parts[1].lower()
        if freq in ['15m', '1h']:
            frequency = freq
        else:
            return ticker, 'invalid'
    
    return ticker, frequency

@router.message(CommandStart())
async def cmd_start(message: Message):
    """Обработчик команды /start"""
    user_id = message.from_user.id
    username = message.from_user.username
    
    # Регистрируем пользователя
    UserService.get_or_create_user(user_id, username)
    
    await message.answer(START_MESSAGE)

@router.message(Command('signal'))
async def cmd_signal(message: Message):
    """Обработчик команды /signal - онлайн сигнал без записи в БД"""
    args = message.text.split(' ', 1)[1] if len(message.text.split()) > 1 else ''
    ticker, _ = parse_ticker_and_frequency(args)
    
    if not ticker:
        await message.answer(ERROR_MESSAGES['ticker_required'])
        return
    
    try:
        # Отправляем сообщение о загрузке
        loading_message = await message.answer("🔄 <b>Fetching Data...</b>")
        
        # Получаем онлайн сигнал
        signal_data = SignalService.get_online_signal(ticker)
        
        if not signal_data:
            # Редактируем сообщение с ошибкой
            await loading_message.edit_text(ERROR_MESSAGES['api_unavailable'])
            return
        
        # Форматируем и редактируем сообщение с результатами
        formatted_message = format_signal_frames(signal_data, "API")
        await loading_message.edit_text(formatted_message)
        
        logger.info(f"Отправлен онлайн сигнал для {ticker} пользователю {message.from_user.id}")
        
    except Exception as e:
        logger.error(f"Ошибка при обработке /signal {ticker}: {e}")
        try:
            # Пытаемся отредактировать loading_message если оно есть
            if 'loading_message' in locals():
                await loading_message.edit_text(ERROR_MESSAGES['api_unavailable'])
            else:
                await message.answer(ERROR_MESSAGES['api_unavailable'])
        except:
            # Если редактирование не удалось, отправляем новое сообщение
            await message.answer(ERROR_MESSAGES['api_unavailable'])

@router.message(Command('last'))
async def cmd_last(message: Message):
    """Обработчик команды /last - последний сигнал из БД"""
    args = message.text.split(' ', 1)[1] if len(message.text.split()) > 1 else ''
    ticker, _ = parse_ticker_and_frequency(args)
    
    if not ticker:
        await message.answer(ERROR_MESSAGES['ticker_required'])
        return
    
    try:
        # Отправляем сообщение о загрузке
        loading_message = await message.answer("📊 <b>Fetching Data...</b>")
        
        # Получаем последние сигналы из БД
        signal_data = SignalService.get_last_signals_from_db(ticker)
        
        if not signal_data:
            # Редактируем сообщение с ошибкой
            await loading_message.edit_text(
                ERROR_MESSAGES['no_data_in_db'].format(f"{ticker}USDT", ticker)
            )
            return
        
        # Форматируем и редактируем сообщение с результатами
        formatted_message = format_signal_frames(signal_data, "DB")
        await loading_message.edit_text(formatted_message)
        
        logger.info(f"Отправлен последний сигнал для {ticker} пользователю {message.from_user.id}")
        
    except Exception as e:
        logger.error(f"Ошибка при обработке /last {ticker}: {e}")
        try:
            # Пытаемся отредактировать loading_message если оно есть
            if 'loading_message' in locals():
                await loading_message.edit_text(f"❌ Ошибка при получении данных для {ticker}")
            else:
                await message.answer(f"❌ Ошибка при получении данных для {ticker}")
        except:
            # Если редактирование не удалось, отправляем новое сообщение
            await message.answer(f"❌ Ошибка при получении данных для {ticker}")

@router.message(Command('history'))
async def cmd_history(message: Message):
    """Обработчик команды /history - история сигналов"""
    args = message.text.split(' ', 1)[1] if len(message.text.split()) > 1 else ''
    ticker, _ = parse_ticker_and_frequency(args)
    
    if not ticker:
        await message.answer(ERROR_MESSAGES['ticker_required'])
        return
    
    try:
        # Отправляем сообщение о загрузке
        loading_message = await message.answer("📜 <b>Fetching Data...</b>")
        
        # Получаем историю сигналов
        history = SignalService.get_signal_history(ticker, limit=10)
        
        # Форматируем и редактируем сообщение с результатами
        formatted_message = format_signal_history(history, ticker)
        await loading_message.edit_text(formatted_message)
        
        logger.info(f"Отправлена история для {ticker} пользователю {message.from_user.id}")
        
    except Exception as e:
        logger.error(f"Ошибка при обработке /history {ticker}: {e}")
        try:
            # Пытаемся отредактировать loading_message если оно есть
            if 'loading_message' in locals():
                await loading_message.edit_text(f"❌ Ошибка при получении истории для {ticker}")
            else:
                await message.answer(f"❌ Ошибка при получении истории для {ticker}")
        except:
            # Если редактирование не удалось, отправляем новое сообщение
            await message.answer(f"❌ Ошибка при получении истории для {ticker}")

@router.message(Command('subscribe'))
async def cmd_subscribe(message: Message):
    """Обработчик команды /subscribe - подписка на тикер"""
    args = message.text.split(' ', 1)[1] if len(message.text.split()) > 1 else ''
    ticker, frequency = parse_ticker_and_frequency(args)
    
    if not ticker:
        await message.answer(ERROR_MESSAGES['ticker_required'])
        return
    
    if frequency == 'invalid':
        await message.answer(ERROR_MESSAGES['invalid_frequency'])
        return
    
    # По умолчанию 15m
    if not frequency:
        frequency = '15m'
    
    user_id = message.from_user.id
    username = message.from_user.username
    
    # Регистрируем пользователя если нужно
    UserService.get_or_create_user(user_id, username)
    
    # Создаем подписку (нормализуем тикер)
    base_ticker = ticker.upper()
    if base_ticker.endswith('USDT'):
        base_ticker = base_ticker[:-4]  # Убираем USDT если есть
    
    ticker_pair = f"{base_ticker}USDT"  # Добавляем USDT для отображения
    success = SubscriptionService.subscribe_user(user_id, ticker_pair, frequency)
    
    if success:
        await message.answer(
            ERROR_MESSAGES['subscription_created'].format(ticker_pair, frequency)
        )
        logger.info(f"Пользователь {user_id} подписался на {ticker_pair} с частотой {frequency}")
    else:
        await message.answer(ERROR_MESSAGES['subscription_failed'])

@router.message(Command('unsubscribe'))
async def cmd_unsubscribe(message: Message):
    """Обработчик команды /unsubscribe - отписка от тикера"""
    args = message.text.split(' ', 1)[1] if len(message.text.split()) > 1 else ''
    ticker, _ = parse_ticker_and_frequency(args)
    
    if not ticker:
        await message.answer(ERROR_MESSAGES['ticker_required'])
        return
    
    user_id = message.from_user.id
    
    # Нормализуем тикер 
    base_ticker = ticker.upper()
    if base_ticker.endswith('USDT'):
        base_ticker = base_ticker[:-4]  # Убираем USDT если есть
        
    ticker_pair = f"{base_ticker}USDT"  # Добавляем USDT для отображения
    
    success = SubscriptionService.unsubscribe_user(user_id, ticker_pair)
    
    if success:
        await message.answer(ERROR_MESSAGES['unsubscribe_success'].format(ticker_pair))
        logger.info(f"Пользователь {user_id} отписался от {ticker_pair}")
    else:
        await message.answer(ERROR_MESSAGES['unsubscribe_not_found'].format(ticker_pair))

@router.message(Command('mytickers'))
async def cmd_mytickers(message: Message):
    """Обработчик команды /mytickers - список подписок"""
    user_id = message.from_user.id
    
    subscriptions = SubscriptionService.get_user_subscriptions(user_id)
    formatted_message = format_subscriptions(subscriptions, user_id)
    
    await message.answer(formatted_message)
    logger.info(f"Отправлен список подписок для пользователя {user_id}")

@router.message(Command('test_notification'))
async def cmd_test_notification(message: Message):
    """Тестовое уведомление для проверки работы подписок"""
    user_id = message.from_user.id
    
    # Проверяем, есть ли подписки у пользователя
    subscriptions = SubscriptionService.get_user_subscriptions(user_id)
    
    if not subscriptions:
        await message.answer("❌ У вас нет активных подписок для тестирования")
        return
    
    # Берем первую подписку для теста
    test_sub = subscriptions[0]
    ticker = test_sub['ticker'].replace('USDT', '')  # Убираем USDT для получения базового тикера
    
    try:
        # Получаем тестовый сигнал
        signal_data = SignalService.get_online_signal(ticker)
        
        if signal_data:
            # Отправляем как уведомление
            from .notifications import NotificationService
            await NotificationService.send_signal_notifications(ticker, signal_data)
            
            await message.answer(f"✅ Тестовое уведомление отправлено для {test_sub['ticker']}")
            logger.info(f"Отправлено тестовое уведомление пользователю {user_id} для {ticker}")
        else:
            await message.answer("❌ Не удалось получить тестовые данные")
            
    except Exception as e:
        logger.error(f"Ошибка тестового уведомления для {user_id}: {e}")
        await message.answer("❌ Ошибка при отправке тестового уведомления")

@router.message(Command('subscribeall'))
async def cmd_subscribeall(message: Message):
    """Обработчик команды /subscribeall - подписка на все тикеры"""
    # TODO: Реализовать после создания списка всех тикеров
    await message.answer("🚧 Функция в разработке. Используй /subscribe TICKER для отдельных подписок.")

@router.message(Command('unsubscribeall'))
async def cmd_unsubscribeall(message: Message):
    """Обработчик команды /unsubscribeall - отписка от всех тикеров"""
    # TODO: Реализовать массовую отписку
    await message.answer("🚧 Функция в разработке. Используй /unsubscribe TICKER для отдельных отписок.")

# Обработчик неизвестных команд
@router.message(F.text.startswith('/'))
async def unknown_command(message: Message):
    """Обработчик неизвестных команд"""
    await message.answer(
        "❓ Неизвестная команда. Используй /start для просмотра всех доступных команд."
    )

def register_handlers(dp):
    """Регистрация всех обработчиков"""
    dp.include_router(router)