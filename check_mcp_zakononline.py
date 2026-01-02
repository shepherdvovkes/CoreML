#!/usr/bin/env python3
"""
Скрипт для проверки доступа к MCP ZakonOnline
"""
import asyncio
import sys
from loguru import logger
from core.mcp.law_client import LawMCPClient
from config import settings

# Настройка логирования
logger.remove()
logger.add(sys.stderr, level="INFO", format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>")


async def test_mcp_connection():
    """Тест подключения к MCP серверу"""
    print("\n" + "="*60)
    print("🔍 Проверка доступа к MCP ZakonOnline")
    print("="*60)
    
    # Проверка конфигурации
    print(f"\n📋 Конфигурация:")
    print(f"   MCP Law Server URL: {settings.mcp_law_server_url}")
    print(f"   Timeout: 30.0 секунд")
    
    # Создание клиента
    print(f"\n🔌 Создание клиента...")
    try:
        client = LawMCPClient()
        print(f"   ✅ Клиент создан успешно")
        print(f"   Base URL: {client.base_url}")
    except Exception as e:
        print(f"   ❌ Ошибка создания клиента: {e}")
        return False
    
    # Тест 1: Поиск дел
    print(f"\n📚 Тест 1: Поиск судебных дел")
    print(f"   Запрос: 'договір'")
    try:
        cases = await client.search_cases("договір", instance="3", limit=5)
        if cases:
            print(f"   ✅ Найдено дел: {len(cases)}")
            for i, case in enumerate(cases[:3], 1):
                title = case.get('title', 'Без названия')
                case_number = case.get('case_number', 'N/A')
                print(f"      {i}. {title[:60]}... (№{case_number})")
        else:
            print(f"   ⚠️  Дела не найдены (пустой результат)")
    except Exception as e:
        print(f"   ❌ Ошибка поиска дел: {e}")
        logger.exception("Search cases error")
        return False
    
    # Тест 2: Получение деталей дела (если есть результаты)
    if cases and len(cases) > 0:
        print(f"\n📄 Тест 2: Получение деталей дела")
        first_case = cases[0]
        case_number = first_case.get('case_number')
        doc_id = first_case.get('doc_id') or first_case.get('id')
        
        if case_number:
            print(f"   Номер дела: {case_number}")
            try:
                details = await client.get_case_details(case_number=case_number)
                if details:
                    print(f"   ✅ Детали получены успешно")
                    print(f"      Ключи в ответе: {list(details.keys())[:10]}")
                else:
                    print(f"   ⚠️  Детали не получены (None)")
            except Exception as e:
                print(f"   ❌ Ошибка получения деталей: {e}")
                logger.exception("Get case details error")
        
        if doc_id:
            print(f"\n   Тест по doc_id: {doc_id}")
            try:
                details = await client.get_case_details(doc_id=str(doc_id))
                if details:
                    print(f"   ✅ Детали по doc_id получены успешно")
                else:
                    print(f"   ⚠️  Детали по doc_id не получены (None)")
            except Exception as e:
                print(f"   ⚠️  Ошибка получения деталей по doc_id: {e}")
    
    # Тест 3: Поиск с разными инстанциями
    print(f"\n⚖️  Тест 3: Поиск с разными инстанциями")
    instances = ["1", "2", "3", "4"]
    for instance in instances:
        try:
            cases = await client.search_cases("права", instance=instance, limit=2)
            print(f"   Инстанция {instance}: {'✅' if cases else '⚠️ '} {'Найдено' if cases else 'Не найдено'} ({len(cases) if cases else 0} дел)")
        except Exception as e:
            print(f"   Инстанция {instance}: ❌ Ошибка - {e}")
    
    # Тест 4: Обработка ошибок
    print(f"\n🛡️  Тест 4: Обработка ошибок")
    try:
        # Пустой запрос
        cases = await client.search_cases("", limit=1)
        print(f"   Пустой запрос: {'✅ Обработан' if cases is not None else '❌ Ошибка'}")
    except Exception as e:
        print(f"   Пустой запрос: ❌ Ошибка - {e}")
    
    try:
        # Несуществующий номер дела
        details = await client.get_case_details(case_number="99999/9999/99")
        print(f"   Несуществующий номер: {'✅ Обработан' if details is None else '⚠️  Получен результат'}")
    except Exception as e:
        print(f"   Несуществующий номер: ⚠️  Исключение - {type(e).__name__}")
    
    # Закрытие клиента
    print(f"\n🔒 Закрытие клиента...")
    try:
        await client.close()
        print(f"   ✅ Клиент закрыт")
    except Exception as e:
        print(f"   ⚠️  Ошибка закрытия: {e}")
    
    print(f"\n" + "="*60)
    print("✅ Проверка завершена")
    print("="*60 + "\n")
    return True


async def main():
    """Главная функция"""
    try:
        success = await test_mcp_connection()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Прервано пользователем")
        sys.exit(1)
    except Exception as e:
        logger.exception("Unexpected error")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

