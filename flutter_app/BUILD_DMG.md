# Создание DMG для macOS

## Требования

1. **Xcode** - должен быть установлен и настроен
2. **Flutter** - должен быть установлен
3. **macOS** - версия 10.14 или выше

## Быстрый старт

### 1. Установите Xcode (если еще не установлен)

См. `INSTALL_XCODE.md` для подробных инструкций.

### 2. Соберите приложение

```bash
cd flutter_app
flutter build macos --release
```

### 3. Создайте DMG

**Простой вариант:**
```bash
./create_dmg.sh
```

**Продвинутый вариант (с настройкой внешнего вида):**
```bash
./create_dmg_advanced.sh
```

## Что делает скрипт

1. ✅ Проверяет наличие собранного приложения
2. ✅ Создает временную директорию
3. ✅ Копирует приложение
4. ✅ Создает символическую ссылку на Applications
5. ✅ Создает DMG файл
6. ✅ Сжимает DMG для уменьшения размера

## Результат

После выполнения скрипта вы получите файл:
- `CoreML_RAG_MCP_Chat.dmg`

## Установка на другой Mac

1. Передайте DMG файл на другой Mac
2. Откройте DMG файл (двойной клик)
3. Перетащите приложение в папку Applications
4. Запустите приложение из Applications

## Устранение проблем

### Ошибка: "Xcode не установлен"
- Установите Xcode из App Store
- Выполните: `sudo xcode-select --switch /Applications/Xcode.app/Contents/Developer`
- Выполните: `sudo xcodebuild -runFirstLaunch`

### Ошибка: "Приложение не найдено"
- Убедитесь, что выполнили: `flutter build macos --release`
- Проверьте путь: `build/macos/Build/Products/Release/flutter_app.app`

### Ошибка при создании DMG
- Убедитесь, что у вас достаточно места на диске
- Проверьте права доступа к файлам
- Попробуйте запустить скрипт с правами администратора (не рекомендуется)

## Подпись приложения (опционально)

Для распространения через App Store или вне App Store требуется подпись:

```bash
# Создание сертификата (требуется Apple Developer аккаунт)
# См. https://developer.apple.com/documentation/security/notarizing_macos_software_before_distribution
```

## Размер DMG

Обычный размер DMG файла: ~50-100 MB (в зависимости от зависимостей)

## Альтернативные методы

### Использование create-dmg (требует установки)

```bash
brew install create-dmg
create-dmg \
  --volname "$APP_NAME" \
  --window-pos 200 120 \
  --window-size 800 400 \
  --icon-size 100 \
  --icon "$APP_BUNDLE" 200 190 \
  --hide-extension "$APP_BUNDLE" \
  --app-drop-link 600 185 \
  "$DMG_NAME.dmg" \
  "$BUILD_DIR/"
```

