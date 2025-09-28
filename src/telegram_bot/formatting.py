"""
Форматирование сообщений для Telegram бота
"""
import os
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
import pytz

def get_kyiv_timezone():
    """Получить киевский часовой пояс"""
    return pytz.timezone('Europe/Kyiv')

def format_datetime_kyiv(dt: datetime) -> str:
    """Форматировать datetime в киевском времени"""
    if dt.tzinfo is None:
        # Предполагаем, что это UTC
        dt = dt.replace(tzinfo=timezone.utc)
    
    kyiv_tz = get_kyiv_timezone()
    local_dt = dt.astimezone(kyiv_tz)
    return local_dt.strftime('%d.%m.%Y %H:%M:%S (Kyiv)')

def format_confidence(confidence: float) -> str:
    """Форматировать confidence с предупреждениями"""
    conf_str = f"{confidence:.0f}%"
    
    if confidence >= 90:
        conf_str += " ⚠️"
    elif confidence < 50:
        conf_str += " (слабый сигнал)"
    
    return conf_str

def format_take_profit(tp_list: List[float]) -> str:
    """Форматировать список take profit"""
    if not tp_list:
        return "—"
    
    if len(tp_list) == 1:
        return f"{tp_list[0]:.4f}"
    
    return ", ".join(f"{tp:.4f}" for tp in tp_list)

def format_price(price: Optional[float]) -> str:
    """Форматировать цену"""
    if price is None:
        return "—"
    return f"{price:.4f}"

def _format_signal_line(frame: Dict[str, Any]) -> str:
    """Форматировать одну строку сигнала"""
    tf = frame['tf']
    direction = frame.get('direction', 'NEUTRAL')
    entry = format_price(frame.get('entry'))
    tp = format_take_profit(frame.get('tp', []))
    sl = format_price(frame.get('sl'))
    confidence = frame.get('confidence', 0)
    
    # Форматируем направление с жирным шрифтом
    if direction in ['LONG', 'SHORT']:
        dir_formatted = f"<b>{direction}</b>"
    else:
        dir_formatted = direction
    
    # Форматируем confidence
    conf_formatted = format_confidence(confidence)
    
    # Форматируем строку
    tf_padded = f"{tf}:"
    if len(tf_padded) < 4:
        tf_padded = tf_padded.ljust(4)
    
    return (f"{tf_padded} {dir_formatted} | "
            f"entry: {entry} | "
            f"tp: {tp} | "
            f"sl: {sl} | "
            f"conf: {conf_formatted}")

def format_signal_frames(signal_data: Dict[str, Any], source_type: str = "API") -> str:
    """
    Форматировать сигналы по всем таймфреймам
    
    Args:
        signal_data: Данные сигналов
        source_type: "API" или "DB"
    """
    if not signal_data or not signal_data.get('frames'):
        return "❌ Нет данных по данному тикеру"
    
    pair = signal_data['pair']
    frames = signal_data['frames']
    source = signal_data.get('source', 'Unknown')
    
    # Заголовок
    if source_type == "API":
        title = f"<b>{pair}</b> · Текущая ситуация (онлайн)"
        time_str = format_datetime_kyiv(datetime.now(timezone.utc))
        time_line = f"<code>{time_str}</code>"
    else:
        title = f"<b>{pair}</b> · Последний сохранённый сигнал"
        stored_at = signal_data.get('stored_at')
        if stored_at:
            time_str = format_datetime_kyiv(stored_at)
            time_line = f"<code>as of {time_str}</code>"
        else:
            time_line = "<code>время неизвестно</code>"
    
    lines = [title, time_line, ""]
    
    # Группируем фреймы по категориям и таймфреймам
    tf_order = {'15m': 1, '1h': 2, '4h': 3, '1d': 4}
    main_frames = {}
    correction_frames = {}
    
    for frame in frames:
        tf = frame['tf']
        category = frame.get('category', 'main')
        
        if category == 'correction':
            correction_frames[tf] = frame
        else:
            main_frames[tf] = frame
    
    # Форматируем MAIN сигналы
    if main_frames:
        lines.append("<b>🎯 MAIN SIGNALS</b>")
        
        for tf in sorted(main_frames.keys(), key=lambda x: tf_order.get(x, 999)):
            frame = main_frames[tf]
            formatted_line = _format_signal_line(frame)
            lines.append(formatted_line)
    
    # Форматируем CORRECTION сигналы (всегда показываем заголовок)
    lines.append("")
    lines.append("<b>⚡ CORRECTION SIGNALS</b>")
    
    if correction_frames:
        for tf in sorted(correction_frames.keys(), key=lambda x: tf_order.get(x, 999)):
            frame = correction_frames[tf]
            formatted_line = _format_signal_line(frame)
            lines.append(formatted_line)
    else:
        lines.append("<i>Нет данных для коррекции</i>")
    
    # Добавляем источник
    lines.extend(["", f"<i>Источник: {source}</i>"])
    
    return "\n".join(lines)

def format_signal_history(history: List[Dict[str, Any]], ticker: str) -> str:
    """Форматировать историю сигналов"""
    if not history:
        return f"❌ История сигналов для {ticker}USDT пуста"
    
    lines = [f"📜 История сигналов {ticker}USDT:", ""]
    
    for signal in history:
        tf = signal['timeframe']
        direction = signal['signal_type']
        entry = format_price(signal.get('entry_price'))
        tp = format_price(signal.get('take_profit'))
        sl = format_price(signal.get('stop_loss'))
        confidence = signal.get('confidence', 0)
        status = signal.get('status', 'unknown')
        created_at = signal['created_at']
        
        # Форматируем статус
        status_emoji = {
            'new': '🆕 новый',
            'active': '⏳ активен',
            'entry_hit': '✅ вход исполнен',
            'tp_hit': '🎯 тейк-профит',
            'sl_hit': '❌ стоп-лосс',
            'closed': '📝 закрыт'
        }.get(status, f"❓ {status}")
        
        # Форматируем время
        time_str = format_datetime_kyiv(created_at)
        
        # Форматируем confidence
        conf_formatted = format_confidence(confidence)
        
        line = (f"[{tf}] <b>{direction}</b> | "
                f"entry: {entry} | "
                f"tp: {tp} | "
                f"sl: {sl} | "
                f"conf: {conf_formatted} | "
                f"{status_emoji}")
        
        lines.append(line)
        lines.append(f"    <i>{time_str}</i>")
        lines.append("")
    
    return "\n".join(lines)

def format_subscriptions(subscriptions: List[Dict[str, str]], telegram_id: int) -> str:
    """Форматировать список подписок пользователя"""
    if not subscriptions:
        return ("📌 У тебя пока нет подписок.\n\n"
                "Используй команды:\n"
                "/subscribe TICKER [15m|1h] - подписаться на тикер\n"
                "/subscribeall - подписаться на все тикеры")
    
    lines = ["📌 Твои подписки:", ""]
    
    for sub in subscriptions:
        ticker = sub['ticker']
        frequency = sub['frequency']
        created = sub['created_at']
        
        freq_emoji = "🕐" if frequency == '15m' else "🕑"
        lines.append(f"• {ticker} {freq_emoji} {frequency} <i>(с {created})</i>")
    
    lines.extend(["", "Управление подписками:"])
    lines.append("/subscribe TICKER [15m|1h] - изменить/добавить")
    lines.append("/unsubscribe TICKER - отписаться")
    lines.append("/subscribeall - подписаться на все")
    lines.append("/unsubscribeall - отписаться от всех")
    
    return "\n".join(lines)

# Шаблоны сообщений
START_MESSAGE = """👋 Привет! Я бот для анализа торговых сигналов CryptoMaxa.

<b>Основные команды:</b>
/signal TICKER - текущий сигнал (онлайн, без записи в БД)
/last TICKER - последний сохранённый сигнал из базы
/history TICKER - история сигналов

<b>Управление подписками:</b>
/subscribe TICKER [15m|1h] - подписаться на тикер
/unsubscribe TICKER - отписаться от тикера
/mytickers - список твоих подписок

<b>Тестирование:</b>
/test_notification - отправить тестовое уведомление

<b>Примеры:</b>
<code>/signal BTC</code> - текущая ситуация по BTCUSDT
<code>/last ETH</code> - последний сигнал по ETHUSDT из базы
<code>/subscribe BTC 15m</code> - подписка на BTC с уведомлениями каждые 15 минут

<b>📢 Уведомления:</b>
После подписки вы будете получать автоматические уведомления о новых сигналах каждые 15 минут (по расписанию системы).

<i>Тикеры указываются без USDT (BTC, ETH, AVAX и т.д.)</i>"""

ERROR_MESSAGES = {
    'ticker_required': '❌ Укажи тикер. Например: <code>/signal BTC</code>',
    'api_unavailable': '⚠️ API временно недоступен. Попробуй позже или используй /last для данных из базы.',
    'no_data_in_db': '❌ Для {} в базе пока пусто. Сначала дождись новых сигналов или используй <code>/signal {}</code> для текущей ситуации.',
    'ticker_not_found': '❌ Тикер {} не найден.',
    'subscription_exists': '✅ Ты уже подписан на {}. Частота обновлена на {}.',
    'subscription_created': '✅ Подписка на {} создана с частотой {}.',
    'subscription_failed': '❌ Ошибка при создании подписки. Попробуй еще раз.',
    'unsubscribe_success': '❌ Подписка на {} отменена.',
    'unsubscribe_not_found': '❌ Ты не подписан на {}.',
    'unsubscribe_failed': '❌ Ошибка при отмене подписки. Попробуй еще раз.',
    'invalid_frequency': '❌ Неверная частота. Используй 15m или 1h.',
    'rate_limit': '⏱ Слишком часто. Попробуй через {} секунд.',
    'global_limit': '🚫 Превышен глобальный лимит запросов. Попробуй через минуту.'
}