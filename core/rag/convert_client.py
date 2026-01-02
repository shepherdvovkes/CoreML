"""
Клиент для Convert API на mail.s0me.uk
"""
import io
import httpx
from typing import Optional, Dict, Any
from pathlib import Path
from loguru import logger
from config import settings


class ConvertAPIClient:
    """Клиент для конвертации документов через Convert API"""
    
    def __init__(self):
        """Инициализация клиента"""
        self.api_url = settings.convert_api_url.rstrip('/')
        self.api_key = settings.convert_api_key
        self.timeout = settings.convert_api_timeout
        
        if not self.api_key:
            logger.warning("Convert API key is not set. Document conversion via Convert API will not be available.")
    
    def is_available(self) -> bool:
        """Проверка доступности API"""
        return bool(self.api_key)
    
    async def convert_document(
        self, 
        file_data: bytes, 
        filename: str,
        output_format: str = "txt",
        encoding: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> Optional[bytes]:
        """
        Конвертация документа в другой формат через Convert API
        
        Args:
            file_data: Байты исходного файла
            filename: Имя файла с расширением
            output_format: Формат вывода (txt, pdf, html, docx, и т.д.)
            encoding: Кодировка исходного файла (utf8, windows-1251, iso-8859-1 и т.д.)
            options: Дополнительные опции конвертации
            
        Returns:
            Конвертированные данные в байтах или None в случае ошибки
        """
        if not self.is_available():
            logger.warning("Convert API is not available (no API key)")
            return None
        
        try:
            url = f"{self.api_url}/v1/api/convert-to-text"
            headers = {
                "X-API-Key": self.api_key
            }
            
            # Определяем MIME тип на основе расширения
            mime_type = "application/octet-stream"
            ext = Path(filename).suffix.lower()
            mime_map = {
                '.pdf': 'application/pdf',
                '.doc': 'application/msword',
                '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                '.xls': 'application/vnd.ms-excel',
                '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                '.html': 'text/html',
                '.htm': 'text/html',
                '.txt': 'text/plain',
                '.rtf': 'application/rtf',
                '.odt': 'application/vnd.oasis.opendocument.text',
            }
            mime_type = mime_map.get(ext, mime_type)
            
            files = {
                "file": (filename, file_data, mime_type)
            }
            
            data = {
                "outputFormat": output_format
            }
            
            # Добавляем кодировку, если указана
            if encoding:
                data["encoding"] = encoding
            
            # Добавляем дополнительные опции, если они есть
            if options:
                for key, value in options.items():
                    data[key] = str(value)
            
            logger.info(f"[Convert API] Preparing to convert document: {filename} to {output_format}")
            logger.info(f"[Convert API] File size: {len(file_data)} bytes, MIME type: {mime_type}")
            logger.debug(f"[Convert API] Request URL: {url}")
            logger.debug(f"[Convert API] Headers: X-API-Key={'*' * 20}... (hidden)")
            logger.debug(f"[Convert API] Data params: {data}")
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                logger.info(f"[Convert API] Sending POST request to Convert API server...")
                response = await client.post(
                    url,
                    headers=headers,
                    files=files,
                    data=data
                )
                logger.info(f"[Convert API] Received response: status={response.status_code}, size={len(response.content)} bytes")
                
                # Обработка успешного ответа (200)
                if response.status_code == 200:
                    try:
                        result = response.json()
                        
                        # Проверяем, что ответ содержит success: true
                        if not result.get("success"):
                            logger.warning(f"Convert API returned 200 but success=false: {result}")
                            error_message = result.get("message") or result.get("error") or "Unknown error"
                            logger.error(f"Convert API error: {error_message}")
                            return None
                        
                        # Извлекаем текст из поля "text" (основной формат ответа)
                        if "text" in result:
                            text = result["text"]
                            # Конвертируем текст в байты
                            encoding = result.get("encoding", "utf-8")
                            try:
                                converted_data = text.encode(encoding)
                                logger.info(f"Successfully converted document via Convert API: {len(converted_data)} bytes (text length: {len(text)} chars, encoding: {encoding})")
                                return converted_data
                            except Exception as encode_error:
                                # Fallback на UTF-8 если указанная кодировка не работает
                                logger.warning(f"Failed to encode with {encoding}, trying UTF-8: {encode_error}")
                                converted_data = text.encode('utf-8', errors='ignore')
                                logger.info(f"Successfully converted document via Convert API: {len(converted_data)} bytes (using UTF-8 fallback)")
                                return converted_data
                        
                        # Если ответ содержит data в base64 (fallback)
                        if "data" in result:
                            import base64
                            try:
                                converted_data = base64.b64decode(result["data"])
                                logger.info(f"Successfully converted document via Convert API: {len(converted_data)} bytes (from base64)")
                                return converted_data
                            except Exception as decode_error:
                                logger.error(f"Failed to decode base64 data from Convert API: {decode_error}")
                                return None
                        
                        logger.warning(f"Convert API response format not recognized: {result}")
                        return None
                        
                    except Exception as json_error:
                        # Если ответ не JSON, возможно это бинарные данные
                        if response.content:
                            logger.info(f"Convert API returned binary data: {len(response.content)} bytes")
                            return response.content
                        logger.error(f"Convert API returned invalid response: {json_error}")
                        return None
                
                # Обработка ошибок (400, 401, 403, 500 и т.д.)
                else:
                    try:
                        result = response.json()
                        error_message = result.get("message") or result.get("error") or "Unknown error"
                        error_type = result.get("error", "Error")
                    except:
                        error_message = response.text[:200] if response.text else "Unknown error"
                        error_type = "Error"
                    
                    if response.status_code == 401:
                        logger.error(f"Convert API authentication error (401): {error_message}")
                    elif response.status_code == 403:
                        logger.error(f"Convert API authorization error (403): {error_message}")
                    elif response.status_code == 400:
                        logger.error(f"Convert API bad request (400): {error_message}")
                    elif response.status_code == 429:
                        logger.error(f"Convert API rate limit exceeded (429): {error_message}")
                    elif response.status_code >= 500:
                        logger.error(f"Convert API server error ({response.status_code}): {error_message}")
                    else:
                        logger.error(f"Convert API error ({response.status_code}): {error_type} - {error_message}")
                    
                    return None
                    
        except httpx.TimeoutException:
            logger.error(f"Convert API timeout after {self.timeout} seconds")
            return None
        except Exception as e:
            logger.error(f"Error calling Convert API: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return None
    
    async def convert_file(
        self, 
        file_path: str,
        output_format: str = "txt",
        encoding: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> Optional[bytes]:
        """
        Конвертация файла в другой формат через Convert API
        
        Args:
            file_path: Путь к файлу
            output_format: Формат вывода
            encoding: Кодировка исходного файла (utf8, windows-1251, iso-8859-1 и т.д.)
            options: Дополнительные опции конвертации
            
        Returns:
            Конвертированные данные в байтах или None в случае ошибки
        """
        try:
            logger.info(f"[Convert API] Reading file: {file_path}")
            with open(file_path, 'rb') as f:
                file_data = f.read()
            
            file_size = len(file_data)
            filename = Path(file_path).name
            logger.info(f"[Convert API] File read successfully: {filename}, size: {file_size} bytes")
            
            return await self.convert_document(file_data, filename, output_format, encoding, options)
            
        except FileNotFoundError:
            logger.error(f"[Convert API] File not found: {file_path}")
            return None
        except PermissionError:
            logger.error(f"[Convert API] Permission denied reading file: {file_path}")
            return None
        except Exception as e:
            logger.error(f"[Convert API] Error reading file for Convert API: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return None

