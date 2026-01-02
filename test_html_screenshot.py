"""
Тест HTML Screenshot Service
"""
import asyncio
import sys
from pathlib import Path
from loguru import logger
from core.rag.html_screenshot_client import HTMLScreenshotClient

# Настройка логирования
logger.remove()
logger.add(sys.stderr, level="INFO", format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>")


async def test_html_screenshot():
    """Тест создания скриншота HTML и извлечения текста"""
    
    print("=" * 80)
    print("Тест HTML Screenshot Service")
    print("=" * 80)
    print()
    
    # Создание клиента
    client = HTMLScreenshotClient()
    print(f"📋 Клиент инициализирован")
    print(f"   Base URL: {client.base_url}")
    print(f"   Timeout: {client.timeout}s")
    print()
    
    # Тест 1: Простой HTML
    print("🧪 Тест 1: Простой HTML контент")
    print("-" * 80)
    
    simple_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Тест</title>
    </head>
    <body>
        <h1>Заголовок документа</h1>
        <p>Это параграф с текстом для тестирования OCR.</p>
        <p>Второй параграф с дополнительным текстом.</p>
        <ul>
            <li>Первый элемент списка</li>
            <li>Второй элемент списка</li>
            <li>Третий элемент списка</li>
        </ul>
    </body>
    </html>
    """
    
    try:
        text = await client.extract_text_from_html(
            html_content=simple_html,
            viewport_width=1920,
            viewport_height=1080,
            language_hints=['uk', 'ru', 'en']
        )
        
        if text:
            print(f"✅ Текст успешно извлечен!")
            print(f"   Длина текста: {len(text)} символов")
            print()
            print("📝 Извлеченный текст:")
            print("-" * 80)
            print(text[:500])
            if len(text) > 500:
                print("...")
            print("-" * 80)
        else:
            print("❌ Не удалось извлечь текст")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False
    
    print()
    
    # Тест 2: HTML файл
    print("🧪 Тест 2: HTML файл")
    print("-" * 80)
    
    html_files = list(Path('.').glob('*.html'))
    if html_files:
        html_file = html_files[0]
        print(f"📄 Тестовый файл: {html_file}")
        print(f"   Размер: {html_file.stat().st_size} байт")
        print()
        
        try:
            text = await client.extract_text_from_html_file(
                file_path=str(html_file),
                viewport_width=1920,
                viewport_height=1080,
                language_hints=['uk', 'ru', 'en']
            )
            
            if text:
                print(f"✅ Текст успешно извлечен из файла!")
                print(f"   Длина текста: {len(text)} символов")
                print()
                print("📝 Первые 500 символов:")
                print("-" * 80)
                print(text[:500])
                if len(text) > 500:
                    print("...")
                print("-" * 80)
            else:
                print("❌ Не удалось извлечь текст из файла")
                return False
                
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    else:
        print("⚠️  HTML файлы не найдены, пропускаем тест")
    
    print()
    print("=" * 80)
    print("✅ Все тесты пройдены успешно!")
    print("=" * 80)
    
    return True


if __name__ == "__main__":
    try:
        result = asyncio.run(test_html_screenshot())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Тест прерван пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

