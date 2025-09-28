#!/bin/bash
# ====================================================================
# Hydra Static Trading System - Управление системой
# ====================================================================

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Конфигурация
HYDRA_DIR="/home/hydrabot/hydrabot-fetcher"
SCHEDULER_SERVICE="hydra-scheduler.service"
TELEGRAM_SERVICE="hydra-telegram-bot.service"
VENV_PATH="$HYDRA_DIR/venv"

# Функция для логирования
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_header() {
    echo -e "${CYAN}=== $1 ===${NC}"
}

# Проверка запущенных сервисов
check_service_status() {
    local service=$1
    if sudo systemctl is-active --quiet "$service"; then
        echo -e "${GREEN}✅ $service - RUNNING${NC}"
        return 0
    else
        echo -e "${RED}❌ $service - STOPPED${NC}"
        return 1
    fi
}

# Получение статуса всех сервисов
status() {
    log_header "Статус Hydra Static System"
    check_service_status "$SCHEDULER_SERVICE"
    check_service_status "$TELEGRAM_SERVICE"
    
    echo ""
    log_info "Подробная информация:"
    sudo systemctl status "$SCHEDULER_SERVICE" "$TELEGRAM_SERVICE" --no-pager -l || true
}

# Запуск системы
start() {
    log_header "Запуск Hydra Static System"
    
    # Проверяем виртуальную среду
    if [ ! -d "$VENV_PATH" ]; then
        log_error "Виртуальная среда не найдена в $VENV_PATH"
        exit 1
    fi
    
    # Проверяем .env файл
    if [ ! -f "$HYDRA_DIR/.env" ]; then
        log_error ".env файл не найден в $HYDRA_DIR"
        exit 1
    fi
    
    # Перезагружаем конфигурацию systemd
    log_info "Перезагрузка systemd daemon..."
    sudo systemctl daemon-reload
    
    # Запускаем планировщик
    log_info "Запуск планировщика сигналов..."
    if sudo systemctl start "$SCHEDULER_SERVICE"; then
        log_success "Планировщик запущен"
    else
        log_error "Ошибка запуска планировщика"
        exit 1
    fi
    
    # Ждем немного для стабилизации
    sleep 2
    
    # Запускаем Telegram бота
    log_info "Запуск Telegram бота..."
    if sudo systemctl start "$TELEGRAM_SERVICE"; then
        log_success "Telegram бот запущен"
    else
        log_error "Ошибка запуска Telegram бота"
        exit 1
    fi
    
    # Включаем автозапуск
    log_info "Включение автозапуска сервисов..."
    sudo systemctl enable "$SCHEDULER_SERVICE" "$TELEGRAM_SERVICE"
    
    sleep 3
    
    echo ""
    log_success "🚀 Hydra Static System успешно запущена!"
    status
}

# Остановка системы
stop() {
    log_header "Остановка Hydra Static System"
    
    log_info "Остановка Telegram бота..."
    sudo systemctl stop "$TELEGRAM_SERVICE" || true
    
    log_info "Остановка планировщика сигналов..."
    sudo systemctl stop "$SCHEDULER_SERVICE" || true
    
    log_success "🛑 Hydra Static System остановлена"
}

# Перезапуск системы
restart() {
    log_header "Перезапуск Hydra Static System"
    stop
    sleep 3
    start
}

# Мониторинг логов в реальном времени
logs() {
    local service=${1:-"all"}
    
    case "$service" in
        "scheduler")
            log_header "Логи планировщика (Ctrl+C для выхода)"
            sudo journalctl -u "$SCHEDULER_SERVICE" -f --no-pager
            ;;
        "telegram"|"bot")
            log_header "Логи Telegram бота (Ctrl+C для выхода)"
            sudo journalctl -u "$TELEGRAM_SERVICE" -f --no-pager
            ;;
        "all"|*)
            log_header "Логи всех сервисов (Ctrl+C для выхода)"
            sudo journalctl -u "$SCHEDULER_SERVICE" -u "$TELEGRAM_SERVICE" -f --no-pager
            ;;
    esac
}

# Проверка базы данных
check_db() {
    log_header "Проверка базы данных"
    cd "$HYDRA_DIR"
    source "$VENV_PATH/bin/activate"
    python scripts/prepare_database.py
}

# Очистка базы данных
clean_db() {
    log_header "Очистка базы данных"
    log_warning "Это удалит все тестовые данные из базы!"
    read -p "Продолжить? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        cd "$HYDRA_DIR"
        source "$VENV_PATH/bin/activate"
        python -c "
from scripts.prepare_database import clean_test_data
clean_test_data()
print('✅ Тестовые данные очищены')
"
        log_success "База данных очищена"
    else
        log_info "Операция отменена"
    fi
}

# Помощь
help() {
    cat << EOF
🤖 Hydra Static Trading System - Управление

Использование: $0 КОМАНДА [ОПЦИИ]

КОМАНДЫ:
    start       Запустить всю систему (планировщик + бот)
    stop        Остановить всю систему
    restart     Перезапустить систему (stop + start)
    status      Показать статус сервисов
    logs        Показать логи в реальном времени
                  - logs scheduler  (только планировщик)
                  - logs telegram   (только бот)
                  - logs all        (все сервисы, по умолчанию)
    
    check-db    Проверить состояние базы данных
    clean-db    Очистить тестовые данные из БД
    
    help        Показать эту справку

ПРИМЕРЫ:
    $0 start              # Запустить систему
    $0 status             # Проверить статус
    $0 logs scheduler     # Смотреть логи планировщика
    $0 restart            # Перезапустить все

СЕРВИСЫ:
    • $SCHEDULER_SERVICE - Сбор торговых сигналов каждые 15 мин
    • $TELEGRAM_SERVICE - Telegram бот @hydracryptomaxa_bot

ФАЙЛЫ:
    • Рабочая директория: $HYDRA_DIR
    • Виртуальная среда: $VENV_PATH
    • Конфигурация: $HYDRA_DIR/.env
EOF
}

# Основная логика
main() {
    # Проверяем, что скрипт запущен из правильной директории
    if [ ! -d "$HYDRA_DIR" ]; then
        log_error "Директория проекта не найдена: $HYDRA_DIR"
        exit 1
    fi
    
    case "${1:-help}" in
        "start")
            start
            ;;
        "stop")
            stop
            ;;
        "restart")
            restart
            ;;
        "status")
            status
            ;;
        "logs")
            logs "$2"
            ;;
        "check-db")
            check_db
            ;;
        "clean-db")
            clean_db
            ;;
        "help"|"-h"|"--help")
            help
            ;;
        *)
            log_error "Неизвестная команда: $1"
            echo ""
            help
            exit 1
            ;;
    esac
}

# Обработка сигналов для корректного завершения
trap 'echo -e "\n${YELLOW}Получен сигнал завершения${NC}"' INT TERM

# Запуск основной функции
main "$@"