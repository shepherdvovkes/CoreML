#!/usr/bin/env python3
"""
Тест одновременной отправки трёх PDF файлов
"""
import time
import requests
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

API_BASE_URL = "http://localhost:8000"

# Пути к файлам
PDF_FILES = [
    "2-2-83dbbec0-9650-11ed-9f5f-491ff4e2e860.PDF",
    "2-2-840d2f00-9650-11ed-9f5f-491ff4e2e860.pdf",
    "2-2-839280c0-9650-11ed-9012-c14e6aee1b6d.PDF"
]

def check_server():
    """Проверка доступности сервера"""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=10)
        if response.status_code == 200:
            print("✅ API сервер доступен")
            return True
        else:
            print(f"❌ API сервер вернул ошибку: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print(f"❌ Не удается подключиться к API серверу на {API_BASE_URL}")
        print("   Убедитесь, что сервер запущен: uvicorn main:app --reload")
        return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False


def upload_single_file(file_path, file_index):
    """Загрузка одного файла"""
    file_path_obj = Path(file_path)
    if not file_path_obj.exists():
        return {
            'success': False,
            'file_index': file_index,
            'filename': file_path,
            'error': 'File not found'
        }
    
    try:
        start_time = time.time()
        with open(file_path_obj, 'rb') as f:
            files = {'file': (file_path_obj.name, f, 'application/pdf')}
            response = requests.post(
                f"{API_BASE_URL}/rag/add-document",
                files=files,
                timeout=30
            )
        
        elapsed = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            return {
                'success': True,
                'file_index': file_index,
                'filename': file_path_obj.name,
                'task_id': data.get('task_id'),
                'status': data.get('status'),
                'elapsed': elapsed,
                'response': data
            }
        else:
            return {
                'success': False,
                'file_index': file_index,
                'filename': file_path_obj.name,
                'error': f"HTTP {response.status_code}: {response.text}",
                'elapsed': elapsed
            }
    except Exception as e:
        return {
            'success': False,
            'file_index': file_index,
            'filename': file_path_obj.name,
            'error': str(e)
        }


def upload_batch():
    """Пакетная загрузка всех файлов"""
    print("\n" + "="*60)
    print("ТЕСТ: Пакетная загрузка трёх PDF файлов")
    print("="*60)
    
    # Проверяем наличие файлов
    missing_files = []
    for pdf_file in PDF_FILES:
        if not Path(pdf_file).exists():
            missing_files.append(pdf_file)
    
    if missing_files:
        print(f"❌ Файлы не найдены: {', '.join(missing_files)}")
        return False
    
    print(f"📁 Файлы для загрузки:")
    for i, pdf_file in enumerate(PDF_FILES, 1):
        size = Path(pdf_file).stat().st_size / 1024  # KB
        print(f"   {i}. {pdf_file} ({size:.1f} KB)")
    
    start_time = time.time()
    
    try:
        # Подготавливаем файлы для пакетной загрузки
        files = []
        file_handles = []
        for pdf_file in PDF_FILES:
            file_path = Path(pdf_file)
            file_handle = open(file_path, 'rb')
            file_handles.append(file_handle)
            files.append(('files', (file_path.name, file_handle, 'application/pdf')))
        
        # Отправляем пакетный запрос
        print(f"\n📤 Отправка пакетного запроса...")
        response = requests.post(
            f"{API_BASE_URL}/rag/add-documents-batch",
            files=files,
            timeout=60
        )
        
        # Закрываем файлы
        for handle in file_handles:
            handle.close()
        
        upload_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Загрузка завершена за {upload_time:.3f} секунд")
            print(f"   Статус: {data.get('status')}")
            print(f"   Всего документов: {data.get('total_documents')}")
            
            results = data.get('results', [])
            print(f"\n📋 Результаты:")
            for i, result in enumerate(results, 1):
                task_id = result.get('task_id')
                filename = result.get('filename')
                print(f"   {i}. {filename}")
                print(f"      Task ID: {task_id}")
            
            # Проверяем статусы задач
            print(f"\n⏳ Проверка статусов задач (через 3 секунды)...")
            time.sleep(3)
            
            for i, result in enumerate(results, 1):
                task_id = result.get('task_id')
                filename = result.get('filename')
                if task_id:
                    try:
                        status_response = requests.get(
                            f"{API_BASE_URL}/rag/task/{task_id}",
                            timeout=10
                        )
                        if status_response.status_code == 200:
                            status_data = status_response.json()
                            status = status_data.get('status')
                            print(f"   {i}. {filename}: {status}")
                            if status == 'success':
                                result_info = status_data.get('result', {})
                                chunks = result_info.get('chunks_count', 0)
                                print(f"      ✅ Обработано, чанков: {chunks}")
                            elif status == 'processing':
                                print(f"      ⏳ Обрабатывается...")
                            elif status == 'pending':
                                print(f"      ⏸️  В очереди...")
                            elif status in ['failure', 'error']:
                                error = status_data.get('error', 'Unknown error')
                                print(f"      ❌ Ошибка: {error}")
                    except Exception as e:
                        print(f"   {i}. {filename}: Ошибка проверки статуса - {e}")
            
            return True
        else:
            print(f"❌ ОШИБКА: HTTP {response.status_code}")
            print(f"   Ответ: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        return False


def upload_concurrent():
    """Параллельная загрузка файлов (каждый отдельным запросом)"""
    print("\n" + "="*60)
    print("ТЕСТ: Параллельная загрузка трёх PDF файлов")
    print("="*60)
    
    # Проверяем наличие файлов
    missing_files = []
    for pdf_file in PDF_FILES:
        if not Path(pdf_file).exists():
            missing_files.append(pdf_file)
    
    if missing_files:
        print(f"❌ Файлы не найдены: {', '.join(missing_files)}")
        return False
    
    print(f"📁 Файлы для загрузки:")
    for i, pdf_file in enumerate(PDF_FILES, 1):
        size = Path(pdf_file).stat().st_size / 1024  # KB
        print(f"   {i}. {pdf_file} ({size:.1f} KB)")
    
    start_time = time.time()
    
    # Загружаем файлы параллельно
    print(f"\n📤 Отправка параллельных запросов...")
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(upload_single_file, pdf_file, i): pdf_file
            for i, pdf_file in enumerate(PDF_FILES, 1)
        }
        
        results = []
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
    
    total_time = time.time() - start_time
    
    # Сортируем результаты по индексу
    results.sort(key=lambda x: x['file_index'])
    
    successful = [r for r in results if r.get('success')]
    failed = [r for r in results if not r.get('success')]
    
    print(f"\n✅ Загружено файлов: {len(successful)}/{len(results)}")
    print(f"   Общее время: {total_time:.3f} секунд")
    print(f"   Среднее время на файл: {total_time/len(results):.3f} секунд")
    
    print(f"\n📋 Результаты:")
    for result in results:
        if result.get('success'):
            print(f"   ✅ {result['filename']}")
            print(f"      Task ID: {result['task_id']}")
            print(f"      Время загрузки: {result['elapsed']:.3f}с")
        else:
            print(f"   ❌ {result['filename']}")
            print(f"      Ошибка: {result.get('error')}")
    
    if len(successful) == len(results):
        # Проверяем статусы задач
        print(f"\n⏳ Проверка статусов задач (через 3 секунды)...")
        time.sleep(3)
        
        for result in successful:
            task_id = result.get('task_id')
            filename = result['filename']
            if task_id:
                try:
                    status_response = requests.get(
                        f"{API_BASE_URL}/rag/task/{task_id}",
                        timeout=10
                    )
                    if status_response.status_code == 200:
                        status_data = status_response.json()
                        status = status_data.get('status')
                        print(f"   {filename}: {status}")
                        if status == 'success':
                            result_info = status_data.get('result', {})
                            chunks = result_info.get('chunks_count', 0)
                            print(f"      ✅ Обработано, чанков: {chunks}")
                except Exception as e:
                    print(f"   {filename}: Ошибка проверки статуса - {e}")
    
    return len(successful) == len(results)


def main():
    """Основная функция"""
    print("\n" + "="*60)
    print("ТЕСТИРОВАНИЕ ОДНОВРЕМЕННОЙ ОТПРАВКИ ТРЁХ PDF ФАЙЛОВ")
    print("="*60)
    
    # Проверяем доступность сервера
    if not check_server():
        sys.exit(1)
    
    results = []
    
    # Тест 1: Пакетная загрузка
    results.append(("Пакетная загрузка", upload_batch()))
    
    # Небольшая пауза между тестами
    time.sleep(2)
    
    # Тест 2: Параллельная загрузка
    results.append(("Параллельная загрузка", upload_concurrent()))
    
    # Итоги
    print("\n" + "="*60)
    print("ИТОГИ ТЕСТИРОВАНИЯ")
    print("="*60)
    
    for test_name, result in results:
        status = "✅ ПРОЙДЕН" if result else "❌ ПРОВАЛЕН"
        print(f"{test_name}: {status}")
    
    print("\n💡 Для просмотра логов сервера выполните:")
    print("   tail -f logs/app.log")
    print("   или")
    print("   tail -f api_server.log")
    
    all_passed = all(result for _, result in results)
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())

