# Анализ и улучшения API клиента

## Текущее состояние

### ✅ Что реализовано хорошо
- Базовая обработка ошибок с типизированными исключениями
- Retry логика для ошибок подключения
- Логирование запросов и ответов
- Поддержка отмены запросов (CancelToken)
- Разделение таймаутов для разных операций
- Обработка различных типов ошибок Dio

### ⚠️ Что можно улучшить

## Критические улучшения

### 1. **Парсинг streaming ответов**
**Проблема**: Сервер возвращает `text/plain` поток, но нет обработки возможных ошибок в потоке.

**Решение**:
```dart
// Добавить обработку ошибок в потоке
await for (final chunk in stream.transform(utf8.decoder)) {
  if (cancelToken != null && cancelToken.isCancelled) {
    break;
  }
  // Проверка на ошибки в потоке
  if (chunk.startsWith('Error:')) {
    throw ServerError(chunk);
  }
  yield chunk;
}
```

### 2. **Дублирование кода обработки ошибок**
**Проблема**: Одинаковая логика обработки DioException повторяется в каждом методе.

**Решение**: Вынести в отдельный метод:
```dart
AppError _handleDioException(DioException e, {CancelToken? cancelToken}) {
  if (cancelToken != null && cancelToken.isCancelled) {
    return CancelledError('Запрос отменен');
  }
  
  if (e.type == DioExceptionType.connectionTimeout ||
      e.type == DioExceptionType.receiveTimeout) {
    return NetworkError('Превышено время ожидания ответа');
  }
  
  if (e.type == DioExceptionType.connectionError ||
      e.message?.contains('Connection reset') == true ||
      e.message?.contains('SocketException') == true) {
    return NetworkError('Ошибка подключения к серверу. Проверьте, что API запущен на $baseUrl');
  }
  
  if (e.response != null) {
    final statusCode = e.response?.statusCode;
    final detail = e.response?.data['detail']?.toString() ?? 'Ошибка сервера';
    
    // Специальная обработка для разных статусов
    if (statusCode == 401) {
      return ServerError('Не авторизован', statusCode: statusCode);
    } else if (statusCode == 403) {
      return ServerError('Доступ запрещен', statusCode: statusCode);
    } else if (statusCode == 404) {
      return ServerError('Ресурс не найден', statusCode: statusCode);
    } else if (statusCode == 429) {
      return ServerError('Слишком много запросов. Попробуйте позже', statusCode: statusCode);
    } else if (statusCode == 500) {
      return ServerError('Внутренняя ошибка сервера', statusCode: statusCode);
    }
    
    return ServerError(detail, statusCode: statusCode);
  }
  
  return NetworkError('Ошибка сети: ${e.message ?? "Неизвестная ошибка"}');
}
```

### 3. **Валидация ответов**
**Проблема**: Нет проверки структуры ответов от сервера.

**Решение**: Добавить валидацию:
```dart
Map<String, dynamic> _validateResponse(
  Response response,
  List<String> requiredFields,
) {
  if (response.data is! Map<String, dynamic>) {
    throw ServerError('Неверный формат ответа сервера');
  }
  
  final data = response.data as Map<String, dynamic>;
  for (final field in requiredFields) {
    if (!data.containsKey(field)) {
      throw ServerError('Отсутствует обязательное поле: $field');
    }
  }
  
  return data;
}
```

### 4. **Прогресс загрузки файлов**
**Проблема**: Нет индикации прогресса при загрузке больших файлов.

**Решение**: Использовать `onSendProgress`:
```dart
Future<Map<String, dynamic>> uploadDocument(
  File file, {
  void Function(int sent, int total)? onProgress,
}) async {
  // ...
  final response = await _dio.post(
    '/rag/add-document',
    data: formData,
    onSendProgress: onProgress != null
        ? (sent, total) => onProgress(sent, total)
        : null,
  );
  // ...
}
```

### 5. **Таймауты для разных операций**
**Проблема**: Одинаковые таймауты для всех операций, хотя streaming может быть долгим.

**Решение**: Разные таймауты:
```dart
static const Duration streamingTimeout = Duration(minutes: 10);
static const Duration uploadTimeout = Duration(minutes: 5);
static const Duration queryTimeout = Duration(seconds: 60);
```

## Важные улучшения

### 6. **Кэширование health check**
**Проблема**: Health check вызывается часто, но результат не кэшируется.

**Решение**:
```dart
DateTime? _lastHealthCheck;
Map<String, dynamic>? _cachedHealthStatus;
static const Duration healthCheckCacheDuration = Duration(seconds: 30);

Future<Map<String, dynamic>> healthCheck({bool forceRefresh = false}) async {
  if (!forceRefresh && 
      _lastHealthCheck != null &&
      _cachedHealthStatus != null &&
      DateTime.now().difference(_lastHealthCheck!) < healthCheckCacheDuration) {
    return _cachedHealthStatus!;
  }
  
  // ... выполнение запроса ...
  
  _lastHealthCheck = DateTime.now();
  _cachedHealthStatus = response.data;
  return _cachedHealthStatus!;
}
```

### 7. **Метрики производительности**
**Проблема**: Нет отслеживания времени выполнения запросов.

**Решение**: Добавить логирование времени:
```dart
void _setupInterceptors() {
  _dio.interceptors.add(
    InterceptorsWrapper(
      onRequest: (options, handler) {
        options.extra['startTime'] = DateTime.now();
        // ...
      },
      onResponse: (response, handler) {
        final startTime = response.requestOptions.extra['startTime'] as DateTime?;
        if (startTime != null) {
          final duration = DateTime.now().difference(startTime);
          AppLogger.d('Request completed in ${duration.inMilliseconds}ms');
        }
        // ...
      },
    ),
  );
}
```

### 8. **Улучшенная retry логика**
**Проблема**: Retry только для connection errors, но не для временных ошибок сервера (5xx).

**Решение**:
```dart
bool _shouldRetry(DioException error, int retryCount) {
  if (retryCount >= 3) return false;
  
  // Retry для ошибок подключения
  if (error.type == DioExceptionType.connectionError ||
      error.type == DioExceptionType.connectionTimeout ||
      error.type == DioExceptionType.sendTimeout) {
    return true;
  }
  
  // Retry для временных ошибок сервера
  if (error.response?.statusCode != null) {
    final statusCode = error.response!.statusCode!;
    if (statusCode >= 500 && statusCode < 600) {
      return true;
    }
    // Retry для rate limiting (429)
    if (statusCode == 429) {
      return true;
    }
  }
  
  return false;
}
```

### 9. **Заголовки запросов**
**Проблема**: Нет User-Agent и других полезных заголовков.

**Решение**:
```dart
ApiClient({String? baseUrl})
    : baseUrl = baseUrl ?? AppConfig.defaultApiUrl,
      _dio = Dio(BaseOptions(
        baseUrl: baseUrl ?? AppConfig.defaultApiUrl,
        connectTimeout: AppConfig.connectionTimeout,
        receiveTimeout: AppConfig.receiveTimeout,
        headers: {
          'Content-Type': 'application/json',
          'User-Agent': 'CoreML-Flutter-Client/1.0.0',
          'Accept': 'application/json',
        },
      )) {
  _setupInterceptors();
}
```

### 10. **Обработка пустых ответов**
**Проблема**: Нет проверки на пустые ответы.

**Решение**:
```dart
if (response.data == null) {
  throw ServerError('Пустой ответ от сервера');
}
```

## Дополнительные улучшения

### 11. **Типизация ответов**
**Проблема**: Все ответы как `Map<String, dynamic>`, нет типизации.

**Решение**: Создать модели ответов:
```dart
class QueryResponse {
  final String answer;
  final List<String> sources;
  final Map<String, dynamic>? metadata;
  
  QueryResponse.fromJson(Map<String, dynamic> json)
      : answer = json['answer'] as String,
        sources = List<String>.from(json['sources'] ?? []),
        metadata = json['metadata'] as Map<String, dynamic>?;
}
```

### 12. **Обработка больших ответов**
**Проблема**: Нет ограничения на размер ответа.

**Решение**: Добавить проверку:
```dart
static const int maxResponseSize = 10 * 1024 * 1024; // 10 MB

if (response.data.toString().length > maxResponseSize) {
  throw ServerError('Ответ слишком большой');
}
```

### 13. **Автоматическое обновление baseUrl**
**Проблема**: При изменении baseUrl нужно пересоздавать клиент.

**Решение**: Метод для обновления:
```dart
void updateBaseUrl(String newBaseUrl) {
  _dio.options.baseUrl = newBaseUrl;
  baseUrl = newBaseUrl;
  AppLogger.i('API base URL updated to: $newBaseUrl');
}
```

### 14. **Интерцептор для токенов авторизации**
**Проблема**: Нет поддержки авторизации (если понадобится в будущем).

**Решение**: Добавить поддержку токенов:
```dart
String? _authToken;

void setAuthToken(String? token) {
  _authToken = token;
  if (token != null) {
    _dio.options.headers['Authorization'] = 'Bearer $token';
  } else {
    _dio.options.headers.remove('Authorization');
  }
}
```

### 15. **Обработка сетевых изменений**
**Проблема**: Нет автоматической обработки изменений сети.

**Решение**: Интеграция с ConnectivityService (уже есть в проекте).

### 16. **Логирование тела запросов/ответов**
**Проблема**: Логируется только URL, но не тело запроса.

**Решение**: Добавить опциональное логирование тела:
```dart
static bool _logRequestBody = false; // можно включить для отладки

onRequest: (options, handler) {
  AppLogger.d('Request: ${options.method} ${options.baseUrl}${options.path}');
  if (_logRequestBody && options.data != null) {
    AppLogger.d('Request body: ${options.data}');
  }
  // ...
}
```

### 17. **Валидация URL**
**Проблема**: Нет проверки корректности baseUrl при создании.

**Решение**:
```dart
ApiClient({String? baseUrl}) {
  final url = baseUrl ?? AppConfig.defaultApiUrl;
  if (!_isValidUrl(url)) {
    throw ArgumentError('Invalid base URL: $url');
  }
  this.baseUrl = url;
  // ...
}

bool _isValidUrl(String url) {
  try {
    final uri = Uri.parse(url);
    return uri.hasScheme && (uri.scheme == 'http' || uri.scheme == 'https');
  } catch (e) {
    return false;
  }
}
```

### 18. **Обработка chunked responses**
**Проблема**: Нет специальной обработки для chunked encoding.

**Решение**: Уже обрабатывается через `stream.transform(utf8.decoder)`.

### 19. **Compression поддержка**
**Проблема**: Нет поддержки gzip/deflate compression.

**Решение**: Dio поддерживает автоматически, но можно явно включить:
```dart
_dio = Dio(BaseOptions(
  // ...
  headers: {
    'Accept-Encoding': 'gzip, deflate',
  },
))
```

### 20. **Connection pooling**
**Проблема**: Нет настройки connection pooling.

**Решение**: Dio использует connection pooling по умолчанию, но можно настроить:
```dart
_dio.httpClientAdapter = IOHttpClientAdapter(
  createHttpClient: () {
    final client = HttpClient();
    client.maxConnectionsPerHost = 5;
    return client;
  },
);
```

## Приоритеты внедрения

### Фаза 1 (Критично - немедленно)
1. ✅ Дублирование кода обработки ошибок - вынести в метод
2. ✅ Валидация ответов - добавить проверки
3. ✅ Улучшенная retry логика - для 5xx и 429
4. ✅ Обработка пустых ответов

### Фаза 2 (Важно - в ближайшее время)
5. ✅ Прогресс загрузки файлов
6. ✅ Разные таймауты для операций
7. ✅ Кэширование health check
8. ✅ Метрики производительности
9. ✅ Заголовки запросов

### Фаза 3 (Дополнительно - по необходимости)
10. ✅ Типизация ответов
11. ✅ Обработка больших ответов
12. ✅ Автоматическое обновление baseUrl
13. ✅ Поддержка авторизации
14. ✅ Валидация URL

## Пример улучшенного кода

См. файл `api_client_improved.dart` для полной реализации всех улучшений.

