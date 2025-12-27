# Быстрое развертывание на mail.s0me.uk

## Шаг 1: Подготовка на сервере

```bash
ssh vovkes@mail.s0me.uk
mkdir -p ~/coreml && cd ~/coreml
```

## Шаг 2: Копирование файлов

Скопируйте все файлы проекта на сервер (через scp, rsync или git):

```bash
# С локальной машины
rsync -avz --exclude 'venv' --exclude '__pycache__' --exclude '.git' \
  /Users/vovkes/CoreML/ vovkes@mail.s0me.uk:~/coreml/
```

## Шаг 3: Настройка

```bash
cd ~/coreml
cp .env.example .env
# Пароли будут сгенерированы автоматически при развертывании
nano .env  # Отредактируйте только необходимые настройки (например, OPENAI_API_KEY)
```

**Минимальные настройки в .env:**
```env
# Пароли Redis и Qdrant будут сгенерированы автоматически
OPENAI_API_KEY=your_key_here  # Обязательно укажите ваш ключ
```

**Примечание:** Пароли для Redis и Qdrant генерируются автоматически при запуске `deploy.sh`. Вам нужно указать только внешние API ключи (например, OpenAI).

## Шаг 4: Развертывание

```bash
chmod +x scripts/*.sh
./scripts/deploy.sh prod
```

## Готово! ✅

**Автоматически созданы:**
- ✅ Коллекция `legal_documents` в Qdrant
- ✅ Настроен доступ с паролями из конфигурации
- ✅ Проверены права доступа

**Сервисы будут доступны:**
- API: `http://mail.s0me.uk:8000`
- API Docs: `http://mail.s0me.uk:8000/docs`
- Flower: `http://mail.s0me.uk:5555`

## Полезные команды

```bash
# Статус
docker-compose -f docker-compose.prod.yml ps

# Логи
docker-compose -f docker-compose.prod.yml logs -f api

# Остановка
docker-compose -f docker-compose.prod.yml down

# Обновление
./scripts/update.sh prod
```

Подробнее: см. `DEPLOYMENT_GUIDE.md`

