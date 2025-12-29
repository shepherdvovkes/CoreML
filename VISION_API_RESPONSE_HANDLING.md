# Обработка ответов от Vision API

## Обзор улучшений

Улучшена обработка ответов от Vision API для более надежной работы и лучшей диагностики проблем.

## Формат ответа от Vision API

### Успешный ответ (200 OK)

```json
{
  "success": true,
  "text": "извлеченный текст...",
  "fullTextAnnotation": {...},
  "confidence": 0.95
}
```

### Ошибки

#### 401 Unauthorized
```json
{
  "error": "Unauthorized",
  "message": "API key is required..."
}
```

#### 403 Forbidden
```json
{
  "error": "Forbidden",
  "message": "Invalid API key"
}
```

#### 400 Bad Request
```json
{
  "error": "Bad Request",
  "message": "Image file is required"
}
```

#### 500+ Server Error
```json
{
  "error": "Internal Server Error",
  "message": "Google Vision API error: ..."
}
```

## Улучшения обработки

### 1. Валидация JSON ответа

- Проверяется, что ответ является валидным JSON
- Обрабатываются случаи, когда сервер возвращает не-JSON ответ

### 2. Обработка успешных ответов

- Проверяется наличие `success: true` в ответе
- Извлекается текст из поля `text`
- **Важно**: Пустая строка `""` - это валидный результат (изображение без текста)
- Логируется confidence score, если доступен

### 3. Обработка ошибок

Улучшена обработка различных типов ошибок:

- **401 Unauthorized**: Ошибка аутентификации (нет API ключа)
- **403 Forbidden**: Ошибка авторизации (неверный API ключ)
- **400 Bad Request**: Неверный запрос (нет файла, неверный формат)
- **429 Too Many Requests**: Превышен лимит запросов
- **500+ Server Error**: Ошибка сервера или Google Vision API

Каждый тип ошибки логируется с соответствующим уровнем важности.

### 4. Обработка пустых результатов

#### Для изображений:
- Пустая строка `""` возвращается как валидный результат
- `None` возвращается только при ошибке

#### Для PDF:
- Если хотя бы одна страница вернула текст - объединяются все результаты
- Если все страницы вернули пустую строку - возвращается `None` (для fallback)
- Если хотя бы одна страница вернула ошибку (`None`) - логируется предупреждение, но обработка продолжается

### 5. Логирование

Улучшено логирование для лучшей диагностики:

- **INFO**: Успешное извлечение текста с указанием количества символов
- **DEBUG**: Дополнительная информация (confidence, пустые страницы)
- **WARNING**: Предупреждения (пустой текст, ошибки на отдельных страницах)
- **ERROR**: Критические ошибки (ошибки API, таймауты)

## Примеры обработки

### Успешное извлечение текста

```python
# Ответ от API
{
  "success": true,
  "text": "Привет, мир!",
  "confidence": 0.95
}

# Результат: "Привет, мир!"
```

### Изображение без текста

```python
# Ответ от API
{
  "success": true,
  "text": "",
  "confidence": 0.0
}

# Результат: "" (пустая строка, валидный результат)
```

### Ошибка API

```python
# Ответ от API
{
  "error": "Forbidden",
  "message": "Invalid API key"
}

# Результат: None (будет использован fallback метод)
```

### PDF с несколькими страницами

```python
# Страница 1: "Текст страницы 1"
# Страница 2: "" (пустая)
# Страница 3: "Текст страницы 3"

# Результат: "Текст страницы 1\n\nТекст страницы 3"
```

## Код обработки

### VisionAPIClient.extract_text_from_image()

```python
# Обработка успешного ответа
if response.status_code == 200:
    result = response.json()
    if result.get("success"):
        text = result.get("text", "")
        # Пустая строка - валидный результат
        return text if text else ""
    
# Обработка ошибок
else:
    error_message = result.get("message") or result.get("error")
    # Логирование в зависимости от типа ошибки
    return None
```

### DocumentProcessor._extract_text_from_pdf_via_vision()

```python
# Обработка каждой страницы
for page_text in pages:
    if page_text is not None:
        if page_text.strip():
            all_text.append(page_text)
        else:
            # Пустая строка - страница без текста
            logger.debug("Page contains no text")
    else:
        # None - ошибка при обработке
        logger.warning("Failed to extract text from page")
```

## Рекомендации

1. **Мониторинг логов**: Следите за предупреждениями и ошибками в логах
2. **Обработка пустых результатов**: Учитывайте, что пустая строка - это валидный результат
3. **Fallback механизм**: Всегда есть fallback на стандартные методы извлечения текста
4. **Таймауты**: Настройте `vision_api_timeout` в зависимости от размера документов

## Тестирование

Для тестирования обработки ответов можно использовать:

```python
from core.rag.vision_client import VisionAPIClient

client = VisionAPIClient()

# Тест с реальным изображением
text = await client.extract_text_from_file("test_image.png")
print(f"Extracted text: {text}")
```

