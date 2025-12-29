#!/usr/bin/env python3
"""
Скрипт для проверки валидности OpenAI API ключа
Использует официальный API согласно документации OpenAI
"""
import asyncio
import httpx
import os
from config import settings


async def check_openai_key():
    """Проверка валидности OpenAI API ключа"""
    api_key = settings.openai_api_key or os.getenv("OPENAI_API_KEY", "")
    
    if not api_key:
        print("❌ OpenAI API ключ не найден!")
        print("   Добавьте в .env файл: OPENAI_API_KEY=sk-...")
        return False
    
    if not api_key.startswith("sk-"):
        print(f"❌ Неверный формат ключа. Ключ должен начинаться с 'sk-'")
        print(f"   Текущий ключ начинается с: {api_key[:5]}...")
        return False
    
    if len(api_key) < 20:
        print(f"❌ Ключ слишком короткий (длина: {len(api_key)})")
        return False
    
    print(f"✓ Формат ключа корректен (длина: {len(api_key)})")
    print(f"  Первые символы: {api_key[:7]}...")
    
    # Проверяем ключ через API согласно документации OpenAI
    # Используем endpoint /models для проверки (не требует много токенов)
    base_url = settings.openai_base_url or "https://api.openai.com/v1"
    
    print(f"\n🔍 Проверяю ключ через OpenAI API ({base_url})...")
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Сначала проверяем доступность моделей (легкий запрос)
            response = await client.get(
                f"{base_url}/models",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
            )
            
            if response.status_code == 200:
                models = response.json()
                print(f"✅ Ключ валиден!")
                print(f"   Доступно моделей: {len(models.get('data', []))}")
                print(f"   Примеры моделей:")
                for model in models.get('data', [])[:5]:
                    print(f"     - {model.get('id', 'unknown')}")
                return True
            elif response.status_code == 401:
                print(f"❌ Ключ невалиден (401 Unauthorized)")
                print(f"   Проверьте правильность ключа в .env файле")
                print(f"   Получите новый ключ: https://platform.openai.com/api-keys")
                return False
            elif response.status_code == 429:
                print(f"⚠️  Rate limit превышен (429)")
                print(f"   Попробуйте позже")
                return False
            else:
                print(f"⚠️  Неожиданный статус: {response.status_code}")
                print(f"   Ответ: {response.text[:200]}")
                return False
                
    except httpx.TimeoutException:
        print(f"❌ Таймаут при подключении к API")
        return False
    except httpx.ConnectError as e:
        print(f"❌ Ошибка подключения: {e}")
        return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False


async def test_simple_chat():
    """Простой тест чата для проверки ключа"""
    api_key = settings.openai_api_key or os.getenv("OPENAI_API_KEY", "")
    
    if not api_key:
        return False
    
    base_url = settings.openai_base_url or "https://api.openai.com/v1"
    
    print(f"\n💬 Тестирую простой запрос к chat/completions...")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-3.5-turbo",
                    "messages": [
                        {"role": "user", "content": "Say 'OK' if you can read this."}
                    ],
                    "max_tokens": 10
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                usage = data.get("usage", {})
                print(f"✅ Тест успешен!")
                print(f"   Ответ: {content.strip()}")
                print(f"   Использовано токенов: {usage.get('total_tokens', 'unknown')}")
                return True
            else:
                print(f"❌ Ошибка: {response.status_code}")
                print(f"   {response.text[:200]}")
                return False
                
    except Exception as e:
        print(f"❌ Ошибка при тестировании: {e}")
        return False


async def main():
    """Основная функция"""
    print("=" * 60)
    print("Проверка OpenAI API ключа")
    print("=" * 60)
    
    # Проверка формата
    key_valid = await check_openai_key()
    
    if key_valid:
        # Если ключ валиден, делаем простой тест чата
        await test_simple_chat()
    
    print("\n" + "=" * 60)
    if key_valid:
        print("✅ Ключ готов к использованию!")
    else:
        print("❌ Ключ требует исправления")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

