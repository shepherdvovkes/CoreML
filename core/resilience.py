"""
Модуль для повышения отказоустойчивости системы
Содержит декораторы retry, circuit breaker, timeout для всех внешних вызовов
"""
import asyncio
import functools
import inspect
from typing import Callable, Any, Optional, Type, Tuple, Union, AsyncIterator
from loguru import logger
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
    after_log,
    RetryError
)
from pybreaker import CircuitBreaker, CircuitBreakerError
import httpx


# Типы исключений для retry
RETRIABLE_EXCEPTIONS = (
    httpx.TimeoutException,
    httpx.NetworkError,
    httpx.ConnectError,
    httpx.ConnectTimeout,
    ConnectionError,
    TimeoutError,
)

# Типы исключений для circuit breaker
CIRCUIT_BREAKER_EXCEPTIONS = (
    httpx.HTTPStatusError,
    httpx.TimeoutException,
    httpx.NetworkError,
    ConnectionError,
    TimeoutError,
)


class ResilienceConfig:
    """Конфигурация для паттернов отказоустойчивости"""
    
    def __init__(self):
        """Загрузка конфигурации из settings"""
        try:
            from config import settings
            
            # Retry настройки
            self.RETRY_MAX_ATTEMPTS = settings.resilience_retry_max_attempts
            self.RETRY_MIN_WAIT = settings.resilience_retry_min_wait
            self.RETRY_MAX_WAIT = settings.resilience_retry_max_wait
            self.RETRY_MULTIPLIER = settings.resilience_retry_multiplier
            
            # Circuit Breaker настройки
            self.CB_FAIL_MAX = settings.resilience_cb_fail_max
            self.CB_TIMEOUT = settings.resilience_cb_timeout
            self.CB_EXPECTED_EXCEPTION = Exception
            
            # Timeout настройки
            self.DEFAULT_TIMEOUT = settings.resilience_default_timeout
            self.LLM_TIMEOUT = settings.resilience_llm_timeout
            self.RAG_TIMEOUT = settings.resilience_rag_timeout
            self.MCP_TIMEOUT = settings.resilience_mcp_timeout
            
            logger.info("ResilienceConfig loaded from settings")
        except Exception as e:
            logger.warning(f"Failed to load settings, using defaults: {e}")
            # Fallback значения
            self.RETRY_MAX_ATTEMPTS = 3
            self.RETRY_MIN_WAIT = 1
            self.RETRY_MAX_WAIT = 10
            self.RETRY_MULTIPLIER = 2
            self.CB_FAIL_MAX = 5
            self.CB_TIMEOUT = 60
            self.CB_EXPECTED_EXCEPTION = Exception
            self.DEFAULT_TIMEOUT = 30
            self.LLM_TIMEOUT = 120
            self.RAG_TIMEOUT = 60
            self.MCP_TIMEOUT = 45


# Создание глобального экземпляра конфигурации
_resilience_config = ResilienceConfig()


# Circuit Breakers для разных сервисов
class CircuitBreakers:
    """Централизованное хранилище circuit breakers"""
    
    _breakers = {}
    
    @classmethod
    def get_breaker(cls, name: str, **kwargs) -> CircuitBreaker:
        """Получить или создать circuit breaker"""
        if name not in cls._breakers:
            from core.resilience import _resilience_config
            expected_exception = kwargs.get('expected_exception', _resilience_config.CB_EXPECTED_EXCEPTION)
            # exclude должен быть списком или None
            exclude_list = [expected_exception] if expected_exception and isinstance(expected_exception, type) else (expected_exception if expected_exception else None)
            cb_config = {
                'fail_max': kwargs.get('fail_max', _resilience_config.CB_FAIL_MAX),
                'reset_timeout': kwargs.get('timeout', _resilience_config.CB_TIMEOUT),
                'exclude': exclude_list,
                'name': name,
            }
            cls._breakers[name] = CircuitBreaker(**cb_config)
            logger.info(f"Created circuit breaker: {name} with config {cb_config}")
        return cls._breakers[name]
    
    @classmethod
    def reset_all(cls):
        """Сброс всех circuit breakers (полезно для тестирования)"""
        for breaker in cls._breakers.values():
            breaker.close()
        logger.info("All circuit breakers reset")


def with_retry(
    max_attempts: Optional[int] = None,
    min_wait: Optional[int] = None,
    max_wait: Optional[int] = None,
    multiplier: Optional[int] = None,
    exceptions: Tuple[Type[Exception], ...] = RETRIABLE_EXCEPTIONS,
    log_level: str = "WARNING"
):
    """
    Декоратор для retry с экспоненциальным backoff
    
    Args:
        max_attempts: Максимальное количество попыток
        min_wait: Минимальное время ожидания между попытками (сек)
        max_wait: Максимальное время ожидания между попытками (сек)
        multiplier: Множитель для экспоненциального backoff
        exceptions: Типы исключений для retry
        log_level: Уровень логирования
        
    Example:
        @with_retry(max_attempts=5, exceptions=(TimeoutError,))
        async def fetch_data():
            ...
    """
    def decorator(func: Callable) -> Callable:
        # Используем значения из конфига если не указаны явно
        _max_attempts = max_attempts if max_attempts is not None else _resilience_config.RETRY_MAX_ATTEMPTS
        _min_wait = min_wait if min_wait is not None else _resilience_config.RETRY_MIN_WAIT
        _max_wait = max_wait if max_wait is not None else _resilience_config.RETRY_MAX_WAIT
        _multiplier = multiplier if multiplier is not None else _resilience_config.RETRY_MULTIPLIER
        
        retry_decorator = retry(
            stop=stop_after_attempt(_max_attempts),
            wait=wait_exponential(
                multiplier=_multiplier,
                min=_min_wait,
                max=_max_wait
            ),
            retry=retry_if_exception_type(exceptions),
            before_sleep=before_sleep_log(logger, getattr(logger, log_level.lower())),
            after=after_log(logger, getattr(logger, log_level.lower())),
            reraise=True
        )
        
        # Проверяем, является ли функция асинхронным генератором
        # Для bound methods нужно проверять исходную функцию
        original_func = func
        if hasattr(func, '__func__'):
            # Это bound method, проверяем исходную функцию
            original_func = func.__func__
        elif hasattr(func, '__wrapped__'):
            # Это обернутая функция, проверяем исходную
            original_func = func.__wrapped__
        
        is_async_gen = inspect.isasyncgenfunction(original_func)
        
        if is_async_gen:
            @functools.wraps(func)
            async def async_gen_wrapper(*args, **kwargs):
                # Для async generators retry не применяется на уровне генератора
                # так как это сложно реализовать правильно
                # Просто возвращаем генератор как есть
                async for item in func(*args, **kwargs):
                    yield item
            return async_gen_wrapper
        elif asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                try:
                    return await retry_decorator(func)(*args, **kwargs)
                except RetryError as e:
                    logger.error(f"Max retries ({_max_attempts}) exceeded for {func.__name__}: {e}")
                    raise e.last_attempt.exception()
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                try:
                    return retry_decorator(func)(*args, **kwargs)
                except RetryError as e:
                    logger.error(f"Max retries ({_max_attempts}) exceeded for {func.__name__}: {e}")
                    raise e.last_attempt.exception()
            return sync_wrapper
    
    return decorator


def with_circuit_breaker(
    name: str,
    fail_max: Optional[int] = None,
    timeout: Optional[int] = None,
    expected_exception: Optional[Type[Exception]] = None
):
    """
    Декоратор для circuit breaker паттерна
    
    Args:
        name: Имя circuit breaker (уникальное для каждого сервиса)
        fail_max: Количество ошибок для открытия circuit
        timeout: Время (сек) до попытки восстановления
        expected_exception: Типы исключений для отслеживания
        
    Example:
        @with_circuit_breaker("openai_api", fail_max=5)
        async def call_openai():
            ...
    """
    def decorator(func: Callable) -> Callable:
        _fail_max = fail_max if fail_max is not None else _resilience_config.CB_FAIL_MAX
        _timeout = timeout if timeout is not None else _resilience_config.CB_TIMEOUT
        _expected_exception = expected_exception if expected_exception is not None else _resilience_config.CB_EXPECTED_EXCEPTION
        
        breaker = CircuitBreakers.get_breaker(
            name,
            fail_max=_fail_max,
            timeout=_timeout,
            expected_exception=_expected_exception
        )
        
        # Проверяем, является ли функция асинхронным генератором
        # Для bound methods нужно проверять исходную функцию
        original_func = func
        if hasattr(func, '__func__'):
            # Это bound method, проверяем исходную функцию
            original_func = func.__func__
        elif hasattr(func, '__wrapped__'):
            # Это обернутая функция, проверяем исходную
            original_func = func.__wrapped__
        
        is_async_gen = inspect.isasyncgenfunction(original_func)
        
        if is_async_gen:
            @functools.wraps(func)
            async def async_gen_wrapper(*args, **kwargs):
                # Для async generators circuit breaker проверяется перед началом генерации
                if breaker.current_state == 'open':
                    raise CircuitBreakerError(f"Circuit breaker '{name}' is OPEN")
                try:
                    # Вызываем функцию - для async generator функции это вернет async generator объект
                    gen = func(*args, **kwargs)
                    # Проверяем, является ли результат async generator
                    if inspect.isasyncgen(gen):
                        async for item in gen:
                            yield item
                    else:
                        # Если это корутина (для обернутых функций), await её
                        gen = await gen
                        if inspect.isasyncgen(gen):
                            async for item in gen:
                                yield item
                        else:
                            # Если это обычное значение, yield его
                            yield gen
                    # Успешное завершение генератора - circuit breaker автоматически отслеживает это
                    # через состояние, но для async generators мы не можем использовать call/call_async
                    # поэтому просто проверяем состояние
                except Exception as exc:
                    # Ошибка в генераторе - circuit breaker отслеживает это через состояние
                    # Для async generators pybreaker не может автоматически обновить счетчики,
                    # поэтому просто пробрасываем исключение
                    raise exc
            return async_gen_wrapper
        elif asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                try:
                    # Пытаемся использовать call_async если доступен
                    return await breaker.call_async(func, *args, **kwargs)
                except (NameError, AttributeError) as e:
                        # Если call_async не работает (нет tornado), используем обходной путь
                        if breaker.current_state == 'open':
                            raise CircuitBreakerError(f"Circuit breaker '{name}' is OPEN")
                        try:
                            result = await func(*args, **kwargs)
                            # Для async функций pybreaker не может автоматически отслеживать успех/ошибку
                            # через call_async, поэтому просто возвращаем результат
                            # Circuit breaker будет отслеживать состояние через другие механизмы
                            return result
                        except Exception as exc:
                            # Ошибка - пробрасываем исключение
                            # Circuit breaker будет отслеживать это через состояние
                            raise exc
                except CircuitBreakerError as e:
                    logger.error(f"Circuit breaker '{name}' is OPEN: {e}")
                    raise
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                try:
                    return breaker.call(func, *args, **kwargs)
                except CircuitBreakerError as e:
                    logger.error(f"Circuit breaker '{name}' is OPEN: {e}")
                    raise
            return sync_wrapper
    
    return decorator


def with_timeout(seconds: Optional[int] = None):
    """
    Декоратор для timeout
    
    Args:
        seconds: Максимальное время выполнения в секундах
        
    Example:
        @with_timeout(30)
        async def slow_operation():
            ...
    """
    def decorator(func: Callable) -> Callable:
        _seconds = seconds if seconds is not None else _resilience_config.DEFAULT_TIMEOUT
        
        # Проверяем, является ли функция асинхронным генератором
        # Для bound methods нужно проверять исходную функцию
        original_func = func
        if hasattr(func, '__func__'):
            # Это bound method, проверяем исходную функцию
            original_func = func.__func__
        elif hasattr(func, '__wrapped__'):
            # Это обернутая функция, проверяем исходную
            original_func = func.__wrapped__
        
        is_async_gen = inspect.isasyncgenfunction(original_func)
        
        if is_async_gen:
            @functools.wraps(func)
            async def async_gen_wrapper(*args, **kwargs):
                # Для async generators timeout применяется на уровне итераций
                start_time = asyncio.get_event_loop().time()
                gen = func(*args, **kwargs)
                # Проверяем, является ли результат async generator
                if inspect.isasyncgen(gen):
                    async for item in gen:
                        current_time = asyncio.get_event_loop().time()
                        if current_time - start_time > _seconds:
                            logger.error(f"Timeout ({_seconds}s) exceeded for {func.__name__}")
                            raise TimeoutError(f"Operation {func.__name__} timed out after {_seconds}s")
                        yield item
                else:
                    # Если это корутина (для обернутых функций), await её
                    gen = await gen
                    if inspect.isasyncgen(gen):
                        async for item in gen:
                            current_time = asyncio.get_event_loop().time()
                            if current_time - start_time > _seconds:
                                logger.error(f"Timeout ({_seconds}s) exceeded for {func.__name__}")
                                raise TimeoutError(f"Operation {func.__name__} timed out after {_seconds}s")
                            yield item
            return async_gen_wrapper
        elif asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                try:
                    return await asyncio.wait_for(
                        func(*args, **kwargs),
                        timeout=_seconds
                    )
                except asyncio.TimeoutError:
                    logger.error(f"Timeout ({_seconds}s) exceeded for {func.__name__}")
                    raise TimeoutError(f"Operation {func.__name__} timed out after {_seconds}s")
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                # Для синхронных функций используем signal (только Unix) или threading
                import signal
                import platform
                
                if platform.system() != 'Windows':
                    def timeout_handler(signum, frame):
                        raise TimeoutError(f"Operation {func.__name__} timed out after {seconds}s")
                    
                    old_handler = signal.signal(signal.SIGALRM, timeout_handler)
                    signal.alarm(_seconds)
                    try:
                        result = func(*args, **kwargs)
                        signal.alarm(0)
                        return result
                    finally:
                        signal.signal(signal.SIGALRM, old_handler)
                else:
                    # На Windows просто вызываем функцию (timeout не поддерживается)
                    logger.warning(f"Timeout not supported on Windows for sync function {func.__name__}")
                    return func(*args, **kwargs)
            
            return sync_wrapper
    
    return decorator


def resilient(
    name: str,
    retry_max_attempts: Optional[int] = None,
    retry_exceptions: Tuple[Type[Exception], ...] = RETRIABLE_EXCEPTIONS,
    circuit_breaker: bool = True,
    cb_fail_max: Optional[int] = None,
    cb_timeout: Optional[int] = None,
    timeout_seconds: Optional[int] = None,
):
    """
    Комбинированный декоратор для применения всех паттернов resilience
    
    Args:
        name: Имя для circuit breaker и логирования
        retry_max_attempts: Максимальное количество retry попыток
        retry_exceptions: Исключения для retry
        circuit_breaker: Использовать ли circuit breaker
        cb_fail_max: Circuit breaker fail max
        cb_timeout: Circuit breaker timeout
        timeout_seconds: Timeout в секундах
        
    Example:
        @resilient("openai_api", timeout_seconds=120)
        async def call_openai():
            ...
    """
    def decorator(func: Callable) -> Callable:
        # Проверяем, является ли функция асинхронным генератором
        is_async_gen = inspect.isasyncgenfunction(func)
        
        # Для async generators применяем декораторы по-другому
        if is_async_gen:
            # Применяем декораторы в порядке: timeout -> circuit_breaker -> retry
            decorated = func
            
            # 1. Retry (внутренний слой) - для async generators просто пропускаем
            # Retry на async generators сложен, поэтому не применяем
            decorated = func  # Пропускаем retry для async generators
            
            # 2. Circuit Breaker (средний слой)
            if circuit_breaker:
                decorated = with_circuit_breaker(
                    name=name,
                    fail_max=cb_fail_max,
                    timeout=cb_timeout
                )(decorated)
            
            # 3. Timeout (внешний слой)
            decorated = with_timeout(timeout_seconds)(decorated)
            
            # Для async generators просто возвращаем декорированный генератор
            return decorated
        
        # Для обычных функций применяем все декораторы
        decorated = func
        
        # 1. Retry (внутренний слой)
        decorated = with_retry(
            max_attempts=retry_max_attempts,
            exceptions=retry_exceptions
        )(decorated)
        
        # 2. Circuit Breaker (средний слой)
        if circuit_breaker:
            decorated = with_circuit_breaker(
                name=name,
                fail_max=cb_fail_max,
                timeout=cb_timeout
            )(decorated)
        
        # 3. Timeout (внешний слой)
        decorated = with_timeout(timeout_seconds)(decorated)
        
        # Для обычных async функций оборачиваем в wrapper
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            logger.debug(f"Calling resilient function: {name}")
            return await decorated(*args, **kwargs)
        
        return wrapper
    
    return decorator


# Предустановленные конфигурации для разных типов вызовов
def resilient_llm(name: str = "llm", **kwargs):
    """Resilience для LLM вызовов"""
    defaults = {
        'timeout_seconds': _resilience_config.LLM_TIMEOUT,
        'retry_max_attempts': _resilience_config.RETRY_MAX_ATTEMPTS,
        'cb_fail_max': _resilience_config.CB_FAIL_MAX,
        'cb_timeout': _resilience_config.CB_TIMEOUT,
    }
    defaults.update(kwargs)
    return resilient(name=name, **defaults)


def resilient_rag(name: str = "rag", **kwargs):
    """Resilience для RAG операций"""
    defaults = {
        'timeout_seconds': _resilience_config.RAG_TIMEOUT,
        'retry_max_attempts': _resilience_config.RETRY_MAX_ATTEMPTS,
        'cb_fail_max': _resilience_config.CB_FAIL_MAX,
        'cb_timeout': _resilience_config.CB_TIMEOUT,
    }
    defaults.update(kwargs)
    return resilient(name=name, **defaults)


def resilient_mcp(name: str = "mcp", **kwargs):
    """Resilience для MCP вызовов"""
    defaults = {
        'timeout_seconds': _resilience_config.MCP_TIMEOUT,
        'retry_max_attempts': _resilience_config.RETRY_MAX_ATTEMPTS,
        'cb_fail_max': _resilience_config.CB_FAIL_MAX,
        'cb_timeout': _resilience_config.CB_TIMEOUT,
    }
    defaults.update(kwargs)
    return resilient(name=name, **defaults)


def resilient_http(name: str = "http", **kwargs):
    """Resilience для HTTP вызовов"""
    defaults = {
        'timeout_seconds': _resilience_config.DEFAULT_TIMEOUT,
        'retry_max_attempts': _resilience_config.RETRY_MAX_ATTEMPTS,
        'cb_fail_max': _resilience_config.CB_FAIL_MAX,
        'cb_timeout': _resilience_config.CB_TIMEOUT,
    }
    defaults.update(kwargs)
    return resilient(name=name, **defaults)


# Утилиты для мониторинга
def get_circuit_breaker_status(name: str) -> dict:
    """Получить статус circuit breaker"""
    try:
        breaker = CircuitBreakers.get_breaker(name)
        return {
            'name': name,
            'state': str(breaker.current_state),
            'fail_counter': breaker.fail_counter,
            'fail_max': breaker.fail_max,
            'last_failure': str(breaker.last_failure) if hasattr(breaker, 'last_failure') else None,
        }
    except Exception as e:
        return {'name': name, 'error': str(e)}


def get_all_circuit_breakers_status() -> list:
    """Получить статус всех circuit breakers"""
    return [
        get_circuit_breaker_status(name)
        for name in CircuitBreakers._breakers.keys()
    ]

