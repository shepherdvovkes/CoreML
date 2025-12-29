#!/usr/bin/env python3
"""
Полный тест: PDF → изображения → Vision API
"""
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from loguru import logger
from core.rag.document_processor import DocumentProcessor

logger.remove()
logger.add(sys.stdout, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>")

def test_pdf_to_vision():
    """Полный тест: PDF → изображения → Vision API"""
    
    print("\n" + "="*80)
    print("ПОЛНЫЙ ТЕСТ: PDF → ИЗОБРАЖЕНИЯ → VISION API")
    print("="*80 + "\n")
    
    # Создаем тестовый PDF с текстом
    print("1. Создание тестового PDF с текстом:")
    try:
        import fitz
        doc = fitz.open()
        page = doc.new_page()
        text = "Тестовый документ для OCR\n\nЭто текст на русском языке.\nThis is text in English.\nЦе текст українською мовою."
        page.insert_text((50, 50), text, fontsize=14)
        
        pdf_path = "test_vision_pdf.pdf"
        doc.save(pdf_path)
        doc.close()
        print(f"   ✅ Создан PDF: {pdf_path}")
    except Exception as e:
        print(f"   ❌ Ошибка создания PDF: {e}")
        return False
    print()
    
    # Тест обработки через DocumentProcessor
    print("2. Обработка PDF через DocumentProcessor с Vision API:")
    try:
        processor = DocumentProcessor(use_vision_api=True)
        
        if not processor.use_vision_api:
            print("   ❌ Vision API не включен")
            return False
        
        print(f"   ✅ Vision API включен")
        print(f"   Обработка файла: {pdf_path}")
        print()
        
        # Обработка документа
        text = processor.process_document(pdf_path)
        
        if text is not None:
            if text.strip():
                print(f"   ✅ Текст успешно извлечен через Vision API!")
                print(f"   Длина текста: {len(text)} символов")
                print(f"   Первые 200 символов:")
                print(f"   {text[:200]}...")
            else:
                print("   ⚠️  Извлечена пустая строка")
        else:
            print("   ❌ Не удалось извлечь текст (вернулся None)")
            return False
        
        # Очистка
        if os.path.exists(pdf_path):
            os.remove(pdf_path)
            print(f"\n   Удален тестовый файл: {pdf_path}")
        
        print()
        print("="*80)
        print("✅ ПОЛНЫЙ ТЕСТ ПРОЙДЕН УСПЕШНО")
        print("="*80)
        return True
        
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    try:
        result = test_pdf_to_vision()
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n\nТест прерван")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

