# Исправление проблем с Celery Worker: LangChain и Vision API

## Проблемы

### 1. LangChain не доступен в Celery worker
**Симптомы:**
- В логах: `LangChain not fully available: No module named 'langchain_community'`
- `LANGCHAIN_AVAILABLE = False` в worker'е
- Код переходит к PyPDF2 fallback

**Причина:**
- LangChain был недоступен при старте worker'а (28 декабря)
- Переменная `LANGCHAIN_AVAILABLE` устанавливается при импорте модуля и не обновляется
- Worker не был перезапущен после установки LangChain

**Решение:**
Перезапустить Celery worker после установки зависимостей.

### 2. Vision API не вызывается
**Симптомы:**
- В логах нет записей о попытках использовать Vision API
- `"[DocumentProcessor] Attempting to extract text from PDF using Vision API"` не появляется

**Причина:**
- Vision API инициализируется при создании `DocumentProcessor`
- Если worker был запущен до установки зависимостей, инициализация могла провалиться
- `self.use_vision_api` может быть `False` в worker'е

**Решение:**
Перезапустить worker, чтобы он переинициализировал `DocumentProcessor` с правильными настройками.

## Решение

### Шаг 1: Остановить текущий Celery worker
```bash
# Найти процесс
ps aux | grep "celery.*worker" | grep -v grep

# Остановить (Ctrl+C или kill)
pkill -f "celery.*worker"
```

### Шаг 2: Убедиться, что зависимости установлены
```bash
cd /Users/vovkes/CoreML
source venv/bin/activate
pip install langchain langchain-community langchain-text-splitters PyPDF2
```

### Шаг 3: Проверить, что все работает
```bash
python3 -c "from core.rag.document_processor import LANGCHAIN_AVAILABLE, VISION_CLIENT_AVAILABLE; print(f'LangChain: {LANGCHAIN_AVAILABLE}, Vision: {VISION_CLIENT_AVAILABLE}')"
```

### Шаг 4: Перезапустить Celery worker
```bash
cd /Users/vovkes/CoreML
source venv/bin/activate
celery -A core.celery_app worker --loglevel=info
```

### Шаг 5: Проверить логи
После перезапуска в логах должно быть:
- `LangChain available` (без ошибок)
- `Vision API client initialized and ready to use`
- `RAG service initialized for Celery worker`

## Проверка

После перезапуска запустите тест:
```bash
python3 test_three_pdfs.py
```

В логах worker'а должны появиться записи:
- `[DocumentProcessor] Attempting to extract text from PDF using Vision API`
- `Attempting to extract text using LangChain PyPDFLoader...`
- Или успешное извлечение через один из методов

## Примечания

- Переменные `LANGCHAIN_AVAILABLE` и `VISION_CLIENT_AVAILABLE` устанавливаются при импорте модуля
- Если worker запущен до установки зависимостей, нужно перезапустить
- Worker использует singleton `_rag_service`, который создается при первом вызове `get_rag_service()`
- После перезапуска worker создаст новый `RAGService` с правильными настройками

