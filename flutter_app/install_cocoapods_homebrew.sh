#!/bin/bash

# Скрипт для установки CocoaPods через Homebrew (рекомендуется)

set -e

echo "🔍 Проверка CocoaPods..."

if command -v pod &> /dev/null; then
    POD_VERSION=$(pod --version)
    echo "✅ CocoaPods уже установлен: версия $POD_VERSION"
    exit 0
fi

echo "📦 CocoaPods не установлен. Установка через Homebrew..."
echo ""

# Проверка наличия Homebrew
if ! command -v brew &> /dev/null; then
    echo "❌ Homebrew не установлен."
    echo ""
    echo "Установите Homebrew:"
    echo '  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
    echo ""
    echo "После установки Homebrew запустите этот скрипт снова."
    exit 1
fi

echo "✅ Homebrew найден"
echo "📥 Установка CocoaPods через Homebrew..."
brew install cocoapods

# Проверка установки
if command -v pod &> /dev/null; then
    POD_VERSION=$(pod --version)
    echo ""
    echo "✅ CocoaPods успешно установлен: версия $POD_VERSION"
else
    echo "❌ Ошибка установки CocoaPods"
    exit 1
fi

