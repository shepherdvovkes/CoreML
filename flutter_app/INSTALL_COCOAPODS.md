# Установка CocoaPods

CocoaPods требуется для работы с iOS/macOS плагинами в Flutter.

## ⚠️ Проблема с версией Ruby

Если у вас старая версия Ruby (< 3.1.0), используйте **Homebrew** для установки CocoaPods.

## Быстрая установка

### Вариант 1: Через Homebrew (рекомендуется)

```bash
cd /Users/vovkes/CoreML/flutter_app
./install_cocoapods_homebrew.sh
```

Или вручную:
```bash
brew install cocoapods
```

### Вариант 2: Автоматический скрипт (попытается использовать Homebrew если Ruby старый)

```bash
cd /Users/vovkes/CoreML/flutter_app
./install_cocoapods.sh
```

### Вариант 3: Через gem (только если Ruby >= 3.1.0)

```bash
sudo gem install cocoapods
```

## После установки

После установки CocoaPods выполните настройку репозитория (опционально, но рекомендуется):

```bash
pod setup
```

Это загрузит репозиторий CocoaPods. Может занять некоторое время.

## Проверка установки

```bash
pod --version
```

Должна отобразиться версия CocoaPods.

## Устранение проблем

### Ошибка: "gem: command not found"

Установите Ruby (обычно уже установлен в macOS):
```bash
# Проверка Ruby
ruby --version
```

### Ошибка: "Permission denied"

Используйте `sudo`:
```bash
sudo gem install cocoapods
```

### Ошибка при установке

Попробуйте установить через Homebrew:
```bash
brew install cocoapods
```

## Для сборки Flutter приложения

После установки CocoaPods можно продолжить сборку:

```bash
cd /Users/vovkes/CoreML/flutter_app
flutter build macos --release
```

