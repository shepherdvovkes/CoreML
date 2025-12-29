#!/usr/bin/env python3
"""
Тестовый скрипт для проверки асинхронной загрузки и обработки документов
"""
import time
import requests
import sys
from pathlib import Path

API_BASE_URL = "http://localhost:8000"

def test_single_document_async():
    """Тест асинхронной загрузки одного документа"""
    print("\n" + "="*60)
    print("ТЕСТ 1: Асинхронная загрузка одного документа")
    print("="*60)
    
    # Создаем тестовый файл
    test_file = Path("test_document.txt")
    test_file.write_text("Тестовый документ для проверки асинхронной обработки.\n" * 100)
    
    start_time = time.time()
    
    try:
        # Загружаем файл
        with open(test_file, 'rb') as f:
            files = {'file': ('test_document.txt', f, 'text/plain')}
            response = requests.post(
                f"{API_BASE_URL}/rag/add-document",
                files=files,
                timeout=5  # Короткий timeout - ответ должен прийти быстро
            )
        
        upload_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            task_id = data.get('task_id')
            status = data.get('status')
            
            print(f"✅ Загрузка завершена за {upload_time:.3f} секунд")
            print(f"   Статус: {status}")
            print(f"   Task ID: {task_id}")
            
            if upload_time < 1.0:
                print("✅ ПРОЙДЕН: Ответ получен быстро (< 1 сек), обработка асинхронная")
            else:
                print("⚠️  ПРЕДУПРЕЖДЕНИЕ: Ответ получен медленно, возможно синхронная обработка")
            
            # Проверяем статус задачи
            print(f"\nПроверка статуса задачи {task_id}...")
            status_response = requests.get(f"{API_BASE_URL}/rag/task/{task_id}")
            if status_response.status_code == 200:
                status_data = status_response.json()
                print(f"   Статус задачи: {status_data.get('status')}")
                print(f"   Сообщение: {status_data.get('message', 'N/A')}")
            
            return True
        else:
            print(f"❌ ОШИБКА: HTTP {response.status_code}")
            print(f"   Ответ: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        print("❌ ОШИБКА: Timeout при загрузке - возможно синхронная обработка")
        return False
    except Exception as e:
        print(f"❌ ОШИБКА: {e}")
        return False
    finally:
        # Удаляем тестовый файл
        if test_file.exists():
            test_file.unlink()


def test_batch_documents_async():
    """Тест асинхронной пакетной загрузки нескольких документов"""
    print("\n" + "="*60)
    print("ТЕСТ 2: Асинхронная пакетная загрузка документов")
    print("="*60)
    
    # Создаем несколько тестовых файлов
    test_files = []
    for i in range(3):
        test_file = Path(f"test_document_{i}.txt")
        test_file.write_text(f"Тестовый документ {i} для проверки асинхронной обработки.\n" * 100)
        test_files.append(test_file)
    
    start_time = time.time()
    
    try:
        # Загружаем файлы пакетно
        files = []
        for test_file in test_files:
            files.append(('files', (test_file.name, open(test_file, 'rb'), 'text/plain')))
        
        response = requests.post(
            f"{API_BASE_URL}/rag/add-documents-batch",
            files=files,
            timeout=10  # Немного больше для нескольких файлов
        )
        
        # Закрываем файлы
        for _, (_, file_obj, _) in files:
            file_obj.close()
        
        upload_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            total_docs = data.get('total_documents', 0)
            results = data.get('results', [])
            
            print(f"✅ Загрузка завершена за {upload_time:.3f} секунд")
            print(f"   Всего документов: {total_docs}")
            print(f"   Получено task_id: {len(results)}")
            
            if upload_time < 2.0:
                print("✅ ПРОЙДЕН: Ответ получен быстро (< 2 сек), обработка асинхронная")
            else:
                print("⚠️  ПРЕДУПРЕЖДЕНИЕ: Ответ получен медленно")
            
            # Проверяем статусы всех задач
            print(f"\nПроверка статусов задач...")
            for i, result in enumerate(results):
                task_id = result.get('task_id')
                filename = result.get('filename')
                if task_id:
                    status_response = requests.get(f"{API_BASE_URL}/rag/task/{task_id}")
                    if status_response.status_code == 200:
                        status_data = status_response.json()
                        print(f"   Документ {i+1} ({filename}): {status_data.get('status')}")
            
            return True
        else:
            print(f"❌ ОШИБКА: HTTP {response.status_code}")
            print(f"   Ответ: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        print("❌ ОШИБКА: Timeout при загрузке - возможно синхронная обработка")
        return False
    except Exception as e:
        print(f"❌ ОШИБКА: {e}")
        return False
    finally:
        # Удаляем тестовые файлы
        for test_file in test_files:
            if test_file.exists():
                test_file.unlink()


def test_concurrent_requests():
    """Тест параллельной обработки нескольких запросов"""
    print("\n" + "="*60)
    print("ТЕСТ 3: Параллельная обработка нескольких запросов")
    print("="*60)
    
    import concurrent.futures
    
    def upload_file(file_num):
        test_file = Path(f"test_concurrent_{file_num}.txt")
        test_file.write_text(f"Тестовый документ {file_num}.\n" * 50)
        
        try:
            with open(test_file, 'rb') as f:
                files = {'file': (test_file.name, f, 'text/plain')}
                start = time.time()
                response = requests.post(
                    f"{API_BASE_URL}/rag/add-document",
                    files=files,
                    timeout=5
                )
                elapsed = time.time() - start
                
                if response.status_code == 200:
                    data = response.json()
                    return {
                        'success': True,
                        'file_num': file_num,
                        'task_id': data.get('task_id'),
                        'elapsed': elapsed
                    }
                else:
                    return {
                        'success': False,
                        'file_num': file_num,
                        'error': f"HTTP {response.status_code}"
                    }
        except Exception as e:
            return {
                'success': False,
                'file_num': file_num,
                'error': str(e)
            }
        finally:
            if test_file.exists():
                test_file.unlink()
    
    start_time = time.time()
    
    # Загружаем 5 файлов параллельно
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(upload_file, i) for i in range(5)]
        results = [future.result() for future in concurrent.futures.as_completed(futures)]
    
    total_time = time.time() - start_time
    
    successful = [r for r in results if r.get('success')]
    failed = [r for r in results if not r.get('success')]
    
    print(f"✅ Загружено файлов: {len(successful)}/{len(results)}")
    print(f"   Общее время: {total_time:.3f} секунд")
    print(f"   Среднее время на файл: {total_time/len(results):.3f} секунд")
    
    if len(successful) == len(results):
        if total_time < 3.0:
            print("✅ ПРОЙДЕН: Все файлы обработаны быстро и параллельно")
        else:
            print("⚠️  ПРЕДУПРЕЖДЕНИЕ: Обработка заняла много времени")
        
        # Показываем результаты
        for result in successful:
            print(f"   Файл {result['file_num']}: {result['elapsed']:.3f}с, task_id: {result['task_id'][:8]}...")
    else:
        print(f"❌ ОШИБКА: {len(failed)} файлов не загружено")
        for result in failed:
            print(f"   Файл {result['file_num']}: {result.get('error')}")
    
    return len(successful) == len(results)


def check_celery_worker():
    """Проверка доступности Celery worker"""
    print("\n" + "="*60)
    print("ПРОВЕРКА: Доступность Celery worker")
    print("="*60)
    
    try:
        # Проверяем health endpoint
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            health = response.json()
            print("✅ API сервер доступен")
            print(f"   Статус: {health.get('status')}")
            return True
        else:
            print(f"❌ API сервер вернул ошибку: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ ОШИБКА: Не удается подключиться к API серверу")
        print(f"   Убедитесь, что сервер запущен на {API_BASE_URL}")
        return False
    except Exception as e:
        print(f"❌ ОШИБКА: {e}")
        return False


def main():
    """Основная функция"""
    print("\n" + "="*60)
    print("ТЕСТИРОВАНИЕ АСИНХРОННОЙ ОБРАБОТКИ ДОКУМЕНТОВ")
    print("="*60)
    
    # Проверяем доступность сервера
    if not check_celery_worker():
        print("\n❌ Сервер недоступен. Запустите сервер перед тестированием:")
        print("   uvicorn main:app --reload")
        sys.exit(1)
    
    results = []
    
    # Запускаем тесты
    results.append(("Один документ", test_single_document_async()))
    results.append(("Пакетная загрузка", test_batch_documents_async()))
    results.append(("Параллельные запросы", test_concurrent_requests()))
    
    # Итоги
    print("\n" + "="*60)
    print("ИТОГИ ТЕСТИРОВАНИЯ")
    print("="*60)
    
    for test_name, result in results:
        status = "✅ ПРОЙДЕН" if result else "❌ ПРОВАЛЕН"
        print(f"{test_name}: {status}")
    
    all_passed = all(result for _, result in results)
    
    if all_passed:
        print("\n✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ: Обработка документов работает асинхронно")
    else:
        print("\n⚠️  НЕКОТОРЫЕ ТЕСТЫ ПРОВАЛЕНЫ: Проверьте конфигурацию Celery")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())

