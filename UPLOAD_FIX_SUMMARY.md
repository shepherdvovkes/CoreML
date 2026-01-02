# Исправление ошибок загрузки файлов

## Проблемы обнаружены:

1. **UnboundLocalError в tasks.py**
   - Ошибка: `cannot access local variable 'temp_file_path' where it is not associated with a value`
   - Причина: переменная использовалась в except блоке до инициализации
   - ✅ Исправлено: инициализация `temp_file_path = None` вынесена до try блока

2. **ImportError: sentence-transformers несовместим с huggingface-hub**
   - Ошибка: `cannot import name 'cached_download' from 'huggingface_hub'`
   - Причина: sentence-transformers 2.2.2 требует старый API huggingface-hub (<0.20.0), но установлен 0.36.0
   - ✅ Исправлено: обновлен sentence-transformers до >=2.3.0 в requirements.txt

## Исправления:

1. **core/tasks.py**:
   - Инициализация `temp_file_path = None` вынесена до try блока (строка 55)

2. **requirements.txt**:
   - Обновлен `sentence-transformers==2.2.2` → `sentence-transformers>=2.3.0`

3. **Docker контейнер**:
   - Обновлен sentence-transformers в контейнере celery_worker
   - Контейнер перезапущен и теперь healthy

## Статус:

- ✅ Celery worker: **healthy**
- ✅ Ошибка UnboundLocalError: **исправлена**
- ✅ Ошибка ImportError: **исправлена**
- ✅ Загрузка файлов должна работать

## Тестирование:

Попробуйте загрузить файл через API:
```bash
curl -X POST "http://127.0.0.1:8000/rag/add-document" \
  -F "file=@test.pdf"
```
