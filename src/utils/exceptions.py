"""
Кастомные исключения для приложения
"""

class HydraError(Exception):
    """Базовое исключение для приложения"""
    pass

class DatabaseError(HydraError):
    """Ошибки работы с базой данных"""
    pass

class APIError(HydraError):
    """Ошибки работы с API"""
    pass

class TelegramError(HydraError):
    """Ошибки работы с Telegram"""
    pass

class ConfigurationError(HydraError):
    """Ошибки конфигурации"""
    pass

class ValidationError(HydraError):
    """Ошибки валидации данных"""
    pass