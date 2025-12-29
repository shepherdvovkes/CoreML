#!/usr/bin/env python3
"""
Скрипт для проверки подключения к Ollama серверу на localhost
Проверяет доступность API и список доступных моделей
"""
import asyncio
import httpx
import json
from typing import Optional


async def check_ollama_server(base_url: str = "http://localhost:11434", timeout: float = 5.0) -> bool:
    """Проверка доступности Ollama сервера"""
    print(f"🔍 Проверяю Ollama сервер на {base_url}...")
    
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            # Проверяем базовый endpoint
            response = await client.get(f"{base_url}/api/tags")
            
            if response.status_code == 200:
                data = response.json()
                models = data.get("models", [])
                print(f"✅ Ollama сервер доступен!")
                print(f"   Доступно моделей: {len(models)}")
                
                if models:
                    print(f"\n📋 Список доступных моделей:")
                    for model in models[:10]:  # Показываем первые 10
                        name = model.get("name", "unknown")
                        size = model.get("size", 0)
                        size_gb = size / (1024**3) if size > 0 else 0
                        modified = model.get("modified_at", "")
                        print(f"   • {name}")
                        if size_gb > 0:
                            print(f"     Размер: {size_gb:.2f} GB")
                        if modified:
                            print(f"     Обновлено: {modified}")
                else:
                    print(f"   ⚠️  Модели не найдены. Установите модель:")
                    print(f"      ollama pull llama2")
                
                return True
            else:
                print(f"❌ Неожиданный статус: {response.status_code}")
                print(f"   Ответ: {response.text[:200]}")
                return False
                
    except httpx.TimeoutException:
        print(f"❌ Таймаут при подключении к {base_url}")
        print(f"   Убедитесь, что Ollama сервер запущен:")
        print(f"   ollama serve")
        return False
    except httpx.ConnectError:
        print(f"❌ Не удалось подключиться к {base_url}")
        print(f"   Убедитесь, что Ollama сервер запущен:")
        print(f"   ollama serve")
        return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False


async def test_ollama_generate(base_url: str = "http://localhost:11434", model: str = "llama2", timeout: float = 30.0) -> bool:
    """Тест генерации через Ollama API"""
    print(f"\n💬 Тестирую генерацию через модель '{model}'...")
    
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{base_url}/api/generate",
                json={
                    "model": model,
                    "prompt": "Say 'OK' if you can read this.",
                    "stream": False
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                response_text = data.get("response", "")
                print(f"✅ Генерация успешна!")
                print(f"   Ответ: {response_text.strip()}")
                
                # Показываем статистику
                if "eval_count" in data:
                    print(f"   Токенов сгенерировано: {data.get('eval_count', 0)}")
                if "total_duration" in data:
                    duration = data.get("total_duration", 0) / 1e9  # наносекунды в секунды
                    print(f"   Время генерации: {duration:.2f} сек")
                
                return True
            elif response.status_code == 404:
                print(f"❌ Модель '{model}' не найдена")
                print(f"   Установите модель:")
                print(f"   ollama pull {model}")
                return False
            else:
                print(f"❌ Ошибка: {response.status_code}")
                print(f"   {response.text[:200]}")
                return False
                
    except httpx.TimeoutException:
        print(f"❌ Таймаут при генерации (>{timeout} сек)")
        print(f"   Модель может быть слишком медленной или большой")
        return False
    except Exception as e:
        print(f"❌ Ошибка при тестировании: {e}")
        return False


async def test_ollama_stream(base_url: str = "http://localhost:11434", model: str = "llama2", timeout: float = 30.0) -> bool:
    """Тест потоковой генерации через Ollama API"""
    print(f"\n🌊 Тестирую потоковую генерацию через модель '{model}'...")
    
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST",
                f"{base_url}/api/generate",
                json={
                    "model": model,
                    "prompt": "Count from 1 to 5.",
                    "stream": True
                }
            ) as response:
                if response.status_code == 200:
                    chunks = []
                    async for line in response.aiter_lines():
                        if line:
                            try:
                                data = json.loads(line)
                                if "response" in data:
                                    chunk = data["response"]
                                    chunks.append(chunk)
                                    print(chunk, end="", flush=True)
                                if data.get("done", False):
                                    break
                            except json.JSONDecodeError:
                                continue
                    
                    print()  # Новая строка после вывода
                    print(f"✅ Потоковая генерация успешна!")
                    print(f"   Получено чанков: {len(chunks)}")
                    return True
                else:
                    error_text = await response.aread()
                    print(f"❌ Ошибка: {response.status_code}")
                    print(f"   {error_text.decode()[:200]}")
                    return False
                    
    except httpx.TimeoutException:
        print(f"❌ Таймаут при потоковой генерации")
        return False
    except Exception as e:
        print(f"❌ Ошибка при тестировании: {e}")
        return False


async def check_ollama_health(base_url: str = "http://localhost:11434") -> bool:
    """Проверка здоровья сервера (если доступен endpoint)"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Пробуем разные возможные endpoints
            endpoints = ["/", "/api/version", "/api/tags"]
            
            for endpoint in endpoints:
                try:
                    response = await client.get(f"{base_url}{endpoint}")
                    if response.status_code == 200:
                        print(f"✅ Health check успешен ({endpoint})")
                        return True
                except:
                    continue
            
            return False
    except:
        return False


async def main():
    """Основная функция"""
    print("=" * 60)
    print("Проверка Ollama сервера на localhost")
    print("=" * 60)
    
    base_url = "http://localhost:11434"
    
    # Проверка доступности сервера
    server_available = await check_ollama_server(base_url)
    
    if not server_available:
        print(f"\n💡 Как запустить Ollama:")
        print(f"   1. Установите Ollama: https://ollama.ai")
        print(f"   2. Запустите сервер: ollama serve")
        print(f"   3. Или просто: ollama (запускает сервер автоматически)")
        print(f"\n💡 Альтернативные порты:")
        print(f"   Если Ollama на другом порту, укажите:")
        print(f"   OLLAMA_BASE_URL=http://localhost:PORT")
        return
    
    # Проверка здоровья
    await check_ollama_health(base_url)
    
    # Получаем список моделей для теста
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{base_url}/api/tags")
            if response.status_code == 200:
                data = response.json()
                models = data.get("models", [])
                if models:
                    # Берем первую доступную модель
                    test_model = models[0].get("name", "llama2")
                    print(f"\n🧪 Используем модель '{test_model}' для тестов...")
                    
                    # Тест обычной генерации
                    await test_ollama_generate(base_url, test_model)
                    
                    # Тест потоковой генерации (опционально, может быть медленным)
                    # await test_ollama_stream(base_url, test_model)
    
    except Exception as e:
        print(f"⚠️  Не удалось получить список моделей: {e}")
    
    print("\n" + "=" * 60)
    print("✅ Проверка завершена!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

