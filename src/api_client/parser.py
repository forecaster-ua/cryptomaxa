"""
Парсер файла тикеров
"""
import re
import logging
from typing import List
from pathlib import Path

from ..utils.exceptions import ValidationError
from ..config import config

logger = logging.getLogger(__name__)

class TickersParser:
    """Класс для парсинга файла с тикерами"""
    
    def __init__(self, file_path: str = None):
        self.file_path = file_path or config.TICKERS_FILE
    
    def parse_tickers(self) -> List[str]:
        """
        Парсит файл tickers.txt и извлекает список тикеров
        
        Returns:
            List[str]: Список тикеров (например: ['BTC', 'ETH', 'BNB'])
        
        Raises:
            ValidationError: Если файл не найден или имеет неверный формат
        """
        try:
            file_path = Path(self.file_path)
            
            if not file_path.exists():
                raise ValidationError(f"Файл тикеров не найден: {self.file_path}")
            
            content = file_path.read_text(encoding='utf-8')
            logger.debug(f"Прочитан файл тикеров: {len(content)} символов")
            
            # Ищем массив COIN_SYMBOLS в файле
            # Паттерн для поиска списка тикеров в Python формате
            pattern = r'COIN_SYMBOLS\s*=\s*\[(.*?)\]'
            match = re.search(pattern, content, re.DOTALL)
            
            if not match:
                raise ValidationError("Не найден массив COIN_SYMBOLS в файле тикеров")
            
            # Извлекаем содержимое массива
            array_content = match.group(1)
            
            # Извлекаем все строки в кавычках
            ticker_pattern = r"['\"]([A-Z0-9]+USDT)['\"]"
            matches = re.findall(ticker_pattern, array_content)
            
            if not matches:
                raise ValidationError("Не найдены тикеры в формате *USDT")
            
            # Убираем USDT суффикс, оставляем только базовую валюту
            tickers = []
            for ticker in matches:
                if ticker.endswith('USDT'):
                    base_ticker = ticker[:-4]  # Убираем 'USDT'
                    if base_ticker:
                        tickers.append(base_ticker)
            
            logger.info(f"Найдено {len(tickers)} тикеров")
            logger.debug(f"Тикеры: {', '.join(tickers[:5])}{'...' if len(tickers) > 5 else ''}")
            
            return tickers
            
        except ValidationError:
            raise
        except Exception as e:
            raise ValidationError(f"Ошибка парсинга файла тикеров: {e}")
    
    def validate_ticker(self, ticker: str) -> bool:
        """
        Валидирует формат тикера
        
        Args:
            ticker: Тикер для проверки
            
        Returns:
            bool: True если тикер валидный
        """
        if not ticker:
            return False
        
        # Проверяем что тикер содержит только буквы и цифры
        if not re.match(r'^[A-Z0-9]+$', ticker.upper()):
            return False
        
        # Проверяем длину (обычно от 2 до 10 символов)
        if len(ticker) < 2 or len(ticker) > 10:
            return False
        
        return True