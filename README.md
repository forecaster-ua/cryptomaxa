
📑 Hydra Static - техническое задание (ТЗ)
Проект: сервис для работы с торговыми сигналами + Telegram-бот

⏰ **ВАЖНО: Все временные метки должны быть в UTC!**
Система работает исключительно в UTC времени для обеспечения корректной синхронизации между компонентами API, базой данных и Telegram-ботом.

## 🚀 Быстрый запуск системы

### Управление через единый скрипт:
```bash
# Универсальный скрипт управления (без пароля sudo)
hydra start     # Запуск всей системы
hydra stop      # Остановка системы  
hydra restart   # Перезапуск
hydra status    # Проверка статуса
hydra logs      # Просмотр логов в реальном времени

# Альтернативно - полный путь к скрипту:
./scripts/hydra_system.sh start

# Экстренный быстрый запуск:
./quick_start.sh
```

### Основные команды:
- **hydra start** - Запускает планировщик сигналов + Telegram бота
- **hydra status** - Показывает статус обеих служб
- **hydra logs scheduler** - Логи сбора сигналов
- **hydra logs telegram** - Логи Telegram бота  
- **hydra check-db** - Проверка базы данных

🎯 Цель проекта
Создать сервис, который:
    1. Каждые 15 минут делает запрос к API для набора тикеров.

    2. Сохраняет все данные в PostgreSQL.

    3. Проверяет исполнение входов, стопов и тейков.

    4. Анализирует confidence и тренд.

    5. Предоставляет данные пользователю через Telegram-бота по системе подписки.


📂 Основные функции сервиса
    • Сбор данных по множеству тикеров из файла tickers.txt.

    • Хранение всех сигналов в БД.

    • Анализ сигналов (входы/стопы/тейки).

    • Сравнение confidence и комментарии ⚠️ при высоком значении или против тренда.

    • Telegram-бот: подписка на тикеры, просмотр последних сигналов, история.

    • Обработка ошибок API/Telegram/БД с логированием.


📑 Работа с API
Запрос формируется так:
http://194.135.94.212:8001/multi_signal?pair={TICKER}USDT&timeframes=15m&timeframes=1h&timeframes=4h&timeframes=1d&lang=uk&model_type=xgb
    • {TICKER}USDT берётся из списка tickers.txt.

    • Данные обновляются каждые 15 минут (время кратное 00) **по UTC**.

    • Все временные метки в БД сохраняются в UTC формате.


📂 Схема базы данных (PostgreSQL)
-- Пользователи
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    username VARCHAR(255),
    subscribed_all BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Подписки пользователей на тикеры
CREATE TABLE subscriptions (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id) ON DELETE CASCADE,
    ticker VARCHAR(20) NOT NULL,
    frequency VARCHAR(10) DEFAULT '15m' CHECK (frequency IN ('15m', '1h')), -- Частота получения сигналов
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, ticker)
);

-- Сигналы
CREATE TABLE signals (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    signal_type VARCHAR(10) NOT NULL,
    entry_price NUMERIC(18,8) NOT NULL,
    take_profit NUMERIC(18,8),
    stop_loss NUMERIC(18,8),
    confidence NUMERIC(5,2),
    risk_reward NUMERIC(6,2),
    current_price NUMERIC(18,8),
    status VARCHAR(20) DEFAULT 'new',  -- new, entry_hit, tp_hit, sl_hit, active, closed
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_signals_ticker_tf ON signals(ticker, timeframe);

-- Логи ошибок
CREATE TABLE error_logs (
    id SERIAL PRIMARY KEY,
    source VARCHAR(50),
    message TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

📊 Логика обработки сигналов
1. Вход
    • LONG: вход исполнен при current_price ≤ entry.

    • SHORT: вход исполнен при current_price ≥ entry.

2. Стоп/тейк
    • LONG: price ≤ stop_loss → стоп, price ≥ take_profit → тейк.

    • SHORT: наоборот.

3. Confidence
    • 90% → ⚠️ (опасность).

    • Если за последние 12 часов confidence >90% и сигнал против динамики → ⚠️ «сигнал против тренда».

    • <50% → «слабый сигнал».


📑 Telegram-бот

## Основные команды
    • /start – приветственное сообщение, список команд.
    • /subscribeall – подписка на все тикеры.
    • /unsubscribeall – отписка от всех тикеров.
    • /subscribe TICKER [15m|1h] – подписка на тикер с частотой (по умолчанию 15m).
    • /unsubscribe TICKER – отписка от тикера.
    • /mytickers – список подписок.
    • /signal TICKER – онлайн сигнал по тикеру (БЕЗ записи в БД).
    • /last TICKER – последний сохраненный сигнал из БД по тикеру.
    • /history TICKER – история последних сигналов (например, 10).

## Специальные команды /signal и /last

### /signal <TICKER> - онлайн сигнал
**Назначение:** получить текущую ситуацию по всем ТФ для тикера БЕЗ записи в БД.

**Особенности:**
- Тикер без USDT (например: BTC, ETH)
- Прямой запрос к API без сохранения в базу
- Таймфреймы: 15m, 1h, 4h, 1d
- Rate limit: 1 запрос в 2 сек на пользователя, 10 запросов/мин глобально
- Время ответа ≤ 2.5 сек при доступном API

### /last <TICKER> - из базы данных  
**Назначение:** выдать последний сохранённый сигнал из БД.

**Особенности:**
- Данные берутся только из БД (последние записи по каждому ТФ)
- Показывает время записи в БД
- Время ответа ≤ 150 мс при прогретом соединении

## Частота подписок
- **15m** - получать сигналы каждые 15 минут
- **1h** - получать сигналы каждый час
- По умолчанию: 15m

👉 Бот не пушит автоматически всё подряд. Пользователь получает данные:
    • либо по команде (/signal, /history),

    • либо в рамках подписки (бот может присылать обновления раз в 15 минут по подписанным тикерам).


📑 Примеры сообщений
/start
👋 Привет! Я бот для анализа торговых сигналов.

Команды:
/subscribeall – подписка на все тикеры
/unsubscribeall – отписка от всех тикеров
/subscribe BTCUSDT – подписка на тикер
/unsubscribe BTCUSDT – отписка от тикера
/mytickers – список подписок
/signal BTCUSDT – вызов текущего сигнала по тикеру (запрос и ответ now, без апдейта базы данных).
/last BTCUSDT - последний сигнал по тикеру
/history BTCUSDT – история сигналов

/subscribe BTCUSDT
✅ Ты подписан на тикер BTCUSDT.

/unsubscribe BTCUSDT
❌ Подписка на BTCUSDT отменена.

/mytickers
📌 Ты подписан на тикеры:
- BTCUSDT
- ETHUSDT
- AVAXUSDT

/signal BTC
<b>BTCUSDT</b> · Текущая ситуация (онлайн)
<code>27.09.2025 15:34:56 (Kyiv)</code>

15m: <b>LONG</b>  | entry: 27000 | tp: 28500 | sl: 26300 | conf: 95% ⚠️
1h:  <b>LONG</b>  | entry: 27000 | tp: 28500 | sl: 26300 | conf: 95% ⚠️
4h:  <b>SHORT</b> | entry: 27200 | tp: 26500 | sl: 27600 | conf: 70%
1d:  <b>LONG</b>  | entry: 26000 | tp: 29000 | sl: 24500 | conf: 92% ⚠️

<i>Источник: API (xgb, lang=uk)</i>

/last BTC
<b>BTCUSDT</b> · Последний сохранённый сигнал
<code>as of 27.09.2025 15:30:00 (Kyiv)</code>

15m: <b>LONG</b>  | entry: 27000 | tp: 28500 | sl: 26300 | conf: 95% ⚠️
1h:  <b>LONG</b>  | entry: 27000 | tp: 28500 | sl: 26300 | conf: 95% ⚠️
4h:  <b>SHORT</b> | entry: 27200 | tp: 26500 | sl: 27600 | conf: 70%
1d:  <b>LONG</b>  | entry: 26000 | tp: 29000 | sl: 24500 | conf: 92% ⚠️

<i>Источник: БД (последний fetcher)</i>

/history BTCUSDT
📜 История сигналов BTCUSDT:
[15m] LONG | Entry: 27000 | TP: 28500 | SL: 26300 | Conf: 95% ⚠️ | ⏳ активен
[1h] LONG | Entry: 27000 | TP: 28500 | SL: 26300 | Conf: 95% ⚠️ | ✅ вход исполнен
[4h] SHORT | Entry: 27200 | TP: 26500 | SL: 27600 | Conf: 70% | ❌ стоп
[1d] LONG | Entry: 26000 | TP: 29000 | SL: 24500 | Conf: 92% ⚠️ | ⏳ активен

Ошибки
❌ Ошибка: тикер XXXUSDT не найден.
⚠️ Временно нет данных по BTCUSDT (ошибка API).

⚠️ Обработка ошибок
    • API (нет ответа, таймаут) → повторить 1–2 раза, логировать в error_logs.

    • JSON (неправильный формат) → пропустить тикер, логировать.

    • Telegram (ограничения, ошибки отправки) → до 3 попыток, логировать.


🛠 Технический стек
    • Python 3.x
    • requests – API
    • schedule/cron – планировщик  
    • PostgreSQL – база
    • SQLAlchemy – ORM
    • logging – логирование
    • aiogram – Telegram-бот
    • pytz – работа с часовыми поясами

## 🤖 Требования к Telegram-боту
    • parse_mode: HTML
    • Часовой пояс: Europe/Kyiv для отображения времени
    • Язык: определяется из LANG в .env (по умолчанию uk)
    • Rate limiting: 1 запрос /signal в 2 сек на пользователя
    • Global rate limit: 10 запросов/мин к API для /signal
    • Время ответа /signal: ≤ 2.5 сек (p95)
    • Время ответа /last: ≤ 150 мс (p95)
    • Логирование всех команд и ошибок


📌 Этапы реализации
    1. ✅ Настроить PostgreSQL, создать таблицы.
    2. ✅ Реализовать API-запросы по тикерам из tickers.txt.
    3. ✅ Записывать результаты в БД.
    4. ✅ Проверять исполнение сигналов.
    5. ✅ Реализовать Telegram-бота с подписками и командами.
    6. ✅ Сделать обработку ошибок.
    7. ✅ Провести тестирование.

## 🚀 Запуск системы

### Планировщик сигналов
```bash
# Запуск
./scripts/scheduler_control.sh start

# Остановка  
./scripts/scheduler_control.sh stop

# Статус
./scripts/scheduler_control.sh status

# Логи
./scripts/scheduler_control.sh logs
```

### Telegram-бот
```bash
# Установка сервиса
./scripts/telegram_bot_control.sh install

# Запуск
./scripts/telegram_bot_control.sh start

# Логи
./scripts/telegram_bot_control.sh logs
```

### Экстренная остановка
```bash
# Если планировщик завис
python scripts/force_stop.py
```