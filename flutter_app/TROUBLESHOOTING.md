# Устранение проблем подключения Flutter к API

## Проблема: Flutter приложение не может подключиться к API на http://localhost:8000

### Решения:

#### 1. Использовать 127.0.0.1 вместо localhost

В настройках приложения измените URL API на:
```
http://127.0.0.1:8000
```

#### 2. Проверить, что API запущен

```bash
# Проверка статуса контейнеров
cd /Users/vovkes/CoreML
docker-compose -f docker-compose.prod.yml ps

# Проверка доступности API
curl http://127.0.0.1:8000/health
```

#### 3. Проверить настройки macOS

Убедитесь, что в `macos/Runner/Info.plist` есть:
```xml
<key>NSAppTransportSecurity</key>
<dict>
    <key>NSAllowsLocalNetworking</key>
    <true/>
</dict>
```

#### 4. Проверить настройки сети Docker

Убедитесь, что порт 8000 проброшен:
```bash
docker-compose -f docker-compose.prod.yml ps api
# Должно быть: 0.0.0.0:8000->8000/tcp
```

#### 5. Использовать IP адрес хоста

Если приложение запущено на физическом устройстве или эмуляторе, используйте IP адрес вашего компьютера в локальной сети:

```bash
# Узнать IP адрес
ifconfig | grep "inet " | grep -v 127.0.0.1
# Или
ipconfig getifaddr en0
```

Затем в настройках приложения используйте:
```
http://<ваш-ip-адрес>:8000
```

#### 6. Проверить файрвол

Убедитесь, что файрвол macOS не блокирует порт 8000:
```bash
# Проверить правила файрвола
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --listapps
```

#### 7. Перезапустить приложение

После изменения настроек перезапустите Flutter приложение:
```bash
flutter run -d macos
```

### Проверка подключения в настройках

В приложении есть встроенная функция проверки подключения:
1. Откройте настройки (Settings)
2. Введите URL API
3. Нажмите "Проверить"
4. Если подключение успешно, нажмите "Сохранить"

### Логи для отладки

Проверьте логи Flutter приложения:
```bash
flutter logs
```

Проверьте логи API:
```bash
docker-compose -f docker-compose.prod.yml logs api
```

