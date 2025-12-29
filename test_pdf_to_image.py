#!/usr/bin/env python3
"""
Тест конвертации PDF в изображения
"""
import sys
import os
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent))

from loguru import logger
from core.rag.document_processor import DocumentProcessor

# Настройка логирования
logger.remove()
logger.add(sys.stdout, level="DEBUG", format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>")

def test_pdf_to_image():
    """Тест конвертации PDF в изображения"""
    
    print("\n" + "="*80)
    print("ТЕСТ КОНВЕРТАЦИИ PDF В ИЗОБРАЖЕНИЯ")
    print("="*80 + "\n")
    
    # Проверка наличия PyMuPDF
    print("1. Проверка наличия PyMuPDF (fitz):")
    try:
        import fitz
        print(f"   ✅ PyMuPDF установлен, версия: {fitz.version}")
    except ImportError:
        print("   ❌ PyMuPDF не установлен!")
        print("   Установите: pip install PyMuPDF")
        return False
    print()
    
    # Создание DocumentProcessor
    print("2. Создание DocumentProcessor:")
    try:
        processor = DocumentProcessor(use_vision_api=True)
        print("   ✅ DocumentProcessor создан")
        if not processor.use_vision_api:
            print("   ⚠️  Vision API не включен (но это не критично для теста конвертации)")
    except Exception as e:
        print(f"   ❌ Ошибка создания DocumentProcessor: {e}")
        return False
    print()
    
    # Проверка метода _pdf_to_images
    print("3. Проверка метода _pdf_to_images:")
    if not hasattr(processor, '_pdf_to_images'):
        print("   ❌ Метод _pdf_to_images не найден!")
        return False
    print("   ✅ Метод _pdf_to_images найден")
    print()
    
    # Тест с реальным PDF файлом
    print("4. Тест конвертации PDF:")
    
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
    else:
        # Ищем PDF файлы в проекте
        pdf_files = list(Path('.').rglob('*.pdf'))
        if pdf_files:
            pdf_path = str(pdf_files[0])
            print(f"   Найден PDF файл: {pdf_path}")
        else:
            print("   ⚠️  PDF файлы не найдены")
            print("   Используйте: python test_pdf_to_image.py <путь_к_pdf>")
            print()
            print("   Тест создания простого PDF для проверки...")
            
            # Создаем простой тестовый PDF
            try:
                import fitz
                doc = fitz.open()  # Создаем новый PDF
                page = doc.new_page()
                # Добавляем текст на страницу
                text = "Тестовый PDF документ\nСтраница 1\n\nЭто тест конвертации PDF в изображения."
                page.insert_text((50, 50), text, fontsize=12)
                
                # Добавляем вторую страницу
                page2 = doc.new_page()
                text2 = "Страница 2\n\nБольше тестового текста для проверки OCR."
                page2.insert_text((50, 50), text2, fontsize=12)
                
                pdf_path = "test_pdf_to_image.pdf"
                doc.save(pdf_path)
                doc.close()
                print(f"   ✅ Создан тестовый PDF: {pdf_path}")
            except Exception as e:
                print(f"   ❌ Не удалось создать тестовый PDF: {e}")
                return False
    
    if not os.path.exists(pdf_path):
        print(f"   ❌ Файл не найден: {pdf_path}")
        return False
    
    print(f"   Тестируем файл: {pdf_path}")
    print(f"   Размер файла: {os.path.getsize(pdf_path)} bytes")
    print()
    
    # Конвертация PDF в изображения
    print("5. Конвертация PDF в изображения:")
    try:
        images = processor._pdf_to_images(pdf_path)
        
        if not images:
            print("   ❌ Конвертация не удалась - список изображений пуст")
            return False
        
        print(f"   ✅ Конвертация успешна!")
        print(f"   Количество страниц: {len(images)}")
        
        total_size = sum(len(img) for img in images)
        print(f"   Общий размер изображений: {total_size} bytes")
        
        for i, img_bytes in enumerate(images, 1):
            print(f"   Страница {i}: {len(img_bytes)} bytes")
        
        # Проверяем, что изображения валидные PNG
        print()
        print("6. Проверка формата изображений:")
        try:
            from PIL import Image
            import io
            
            for i, img_bytes in enumerate(images, 1):
                try:
                    img = Image.open(io.BytesIO(img_bytes))
                    print(f"   Страница {i}: {img.format}, размер: {img.size[0]}x{img.size[1]} px")
                except Exception as e:
                    print(f"   ⚠️  Страница {i}: ошибка проверки формата - {e}")
        except ImportError:
            print("   ⚠️  PIL не установлен, пропускаем проверку формата")
        
        print()
        print("="*80)
        print("✅ ТЕСТ ПРОЙДЕН УСПЕШНО")
        print("="*80)
        
        # Очистка тестового файла
        if pdf_path == "test_pdf_to_image.pdf" and os.path.exists(pdf_path):
            os.remove(pdf_path)
            print(f"\nУдален тестовый файл: {pdf_path}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Ошибка при конвертации: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    try:
        result = test_pdf_to_image()
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n\nТест прерван пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

