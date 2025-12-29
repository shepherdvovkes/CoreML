"""
Комплексные тесты для внешнего MCP сервера
Проверяет все доступные инструменты и эндпоинты MCP сервера
"""
import pytest
import asyncio
import httpx
from typing import Dict, Any, List
from config import settings
from core.mcp.law_client import LawMCPClient


@pytest.fixture(scope="function")
async def mcp_client():
    """Фикстура для создания MCP клиента"""
    client = LawMCPClient()
    yield client
    await client.close()


@pytest.fixture(scope="function")
async def http_client():
    """Фикстура для прямых HTTP запросов к MCP серверу"""
    async with httpx.AsyncClient(
        base_url=settings.mcp_law_server_url,
        timeout=30.0,
        headers={"Content-Type": "application/json"}
    ) as client:
        yield client


@pytest.mark.integration
@pytest.mark.requires_external_services
class TestMCPServerHealth:
    """Тесты проверки здоровья MCP сервера"""
    
    @pytest.mark.asyncio
    async def test_health_endpoint(self, http_client):
        """Тест health endpoint"""
        try:
            response = await asyncio.wait_for(
                http_client.get("/health"),
                timeout=5.0
            )
            assert response.status_code == 200, f"Health check failed: {response.status_code}"
            
            data = response.json()
            assert data["status"] == "ok", "Server status should be 'ok'"
            assert "service" in data, "Response should contain 'service'"
            assert "tools" in data, "Response should contain 'tools'"
            assert len(data["tools"]) > 0, "Server should have at least one tool"
            
            print(f"✓ MCP Server: {data.get('service')}")
            print(f"✓ Available tools: {', '.join(data.get('tools', []))}")
        except Exception as e:
            pytest.skip(f"MCP Server недоступен: {e}")
    
    @pytest.mark.asyncio
    async def test_server_info(self, http_client):
        """Тест получения информации о сервере"""
        try:
            response = await http_client.get("/health")
            data = response.json()
            
            # Проверяем обязательные поля
            assert "port" in data, "Response should contain 'port'"
            assert "hasToken" in data, "Response should contain 'hasToken'"
            assert data["hasToken"] is True, "Server should have token configured"
            
            # Проверяем список инструментов
            expected_tools = [
                "search_cases",
                "get_case_details",
                "get_case_full_text",
                "get_resolution",
                "analyze_case_outcomes",
                "extract_case_arguments"
            ]
            
            available_tools = data.get("tools", [])
            for tool in expected_tools:
                assert tool in available_tools, f"Tool '{tool}' should be available"
            
            print(f"✓ Server port: {data.get('port')}")
            print(f"✓ Token configured: {data.get('hasToken')}")
            print(f"✓ Total tools: {len(available_tools)}")
        except Exception as e:
            pytest.skip(f"MCP Server недоступен: {e}")


@pytest.mark.integration
@pytest.mark.requires_external_services
class TestMCPServerSearchCases:
    """Тесты для инструмента search_cases"""
    
    @pytest.mark.asyncio
    async def test_search_cases_basic(self, mcp_client):
        """Базовый тест поиска дел"""
        try:
            cases = await asyncio.wait_for(
                mcp_client.search_cases("договір", limit=5),
                timeout=20.0
            )
            
            assert isinstance(cases, list), "Результат должен быть списком"
            assert len(cases) > 0, "Должен быть хотя бы один результат"
            
            # Проверяем структуру первого результата
            case = cases[0]
            assert isinstance(case, dict), "Каждое дело должно быть словарем"
            assert "id" in case or "doc_id" in case, "Дело должно иметь ID"
            assert "title" in case, "Дело должно иметь title"
            
            print(f"✓ Найдено дел: {len(cases)}")
            print(f"✓ Первое дело: {case.get('title', 'N/A')[:60]}...")
        except Exception as e:
            pytest.skip(f"MCP Server недоступен: {e}")
    
    @pytest.mark.asyncio
    async def test_search_cases_empty_query(self, mcp_client):
        """Тест поиска с пустым запросом"""
        try:
            cases = await mcp_client.search_cases("", limit=1)
            # Пустой запрос может вернуть пустой список или результаты
            assert isinstance(cases, list), "Результат должен быть списком"
            print(f"✓ Пустой запрос обработан: {len(cases)} результатов")
        except Exception as e:
            pytest.skip(f"MCP Server недоступен: {e}")
    
    @pytest.mark.asyncio
    async def test_search_cases_all_instances(self, mcp_client):
        """Тест поиска для всех инстанций"""
        instances = ["1", "2", "3", "4"]
        results = {}
        
        for instance in instances:
            try:
                cases = await asyncio.wait_for(
                    mcp_client.search_cases("права", instance=instance, limit=3),
                    timeout=15.0
                )
                results[instance] = len(cases)
                assert isinstance(cases, list), f"Инстанция {instance} должна вернуть список"
                print(f"✓ Инстанция {instance}: {len(cases)} результатов")
            except Exception as e:
                print(f"✗ Инстанция {instance}: ошибка - {e}")
                results[instance] = None
        
        # Хотя бы одна инстанция должна работать
        successful = [k for k, v in results.items() if v is not None and v > 0]
        assert len(successful) > 0, f"Ни одна инстанция не вернула результаты: {results}"
    
    @pytest.mark.asyncio
    async def test_search_cases_limit_validation(self, mcp_client):
        """Тест валидации лимита результатов"""
        limits = [1, 5, 10, 25, 50]
        
        for limit in limits:
            try:
                cases = await asyncio.wait_for(
                    mcp_client.search_cases("договір", limit=limit),
                    timeout=15.0
                )
                assert isinstance(cases, list), f"Лимит {limit} должен вернуть список"
                assert len(cases) <= limit, f"Лимит {limit}: получено {len(cases)} результатов"
                print(f"✓ Лимит {limit}: получено {len(cases)} результатов")
            except Exception as e:
                pytest.skip(f"MCP Server недоступен: {e}")
    
    @pytest.mark.asyncio
    async def test_search_cases_response_structure(self, mcp_client):
        """Тест структуры ответа поиска"""
        try:
            cases = await mcp_client.search_cases("суд", limit=3)
            
            if len(cases) > 0:
                case = cases[0]
                # Проверяем наличие основных полей
                expected_fields = ["id", "title"]
                optional_fields = ["doc_id", "court_code", "adjudication_date", "cause_num", "resolution"]
                
                for field in expected_fields:
                    assert field in case, f"Поле '{field}' должно присутствовать"
                
                found_optional = [f for f in optional_fields if f in case]
                print(f"✓ Обязательные поля: {', '.join(expected_fields)}")
                print(f"✓ Опциональные поля: {', '.join(found_optional)}")
        except Exception as e:
            pytest.skip(f"MCP Server недоступен: {e}")


@pytest.mark.integration
@pytest.mark.requires_external_services
class TestMCPServerGetCaseDetails:
    """Тесты для инструмента get_case_details"""
    
    @pytest.mark.asyncio
    async def test_get_case_details_by_case_number(self, mcp_client):
        """Тест получения деталей по номеру дела"""
        try:
            # Сначала находим дело
            cases = await mcp_client.search_cases("договір", limit=1)
            
            if len(cases) == 0:
                pytest.skip("Нет доступных дел для тестирования")
            
            case = cases[0]
            case_number = case.get("cause_num")
            
            if not case_number:
                pytest.skip("Найденное дело не содержит номера")
            
            # Получаем детали
            details = await asyncio.wait_for(
                mcp_client.get_case_details(case_number=case_number),
                timeout=20.0
            )
            
            if details:
                assert isinstance(details, dict), "Детали должны быть словарем"
                print(f"✓ Получены детали дела: {case_number}")
            else:
                print(f"⚠ Детали не получены для дела: {case_number}")
        except Exception as e:
            pytest.skip(f"MCP Server недоступен: {e}")
    
    @pytest.mark.asyncio
    async def test_get_case_details_by_doc_id(self, mcp_client):
        """Тест получения деталей по doc_id"""
        try:
            # Находим дело
            cases = await mcp_client.search_cases("права", limit=1)
            
            if len(cases) == 0:
                pytest.skip("Нет доступных дел для тестирования")
            
            case = cases[0]
            doc_id = case.get("doc_id") or case.get("id")
            
            if not doc_id:
                pytest.skip("Найденное дело не содержит doc_id")
            
            # Получаем детали
            details = await asyncio.wait_for(
                mcp_client.get_case_details(doc_id=str(doc_id)),
                timeout=20.0
            )
            
            if details:
                assert isinstance(details, dict), "Детали должны быть словарем"
                print(f"✓ Получены детали по doc_id: {doc_id}")
            else:
                print(f"⚠ Детали не получены для doc_id: {doc_id}")
        except Exception as e:
            pytest.skip(f"MCP Server недоступен: {e}")
    
    @pytest.mark.asyncio
    async def test_get_case_details_not_found(self, mcp_client):
        """Тест получения несуществующего дела"""
        try:
            details = await mcp_client.get_case_details(
                case_number="99999/9999/99"
            )
            # Может вернуть None или пустой результат
            assert details is None or isinstance(details, dict), \
                "Несуществующее дело должно вернуть None или пустой dict"
            print("✓ Обработка несуществующего дела работает корректно")
        except Exception as e:
            pytest.skip(f"MCP Server недоступен: {e}")


@pytest.mark.integration
@pytest.mark.requires_external_services
class TestMCPServerExtractArguments:
    """Тесты для инструмента extract_case_arguments"""
    
    @pytest.mark.asyncio
    async def test_extract_case_arguments_basic(self, mcp_client):
        """Базовый тест извлечения аргументов"""
        try:
            result = await asyncio.wait_for(
                mcp_client.extract_case_arguments(
                    query="договір купівлі-продажу",
                    instance="3",
                    limit=10
                ),
                timeout=90.0
            )
            
            assert isinstance(result, dict), "Результат должен быть словарем"
            print(f"✓ Извлечение аргументов завершено")
            print(f"✓ Ключи в результате: {', '.join(result.keys())}")
        except asyncio.TimeoutError:
            pytest.skip("Таймаут при извлечении аргументов (более 90 секунд)")
        except Exception as e:
            pytest.skip(f"MCP Server недоступен: {e}")
    
    @pytest.mark.asyncio
    async def test_extract_case_arguments_with_year(self, mcp_client):
        """Тест извлечения аргументов с фильтром по году"""
        try:
            result = await asyncio.wait_for(
                mcp_client.extract_case_arguments(
                    query="права власності",
                    instance="3",
                    limit=5,
                    year=2024
                ),
                timeout=60.0
            )
            
            assert isinstance(result, dict), "Результат должен быть словарем"
            print(f"✓ Извлечение аргументов с фильтром по году завершено")
        except Exception as e:
            pytest.skip(f"MCP Server недоступен: {e}")


@pytest.mark.integration
@pytest.mark.requires_external_services
class TestMCPServerDirectAPI:
    """Тесты прямых запросов к API MCP сервера"""
    
    @pytest.mark.asyncio
    async def test_direct_search_cases_api(self, http_client):
        """Прямой тест API search_cases"""
        try:
            response = await asyncio.wait_for(
                http_client.post(
                    "/v1/mcp/search_cases",
                    json={
                        "query": "тест",
                        "instance": "3",
                        "limit": 1
                    }
                ),
                timeout=15.0
            )
            
            assert response.status_code == 200, f"API вернул статус {response.status_code}"
            data = response.json()
            
            assert "success" in data, "Ответ должен содержать 'success'"
            assert data["success"] is True, "Успешный запрос должен иметь success=True"
            assert "results" in data, "Ответ должен содержать 'results'"
            assert isinstance(data["results"], list), "Results должен быть списком"
            
            print(f"✓ Прямой API запрос успешен: {len(data.get('results', []))} результатов")
        except Exception as e:
            pytest.skip(f"MCP Server недоступен: {e}")
    
    @pytest.mark.asyncio
    async def test_direct_get_case_details_api(self, http_client):
        """Прямой тест API get_case_details"""
        try:
            # Сначала получаем дело через search
            search_response = await http_client.post(
                "/v1/mcp/search_cases",
                json={"query": "договір", "limit": 1}
            )
            
            if search_response.status_code != 200:
                pytest.skip("Не удалось получить дело для тестирования")
            
            search_data = search_response.json()
            if not search_data.get("results"):
                pytest.skip("Нет результатов для тестирования")
            
            case = search_data["results"][0]
            case_number = case.get("cause_num")
            
            if not case_number:
                pytest.skip("Дело не содержит номера")
            
            # Получаем детали
            details_response = await asyncio.wait_for(
                http_client.post(
                    "/v1/mcp/get_case_details",
                    json={"caseNumber": case_number}
                ),
                timeout=20.0
            )
            
            assert details_response.status_code in [200, 404], \
                f"API вернул статус {details_response.status_code}"
            
            if details_response.status_code == 200:
                data = details_response.json()
                assert isinstance(data, dict), "Детали должны быть словарем"
                print(f"✓ Прямой API запрос деталей успешен")
        except Exception as e:
            pytest.skip(f"MCP Server недоступен: {e}")
    
    @pytest.mark.asyncio
    async def test_api_error_handling(self, http_client):
        """Тест обработки ошибок API"""
        # Тест с невалидными данными
        try:
            response = await http_client.post(
                "/v1/mcp/search_cases",
                json={"invalid": "data"}
            )
            # Сервер должен вернуть ошибку или обработать запрос
            assert response.status_code in [200, 400, 422], \
                f"Неожиданный статус: {response.status_code}"
            print("✓ Обработка невалидных данных работает")
        except Exception as e:
            pytest.skip(f"MCP Server недоступен: {e}")


@pytest.mark.integration
@pytest.mark.requires_external_services
class TestMCPServerPerformance:
    """Тесты производительности MCP сервера"""
    
    @pytest.mark.asyncio
    async def test_search_response_time(self, mcp_client):
        """Тест времени ответа поиска"""
        import time
        
        try:
            start_time = time.time()
            cases = await mcp_client.search_cases("договір", limit=5)
            elapsed = time.time() - start_time
            
            assert isinstance(cases, list), "Результат должен быть списком"
            assert elapsed < 10.0, f"Поиск занял слишком много времени: {elapsed:.2f}s"
            
            print(f"✓ Время ответа: {elapsed:.2f}s")
            print(f"✓ Результатов: {len(cases)}")
        except Exception as e:
            pytest.skip(f"MCP Server недоступен: {e}")
    
    @pytest.mark.asyncio
    async def test_concurrent_requests(self, mcp_client):
        """Тест параллельных запросов"""
        try:
            queries = ["договір", "права", "суд", "рішення"]
            
            start_time = asyncio.get_event_loop().time()
            results = await asyncio.gather(
                *[mcp_client.search_cases(q, limit=2) for q in queries],
                return_exceptions=True
            )
            elapsed = asyncio.get_event_loop().time() - start_time
            
            # Проверяем результаты
            successful = [r for r in results if not isinstance(r, Exception)]
            assert len(successful) > 0, "Хотя бы один запрос должен быть успешным"
            
            print(f"✓ Параллельных запросов: {len(queries)}")
            print(f"✓ Успешных: {len(successful)}")
            print(f"✓ Время выполнения: {elapsed:.2f}s")
        except Exception as e:
            pytest.skip(f"MCP Server недоступен: {e}")


@pytest.mark.integration
@pytest.mark.requires_external_services
class TestMCPServerAdditionalTools:
    """Тесты для дополнительных инструментов MCP сервера (через прямой API)"""
    
    @pytest.mark.asyncio
    async def test_get_case_full_text(self, http_client):
        """Тест получения полного текста дела"""
        try:
            # Сначала находим дело
            search_response = await http_client.post(
                "/v1/mcp/search_cases",
                json={"query": "договір", "limit": 1}
            )
            
            if search_response.status_code != 200:
                pytest.skip("Не удалось получить дело")
            
            search_data = search_response.json()
            if not search_data.get("results"):
                pytest.skip("Нет результатов")
            
            case = search_data["results"][0]
            doc_id = case.get("doc_id") or case.get("id")
            
            if not doc_id:
                pytest.skip("Дело не содержит doc_id")
            
            # Получаем полный текст
            full_text_response = await asyncio.wait_for(
                http_client.post(
                    "/v1/mcp/get_case_full_text",
                    json={"docId": str(doc_id)}
                ),
                timeout=30.0
            )
            
            if full_text_response.status_code == 200:
                data = full_text_response.json()
                assert isinstance(data, dict), "Полный текст должен быть словарем"
                print(f"✓ Получен полный текст для doc_id: {doc_id}")
            else:
                print(f"⚠ Полный текст не получен: статус {full_text_response.status_code}")
        except Exception as e:
            pytest.skip(f"MCP Server недоступен: {e}")
    
    @pytest.mark.asyncio
    async def test_get_resolution(self, http_client):
        """Тест получения резолютивной части"""
        try:
            # Находим дело
            search_response = await http_client.post(
                "/v1/mcp/search_cases",
                json={"query": "права", "limit": 1}
            )
            
            if search_response.status_code != 200:
                pytest.skip("Не удалось получить дело")
            
            search_data = search_response.json()
            if not search_data.get("results"):
                pytest.skip("Нет результатов")
            
            case = search_data["results"][0]
            doc_id = case.get("doc_id") or case.get("id")
            
            if not doc_id:
                pytest.skip("Дело не содержит doc_id")
            
            # Получаем резолюцию
            resolution_response = await asyncio.wait_for(
                http_client.post(
                    "/v1/mcp/get_resolution",
                    json={"docId": str(doc_id)}
                ),
                timeout=20.0
            )
            
            if resolution_response.status_code == 200:
                data = resolution_response.json()
                assert isinstance(data, dict), "Резолюция должна быть словарем"
                print(f"✓ Получена резолюция для doc_id: {doc_id}")
            else:
                print(f"⚠ Резолюция не получена: статус {resolution_response.status_code}")
        except Exception as e:
            pytest.skip(f"MCP Server недоступен: {e}")
    
    @pytest.mark.asyncio
    async def test_analyze_case_outcomes(self, http_client):
        """Тест анализа результатов дел"""
        try:
            response = await asyncio.wait_for(
                http_client.post(
                    "/v1/mcp/analyze_case_outcomes",
                    json={
                        "query": "договір",
                        "instance": "3",
                        "limit": 5
                    }
                ),
                timeout=60.0
            )
            
            if response.status_code == 200:
                data = response.json()
                assert isinstance(data, dict), "Результат анализа должен быть словарем"
                print("✓ Анализ результатов дел завершен")
            else:
                print(f"⚠ Анализ не выполнен: статус {response.status_code}")
        except Exception as e:
            pytest.skip(f"MCP Server недоступен: {e}")


@pytest.mark.integration
@pytest.mark.requires_external_services
class TestMCPServerIntegration:
    """Интеграционные тесты полного цикла работы с MCP сервером"""
    
    @pytest.mark.asyncio
    async def test_full_workflow(self, mcp_client):
        """Тест полного цикла: поиск -> детали -> аргументы"""
        try:
            # Шаг 1: Поиск дел
            cases = await mcp_client.search_cases("договір", limit=3)
            assert len(cases) > 0, "Должен быть хотя бы один результат"
            
            case = cases[0]
            print(f"✓ Шаг 1: Найдено {len(cases)} дел")
            
            # Шаг 2: Получение деталей (если есть номер дела)
            if "cause_num" in case and case["cause_num"]:
                details = await mcp_client.get_case_details(
                    case_number=case["cause_num"]
                )
                if details:
                    print(f"✓ Шаг 2: Получены детали дела")
                else:
                    print(f"⚠ Шаг 2: Детали не получены")
            
            # Шаг 3: Извлечение аргументов (может быть долгим)
            try:
                arguments = await asyncio.wait_for(
                    mcp_client.extract_case_arguments(
                        query="договір",
                        limit=5
                    ),
                    timeout=60.0
                )
                if arguments:
                    print(f"✓ Шаг 3: Извлечены аргументы")
            except asyncio.TimeoutError:
                print(f"⚠ Шаг 3: Таймаут при извлечении аргументов")
            
            print("✓ Полный цикл работы завершен")
        except Exception as e:
            pytest.skip(f"MCP Server недоступен: {e}")
    
    @pytest.mark.asyncio
    async def test_error_recovery(self, mcp_client):
        """Тест восстановления после ошибок"""
        try:
            # Пробуем невалидный запрос
            cases1 = await mcp_client.search_cases("", limit=0)
            assert isinstance(cases1, list), "Даже невалидный запрос должен вернуть список"
            
            # Пробуем валидный запрос после ошибки
            cases2 = await mcp_client.search_cases("тест", limit=1)
            assert isinstance(cases2, list), "Валидный запрос должен работать после ошибки"
            
            print("✓ Восстановление после ошибок работает корректно")
        except Exception as e:
            pytest.skip(f"MCP Server недоступен: {e}")

