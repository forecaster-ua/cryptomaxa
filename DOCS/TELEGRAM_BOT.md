# Документация Telegram-бота Hydra Static

## Обзор

Telegram-бот предоставляет интерфейс для получения торговых сигналов и управления подписками на тикеры. Бот поддерживает как онлайн-запросы к API, так и получение данных из базы данных.

## Архитектура

```
src/telegram_bot/
├── __init__.py          # Инициализация пакета
├── bot.py              # Основной файл бота и конфигурация
├── handlers.py         # Обработчики команд
├── middleware.py       # Middleware (логирование, rate limiting)
├── services.py         # Бизнес-логика (API, БД)
└── formatting.py       # Форматирование сообщений
```

## Основные компоненты

### 1. Обработчики команд (handlers.py)
- `/start` - приветственное сообщение
- `/signal TICKER` - онлайн сигнал без записи в БД
- `/last TICKER` - последний сохранённый сигнал из БД
- `/history TICKER` - история сигналов
- `/subscribe TICKER [15m|1h]` - управление подписками
- `/unsubscribe TICKER` - отписка от тикера
- `/mytickers` - список подписок

### 2. Сервисы (services.py)
- **SignalService** - работа с сигналами (API и БД)
- **UserService** - управление пользователями
- **SubscriptionService** - управление подписками

### 3. Middleware (middleware.py)
- **LoggingMiddleware** - логирование всех команд
- **RateLimitMiddleware** - ограничение частоты запросов

### 4. Форматирование (formatting.py)
- HTML-форматирование сообщений
- Работа с часовыми поясами (Europe/Kyiv)
- Шаблоны сообщений

## Особенности реализации

### Rate Limiting
- **Per-user limit**: 1 запрос `/signal` в 2 секунды
- **Global limit**: 10 запросов `/signal` в минуту
- Защита от спама и перегрузки API

### Парсинг API ответов
API возвращает массив объектов с разной структурой:
```json
[
  {
    "timeframe": "15m",
    "main_signal": {
      "type": "LONG",
      "entry": 109023.53,
      "tp": 109586.61,
      "sl": 108695.7773,
      "confidence": 78.5
    }
  },
  {
    "timeframe": "1h", 
    "signal": "SHORT",
    "entry_price": 109250.9,
    "take_profit": 108378.908,
    "stop_loss": 109686.896,
    "confidence": 43.3
  }
]
```

### Часовые пояса
- **Внутренняя работа**: UTC
- **Отображение пользователям**: Europe/Kyiv
- **Библиотека**: pytz

### HTML-форматирование
Все сообщения используют HTML parse_mode:
- `<b>текст</b>` - жирный
- `<i>текст</i>` - курсив  
- `<code>текст</code>` - моноширинный

## Конфигурация

### Переменные окружения (.env)
```bash
# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_ADMIN_ID=admin_user_id

# API
API_BASE=http://194.135.94.212:8001
LANG=uk
MODEL_TYPE=xgb

# База данных
DB_HOST=localhost
DB_NAME=hydra_signals
DB_USER=hydra_user
DB_PASSWORD=password
```

## Запуск и управление

### Ручной запуск
```bash
cd /home/hydrabot/hydrabot-fetcher
source venv/bin/activate
python run_telegram_bot.py
```

### Systemd сервис
```bash
# Установка
./scripts/telegram_bot_control.sh install

# Управление
./scripts/telegram_bot_control.sh start|stop|restart|status

# Логи
./scripts/telegram_bot_control.sh logs
```

## Тестирование

### Компонентный тест
```bash
python tests/test_telegram_bot.py
```

### API тест  
```bash
python tests/test_api_structure.py
```

## Логирование

Все события логируются:
- Команды пользователей
- API запросы и ответы
- Ошибки и исключения
- Performance метрики

Логи доступны через:
- `journalctl -u hydra-telegram-bot -f`
- Файл `logs/telegram_bot.log`

## Безопасность

### Rate Limiting
- Пользовательские лимиты
- Глобальные лимиты
- Защита от DoS

### Валидация
- Проверка входных параметров
- Санитизация тикеров
- Защита от SQL-инъекций (SQLAlchemy ORM)

### Systemd Security
```ini
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
```

## Мониторинг

### Метрики производительности
- Время ответа `/signal`: ≤ 2.5 сек (p95)
- Время ответа `/last`: ≤ 150 мс (p95)
- Использование памяти
- Количество активных пользователей

### Алерты
- Превышение лимитов ответа
- Ошибки API (>10% в минуту)
- Недоступность БД
- Критические исключения

## Масштабирование

### Горизонтальное
- Можно запускать несколько инстансов
- Rate limiting работает per-process
- Общая БД для всех инстансов

### Вертикальное
- Увеличение лимитов rate limiting
- Оптимизация SQL запросов
- Кэширование частых запросов

## Troubleshooting

### Частые проблемы

1. **Бот не отвечает**
   ```bash
   ./scripts/telegram_bot_control.sh status
   ./scripts/telegram_bot_control.sh logs
   ```

2. **API недоступен**
   - Проверить `API_BASE` в .env
   - Тестировать `curl http://194.135.94.212:8001/multi_signal?pair=BTCUSDT&timeframes=15m`

3. **Ошибки БД**
   - Проверить подключение к PostgreSQL
   - Проверить credentials в .env

4. **Rate limiting срабатывает**
   - Нормальная защита
   - Можно увеличить лимиты в middleware.py

### Логи для отладки
```bash
# Все логи бота
journalctl -u hydra-telegram-bot --since "1 hour ago"

# Только ошибки
journalctl -u hydra-telegram-bot -p err --since today

# Конкретный пользователь
journalctl -u hydra-telegram-bot | grep "user_id"
```