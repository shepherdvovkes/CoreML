"""
Пример использования resilience паттернов
"""
import asyncio
from loguru import logger
from core.resilience import (
    with_retry,
    with_circuit_breaker,
    with_timeout,
    resilient,
    resilient_llm,
    resilient_http,
    get_circuit_breaker_status,
    get_all_circuit_breakers_status,
    CircuitBreakers
)


# Пример 1: Простой retry
@with_retry(max_attempts=5, min_wait=1, max_wait=10)
async def fetch_with_retry():
    """Функция с автоматическим retry"""
    logger.info("Attempting to fetch data...")
    # Имитация API вызова
    import random
    if random.random() < 0.7:  # 70% шанс ошибки
        raise ConnectionError("Network error")
    return {"status": "success"}


# Пример 2: Circuit breaker
@with_circuit_breaker(name="external_api", fail_max=3, timeout=30)
async def call_external_api():
    """Вызов с circuit breaker защитой"""
    logger.info("Calling external API...")
    import random
    if random.random() < 0.5:
        raise Exception("API error")
    return {"data": "response"}


# Пример 3: Timeout
@with_timeout(seconds=5)
async def slow_operation():
    """Операция с ограничением по времени"""
    logger.info("Starting slow operation...")
    await asyncio.sleep(2)  # Имитация медленной операции
    return "completed"


# Пример 4: Комбинированный resilient декоратор
@resilient(
    name="robust_service",
    retry_max_attempts=3,
    circuit_breaker=True,
    cb_fail_max=5,
    timeout_seconds=30
)
async def robust_service_call():
    """Вызов с полной защитой"""
    logger.info("Calling robust service...")
    return {"status": "ok"}


# Пример 5: Использование предустановленных конфигураций
@resilient_llm(name="my_llm_call")
async def call_llm():
    """LLM вызов с автоматической resilience"""
    logger.info("Calling LLM...")
    await asyncio.sleep(1)
    return "LLM response"


@resilient_http(name="my_http_call")
async def make_http_request():
    """HTTP запрос с автоматической resilience"""
    logger.info("Making HTTP request...")
    return {"data": "response"}


# Пример 6: Обработка ошибок
async def example_error_handling():
    """Пример обработки ошибок"""
    from pybreaker import CircuitBreakerError
    
    try:
        result = await call_external_api()
        logger.success(f"Success: {result}")
    except CircuitBreakerError:
        logger.warning("Circuit breaker is OPEN - service unavailable")
        # Возвращаем fallback значение
        return {"data": "cached_response"}
    except TimeoutError:
        logger.error("Request timed out")
        return None
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return None


# Пример 7: Мониторинг circuit breakers
async def monitor_circuit_breakers():
    """Проверка статуса circuit breakers"""
    
    # Статус одного breaker
    status = get_circuit_breaker_status("external_api")
    logger.info(f"Circuit breaker status: {status}")
    
    # Статус всех breakers
    all_status = get_all_circuit_breakers_status()
    logger.info("All circuit breakers:")
    for cb_status in all_status:
        logger.info(f"  {cb_status['name']}: {cb_status['state']} "
                   f"(failures: {cb_status['fail_counter']}/{cb_status['fail_max']})")


# Пример 8: Кастомная конфигурация для специфичной операции
@resilient(
    name="heavy_computation",
    retry_max_attempts=2,  # Мало retry для тяжелых операций
    circuit_breaker=True,
    cb_fail_max=3,
    timeout_seconds=300  # 5 минут для тяжелой обработки
)
async def heavy_computation():
    """Тяжелая операция с специальными настройками"""
    logger.info("Starting heavy computation...")
    await asyncio.sleep(2)
    return "computation result"


# Главная функция для демонстрации
async def main():
    """Демонстрация всех примеров"""
    
    logger.info("=== Resilience Patterns Examples ===\n")
    
    # 1. Retry example
    logger.info("1. Testing Retry Pattern:")
    try:
        for i in range(3):
            result = await fetch_with_retry()
            logger.success(f"  Attempt {i+1} succeeded: {result}")
            break
    except Exception as e:
        logger.error(f"  All retries failed: {e}")
    
    await asyncio.sleep(1)
    
    # 2. Circuit breaker example
    logger.info("\n2. Testing Circuit Breaker Pattern:")
    for i in range(5):
        try:
            result = await call_external_api()
            logger.success(f"  Call {i+1} succeeded: {result}")
        except Exception as e:
            logger.warning(f"  Call {i+1} failed: {type(e).__name__}")
    
    await asyncio.sleep(1)
    
    # 3. Timeout example
    logger.info("\n3. Testing Timeout Pattern:")
    try:
        result = await slow_operation()
        logger.success(f"  Operation completed: {result}")
    except TimeoutError:
        logger.error("  Operation timed out")
    
    await asyncio.sleep(1)
    
    # 4. Combined resilient example
    logger.info("\n4. Testing Combined Resilient Decorator:")
    try:
        result = await robust_service_call()
        logger.success(f"  Robust call succeeded: {result}")
    except Exception as e:
        logger.error(f"  Robust call failed: {e}")
    
    await asyncio.sleep(1)
    
    # 5. LLM call example
    logger.info("\n5. Testing LLM Call with Resilience:")
    try:
        result = await call_llm()
        logger.success(f"  LLM call succeeded: {result}")
    except Exception as e:
        logger.error(f"  LLM call failed: {e}")
    
    await asyncio.sleep(1)
    
    # 6. Error handling example
    logger.info("\n6. Testing Error Handling:")
    result = await example_error_handling()
    logger.info(f"  Result with error handling: {result}")
    
    await asyncio.sleep(1)
    
    # 7. Monitor circuit breakers
    logger.info("\n7. Circuit Breaker Monitoring:")
    await monitor_circuit_breakers()
    
    await asyncio.sleep(1)
    
    # 8. Heavy computation example
    logger.info("\n8. Testing Heavy Computation:")
    try:
        result = await heavy_computation()
        logger.success(f"  Heavy computation completed: {result}")
    except Exception as e:
        logger.error(f"  Heavy computation failed: {e}")
    
    # Reset circuit breakers for clean state
    logger.info("\n9. Resetting all circuit breakers...")
    CircuitBreakers.reset_all()
    logger.success("  All circuit breakers reset")
    
    logger.info("\n=== Examples Complete ===")


if __name__ == "__main__":
    # Настройка логирования
    logger.remove()
    logger.add(
        lambda msg: print(msg, end=""),
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
        level="INFO"
    )
    
    # Запуск примеров
    asyncio.run(main())

