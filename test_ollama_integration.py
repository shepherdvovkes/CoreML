#!/usr/bin/env python3
"""
Тест интеграции Ollama с проектом через CustomProvider
"""
import asyncio
from core.llm.custom_provider import CustomProvider
from core.llm.base import LLMMessage
from config import settings


async def test_ollama_via_custom_provider():
    """Тест использования Ollama через CustomProvider"""
    print("=" * 60)
    print("Тест интеграции Ollama с проектом")
    print("=" * 60)
    
    # Ollama использует OpenAI-совместимый API на порту 11434
    # Но endpoint немного отличается: /api/generate вместо /chat/completions
    # Для совместимости можно использовать /v1/chat/completions если Ollama поддерживает
    
    # Проверяем через CustomProvider с базовым URL Ollama
    ollama_url = "http://localhost:11434/v1"  # Попробуем с /v1
    
    print(f"\n🔍 Тестирую Ollama через CustomProvider...")
    print(f"   URL: {ollama_url}")
    
    try:
        provider = CustomProvider(
            base_url=ollama_url,
            api_key="ollama",  # Ollama не требует реальный ключ
            model="gpt-oss:120b-cloud"  # Модель из проверки
        )
        
        messages = [
            LLMMessage(role="system", content="You are a helpful assistant."),
            LLMMessage(role="user", content="Say 'Hello from Ollama!' in one sentence.")
        ]
        
        print(f"\n💬 Отправляю запрос...")
        response = await provider.generate(messages, temperature=0.7)
        
        print(f"✅ Успешно!")
        print(f"   Ответ: {response.content}")
        print(f"   Модель: {response.model}")
        
        await provider.close()
        return True
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        print(f"\n💡 Ollama использует другой API формат.")
        print(f"   Нужно создать отдельный OllamaProvider или использовать прямой API.")
        return False


async def test_ollama_direct_api():
    """Прямой тест Ollama API"""
    import httpx
    import json
    
    print(f"\n🔍 Тестирую прямой Ollama API...")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Ollama использует /api/generate, не /chat/completions
            response = await client.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": "gpt-oss:120b-cloud",
                    "prompt": "Say 'Hello from Ollama!' in one sentence.",
                    "stream": False
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Прямой API работает!")
                print(f"   Ответ: {data.get('response', '')}")
                print(f"   Токенов: {data.get('eval_count', 0)}")
                return True
            else:
                print(f"❌ Ошибка: {response.status_code}")
                print(f"   {response.text[:200]}")
                return False
                
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False


async def main():
    """Основная функция"""
    # Сначала тест прямого API
    direct_ok = await test_ollama_direct_api()
    
    # Затем тест через CustomProvider
    if direct_ok:
        await test_ollama_via_custom_provider()
    
    print("\n" + "=" * 60)
    print("💡 Рекомендации:")
    print("=" * 60)
    print("1. Ollama работает на http://localhost:11434")
    print("2. API формат отличается от OpenAI:")
    print("   - Ollama: /api/generate")
    print("   - OpenAI: /v1/chat/completions")
    print("3. Для интеграции можно:")
    print("   a) Создать OllamaProvider (рекомендуется)")
    print("   b) Использовать CustomProvider с адаптацией")
    print("   c) Настроить Ollama proxy для OpenAI-совместимого API")


if __name__ == "__main__":
    asyncio.run(main())

