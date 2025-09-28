#!/bin/bash
set -e

# Переходим в рабочую директорию
cd /home/hydrabot/hydrabot-fetcher

# Активируем виртуальную среду
source venv/bin/activate

# Проверяем переменные окружения
if [ ! -f .env ]; then
    echo "ERROR: .env file not found"
    exit 1
fi

# Загружаем переменные окружения
export $(cat .env | grep -v '^#' | xargs)

# Запускаем бота
exec python run_telegram_bot.py