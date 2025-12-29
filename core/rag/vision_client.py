"""
Клиент для Google Vision API на mail.s0me.uk
"""
import io
import httpx
from typing import Optional, Dict, Any
from pathlib import Path
from loguru import logger
from config import settings


class VisionAPIClient:
    """Клиент для отправки документов в Google Vision API"""
    
    def __init__(self):
        """Инициализация клиента"""
        self.api_url = settings.vision_api_url.rstrip('/')
        self.api_key = settings.vision_api_key
        self.timeout = settings.vision_api_timeout
        
        if not self.api_key:
            logger.warning("Vision API key is not set. OCR via Vision API will not be available.")
    
    def is_available(self) -> bool:
        """Проверка доступности API"""
        return bool(self.api_key)
    
    async def extract_text_from_image(
        self, 
        image_data: bytes, 
        filename: Optional[str] = None,
        language_hints: Optional[list] = None
    ) -> Optional[str]:
        """
        Извлечение текста из изображения через Vision API
        
        Args:
            image_data: Байты изображения
            filename: Имя файла (опционально)
            language_hints: Подсказки по языкам (по умолчанию ['uk', 'ru', 'en'])
            
        Returns:
            Извлеченный текст или None в случае ошибки
        """
        if not self.is_available():
            logger.warning("Vision API is not available (no API key)")
            return None
        
        if not language_hints:
            language_hints = ['uk', 'ru', 'en']
        
        try:
            url = f"{self.api_url}/v1/api/ocr"
            headers = {
                "X-API-Key": self.api_key
            }
            
            # Определяем MIME тип
            mime_type = "image/png"
            if filename:
                ext = Path(filename).suffix.lower()
                if ext in ['.jpg', '.jpeg']:
                    mime_type = "image/jpeg"
                elif ext == '.gif':
                    mime_type = "image/gif"
                elif ext == '.webp':
                    mime_type = "image/webp"
            
            files = {
                "image": (filename or "image.png", image_data, mime_type)
            }
            
            data = {
                "languageHints": ",".join(language_hints),
                "enablePreprocessing": "true",
                "preprocessingMode": "normal"
            }
            
            logger.info(f"[Vision API] Preparing to send image to {url}")
            logger.info(f"[Vision API] File size: {len(image_data)} bytes, filename: {filename or 'image.png'}, MIME type: {mime_type}")
            logger.info(f"[Vision API] Language hints: {language_hints}")
            logger.debug(f"[Vision API] Request URL: {url}")
            logger.debug(f"[Vision API] Headers: X-API-Key={'*' * 20}... (hidden)")
            logger.debug(f"[Vision API] Data params: {data}")
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                logger.info(f"[Vision API] Sending POST request to Vision API server...")
                response = await client.post(
                    url,
                    headers=headers,
                    files=files,
                    data=data
                )
                logger.info(f"[Vision API] Received response: status={response.status_code}, size={len(response.content)} bytes")
                
                # Пытаемся распарсить JSON ответ (даже для ошибок)
                try:
                    result = response.json()
                except Exception as json_error:
                    logger.error(f"Vision API returned invalid JSON: {response.status_code} - {response.text[:200]}")
                    return None
                
                # Обработка успешного ответа (200)
                if response.status_code == 200:
                    # Проверяем, что ответ содержит success: true
                    if not result.get("success"):
                        logger.warning(f"Vision API returned 200 but success=false: {result}")
                        # Возможно, это ошибка в формате ответа, но попробуем извлечь текст
                        if "text" in result:
                            text = result.get("text", "")
                            if text:
                                logger.info(f"Extracted text despite success=false: {len(text)} characters")
                                return text
                        return None
                    
                    # Извлекаем текст (может быть пустой строкой, если на изображении нет текста)
                    text = result.get("text", "")
                    
                    # Пустая строка - это валидный результат (изображение без текста)
                    # Но логируем это как предупреждение для отладки
                    if not text:
                        logger.debug(f"Vision API returned empty text (image may not contain text)")
                        # Возвращаем пустую строку, а не None, чтобы показать, что обработка прошла успешно
                        return ""
                    
                    logger.info(f"Successfully extracted text from image via Vision API: {len(text)} characters")
                    if result.get("confidence"):
                        logger.debug(f"OCR confidence: {result.get('confidence')}")
                    return text
                
                # Обработка ошибок (400, 401, 403, 500 и т.д.)
                else:
                    error_message = result.get("message") or result.get("error") or "Unknown error"
                    error_type = result.get("error", "Error")
                    
                    if response.status_code == 401:
                        logger.error(f"Vision API authentication error (401): {error_message}")
                    elif response.status_code == 403:
                        logger.error(f"Vision API authorization error (403): {error_message}")
                    elif response.status_code == 400:
                        logger.error(f"Vision API bad request (400): {error_message}")
                    elif response.status_code == 429:
                        logger.error(f"Vision API rate limit exceeded (429): {error_message}")
                    elif response.status_code >= 500:
                        logger.error(f"Vision API server error ({response.status_code}): {error_message}")
                    else:
                        logger.error(f"Vision API error ({response.status_code}): {error_type} - {error_message}")
                    
                    return None
                    
        except httpx.TimeoutException:
            logger.error(f"Vision API timeout after {self.timeout} seconds")
            return None
        except Exception as e:
            logger.error(f"Error calling Vision API: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return None
    
    async def extract_text_from_file(
        self, 
        file_path: str,
        language_hints: Optional[list] = None
    ) -> Optional[str]:
        """
        Извлечение текста из файла через Vision API
        
        Args:
            file_path: Путь к файлу
            language_hints: Подсказки по языкам
            
        Returns:
            Извлеченный текст или None в случае ошибки
        """
        try:
            logger.info(f"[Vision API] Reading file: {file_path}")
            with open(file_path, 'rb') as f:
                file_data = f.read()
            
            file_size = len(file_data)
            filename = Path(file_path).name
            logger.info(f"[Vision API] File read successfully: {filename}, size: {file_size} bytes")
            
            return await self.extract_text_from_image(file_data, filename, language_hints)
            
        except FileNotFoundError:
            logger.error(f"[Vision API] File not found: {file_path}")
            return None
        except PermissionError:
            logger.error(f"[Vision API] Permission denied reading file: {file_path}")
            return None
        except Exception as e:
            logger.error(f"[Vision API] Error reading file for Vision API: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return None

