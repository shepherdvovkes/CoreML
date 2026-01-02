#!/usr/bin/env python3
"""
Тест загрузки PDF файлов через API (как от клиента)
"""
import time
import requests
import sys
from pathlib import Path
from typing import List, Dict, Any

API_BASE_URL = "http://127.0.0.1:8000"

def find_pdf_files() -> List[Path]:
    """Найти все PDF файлы в текущей директории"""
    pdf_files = []
    for ext in ['*.pdf', '*.PDF']:
        pdf_files.extend(Path('.').glob(ext))
    return sorted(pdf_files)


def check_server() -> bool:
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
        print("   Убедитесь, что сервер запущен")
        return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False


def upload_single_file(file_path: Path) -> Dict[str, Any]:
    """Загрузка одного файла через API"""
    try:
        print(f"\n📤 Загрузка файла: {file_path.name}...")
        start_time = time.time()
        
        with open(file_path, 'rb') as f:
            files = {'file': (file_path.name, f, 'application/pdf')}
            response = requests.post(
                f"{API_BASE_URL}/rag/add-document",
                files=files,
                timeout=60
            )
        
        elapsed = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Файл принят сервером за {elapsed:.2f}с")
            print(f"   📋 Task ID: {data.get('task_id')}")
            print(f"   📊 Статус: {data.get('status')}")
            return {
                'success': True,
                'filename': file_path.name,
                'task_id': data.get('task_id'),
                'status': data.get('status'),
                'elapsed': elapsed,
                'response': data
            }
        else:
            print(f"   ❌ Ошибка HTTP {response.status_code}")
            print(f"   Ответ: {response.text[:200]}")
            return {
                'success': False,
                'filename': file_path.name,
                'error': f"HTTP {response.status_code}: {response.text[:200]}",
                'elapsed': elapsed
            }
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'filename': file_path.name,
            'error': str(e)
        }


def check_task_status(task_id: str, filename: str, max_wait: int = 60) -> Dict[str, Any]:
    """Проверка статуса задачи обработки"""
    start_time = time.time()
    last_status = None
    
    print(f"\n⏳ Ожидание обработки {filename}...")
    
    while time.time() - start_time < max_wait:
        try:
            response = requests.get(
                f"{API_BASE_URL}/rag/task/{task_id}",
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                status = data.get('status')
                
                # Показываем только при изменении статуса
                if status != last_status:
                    print(f"   📊 Статус: {status}")
                    last_status = status
                
                if status == 'success':
                    result = data.get('result', {})
                    chunks = result.get('chunks_count', 0)
                    print(f"   ✅ Обработка завершена успешно!")
                    print(f"   📄 Чанков создано: {chunks}")
                    return {
                        'success': True,
                        'status': status,
                        'chunks_count': chunks,
                        'result': result
                    }
                elif status in ['failure', 'error']:
                    error = data.get('error', 'Unknown error')
                    print(f"   ❌ Ошибка обработки: {error}")
                    return {
                        'success': False,
                        'status': status,
                        'error': error
                    }
                elif status == 'processing':
                    # Продолжаем ожидание
                    time.sleep(2)
                elif status == 'pending':
                    # Продолжаем ожидание
                    time.sleep(2)
                else:
                    # Неизвестный статус
                    time.sleep(2)
            else:
                print(f"   ⚠️  Ошибка проверки статуса: HTTP {response.status_code}")
                time.sleep(2)
        except Exception as e:
            print(f"   ⚠️  Ошибка проверки статуса: {e}")
            time.sleep(2)
    
    print(f"   ⏱️  Превышено время ожидания ({max_wait}с)")
    return {
        'success': False,
        'status': 'timeout',
        'error': f'Timeout after {max_wait} seconds'
    }


def main():
    """Основная функция тестирования"""
    print("\n" + "="*70)
    print("ТЕСТ ЗАГРУЗКИ PDF ФАЙЛОВ ЧЕРЕЗ API")
    print("="*70)
    
    # Проверяем доступность сервера
    if not check_server():
        sys.exit(1)
    
    # Находим PDF файлы
    pdf_files = find_pdf_files()
    
    if not pdf_files:
        print("❌ PDF файлы не найдены в текущей директории")
        sys.exit(1)
    
    print(f"\n📁 Найдено PDF файлов: {len(pdf_files)}")
    for i, pdf_file in enumerate(pdf_files, 1):
        size = pdf_file.stat().st_size / 1024  # KB
        print(f"   {i}. {pdf_file.name} ({size:.1f} KB)")
    
    # Загружаем каждый файл
    results = []
    for i, pdf_file in enumerate(pdf_files, 1):
        print(f"\n{'='*70}")
        print(f"Файл {i}/{len(pdf_files)}: {pdf_file.name}")
        print('='*70)
        
        # Загрузка файла
        upload_result = upload_single_file(pdf_file)
        results.append(upload_result)
        
        if upload_result.get('success'):
            task_id = upload_result.get('task_id')
            if task_id:
                # Проверяем статус обработки
                status_result = check_task_status(task_id, pdf_file.name)
                upload_result['processing'] = status_result
        
        # Небольшая пауза между файлами
        if i < len(pdf_files):
            time.sleep(1)
    
    # Итоги
    print("\n" + "="*70)
    print("ИТОГИ ТЕСТИРОВАНИЯ")
    print("="*70)
    
    successful_uploads = [r for r in results if r.get('success')]
    successful_processing = [r for r in results if r.get('success') and r.get('processing', {}).get('success')]
    
    print(f"\n📊 Статистика:")
    print(f"   Всего файлов: {len(results)}")
    print(f"   ✅ Успешно загружено: {len(successful_uploads)}")
    print(f"   ✅ Успешно обработано: {len(successful_processing)}")
    
    print(f"\n📋 Детали:")
    for i, result in enumerate(results, 1):
        filename = result.get('filename', 'unknown')
        if result.get('success'):
            status_icon = "✅" if result.get('processing', {}).get('success') else "⏳"
            chunks = result.get('processing', {}).get('chunks_count', 0)
            print(f"   {status_icon} {filename}: {chunks} чанков")
        else:
            error = result.get('error', 'Unknown error')
            print(f"   ❌ {filename}: {error}")
    
    # Проверяем, что все успешно
    all_success = len(successful_processing) == len(results)
    
    if all_success:
        print(f"\n✅ Все тесты пройдены успешно!")
    else:
        print(f"\n⚠️  Некоторые тесты не прошли")
        print(f"   Проверьте логи сервера: tail -f logs/app.log")
        print(f"   Проверьте логи Celery: docker-compose logs celery_worker")
    
    return 0 if all_success else 1


if __name__ == "__main__":
    sys.exit(main())

