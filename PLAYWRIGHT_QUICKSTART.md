# Playwright HTML Screenshot Service - Быстрый старт

## Что это?

Docker сервис с Playwright для создания скриншотов HTML страниц и автоматической отправки их в Google Vision API для OCR распознавания текста.

## Быстрый запуск

### 1. Сборка образа

```bash
docker build -f Dockerfile.playwright -t coreml-html-screenshot .
```

### 2. Запуск сервиса

```bash
docker-compose up -d html_screenshot
```

### 3. Проверка работы

```bash
curl http://localhost:3015/health
```

Должен вернуть:
```json
{
  "status": "ok",
  "service": "html-screenshot-service",
  "browser_initialized": true,
  "vision_api_available": true
}
```

## Использование

### Через API

```bash
# Создание скриншота из HTML контента
curl -X POST http://localhost:3015/screenshot \
  -H "Content-Type: application/json" \
  -d '{
    "html_content": "<html><body><h1>Тест</h1></body></html>",
    "viewport_width": 1920,
    "viewport_height": 1080
  }'
```

### Через Python клиент

```python
from core.rag.html_screenshot_client import HTMLScreenshotClient

client = HTMLScreenshotClient()
text = await client.extract_text_from_html(
    html_content="<html>...</html>",
    language_hints=['uk', 'ru', 'en']
)
```

### Тестирование

```bash
python test_html_screenshot.py
```

## Конфигурация

Убедитесь, что в `.env` файле установлены:

```bash
VISION_API_URL=https://mail.s0me.uk/vision
VISION_API_KEY=your_api_key
```

## Структура

- `Dockerfile.playwright` - Docker образ с Playwright
- `services/html_screenshot_service.py` - FastAPI сервис
- `core/rag/html_screenshot_client.py` - Python клиент
- `docker-compose.yml` - Конфигурация для запуска

## Порт

Сервис работает на порту **3015** (можно изменить через переменную окружения `PORT`).

## Подробная документация

См. `HTML_SCREENSHOT_SERVICE.md`

