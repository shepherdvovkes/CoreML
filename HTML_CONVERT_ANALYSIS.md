# Анализ работы convert (html-to-text) в Node.js скриптах

## Обзор

В Node.js скриптах (`ZO/fetchFullText_ByCaseNumber.js` и `ZO/fetchFullText_ByDocId.js`) используется библиотека `html-to-text` для конвертации HTML в читабельный текст.

## Как работает convert в Node.js

### Использование

```javascript
const { convert } = require("html-to-text");

const plainText = convert(htmlText || "", {
  wordwrap: false,
  selectors: [{ selector: "a", format: "inline" }],
});
```

### Параметры

1. **`wordwrap: false`** - не переносить слова на новую строку
2. **`selectors: [{ selector: "a", format: "inline" }]`** - обрабатывать ссылки как inline текст (не на новой строке)

### Что делает convert

1. Удаляет HTML теги
2. Извлекает текстовое содержимое
3. Сохраняет структуру (параграфы, списки)
4. Обрабатывает ссылки как inline текст
5. Удаляет лишние пробелы и переносы строк

## Текущая реализация в Python

В `core/rag/document_processor.py` уже есть реализация извлечения текста из HTML:

### Методы (в порядке приоритета):

1. **LangChain HTML Loader** (BSHTMLLoader/UnstructuredHTMLLoader)
2. **BeautifulSoup** (fallback)
3. **html.parser** (стандартная библиотека Python)

### Текущая логика BeautifulSoup:

```python
soup = BeautifulSoup(html_content, 'html.parser')

# Удаляем скрипты и стили
for script in soup(["script", "style"]):
    script.decompose()

# Извлекаем текст
text = soup.get_text()

# Очищаем текст от лишних пробелов и переносов строк
lines = (line.strip() for line in text.splitlines())
chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
text = '\n'.join(chunk for chunk in chunks if chunk)
```

## Сравнение с convert из html-to-text

### Что делает convert лучше:

1. **Обработка ссылок**: `format: "inline"` - ссылки остаются в тексте, а не на новой строке
2. **Сохранение структуры**: Лучше сохраняет структуру параграфов и списков
3. **Обработка специальных элементов**: Таблицы, списки, заголовки

### Что можно улучшить в Python версии:

1. **Обработка ссылок**: Сохранять текст ссылок inline
2. **Обработка таблиц**: Извлекать текст из таблиц с сохранением структуры
3. **Обработка списков**: Сохранять маркеры списков
4. **Обработка заголовков**: Сохранять иерархию заголовков

## Рекомендации по улучшению

### Вариант 1: Использовать библиотеку `html2text` (Python аналог)

```python
# Установка
pip install html2text

# Использование
import html2text

h = html2text.HTML2Text()
h.ignore_links = False  # Сохранять ссылки
h.body_width = 0  # Не переносить строки (аналог wordwrap: false)
h.ignore_images = True
text = h.handle(html_content)
```

### Вариант 2: Улучшить текущую реализацию BeautifulSoup

```python
def extract_text_from_html_improved(self, file_path: str) -> str:
    """Улучшенное извлечение текста из HTML"""
    encoding = self._detect_html_encoding(file_path)
    
    with open(file_path, 'r', encoding=encoding) as file:
        html_content = file.read()
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Удаляем скрипты и стили
        for script in soup(["script", "style"]):
            script.decompose()
        
        # Обрабатываем ссылки как inline (как в convert)
        for link in soup.find_all('a'):
            if link.string:
                link.replace_with(link.string)
            else:
                link.replace_with(link.get_text())
        
        # Извлекаем текст с сохранением структуры
        text = soup.get_text(separator='\n', strip=True)
        
        # Очищаем от лишних пробелов
        lines = []
        for line in text.splitlines():
            line = line.strip()
            if line:  # Пропускаем пустые строки
                lines.append(line)
        
        return '\n'.join(lines)
```

### Вариант 3: Использовать оба подхода (гибридный)

1. Сначала пробовать `html2text` (если установлен)
2. Fallback на улучшенный BeautifulSoup
3. Последний fallback на html.parser

## Текущее состояние

### ✅ Что уже работает:

- Определение кодировки HTML файлов
- Извлечение текста через BeautifulSoup
- Удаление скриптов и стилей
- Очистка от лишних пробелов

### ⚠️ Что можно улучшить:

- Обработка ссылок (сейчас они могут быть на новой строке)
- Сохранение структуры таблиц
- Обработка списков с маркерами
- Сохранение иерархии заголовков

## Рекомендация

Для максимальной совместимости с Node.js версией рекомендуется:

1. **Добавить библиотеку `html2text`** в `requirements.txt`
2. **Использовать её как первый вариант** (аналог convert)
3. **Оставить BeautifulSoup как fallback**

Это обеспечит:
- ✅ Совместимость с результатами Node.js скриптов
- ✅ Лучшую обработку сложных HTML структур
- ✅ Сохранение структуры документа

## Пример использования html2text

```python
import html2text

def extract_text_with_html2text(html_content: str) -> str:
    """Извлечение текста через html2text (аналог convert)"""
    h = html2text.HTML2Text()
    h.ignore_links = False  # Сохранять ссылки
    h.body_width = 0  # Не переносить строки (wordwrap: false)
    h.ignore_images = True
    h.ignore_emphasis = False  # Сохранять форматирование
    h.unicode_snob = True  # Лучшая обработка Unicode
    
    # Настройка селекторов (аналог selectors в convert)
    h.inline_links = True  # Ссылки inline (format: "inline")
    
    text = h.handle(html_content)
    return text.strip()
```

## Вывод

Текущая реализация в Python работает, но можно улучшить её, добавив библиотеку `html2text`, которая является прямым аналогом `html-to-text` из Node.js и обеспечит максимальную совместимость результатов.

