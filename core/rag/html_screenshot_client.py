"""
Клиент для HTML Screenshot Service
"""
import httpx
from typing import Optional, Dict, Any
from pathlib import Path
from loguru import logger
from config import settings


class HTMLScreenshotClient:
    """Клиент для создания скриншотов HTML и получения текста через Vision API"""
    
    def __init__(self, base_url: Optional[str] = None):
        """
        Инициализация клиента
        
        Args:
            base_url: URL сервиса скриншотов (по умолчанию из настроек или localhost:3015)
        """
        self.base_url = base_url or getattr(settings, 'html_screenshot_url', 'http://localhost:3015')
        self.base_url = self.base_url.rstrip('/')
        self.timeout = getattr(settings, 'html_screenshot_timeout', 120)
    
    async def extract_text_from_html(
        self,
        html_content: str,
        viewport_width: int = 1920,
        viewport_height: int = 1080,
        wait_time: int = 1000,
        full_page: bool = True,
        language_hints: Optional[list] = None
    ) -> Optional[str]:
        """
        Создание скриншота HTML и извлечение текста через Vision API
        
        Args:
            html_content: HTML контент
            viewport_width: Ширина viewport
            viewport_height: Высота viewport
            wait_time: Время ожидания после загрузки (мс)
            full_page: Делать скриншот всей страницы
            language_hints: Подсказки по языкам
            
        Returns:
            Извлеченный текст или None в случае ошибки
        """
        try:
            url = f"{self.base_url}/screenshot"
            
            data = {
                "html_content": html_content,
                "viewport_width": viewport_width,
                "viewport_height": viewport_height,
                "wait_time": wait_time,
                "full_page": full_page
            }
            
            if language_hints:
                data["language_hints"] = language_hints
            
            logger.info(f"[HTML Screenshot] Sending HTML to screenshot service: {len(html_content)} chars")
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=data)
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get("success"):
                        text = result.get("text")
                        screenshot_size = result.get("screenshot_size", 0)
                        logger.info(f"[HTML Screenshot] Successfully extracted text: {len(text) if text else 0} chars (screenshot: {screenshot_size} bytes)")
                        return text
                    else:
                        error = result.get("error", "Unknown error")
                        logger.error(f"[HTML Screenshot] Service returned error: {error}")
                        return None
                else:
                    logger.error(f"[HTML Screenshot] Service returned status {response.status_code}: {response.text[:200]}")
                    return None
                    
        except httpx.TimeoutException:
            logger.error(f"[HTML Screenshot] Timeout after {self.timeout} seconds")
            return None
        except Exception as e:
            logger.error(f"[HTML Screenshot] Error calling service: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return None
    
    async def extract_text_from_html_file(
        self,
        file_path: str,
        viewport_width: int = 1920,
        viewport_height: int = 1080,
        wait_time: int = 1000,
        full_page: bool = True,
        language_hints: Optional[list] = None
    ) -> Optional[str]:
        """
        Создание скриншота из HTML файла и извлечение текста
        
        Args:
            file_path: Путь к HTML файлу
            viewport_width: Ширина viewport
            viewport_height: Высота viewport
            wait_time: Время ожидания после загрузки (мс)
            full_page: Делать скриншот всей страницы
            language_hints: Подсказки по языкам
            
        Returns:
            Извлеченный текст или None в случае ошибки
        """
        try:
            # Читаем HTML файл
            encoding = 'utf-8'
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    html_content = f.read()
            except UnicodeDecodeError:
                # Пробуем другие кодировки
                for enc in ['windows-1251', 'iso-8859-1', 'cp1252']:
                    try:
                        with open(file_path, 'r', encoding=enc) as f:
                            html_content = f.read()
                        encoding = enc
                        logger.info(f"[HTML Screenshot] Detected encoding: {encoding}")
                        break
                    except UnicodeDecodeError:
                        continue
                else:
                    logger.error(f"[HTML Screenshot] Failed to decode HTML file: {file_path}")
                    return None
            
            return await self.extract_text_from_html(
                html_content=html_content,
                viewport_width=viewport_width,
                viewport_height=viewport_height,
                wait_time=wait_time,
                full_page=full_page,
                language_hints=language_hints
            )
            
        except FileNotFoundError:
            logger.error(f"[HTML Screenshot] File not found: {file_path}")
            return None
        except Exception as e:
            logger.error(f"[HTML Screenshot] Error reading HTML file: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return None
    
    async def extract_text_from_html_url(
        self,
        url: str,
        viewport_width: int = 1920,
        viewport_height: int = 1080,
        wait_time: int = 1000,
        full_page: bool = True,
        language_hints: Optional[list] = None
    ) -> Optional[str]:
        """
        Создание скриншота из URL и извлечение текста
        
        Args:
            url: URL для загрузки
            viewport_width: Ширина viewport
            viewport_height: Высота viewport
            wait_time: Время ожидания после загрузки (мс)
            full_page: Делать скриншот всей страницы
            language_hints: Подсказки по языкам
            
        Returns:
            Извлеченный текст или None в случае ошибки
        """
        try:
            screenshot_url = f"{self.base_url}/screenshot"
            
            data = {
                "html_url": url,
                "viewport_width": viewport_width,
                "viewport_height": viewport_height,
                "wait_time": wait_time,
                "full_page": full_page
            }
            
            if language_hints:
                data["language_hints"] = language_hints
            
            logger.info(f"[HTML Screenshot] Sending URL to screenshot service: {url}")
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(screenshot_url, json=data)
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get("success"):
                        text = result.get("text")
                        screenshot_size = result.get("screenshot_size", 0)
                        logger.info(f"[HTML Screenshot] Successfully extracted text from URL: {len(text) if text else 0} chars (screenshot: {screenshot_size} bytes)")
                        return text
                    else:
                        error = result.get("error", "Unknown error")
                        logger.error(f"[HTML Screenshot] Service returned error: {error}")
                        return None
                else:
                    logger.error(f"[HTML Screenshot] Service returned status {response.status_code}: {response.text[:200]}")
                    return None
                    
        except httpx.TimeoutException:
            logger.error(f"[HTML Screenshot] Timeout after {self.timeout} seconds")
            return None
        except Exception as e:
            logger.error(f"[HTML Screenshot] Error calling service: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return None

