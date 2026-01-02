# HTML Screenshot Service с Playwright

## Обзор

Сервис для создания скриншотов HTML страниц через Playwright и отправки их в Google Vision API для OCR распознавания текста. Это полезно для сложных HTML документов с CSS стилями, где простое извлечение текста не работает хорошо.

## Архитектура

1. **HTML Screenshot Service** (Playwright) - создает скриншоты HTML
2. **Vision API** - распознает текст из скриншотов через OCR
3. **Интеграция** - автоматическая отправка скриншотов в Vision API

## Запуск через Docker

### 1. Сборка образа

```bash
docker build -f Dockerfile.playwright -t coreml-html-screenshot .
```

### 2. Запуск через docker-compose

```bash
docker-compose up -d html_screenshot
```

### 3. Проверка работы

```bash
curl http://localhost:3015/health
```

## Использование

### API Endpoints

#### 1. Health Check
```bash
GET /health
```

#### 2. Создание скриншота из HTML контента
```bash
POST /screenshot
Content-Type: application/json

{
  "html_content": "<html>...</html>",
  "viewport_width": 1920,
  "viewport_height": 1080,
  "wait_time": 1000,
  "full_page": true,
  "language_hints": ["uk", "ru", "en"]
}
```

**Ответ:**
```json
{
  "success": true,
  "screenshot_size": 123456,
  "text": "Извлеченный текст из скриншота..."
}
```

#### 3. Создание скриншота из HTML файла
```bash
POST /screenshot/upload
Content-Type: multipart/form-data

file: <HTML файл>
viewport_width: 1920
viewport_height: 1080
wait_time: 1000
full_page: true
language_hints: "uk,ru,en"
```

#### 4. Создание скриншота из URL
```bash
POST /screenshot
Content-Type: application/json

{
  "html_url": "https://example.com/page.html",
  "viewport_width": 1920,
  "viewport_height": 1080,
  "wait_time": 1000,
  "full_page": true
}
```

### Использование в Python коде

```python
from core.rag.html_screenshot_client import HTMLScreenshotClient

# Создание клиента
client = HTMLScreenshotClient()

# Извлечение текста из HTML контента
text = await client.extract_text_from_html(
    html_content="<html>...</html>",
    viewport_width=1920,
    viewport_height=1080,
    language_hints=['uk', 'ru', 'en']
)

# Извлечение текста из HTML файла
text = await client.extract_text_from_html_file(
    file_path="document.html",
    language_hints=['uk', 'ru', 'en']
)

# Извлечение текста из URL
text = await client.extract_text_from_html_url(
    url="https://example.com/page.html"
)
```

## Конфигурация

### Переменные окружения

```bash
# URL сервиса скриншотов
HTML_SCREENSHOT_URL=http://localhost:3015

# Таймаут для запросов (секунды)
HTML_SCREENSHOT_TIMEOUT=120

# Vision API настройки (уже настроены)
VISION_API_URL=https://mail.s0me.uk/vision
VISION_API_KEY=your_api_key
```

### Настройки в config.py

```python
# HTML Screenshot Service Configuration
html_screenshot_url: str = "http://localhost:3015"
html_screenshot_timeout: int = 120  # 2 minutes
```

## Параметры скриншота

- **viewport_width** (int): Ширина viewport браузера (по умолчанию 1920)
- **viewport_height** (int): Высота viewport браузера (по умолчанию 1080)
- **wait_time** (int): Время ожидания после загрузки страницы в миллисекундах (по умолчанию 1000)
- **full_page** (bool): Делать скриншот всей страницы или только видимой области (по умолчанию True)
- **language_hints** (list): Подсказки по языкам для OCR (по умолчанию ['uk', 'ru', 'en'])

## Интеграция с DocumentProcessor

Сервис можно использовать в `DocumentProcessor` для обработки HTML файлов:

```python
from core.rag.html_screenshot_client import HTMLScreenshotClient

# В методе extract_text_from_html
screenshot_client = HTMLScreenshotClient()
text = await screenshot_client.extract_text_from_html_file(file_path)
```

## Преимущества подхода

1. **Точное отображение** - HTML рендерится как в браузере
2. **CSS стили** - Учитываются все стили и форматирование
3. **JavaScript** - Может обрабатывать динамический контент (если нужен wait_time)
4. **OCR качество** - Vision API хорошо распознает текст из скриншотов
5. **Сложные макеты** - Работает с таблицами, колонками и сложными структурами

## Ограничения

1. **Производительность** - Скриншоты медленнее простого извлечения текста
2. **Ресурсы** - Требует больше памяти и CPU для браузера
3. **Размер** - Большие HTML страницы могут создавать большие скриншоты
4. **Таймауты** - Может потребоваться больше времени для сложных страниц

## Troubleshooting

### Браузер не запускается

```bash
# Проверьте логи
docker logs coreml_html_screenshot

# Проверьте, что установлены браузеры
docker exec coreml_html_screenshot playwright install chromium
```

### Vision API не работает

```bash
# Проверьте переменные окружения
docker exec coreml_html_screenshot env | grep VISION

# Проверьте health endpoint
curl http://localhost:3015/health
```

### Большие HTML файлы

- Увеличьте `wait_time` для полной загрузки
- Используйте `full_page=false` для видимой области
- Увеличьте таймауты в настройках

## Примеры использования

### Пример 1: Простой HTML

```python
html = "<html><body><h1>Заголовок</h1><p>Текст параграфа</p></body></html>"
text = await client.extract_text_from_html(html)
```

### Пример 2: HTML файл с кодировкой

```python
text = await client.extract_text_from_html_file(
    "document.html",
    viewport_width=1920,
    language_hints=['uk', 'ru']
)
```

### Пример 3: Веб-страница

```python
text = await client.extract_text_from_html_url(
    "https://example.com/page.html",
    wait_time=3000,  # 3 секунды для загрузки
    full_page=True
)
```

## Мониторинг

### Health Check

```bash
curl http://localhost:3015/health
```

**Ответ:**
```json
{
  "status": "ok",
  "service": "html-screenshot-service",
  "browser_initialized": true,
  "vision_api_available": true
}
```

## Производительность

- **Скриншот простого HTML**: ~2-5 секунд
- **Скриншот + OCR**: ~5-15 секунд
- **Большие страницы**: ~10-30 секунд
- **С JavaScript**: зависит от сложности, может быть дольше

## Безопасность

- Сервис работает в изолированном Docker контейнере
- Браузер запускается в headless режиме
- Нет доступа к файловой системе хоста (кроме volumes)
- API не требует аутентификации (можно добавить при необходимости)

