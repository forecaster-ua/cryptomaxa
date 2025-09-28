"""
HTTP клиент для работы с API торговых сигналов
"""
import requests
import logging
import time
from typing import Dict, Any, Optional, List
from urllib.parse import urljoin

from ..utils.exceptions import APIError
from ..config import config

logger = logging.getLogger(__name__)

class SignalAPIClient:
    """Клиент для работы с API торговых сигналов"""
    
    def __init__(self):
        self.base_url = config.API_BASE_URL
        self.timeout = config.API_TIMEOUT
        self.timeframes = config.TIMEFRAMES
        self.session = requests.Session()
        
        # Настраиваем заголовки
        self.session.headers.update({
            'User-Agent': 'Hydra-Bot/1.0',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        })
    
    def get_multi_signal(self, ticker: str, retries: int = 2) -> Optional[Dict[str, Any]]:
        """
        Получает сигналы для тикера по всем таймфреймам
        
        Args:
            ticker: Базовая валюта (например: 'BTC')
            retries: Количество повторных попыток при ошибке
            
        Returns:
            Dict с данными сигналов или None при ошибке
            
        Raises:
            APIError: При критических ошибках API
        """
        pair = f"{ticker}USDT"
        
        # Формируем параметры согласно ТЗ
        params = [
            ('pair', pair),
            ('lang', 'uk'),
            ('model_type', 'xgb')
        ]
        
        # Добавляем все таймфреймы как отдельные параметры
        for tf in self.timeframes:
            params.append(('timeframes', tf))
        
        url = f"{self.base_url}/multi_signal"
        
        for attempt in range(retries + 1):
            try:
                logger.debug(f"📡 API запрос для {pair}, попытка {attempt + 1}/{retries + 1}")
                
                response = self.session.get(
                    url,
                    params=params,
                    timeout=self.timeout
                )
                
                logger.debug(f"📡 Ответ API для {pair}: статус {response.status_code}, размер {len(response.content)} байт")
                
                # Проверяем статус ответа
                response.raise_for_status()
                
                # Парсим JSON
                data = response.json()
                
                # Проверяем структуру ответа
                if isinstance(data, list):
                    logger.debug(f"✅ {pair}: получен список из {len(data)} сигналов")
                elif isinstance(data, dict):
                    logger.debug(f"✅ {pair}: получен объект с ключами: {list(data.keys())}")
                else:
                    logger.warning(f"⚠️  {pair}: неожиданный тип ответа: {type(data)}")
                
                return data
                
            except requests.exceptions.Timeout as e:
                logger.warning(f"⏰ Таймаут для {pair} (попытка {attempt + 1}): {e}")
                print(f"⏰ Таймаут API для {pair}, повтор через 1 сек...")
                if attempt < retries:
                    time.sleep(1)  # Пауза перед повтором
                    continue
                else:
                    logger.error(f"❌ Превышено количество попыток для {pair} (таймауты)")
                    print(f"❌ {pair}: все попытки исчерпаны (таймауты)")
                    return None
                    
            except requests.exceptions.ConnectionError as e:
                logger.warning(f"🔌 Ошибка соединения для {pair} (попытка {attempt + 1}): {e}")
                print(f"🔌 Нет соединения с API для {pair}, повтор через 2 сек...")
                if attempt < retries:
                    time.sleep(2)  # Увеличенная пауза
                    continue
                else:
                    logger.error(f"❌ Не удалось соединиться с API для {pair}")
                    print(f"❌ {pair}: соединение недоступно")
                    return None
                    
            except requests.exceptions.HTTPError as e:
                status_code = e.response.status_code if e.response else 'unknown'
                response_text = e.response.text[:200] if e.response else 'нет текста'
                
                logger.error(f"🚫 HTTP {status_code} для {pair}: {response_text}")
                print(f"🚫 {pair}: HTTP {status_code} - {response_text}")
                
                # При 4xx ошибках не повторяем
                if e.response and 400 <= e.response.status_code < 500:
                    return None
                
                # При 5xx ошибках повторяем
                if attempt < retries:
                    print(f"🔄 {pair}: повтор через 3 сек (HTTP {status_code})")
                    time.sleep(3)
                    continue
                else:
                    return None
                    
            except ValueError as e:  # JSON decode error
                logger.error(f"📄 Ошибка парсинга JSON для {pair}: {e}")
                print(f"📄 {pair}: некорректный JSON от API")
                return None
                
            except Exception as e:
                logger.error(f"💥 Неожиданная ошибка для {pair}: {e}")
                print(f"💥 {pair}: неожиданная ошибка - {str(e)[:100]}")
                return None
        
        return None
    
    def get_signals_batch(self, tickers: List[str], delay: float = 0.1) -> Dict[str, Any]:
        """
        Получает сигналы для списка тикеров с задержкой между запросами
        
        Args:
            tickers: Список тикеров
            delay: Задержка между запросами в секундах
            
        Returns:
            Dict где ключ - тикер, значение - данные сигналов или None
        """
        results = {}
        
        logger.info(f"Получение сигналов для {len(tickers)} тикеров")
        
        for i, ticker in enumerate(tickers):
            try:
                # Добавляем задержку между запросами
                if i > 0:
                    time.sleep(delay)
                
                result = self.get_multi_signal(ticker)
                results[ticker] = result
                
                if result:
                    # Определяем количество сигналов
                    signals_count = len(result) if isinstance(result, list) else "объект"
                    logger.debug(f"✅ {ticker}: {signals_count} сигналов")
                else:
                    logger.warning(f"❌ {ticker}: нет данных")
                    
            except Exception as e:
                logger.error(f"💥 Ошибка при обработке {ticker}: {e}")
                results[ticker] = None
        
        successful = sum(1 for v in results.values() if v is not None)
        logger.info(f"Успешно получено сигналов: {successful}/{len(tickers)}")
        
        return results
    
    def close(self):
        """Закрывает сессию"""
        self.session.close()