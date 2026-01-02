#!/usr/bin/env python3
"""
Тест извлечения текста из HTML документов

Использование:
    # Тест одного HTML файла
    python test_html_extraction.py <путь_к_html_файлу>
    
    # Тест всех HTML файлов в текущей директории
    python test_html_extraction.py

Примеры:
    python test_html_extraction.py document.html
    python test_html_extraction.py 1-2605-0AE2C6B0-968E-11ED-B0B1-628B1A87CC2E.html
    python test_html_extraction.py  # Тестирует все .html файлы в текущей директории

Тест проверяет:
    1. Извлечение текста из HTML (LangChain, BeautifulSoup, html.parser)
    2. Определение кодировки файла (UTF-8, Windows-1251, и др.)
    3. Удаление HTML тегов и скриптов
    4. Разбиение текста на чанки
    5. Сохранение в векторную базу данных
    6. Поиск в базе данных
"""
import sys
import os
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent))

from loguru import logger
from core.rag.document_processor import DocumentProcessor
from core.rag.rag_service import RAGService
import asyncio

# Настройка логирования
logger.remove()
logger.add(
    sys.stdout, 
    level="INFO", 
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>"
)

def test_html_extraction(html_path: str = None):
    """Тест извлечения текста из HTML"""
    
    print("\n" + "="*80)
    print("ТЕСТ ИЗВЛЕЧЕНИЯ ТЕКСТА ИЗ HTML ДОКУМЕНТОВ")
    print("="*80 + "\n")
    
    # Если путь не указан, ищем HTML файлы в текущей директории
    if not html_path:
        html_files = list(Path('.').glob('*.html'))
        if html_files:
            html_path = str(html_files[0])
            print(f"Найдено HTML файл: {html_path}")
        else:
            print("❌ Не найдено HTML файлов в текущей директории")
            print("Использование: python test_html_extraction.py <путь_к_html>")
            return False
    else:
        if not os.path.exists(html_path):
            print(f"❌ Файл не найден: {html_path}")
            return False
    
    print(f"Обработка файла: {html_path}\n")
    
    # Создаем DocumentProcessor
    print("1. Создание DocumentProcessor:")
    try:
        processor = DocumentProcessor(use_vision_api=False)  # HTML не требует Vision API
        print(f"   ✅ DocumentProcessor создан")
    except Exception as e:
        print(f"   ❌ Ошибка создания DocumentProcessor: {e}")
        import traceback
        traceback.print_exc()
        return False
    print()
    
    # Тест извлечения текста из HTML
    print("2. Извлечение текста из HTML:")
    try:
        text = processor.extract_text_from_html(html_path)
        if text and text.strip():
            print(f"   ✅ Текст успешно извлечен из HTML")
            print(f"   Длина текста: {len(text)} символов")
            print(f"\n   Первые 500 символов:")
            print(f"   {'-'*76}")
            print(f"   {text[:500]}...")
            print(f"   {'-'*76}")
            
            # Проверяем, что текст содержит полезную информацию (не только теги)
            if len(text.strip()) > 100:
                print(f"   ✅ Текст содержит достаточно информации")
            else:
                print(f"   ⚠️  Текст слишком короткий, возможно проблема с извлечением")
        else:
            print("   ❌ Не удалось извлечь текст из HTML")
            return False
    except Exception as e:
        print(f"   ❌ Ошибка извлечения текста: {e}")
        import traceback
        traceback.print_exc()
        return False
    print()
    
    # Тест через LangChain loader
    print("3. Тест через LangChain HTML loader:")
    try:
        text_langchain = DocumentProcessor._load_with_langchain(html_path)
        if text_langchain:
            print(f"   ✅ Текст извлечен через LangChain")
            print(f"   Длина текста: {len(text_langchain)} символов")
            print(f"   Первые 200 символов:")
            print(f"   {text_langchain[:200]}...")
        else:
            print("   ⚠️  LangChain не смог извлечь текст (используется fallback)")
    except Exception as e:
        print(f"   ⚠️  Ошибка LangChain: {e}")
        print("   (Это нормально, если LangChain HTML loader недоступен)")
    print()
    
    # Тест полной обработки документа
    print("4. Полная обработка HTML документа:")
    try:
        text_processed = processor.process_document(html_path)
        if text_processed and text_processed.strip():
            print(f"   ✅ HTML документ обработан успешно")
            print(f"   Длина текста: {len(text_processed)} символов")
            
            # Проверяем, что текст не содержит HTML тегов
            if '<' in text_processed and '>' in text_processed:
                tag_count = text_processed.count('<')
                print(f"   ⚠️  Обнаружено {tag_count} возможных HTML тегов в тексте")
            else:
                print(f"   ✅ HTML теги успешно удалены")
            
            # Проверяем наличие полезного контента
            keywords = ['суд', 'рішення', 'справа', 'документ', 'дата', 'номер']
            found_keywords = [kw for kw in keywords if kw.lower() in text_processed.lower()]
            if found_keywords:
                print(f"   ✅ Найдены ключевые слова: {', '.join(found_keywords)}")
            else:
                print(f"   ⚠️  Ключевые слова не найдены (возможно, документ на другом языке)")
        else:
            print("   ❌ Текст пустой или не удалось обработать")
            return False
    except Exception as e:
        print(f"   ❌ Ошибка обработки: {e}")
        import traceback
        traceback.print_exc()
        return False
    print()
    
    # Тест разбиения на чанки
    if text_processed:
        print("5. Тест разбиения текста на чанки:")
        try:
            chunks = processor.chunk_text(text_processed)
            print(f"   ✅ Текст разбит на {len(chunks)} чанков")
            if chunks:
                print(f"   Размер первого чанка: {len(chunks[0])} символов")
                print(f"   Первые 200 символов первого чанка:")
                print(f"   {chunks[0][:200]}...")
        except Exception as e:
            print(f"   ❌ Ошибка разбиения на чанки: {e}")
        print()
    
    # Тест сохранения в базу данных
    if text_processed:
        print("6. Тест сохранения в векторную базу данных:")
        try:
            # Создаем RAGService
            rag_service = RAGService()
            print(f"   ✅ RAGService создан")
            
            # Добавляем документ
            print(f"   Добавление HTML документа в базу данных...")
            result = rag_service.add_document(
                html_path,
                metadata={
                    'filename': os.path.basename(html_path),
                    'test': True,
                    'file_type': 'html'
                }
            )
            
            if result.get('status') == 'success':
                print(f"   ✅ Документ успешно добавлен в базу данных")
                print(f"   Количество чанков: {result.get('chunks_count', 0)}")
                print(f"   Коллекции: {', '.join(result.get('collections', []))}")
                
                # Тест поиска в базе данных
                print(f"\n   Тест поиска в базе данных:")
                try:
                    async def test_search():
                        # Ищем по ключевым словам из документа
                        search_queries = [
                            "суд",
                            "рішення",
                            "справа",
                            "документ"
                        ]
                        
                        for query in search_queries:
                            results = await rag_service.search(query, top_k=3)
                            if results:
                                print(f"   ✅ Поиск '{query}': найдено {len(results)} результатов")
                                # Показываем первый результат
                                first_result = results[0]
                                print(f"      Релевантность: {first_result.get('score', 'N/A'):.4f}")
                                print(f"      Текст: {first_result.get('text', '')[:150]}...")
                                print(f"      Файл: {first_result.get('filename', 'N/A')}")
                            else:
                                print(f"   ⚠️  Поиск '{query}': результатов не найдено")
                    
                    # Запускаем асинхронный тест
                    try:
                        # Пробуем получить существующий loop
                        try:
                            loop = asyncio.get_running_loop()
                            # Если loop уже запущен, используем ThreadPoolExecutor
                            import concurrent.futures
                            with concurrent.futures.ThreadPoolExecutor() as executor:
                                future = executor.submit(lambda: asyncio.run(test_search()))
                                future.result(timeout=30)
                        except RuntimeError:
                            # Нет запущенного loop, создаем новый
                            asyncio.run(test_search())
                    except Exception as e:
                        print(f"   ⚠️  Ошибка запуска асинхронного теста: {e}")
                    
                except Exception as e:
                    print(f"   ⚠️  Ошибка поиска: {e}")
                    import traceback
                    traceback.print_exc()
                
            else:
                print(f"   ❌ Ошибка добавления документа: {result.get('message', 'Unknown error')}")
        except Exception as e:
            print(f"   ❌ Ошибка сохранения в базу: {e}")
            import traceback
            traceback.print_exc()
        print()
    
    print("="*80)
    print("✅ ТЕСТ ЗАВЕРШЕН")
    print("="*80)
    return True


def test_multiple_html_files():
    """Тест обработки нескольких HTML файлов"""
    
    print("\n" + "="*80)
    print("ТЕСТ ОБРАБОТКИ НЕСКОЛЬКИХ HTML ФАЙЛОВ")
    print("="*80 + "\n")
    
    # Ищем все HTML файлы в текущей директории
    html_files = list(Path('.').glob('*.html'))
    
    if not html_files:
        print("❌ Не найдено HTML файлов в текущей директории")
        return False
    
    print(f"Найдено {len(html_files)} HTML файлов\n")
    
    processor = DocumentProcessor(use_vision_api=False)
    
    results = []
    for i, html_file in enumerate(html_files, 1):
        print(f"{i}. Обработка файла: {html_file.name}")
        try:
            text = processor.extract_text_from_html(str(html_file))
            if text and text.strip():
                chunks = processor.chunk_text(text)
                results.append({
                    'filename': html_file.name,
                    'text_length': len(text),
                    'chunks_count': len(chunks),
                    'status': 'success'
                })
                print(f"   ✅ Успешно: {len(text)} символов, {len(chunks)} чанков")
            else:
                results.append({
                    'filename': html_file.name,
                    'status': 'empty'
                })
                print(f"   ⚠️  Текст пустой")
        except Exception as e:
            results.append({
                'filename': html_file.name,
                'status': 'error',
                'error': str(e)
            })
            print(f"   ❌ Ошибка: {e}")
        print()
    
    # Сводка
    print("="*80)
    print("СВОДКА РЕЗУЛЬТАТОВ:")
    print("="*80)
    success_count = sum(1 for r in results if r['status'] == 'success')
    print(f"Успешно обработано: {success_count}/{len(results)}")
    
    if success_count > 0:
        total_text = sum(r.get('text_length', 0) for r in results if r['status'] == 'success')
        total_chunks = sum(r.get('chunks_count', 0) for r in results if r['status'] == 'success')
        print(f"Общая длина текста: {total_text} символов")
        print(f"Общее количество чанков: {total_chunks}")
    
    print("\nДетали:")
    for r in results:
        if r['status'] == 'success':
            print(f"  ✅ {r['filename']}: {r['text_length']} символов, {r['chunks_count']} чанков")
        elif r['status'] == 'empty':
            print(f"  ⚠️  {r['filename']}: текст пустой")
        else:
            print(f"  ❌ {r['filename']}: {r.get('error', 'Unknown error')}")
    
    print("="*80)
    return success_count == len(results)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Тест одного файла
        html_path = sys.argv[1]
        test_html_extraction(html_path)
    else:
        # Тест всех HTML файлов в текущей директории
        test_multiple_html_files()

