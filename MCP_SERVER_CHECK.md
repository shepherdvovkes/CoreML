# Проверка MCP сервера и nginx конфигурации

**Дата проверки:** 2026-01-01

## ✅ Статус: Работает корректно

### Результаты проверки:

1. **MCP сервер работает** ✅
   - Процесс: `node /home/vovkes/court-app-servers/server-zakononline-mcp`
   - Порт: `3014` (слушает на всех интерфейсах)
   - PID: `469585`

2. **Health check работает** ✅
   - Локально: `http://localhost:3014/health` → OK
   - Через nginx: `https://mcp.lexapp.co.ua/health` → OK
   - Через nginx с /mcp: `https://mcp.lexapp.co.ua/mcp/health` → OK

3. **API работает** ✅
   - Локально: `http://localhost:3014/v1/mcp/search_cases` → OK
   - Через nginx: `https://mcp.lexapp.co.ua/mcp/v1/mcp/search_cases` → OK

4. **Nginx конфигурация** ✅
   - Сервер работает (active running)
   - Проксирование настроено правильно:
     - `location /mcp/` → `proxy_pass http://localhost:3014/`
     - Таймауты увеличены для долгоживущих соединений (600s)
     - Поддержка SSE (Server-Sent Events)

### Конфигурация:

**Base URL в config.py:**
```python
mcp_law_server_url: str = "https://mcp.lexapp.co.ua/mcp"
```

**Правильные пути для запросов:**
- Health: `https://mcp.lexapp.co.ua/mcp/health`
- Search: `https://mcp.lexapp.co.ua/mcp/v1/mcp/search_cases`
- Case details: `https://mcp.lexapp.co.ua/mcp/v1/mcp/get_case_details`
- Full text: `https://mcp.lexapp.co.ua/mcp/v1/mcp/get_case_full_text`

### Проблемы:

1. **Nginx конфигурация имеет предупреждение:**
   - Ошибка с SSL сертификатом для `auth.lexapp.co.ua` (не критично для MCP)
   - Команда `nginx -t` показывает ошибку, но nginx работает

2. **Доступ к логам:**
   - Нет прав для чтения `/var/log/nginx/mcp.lexapp.co.ua.*.log` (нужны root права)

### Рекомендации:

1. ✅ MCP сервер работает корректно
2. ✅ Nginx проксирует запросы правильно
3. ✅ Все эндпоинты доступны
4. ⚠️ Исправить проблему с SSL сертификатом для auth.lexapp.co.ua (не критично)

### Тестирование:

```bash
# Health check
curl https://mcp.lexapp.co.ua/health

# Поиск дел
curl -X POST https://mcp.lexapp.co.ua/mcp/v1/mcp/search_cases \
  -H 'Content-Type: application/json' \
  -d '{"query":"договір","limit":1}'
```

Все тесты пройдены успешно! ✅

