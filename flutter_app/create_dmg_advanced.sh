#!/bin/bash

# Продвинутый скрипт для создания DMG с настройками внешнего вида

set -e

APP_NAME="CoreML RAG MCP Chat"
APP_BUNDLE="flutter_app.app"
DMG_NAME="CoreML_RAG_MCP_Chat"
VERSION="1.0.0"
BUILD_DIR="build/macos/Build/Products/Release"
DMG_TEMP="dmg_temp"
DMG_SIZE="200m"

echo "🚀 Создание улучшенного DMG для $APP_NAME..."

# Проверка наличия собранного приложения
if [ ! -d "$BUILD_DIR/$APP_BUNDLE" ]; then
    echo "❌ Приложение не найдено. Запустите: flutter build macos --release"
    exit 1
fi

# Очистка
rm -rf "$DMG_TEMP" "${DMG_NAME}.dmg" "${DMG_NAME}_temp.dmg"

# Создание временной директории
mkdir -p "$DMG_TEMP"
cp -R "$BUILD_DIR/$APP_BUNDLE" "$DMG_TEMP/"

# Создание символической ссылки на Applications
ln -s /Applications "$DMG_TEMP/Applications"

# Создание временного DMG
echo "💿 Создание временного DMG..."
hdiutil create -srcfolder "$DMG_TEMP" -volname "$APP_NAME" -fs HFS+ -fsargs "-c c=64,a=16,e=16" -format UDRW -size "$DMG_SIZE" "${DMG_NAME}_temp.dmg"

# Монтирование DMG
echo "📂 Монтирование DMG..."
DEVICE=$(hdiutil attach -readwrite -noverify -noautoopen "${DMG_NAME}_temp.dmg" | egrep '^/dev/' | sed 1q | awk '{print $1}')
MOUNT_POINT="/Volumes/$APP_NAME"

# Настройка внешнего вида через AppleScript
echo "🎨 Настройка внешнего вида..."
osascript <<EOF
tell application "Finder"
    tell disk "$APP_NAME"
        open
        set current view of container window to icon view
        set toolbar visible of container window to false
        set statusbar visible of container window to false
        set the bounds of container window to {400, 100, 920, 420}
        set viewOptions to the icon view options of container window
        set arrangement of viewOptions to not arranged
        set icon size of viewOptions to 72
        set position of item "$APP_BUNDLE" of container window to {160, 205}
        set position of item "Applications" of container window to {360, 205}
        close
        open
        update without registering applications
        delay 2
    end tell
end tell
EOF

# Синхронизация
sync
sync

# Размонтирование
echo "📤 Размонтирование..."
hdiutil detach "$DEVICE"

# Создание финального сжатого DMG
echo "🗜️ Создание финального DMG..."
hdiutil convert "${DMG_NAME}_temp.dmg" -format UDZO -imagekey zlib-level=9 -o "${DMG_NAME}.dmg"

# Очистка
rm -f "${DMG_NAME}_temp.dmg"
rm -rf "$DMG_TEMP"

echo "✅ DMG файл создан: ${DMG_NAME}.dmg"
echo "📦 Размер: $(du -h "${DMG_NAME}.dmg" | cut -f1)"
echo ""
echo "📝 Для установки:"
echo "   1. Откройте ${DMG_NAME}.dmg"
echo "   2. Перетащите $APP_BUNDLE в папку Applications"
echo "   3. Запустите приложение из Applications"

