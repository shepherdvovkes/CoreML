# Исправление ошибки "name 'PyPDF2' is not defined"

## Проблема
При обработке PDF файлов возникала ошибка:
```
Error extracting text from PDF: name 'PyPDF2' is not defined
```

## Причина
1. PyPDF2 был установлен в venv, но при импорте в Celery worker возникали проблемы с областью видимости
2. Код не обрабатывал случай, когда PyPDF2 не определен в контексте выполнения

## Исправления

### 1. Улучшен импорт PyPDF2/pypdf
В `core/rag/document_processor.py`:
- Добавлена поддержка как PyPDF2, так и pypdf (новая версия)
- Улучшена обработка ошибок импорта
- Добавлена обработка NameError для случаев, когда PyPDF2 не определен в области видимости

### 2. Улучшена обработка ошибок
- Добавлена проверка на NameError при использовании PyPDF2
- Улучшены сообщения об ошибках для диагностики

## Что нужно сделать

### Перезапустить Celery worker
```bash
# Остановить текущий worker (Ctrl+C или kill процесс)
# Затем запустить заново:
cd /Users/vovkes/CoreML
source venv/bin/activate
celery -A core.celery_app worker --loglevel=info
```

### Проверить установку PyPDF2
```bash
source venv/bin/activate
python3 -c "import PyPDF2; print('PyPDF2 version:', PyPDF2.__version__)"
```

Если PyPDF2 не установлен:
```bash
pip install PyPDF2
```

## Тестирование
После перезапуска worker'а запустите тест:
```bash
python3 test_three_pdfs.py
```

Теперь PDF файлы должны обрабатываться без ошибок.

