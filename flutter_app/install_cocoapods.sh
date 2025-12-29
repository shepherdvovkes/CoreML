#!/bin/bash

# Скрипт для установки CocoaPods

set -e

echo "🔍 Проверка CocoaPods..."

if command -v pod &> /dev/null; then
    POD_VERSION=$(pod --version)
    echo "✅ CocoaPods уже установлен: версия $POD_VERSION"
    exit 0
fi

echo "📦 CocoaPods не установлен. Начинаю установку..."
echo ""

# Проверка наличия Ruby
if ! command -v ruby &> /dev/null; then
    echo "❌ Ruby не найден. CocoaPods требует Ruby."
    exit 1
fi

RUBY_VERSION=$(ruby --version | cut -d' ' -f2)
RUBY_MAJOR=$(echo $RUBY_VERSION | cut -d'.' -f1)
RUBY_MINOR=$(echo $RUBY_VERSION | cut -d'.' -f2)

echo "📦 Текущая версия Ruby: $RUBY_VERSION"

# Проверка версии Ruby
if [ "$RUBY_MAJOR" -lt 3 ] || ([ "$RUBY_MAJOR" -eq 3 ] && [ "$RUBY_MINOR" -lt 1 ]); then
    echo "⚠️  Версия Ruby слишком старая ($RUBY_VERSION). CocoaPods требует Ruby >= 3.1.0"
    echo ""
    echo "Рекомендуется установить CocoaPods через Homebrew:"
    echo "   brew install cocoapods"
    echo ""
    
    # Проверка наличия Homebrew
    if command -v brew &> /dev/null; then
        echo "✅ Homebrew найден. Использовать Homebrew для установки? (y/n)"
        read -p "> " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo "📥 Установка CocoaPods через Homebrew..."
            brew install cocoapods
            if command -v pod &> /dev/null; then
                POD_VERSION=$(pod --version)
                echo "✅ CocoaPods успешно установлен через Homebrew: версия $POD_VERSION"
                exit 0
            fi
        fi
    else
        echo "❌ Homebrew не установлен."
        echo ""
        echo "Варианты решения:"
        echo "1. Установить Homebrew: /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
        echo "2. Затем: brew install cocoapods"
        echo "3. Или обновить Ruby через rbenv/rvm"
        exit 1
    fi
    
    echo ""
    echo "Попытка установить старую версию CocoaPods, совместимую с Ruby $RUBY_VERSION..."
    sudo gem install cocoapods -v 1.11.3 || {
        echo "❌ Не удалось установить CocoaPods"
        echo "Рекомендуется использовать Homebrew: brew install cocoapods"
        exit 1
    }
else
    # Установка CocoaPods через gem (для Ruby >= 3.1)
    echo "📥 Установка CocoaPods через gem (это может занять несколько минут)..."
    sudo gem install cocoapods
fi

# Проверка установки
if command -v pod &> /dev/null; then
    POD_VERSION=$(pod --version)
    echo ""
    echo "✅ CocoaPods успешно установлен: версия $POD_VERSION"
    echo ""
    echo "📝 Для завершения настройки выполните:"
    echo "   pod setup"
    echo ""
    echo "Это загрузит репозиторий CocoaPods (может занять время)."
else
    echo "❌ Ошибка установки CocoaPods"
    exit 1
fi

