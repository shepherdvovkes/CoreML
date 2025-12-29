#!/bin/bash

# Скрипт для настройки Xcode и сборки приложения

set -e

echo "🔍 Проверка установки Xcode..."

# Проверка наличия Xcode.app
if [ ! -d "/Applications/Xcode.app" ]; then
    echo "❌ Xcode.app не найден в /Applications/"
    echo "📖 Установите Xcode из App Store"
    exit 1
fi

echo "✅ Xcode.app найден"

# Проверка текущей настройки
CURRENT_PATH=$(xcode-select -p)
XCODE_PATH="/Applications/Xcode.app/Contents/Developer"

if [ "$CURRENT_PATH" != "$XCODE_PATH" ]; then
    echo "⚠️  xcode-select указывает на: $CURRENT_PATH"
    echo "📝 Нужно переключить на: $XCODE_PATH"
    echo ""
    echo "Выполните в терминале:"
    echo "  sudo xcode-select --switch $XCODE_PATH"
    echo "  sudo xcodebuild -runFirstLaunch"
    echo ""
    echo "После этого запустите этот скрипт снова."
    exit 1
fi

echo "✅ xcode-select настроен правильно"

# Проверка xcodebuild
if ! command -v xcodebuild &> /dev/null; then
    echo "❌ xcodebuild не найден в PATH"
    exit 1
fi

echo "✅ xcodebuild доступен"

# Проверка версии Xcode
XCODE_VERSION=$(xcodebuild -version 2>&1 | head -1)
echo "📦 Версия Xcode: $XCODE_VERSION"

# Проверка CocoaPods
echo ""
echo "🔍 Проверка CocoaPods..."
if ! command -v pod &> /dev/null; then
    echo "⚠️  CocoaPods не установлен"
    echo "📝 Для установки выполните:"
    echo "   ./install_cocoapods.sh"
    echo ""
    echo "Или вручную:"
    echo "   sudo gem install cocoapods"
    echo ""
    read -p "Продолжить без CocoaPods? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    POD_VERSION=$(pod --version)
    echo "✅ CocoaPods установлен: версия $POD_VERSION"
fi

# Сборка приложения
echo ""
echo "🚀 Начинаю сборку приложения..."
cd "$(dirname "$0")"
flutter build macos --release

echo ""
echo "✅ Сборка завершена!"
echo "📦 Приложение находится в: build/macos/Build/Products/Release/flutter_app.app"
echo ""
echo "💿 Для создания DMG выполните:"
echo "   ./create_dmg.sh"

