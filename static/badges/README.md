# Кнопки (Badges) для загрузки приложений

Эта директория содержит официальные кнопки для загрузки приложения LexApp с различных платформ.

## Структура файлов

### Google Play (Android)
- `google-play-badge-en.png` - Английская версия
- `google-play-badge-ru.png` - Русская версия
- `google-play-badge-uk.png` - Украинская версия

### Apple App Store (iOS/macOS)
- `app-store-badge-en.svg` - Английская версия
- `app-store-badge-ru.svg` - Русская версия
- `app-store-badge-uk.svg` - Украинская версия

### Microsoft Store (Windows)
- `microsoft-store-badge-en.svg` - Английская версия
- `microsoft-store-badge-ru.svg` - Русская версия
- `microsoft-store-badge-uk.svg` - Украинская версия

### Flathub (Linux)
- `flathub-badge-en.png` - Английская версия
- `flathub-badge-ru.png` - Русская версия
- `flathub-badge-uk.png` - Украинская версия

## Использование

### HTML страница

Файл `index.html` содержит готовую HTML страницу с кнопками для всех платформ и языков. Страница включает:
- Переключатель языков (украинский, русский, английский)
- Адаптивный дизайн
- Красивое оформление с градиентом

### Интеграция в существующий сайт

Чтобы использовать кнопки на вашем сайте, просто добавьте ссылки на изображения:

```html
<!-- Google Play -->
<a href="YOUR_GOOGLE_PLAY_LINK" target="_blank">
    <img src="/static/badges/google-play-badge-uk.png" alt="Доступно в Google Play">
</a>

<!-- App Store -->
<a href="YOUR_APP_STORE_LINK" target="_blank">
    <img src="/static/badges/app-store-badge-uk.svg" alt="Завантажити в App Store">
</a>

<!-- Microsoft Store -->
<a href="YOUR_MICROSOFT_STORE_LINK" target="_blank">
    <img src="/static/badges/microsoft-store-badge-uk.svg" alt="Отримати з Microsoft Store">
</a>

<!-- Flathub -->
<a href="YOUR_FLATHUB_LINK" target="_blank">
    <img src="/static/badges/flathub-badge-uk.png" alt="Доступно на Flathub">
</a>
```

## Размещение на lexapp.co.ua

### Вариант 1: Статический сайт через nginx

1. Скопируйте директорию `static/badges` на сервер:
```bash
scp -r static/badges/ user@lexapp.co.ua:/var/www/lexapp.co.ua/badges/
```

2. Настройте nginx для обслуживания статических файлов:
```nginx
server {
    listen 80;
    listen [::]:80;
    server_name lexapp.co.ua www.lexapp.co.ua;
    
    root /var/www/lexapp.co.ua;
    index index.html;
    
    location /badges {
        alias /var/www/lexapp.co.ua/badges;
        try_files $uri $uri/ =404;
    }
}
```

3. Доступ к странице будет по адресу: `https://lexapp.co.ua/badges/index.html`

### Вариант 2: Интеграция в FastAPI приложение

Если у вас есть FastAPI приложение, добавьте статические файлы:

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

app = FastAPI()

# Подключение статических файлов
app.mount("/static", StaticFiles(directory="static"), name="static")
```

Тогда кнопки будут доступны по адресу: `https://lexapp.co.ua/static/badges/`

### Вариант 3: CDN или облачное хранилище

Вы также можете загрузить файлы в облачное хранилище (AWS S3, Cloudflare R2, etc.) и использовать CDN для быстрой загрузки.

## Важные замечания

1. **Соблюдайте правила использования**: Google, Apple и Microsoft имеют строгие гайдлайны по использованию своих бейджей. Убедитесь, что вы следуете их правилам.

2. **Обновите ссылки**: В файле `index.html` все ссылки ведут на `#`. Замените их на реальные ссылки на ваши приложения в соответствующих магазинах.

3. **Размеры изображений**: Официальные кнопки имеют рекомендуемые размеры. Не изменяйте пропорции изображений.

4. **SVG vs PNG**: SVG файлы масштабируются лучше, но PNG файлы могут быть более совместимыми со старыми браузерами.

## Источники

- **Google Play**: https://developers.google.com/google-play/badges
- **Apple App Store**: https://developer.apple.com/app-store/marketing/guidelines/
- **Microsoft Store**: https://developer.microsoft.com/en-us/store/badges
- **Flathub**: https://flathub.org/badges

## Обновление кнопок

Если нужно обновить кнопки, используйте следующие команды:

```bash
cd static/badges

# Google Play
curl -L -o google-play-badge-en.png "https://play.google.com/intl/en_us/badges/static/images/badges/en_badge_web_generic.png"
curl -L -o google-play-badge-ru.png "https://play.google.com/intl/ru/badges/static/images/badges/ru_badge_web_generic.png"
curl -L -o google-play-badge-uk.png "https://play.google.com/intl/uk/badges/static/images/badges/uk_badge_web_generic.png"

# App Store
curl -L -o app-store-badge-en.svg "https://tools.applemediaservices.com/api/badges/download-on-the-app-store/black/en-us.svg"
curl -L -o app-store-badge-ru.svg "https://tools.applemediaservices.com/api/badges/download-on-the-app-store/black/ru-ru.svg"
curl -L -o app-store-badge-uk.svg "https://tools.applemediaservices.com/api/badges/download-on-the-app-store/black/uk-ua.svg"

# Microsoft Store
curl -L -o microsoft-store-badge-en.svg "https://get.microsoft.com/images/en-us%20dark.svg"
curl -L -o microsoft-store-badge-ru.svg "https://get.microsoft.com/images/ru-ru%20dark.svg"
curl -L -o microsoft-store-badge-uk.svg "https://get.microsoft.com/images/uk-ua%20dark.svg"

# Flathub
curl -L -o flathub-badge-en.png "https://flathub.org/assets/badges/flathub-badge-en.png"
curl -L -o flathub-badge-ru.png "https://flathub.org/assets/badges/flathub-badge-ru.png"
curl -L -o flathub-badge-uk.png "https://flathub.org/assets/badges/flathub-badge-uk.png"
```
