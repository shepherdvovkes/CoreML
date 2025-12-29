#!/bin/bash

# Скрипт для создания DMG файла для macOS приложения

set -e

APP_NAME="CoreML RAG MCP Chat"
APP_BUNDLE="flutter_app.app"
DMG_NAME="CoreML_RAG_MCP_Chat"
VERSION="1.0.0"
BUILD_DIR="build/macos/Build/Products/Release"
DMG_DIR="dmg_build"
DMG_TEMP="dmg_temp"

echo "🚀 Создание DMG для $APP_NAME..."

# Проверка наличия Xcode
if ! command -v xcodebuild &> /dev/null; then
    echo "❌ Xcode не установлен или не настроен."
    echo "📖 См. инструкции в INSTALL_XCODE.md"
    echo ""
    echo "Быстрая установка:"
    echo "1. Установите Xcode из App Store"
    echo "2. Выполните: sudo xcode-select --switch /Applications/Xcode.app/Contents/Developer"
    echo "3. Выполните: sudo xcodebuild -runFirstLaunch"
    exit 1
fi

# Проверка наличия собранного приложения
if [ ! -d "$BUILD_DIR/$APP_BUNDLE" ]; then
    echo "📦 Приложение не собрано. Запускаю сборку..."
    flutter build macos --release
    
    if [ ! -d "$BUILD_DIR/$APP_BUNDLE" ]; then
        echo "❌ Ошибка сборки приложения. Проверьте логи выше."
        exit 1
    fi
fi

# Очистка предыдущих сборок
echo "🧹 Очистка предыдущих сборок..."
rm -rf "$DMG_DIR" "$DMG_TEMP" "${DMG_NAME}.dmg"

# Создание временной директории
echo "📁 Создание структуры DMG..."
mkdir -p "$DMG_TEMP"

# Копирование приложения
echo "📦 Копирование приложения..."
cp -R "$BUILD_DIR/$APP_BUNDLE" "$DMG_TEMP/"

# Создание символической ссылки на Applications
ln -s /Applications "$DMG_TEMP/Applications"

# Создание DMG с настройками
echo "💿 Создание DMG файла..."
hdiutil create -volname "$APP_NAME" -srcfolder "$DMG_TEMP" -ov -format UDZO "${DMG_NAME}.dmg"

# Опционально: монтирование и настройка внешнего вида
echo "🎨 Настройка внешнего вида DMG..."
DMG_MOUNT="/Volumes/$APP_NAME"
if [ -d "$DMG_MOUNT" ]; then
    # Установка размера окна (опционально)
    # Можно использовать AppleScript для настройки, но это требует монтирования
    echo "✅ DMG создан и смонтирован"
fi

# Очистка
echo "🧹 Очистка временных файлов..."
rm -rf "$DMG_TEMP"

echo "✅ DMG файл создан: ${DMG_NAME}.dmg"
echo "📦 Размер: $(du -h "${DMG_NAME}.dmg" | cut -f1)"

