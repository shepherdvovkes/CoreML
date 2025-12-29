#!/usr/bin/env python3
"""
Тестовый скрипт для проверки отправки файлов в Vision API
"""
import sys
import os
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent))

from loguru import logger
from config import settings
from core.rag.vision_client import VisionAPIClient
from core.rag.document_processor import DocumentProcessor
import asyncio

# Настройка логирования для детального вывода
logger.remove()
logger.add(sys.stdout, level="DEBUG", format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>")

async def test_vision_api_send():
    """Тест отправки файла в Vision API"""
    
    print("\n" + "="*80)
    print("ТЕСТ ОТПРАВКИ ФАЙЛА В VISION API")
    print("="*80 + "\n")
    
    # Проверка конфигурации
    print("1. Проверка конфигурации:")
    print(f"   Vision API URL: {settings.vision_api_url}")
    print(f"   Vision API Key: {'*' * 20 if settings.vision_api_key else 'NOT SET'}")
    print(f"   Vision API Timeout: {settings.vision_api_timeout}s")
    print()
    
    # Создание клиента
    print("2. Создание Vision API клиента...")
    client = VisionAPIClient()
    
    if not client.is_available():
        print("   ❌ Vision API клиент недоступен (нет API ключа)")
        return False
    
    print("   ✅ Vision API клиент создан и доступен")
    print()
    
    # Проверка доступности сервера
    print("3. Проверка доступности Vision API сервера...")
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as http_client:
            health_url = f"{settings.vision_api_url.rstrip('/')}/health"
            response = await http_client.get(health_url)
            if response.status_code == 200:
                print(f"   ✅ Сервер доступен: {health_url}")
                print(f"   Ответ: {response.json()}")
            else:
                print(f"   ⚠️  Сервер ответил с кодом: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Ошибка при проверке сервера: {e}")
        return False
    print()
    
    # Тест отправки (нужен реальный файл)
    print("4. Тест отправки файла:")
    print("   Для полного теста нужен реальный файл (изображение или PDF)")
    print("   Используйте: python test_vision_api_send.py <путь_к_файлу>")
    print()
    
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        if not os.path.exists(file_path):
            print(f"   ❌ Файл не найден: {file_path}")
            return False
        
        print(f"   Отправка файла: {file_path}")
        print(f"   Размер файла: {os.path.getsize(file_path)} bytes")
        print()
        
        # Тест отправки через DocumentProcessor
        print("5. Тест через DocumentProcessor:")
        processor = DocumentProcessor(use_vision_api=True)
        
        if not processor.use_vision_api:
            print("   ❌ Vision API не включен в DocumentProcessor")
            return False
        
        print("   ✅ Vision API включен в DocumentProcessor")
        print(f"   Обработка файла: {file_path}")
        print()
        
        try:
            text = processor.process_document(file_path)
            if text is not None:
                if text.strip():
                    print(f"   ✅ Текст успешно извлечен: {len(text)} символов")
                    print(f"   Первые 200 символов: {text[:200]}...")
                else:
                    print("   ⚠️  Извлечена пустая строка (файл может не содержать текста)")
            else:
                print("   ❌ Не удалось извлечь текст (вернулся None)")
        except Exception as e:
            print(f"   ❌ Ошибка при обработке: {e}")
            import traceback
            traceback.print_exc()
            return False
    else:
        print("   ℹ️  Пропущен (укажите путь к файлу для полного теста)")
    
    print()
    print("="*80)
    print("ТЕСТ ЗАВЕРШЕН")
    print("="*80)
    
    return True

if __name__ == "__main__":
    try:
        result = asyncio.run(test_vision_api_send())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n\nТест прерван пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

