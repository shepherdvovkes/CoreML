#!/usr/bin/env python3
"""
Тест розпізнавання PDF в текст з перевіркою фільтрації
"""
import sys
import os
from pathlib import Path

# Додаємо кореневу директорію в шлях
sys.path.insert(0, str(Path(__file__).parent))

from loguru import logger
from core.rag.document_processor import DocumentProcessor
from core.rag.rag_service import RAGService
import asyncio

# Налаштування логування
logger.remove()
logger.add(
    sys.stdout, 
    level="INFO", 
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>"
)

def test_pdf_extraction(pdf_path: str = None):
    """Тест розпізнавання PDF в текст"""
    
    print("\n" + "="*80)
    print("ТЕСТ РОЗПІЗНАВАННЯ PDF В ТЕКСТ")
    print("="*80 + "\n")
    
    # Якщо шлях не вказано, шукаємо PDF файли в поточній директорії
    if not pdf_path:
        pdf_files = list(Path('.').glob('*.pdf'))
        if pdf_files:
            pdf_path = str(pdf_files[0])
            print(f"Знайдено PDF файл: {pdf_path}")
        else:
            print("❌ Не знайдено PDF файлів у поточній директорії")
            print("Використання: python test_pdf_extraction.py <шлях_до_pdf>")
            return False
    else:
        if not os.path.exists(pdf_path):
            print(f"❌ Файл не знайдено: {pdf_path}")
            return False
    
    print(f"Обробка файлу: {pdf_path}\n")
    
    # Створюємо DocumentProcessor
    print("1. Створення DocumentProcessor:")
    try:
        processor = DocumentProcessor(use_vision_api=True)
        print(f"   ✅ DocumentProcessor створено")
        print(f"   Vision API увімкнено: {processor.use_vision_api}")
        if processor.vision_client:
            print(f"   Vision API доступний: {processor.vision_client.is_available()}")
    except Exception as e:
        print(f"   ❌ Помилка створення DocumentProcessor: {e}")
        import traceback
        traceback.print_exc()
        return False
    print()
    
    # Тест конвертації PDF в зображення
    print("2. Конвертація PDF в зображення:")
    try:
        images = processor._pdf_to_images(pdf_path)
        if images:
            print(f"   ✅ PDF конвертовано в {len(images)} зображень")
            for i, img_bytes in enumerate(images):
                print(f"   Сторінка {i+1}: {len(img_bytes)} байт")
        else:
            print("   ⚠️  Не вдалося конвертувати PDF в зображення")
    except Exception as e:
        print(f"   ❌ Помилка конвертації: {e}")
    print()
    
    # Тест витягування тексту через Vision API
    print("3. Витягування тексту через Vision API:")
    try:
        text_vision = processor._extract_text_from_pdf_via_vision(pdf_path)
        if text_vision is not None:
            print(f"   ✅ Текст витягнуто через Vision API")
            print(f"   Довжина тексту: {len(text_vision)} символів")
            print(f"\n   Перші 500 символів (ДО фільтрації):")
            print(f"   {'-'*76}")
            print(f"   {text_vision[:500]}...")
            print(f"   {'-'*76}")
        else:
            print("   ❌ Не вдалося витягнути текст через Vision API")
    except Exception as e:
        print(f"   ❌ Помилка витягування через Vision API: {e}")
        import traceback
        traceback.print_exc()
    print()
    
    # Тест повної обробки (з фільтрацією)
    print("4. Повна обробка PDF (з фільтрацією):")
    try:
        text_processed = processor.extract_text_from_pdf(pdf_path)
        if text_processed:
            print(f"   ✅ PDF оброблено успішно")
            print(f"   Довжина тексту: {len(text_processed)} символів")
            print(f"\n   Перші 500 символів (ПІСЛЯ фільтрації):")
            print(f"   {'-'*76}")
            print(f"   {text_processed[:500]}...")
            print(f"   {'-'*76}")
            
            # Порівняння довжини
            if text_vision and len(text_vision) != len(text_processed):
                removed = len(text_vision) - len(text_processed)
                print(f"\n   📊 Видалено технічної інформації: {removed} символів ({removed/len(text_vision)*100:.1f}%)")
        else:
            print("   ⚠️  Текст порожній або не вдалося обробити")
    except Exception as e:
        print(f"   ❌ Помилка обробки: {e}")
        import traceback
        traceback.print_exc()
    print()
    
    # Тест фільтрації окремо
    if text_vision:
        print("5. Тест фільтрації технічної інформації:")
        try:
            cleaned = DocumentProcessor._clean_ocr_text(text_vision)
            print(f"   ✅ Фільтрація виконана")
            print(f"   Довжина до: {len(text_vision)} символів")
            print(f"   Довжина після: {len(cleaned)} символів")
            if len(text_vision) != len(cleaned):
                removed = len(text_vision) - len(cleaned)
                print(f"   Видалено: {removed} символів ({removed/len(text_vision)*100:.1f}%)")
        except Exception as e:
            print(f"   ❌ Помилка фільтрації: {e}")
        print()
    
    # Тест розбиття на чанки
    if text_processed:
        print("6. Тест розбиття тексту на чанки:")
        try:
            chunks = processor.chunk_text(text_processed)
            print(f"   ✅ Текст розбито на {len(chunks)} чанків")
            if chunks:
                print(f"   Розмір першого чанку: {len(chunks[0])} символів")
                print(f"   Перші 200 символів першого чанку:")
                print(f"   {chunks[0][:200]}...")
        except Exception as e:
            print(f"   ❌ Помилка розбиття на чанки: {e}")
        print()
    
    # Тест збереження в базу даних
    if text_processed:
        print("7. Тест збереження в векторну базу даних:")
        try:
            # Створюємо RAGService
            rag_service = RAGService()
            print(f"   ✅ RAGService створено")
            
            # Додаємо документ
            print(f"   Додавання документа в базу даних...")
            result = rag_service.add_document(
                pdf_path,
                metadata={
                    'filename': os.path.basename(pdf_path),
                    'test': True
                }
            )
            
            if result.get('status') == 'success':
                print(f"   ✅ Документ успішно додано в базу даних")
                print(f"   Кількість чанків: {result.get('chunks_count', 0)}")
                print(f"   Колекції: {', '.join(result.get('collections', []))}")
                
                # Тест пошуку в базі даних
                print(f"\n   Тест пошуку в базі даних:")
                try:
                    # Використовуємо асинхронний пошук
                    async def test_search():
                        # Шукаємо за ключовими словами з документа
                        search_queries = [
                            "Дія Сіті",
                            "резидент",
                            "Міністерство цифрової трансформації"
                        ]
                        
                        for query in search_queries:
                            results = await rag_service.search(query, top_k=3)
                            if results:
                                print(f"   ✅ Пошук '{query}': знайдено {len(results)} результатів")
                                # Показуємо перший результат
                                first_result = results[0]
                                print(f"      Релевантність: {first_result.get('score', 'N/A'):.4f}")
                                print(f"      Текст: {first_result.get('text', '')[:150]}...")
                                print(f"      Файл: {first_result.get('filename', 'N/A')}")
                            else:
                                print(f"   ⚠️  Пошук '{query}': результатів не знайдено")
                    
                    # Запускаємо асинхронний тест
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            # Якщо loop вже запущений, використовуємо ThreadPoolExecutor
                            import concurrent.futures
                            with concurrent.futures.ThreadPoolExecutor() as executor:
                                future = executor.submit(lambda: asyncio.run(test_search()))
                                future.result(timeout=30)
                        else:
                            loop.run_until_complete(test_search())
                    except RuntimeError:
                        asyncio.run(test_search())
                    
                except Exception as e:
                    print(f"   ⚠️  Помилка пошуку: {e}")
                    import traceback
                    traceback.print_exc()
                
                # Тест отримання чанків документа
                print(f"\n   Тест отримання чанків документа:")
                try:
                    filename = os.path.basename(pdf_path)
                    # Використовуємо синхронний метод з vector_store
                    chunks_from_db = rag_service.vector_store.get_document_chunks(filename)
                    if chunks_from_db:
                        print(f"   ✅ Отримано {len(chunks_from_db)} чанків з бази даних")
                        print(f"   Перший чанк з бази:")
                        first_chunk = chunks_from_db[0]
                        chunk_text = first_chunk.get('text', '')
                        chunk_metadata = first_chunk.get('metadata', {})
                        print(f"   Текст: {chunk_text[:200]}...")
                        print(f"   Метадані: filename={chunk_metadata.get('filename', 'N/A')}, chunk_id={first_chunk.get('chunk_id', 'N/A')}")
                        
                        # Перевірка, що текст зберігся правильно
                        total_text_length = sum(len(ch.get('text', '')) for ch in chunks_from_db)
                        print(f"   Загальна довжина тексту в базі: {total_text_length} символів")
                        print(f"   Оригінальна довжина: {len(text_processed)} символів")
                        if abs(total_text_length - len(text_processed)) < len(text_processed) * 0.1:
                            print(f"   ✅ Текст зберігся коректно (різниця < 10%)")
                        else:
                            print(f"   ⚠️  Є відмінності в довжині тексту")
                    else:
                        print(f"   ⚠️  Чанки не знайдено в базі даних")
                except Exception as e:
                    print(f"   ⚠️  Помилка отримання чанків: {e}")
                    import traceback
                    traceback.print_exc()
                
            else:
                print(f"   ❌ Помилка додавання документа: {result.get('message', 'Unknown error')}")
        except Exception as e:
            print(f"   ❌ Помилка збереження в базу: {e}")
            import traceback
            traceback.print_exc()
        print()
    
    # Тест через LangChain (fallback)
    print("8. Тест через LangChain (fallback):")
    try:
        text_langchain = DocumentProcessor._load_with_langchain(pdf_path)
        if text_langchain:
            print(f"   ✅ Текст витягнуто через LangChain")
            print(f"   Довжина тексту: {len(text_langchain)} символів")
            print(f"   Перші 200 символів:")
            print(f"   {text_langchain[:200]}...")
        else:
            print("   ⚠️  LangChain не зміг витягнути текст")
    except Exception as e:
        print(f"   ❌ Помилка LangChain: {e}")
    print()
    
    print("="*80)
    print("✅ ТЕСТ ЗАВЕРШЕНО")
    print("="*80)
    return True

if __name__ == "__main__":
    pdf_path = sys.argv[1] if len(sys.argv) > 1 else None
    test_pdf_extraction(pdf_path)

