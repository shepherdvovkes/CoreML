#!/usr/bin/env python3
"""
Детальный список доступных моделей в Ollama
"""
import asyncio
import httpx
import json
from datetime import datetime


async def list_ollama_models(base_url: str = "http://localhost:11434"):
    """Получить детальный список моделей Ollama"""
    print("=" * 70)
    print("Доступные модели в Ollama сервере")
    print("=" * 70)
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{base_url}/api/tags")
            
            if response.status_code == 200:
                data = response.json()
                models = data.get("models", [])
                
                if not models:
                    print("❌ Модели не найдены")
                    print("\n💡 Установите модель:")
                    print("   ollama pull llama2")
                    return
                
                print(f"\n📊 Всего моделей: {len(models)}\n")
                
                for idx, model in enumerate(models, 1):
                    name = model.get("name", "unknown")
                    size = model.get("size", 0)
                    digest = model.get("digest", "")[:12]
                    modified = model.get("modified_at", "")
                    
                    # Форматируем размер
                    if size > 0:
                        if size >= 1024**3:
                            size_str = f"{size / (1024**3):.2f} GB"
                        elif size >= 1024**2:
                            size_str = f"{size / (1024**2):.2f} MB"
                        else:
                            size_str = f"{size / 1024:.2f} KB"
                    else:
                        size_str = "unknown"
                    
                    # Форматируем дату
                    if modified:
                        try:
                            dt = datetime.fromisoformat(modified.replace('Z', '+00:00'))
                            date_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                        except:
                            date_str = modified
                    else:
                        date_str = "unknown"
                    
                    print(f"{idx}. {name}")
                    print(f"   Размер: {size_str}")
                    print(f"   Digest: {digest}...")
                    print(f"   Обновлено: {date_str}")
                    print()
                
                # Показываем детали первой модели
                if models:
                    first_model = models[0]
                    model_name = first_model.get("name", "")
                    print("=" * 70)
                    print(f"Детали модели: {model_name}")
                    print("=" * 70)
                    print(json.dumps(first_model, indent=2, ensure_ascii=False))
                
            else:
                print(f"❌ Ошибка: {response.status_code}")
                print(response.text)
                
    except httpx.ConnectError:
        print("❌ Не удалось подключиться к Ollama серверу")
        print("   Убедитесь, что сервер запущен: ollama serve")
    except Exception as e:
        print(f"❌ Ошибка: {e}")


async def show_model_info(base_url: str = "http://localhost:11434", model_name: str = None):
    """Показать информацию о конкретной модели"""
    if not model_name:
        return
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Пробуем получить информацию о модели через show
            response = await client.post(
                f"{base_url}/api/show",
                json={"name": model_name}
            )
            
            if response.status_code == 200:
                data = response.json()
                print("\n" + "=" * 70)
                print(f"Детальная информация о модели: {model_name}")
                print("=" * 70)
                print(json.dumps(data, indent=2, ensure_ascii=False))
            else:
                print(f"⚠️  Не удалось получить детали модели: {response.status_code}")
                
    except Exception as e:
        print(f"⚠️  Ошибка при получении деталей: {e}")


async def main():
    """Основная функция"""
    await list_ollama_models()
    
    # Можно показать детали первой модели
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get("http://localhost:11434/api/tags")
            if response.status_code == 200:
                data = response.json()
                models = data.get("models", [])
                if models:
                    first_model = models[0].get("name", "")
                    await show_model_info(model_name=first_model)
    except:
        pass


if __name__ == "__main__":
    asyncio.run(main())

