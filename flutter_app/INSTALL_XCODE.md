# Установка Xcode для сборки macOS приложения

Для сборки macOS приложения требуется Xcode. Следуйте этим инструкциям:

## 1. Установка Xcode

### Вариант A: Через App Store (рекомендуется)
1. Откройте App Store
2. Найдите "Xcode"
3. Нажмите "Получить" или "Установить"
4. Дождитесь завершения установки (может занять время)

### Вариант B: Через сайт Apple Developer
1. Перейдите на https://developer.apple.com/xcode/
2. Скачайте Xcode
3. Установите приложение

## 2. Настройка Xcode

После установки выполните в терминале:

```bash
# Установка командной строки инструментов
sudo xcode-select --switch /Applications/Xcode.app/Contents/Developer

# Принятие лицензии
sudo xcodebuild -runFirstLaunch

# Установка дополнительных компонентов (если потребуется)
sudo xcodebuild -license accept
```

## 3. Установка CocoaPods (опционально, но рекомендуется)

```bash
sudo gem install cocoapods
```

## 4. Проверка установки

```bash
flutter doctor
```

Должно показать, что Xcode установлен и настроен правильно.

## 5. Сборка приложения

После установки Xcode выполните:

```bash
cd flutter_app
flutter build macos --release
```

## 6. Создание DMG

```bash
./create_dmg.sh
```

