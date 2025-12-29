# Интеграция Google Vision API

## Обзор

Интегрирован Google Vision API сервер (mail.s0me.uk:3006) для извлечения текста из документов. Когда пользователь загружает документ, он автоматически отправляется в Vision API для OCR распознавания.

## Конфигурация

### Переменные окружения

Добавлены следующие переменные в `.env`:

```bash
VISION_API_URL=http://mail.s0me.uk:3006
VISION_API_KEY=617989a002d4d2a82d970a7947f13b74e8d881570c797e5b76077ea0c4079925
```

### Настройки в config.py

```python
# Google Vision API Configuration
vision_api_url: str = "http://mail.s0me.uk:3006"
vision_api_key: str = ""
vision_api_timeout: int = 120  # 2 minutes for OCR processing
```

## Как это работает

1. **Для изображений** (PNG, JPG, JPEG, GIF, WEBP, BMP):
   - Файл отправляется напрямую в Vision API
   - Полученный текст используется для RAG

2. **Для PDF документов**:
   - PDF конвертируется в изображения (каждая страница отдельно) с помощью PyMuPDF
   - Каждое изображение отправляется в Vision API
   - Тексты со всех страниц объединяются

3. **Для других форматов** (DOCX, XLSX, TXT):
   - Используются стандартные методы извлечения текста
   - Vision API не используется (можно расширить в будущем)

## Fallback механизм

Если Vision API недоступен или возвращает ошибку:
- Для PDF: используется LangChain PyPDFLoader или PyPDF2
- Для DOCX: используется LangChain Docx2txtLoader или python-docx
- Для XLSX: используется LangChain UnstructuredExcelLoader или openpyxl
- Для TXT: используется LangChain TextLoader или стандартное чтение файла

## Зависимости

Добавлены новые зависимости в `requirements.txt`:

```
PyMuPDF==1.23.8  # Для конвертации PDF в изображения
Pillow==10.1.0   # Для работы с изображениями
```

## Файлы

### Новые файлы:
- `core/rag/vision_client.py` - клиент для работы с Vision API

### Измененные файлы:
- `core/rag/document_processor.py` - добавлена поддержка Vision API
- `config.py` - добавлены настройки Vision API
- `requirements.txt` - добавлены зависимости

## Использование

Интеграция работает автоматически. При загрузке документа через `/rag/add-document`:

1. Система проверяет доступность Vision API
2. Если доступен - использует его для извлечения текста
3. Если недоступен - использует fallback методы

## Логирование

Все операции логируются:
- `INFO`: Успешное извлечение текста через Vision API
- `WARNING`: Vision API недоступен или вернул пустой результат, используется fallback
- `ERROR`: Ошибки при работе с Vision API

## Проверка работы

Для проверки работы Vision API:

```python
from core.rag.vision_client import VisionAPIClient

client = VisionAPIClient()
if client.is_available():
    print("Vision API доступен")
else:
    print("Vision API недоступен (нет API ключа)")
```

## API Endpoint

Vision API сервер доступен по адресу:
- URL: `http://mail.s0me.uk:3006`
- Endpoint: `/v1/api/ocr`
- Метод: `POST`
- Заголовок: `X-API-Key: <api_key>`
- Формат: `multipart/form-data` с полем `image`

## Примечания

- Vision API работает асинхронно, но DocumentProcessor синхронный, поэтому используется обертка для запуска асинхронного кода
- Для больших PDF файлов обработка может занять время (каждая страница обрабатывается отдельно)
- Timeout для Vision API запросов: 120 секунд (настраивается в config.py)

