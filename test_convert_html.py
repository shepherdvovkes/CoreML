"""
Тест конвертации HTML в текст через Convert API
"""
import asyncio
import sys
from pathlib import Path
from loguru import logger
from core.rag.convert_client import ConvertAPIClient
from config import settings

# Настройка логирования
logger.remove()
logger.add(sys.stderr, level="INFO", format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>")


async def test_convert_html():
    """Тест конвертации HTML файла в текст"""
    
    print("=" * 80)
    print("Тест конвертации HTML в текст через Convert API")
    print("=" * 80)
    print()
    
    # Проверка конфигурации
    print("📋 Конфигурация:")
    print(f"   Convert API URL: {settings.convert_api_url}")
    print(f"   Convert API Key: {'*' * 20 if settings.convert_api_key else 'НЕ УСТАНОВЛЕН'}")
    print(f"   Timeout: {settings.convert_api_timeout}s")
    print()
    
    # Создание клиента
    client = ConvertAPIClient()
    
    if not client.is_available():
        print("❌ Convert API недоступен (не установлен API ключ)")
        print("   Установите CONVERT_API_KEY в .env файле")
        return False
    
    print("✅ Convert API клиент инициализирован")
    print()
    
    # Поиск HTML файлов в текущей директории
    html_files = list(Path('.').glob('*.html'))
    
    if not html_files:
        print("❌ HTML файлы не найдены в текущей директории")
        print("   Ожидаются файлы с расширением .html")
        return False
    
    # Используем первый найденный HTML файл
    html_file = html_files[0]
    print(f"📄 Тестовый файл: {html_file}")
    print(f"   Размер: {html_file.stat().st_size} байт")
    print()
    
    # Тест 1: Конвертация HTML в текст
    print("🧪 Тест 1: Конвертация HTML → TXT")
    print("-" * 80)
    
    try:
        converted_data = await client.convert_file(
            file_path=str(html_file),
            output_format="txt"
        )
        
        if converted_data:
            text = converted_data.decode('utf-8', errors='ignore')
            print(f"✅ Конвертация успешна!")
            print(f"   Размер результата: {len(converted_data)} байт")
            print(f"   Длина текста: {len(text)} символов")
            print()
            print("📝 Первые 500 символов результата:")
            print("-" * 80)
            print(text[:500])
            if len(text) > 500:
                print("...")
            print("-" * 80)
            print()
        else:
            print("❌ Конвертация не удалась (вернулся None)")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка при конвертации: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False
    
    # Тест 2: Конвертация из байтов
    print("🧪 Тест 2: Конвертация HTML из байтов → TXT")
    print("-" * 80)
    
    try:
        with open(html_file, 'rb') as f:
            file_data = f.read()
        
        converted_data = await client.convert_document(
            file_data=file_data,
            filename=html_file.name,
            output_format="txt"
        )
        
        if converted_data:
            text = converted_data.decode('utf-8', errors='ignore')
            print(f"✅ Конвертация из байтов успешна!")
            print(f"   Размер результата: {len(converted_data)} байт")
            print(f"   Длина текста: {len(text)} символов")
            print()
        else:
            print("❌ Конвертация из байтов не удалась (вернулся None)")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка при конвертации из байтов: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False
    
    print()
    print("=" * 80)
    print("✅ Все тесты пройдены успешно!")
    print("=" * 80)
    
    return True


if __name__ == "__main__":
    try:
        result = asyncio.run(test_convert_html())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Тест прерван пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

