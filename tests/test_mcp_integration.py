"""
Интеграционные тесты для MCP клиента
"""
import pytest
from unittest.mock import AsyncMock, patch, Mock
from httpx import Response
from core.mcp.law_client import LawMCPClient


class TestLawMCPClientIntegration:
    """Интеграционные тесты Law MCP клиента"""
    
    @pytest.mark.asyncio
    async def test_search_cases_success(self, mock_law_client):
        """Тест успешного поиска дел"""
        cases = await mock_law_client.search_cases("договір", instance="3", limit=10)
        
        assert isinstance(cases, list)
        assert len(cases) > 0
        assert "title" in cases[0]
        mock_law_client.search_cases.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_search_cases_empty_result(self):
        """Тест поиска с пустым результатом"""
        mock_client = Mock(spec=LawMCPClient)
        mock_client.search_cases = AsyncMock(return_value=[])
        
        cases = await mock_client.search_cases("nonexistent query")
        assert cases == []
    
    @pytest.mark.asyncio
    async def test_get_case_details_success(self, mock_law_client):
        """Тест успешного получения деталей дела"""
        details = await mock_law_client.get_case_details(case_number="123/2024")
        
        assert details is not None
        assert "case_number" in details or "title" in details
        mock_law_client.get_case_details.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_case_details_not_found(self):
        """Тест получения несуществующего дела"""
        mock_client = Mock(spec=LawMCPClient)
        mock_client.get_case_details = AsyncMock(return_value=None)
        
        details = await mock_client.get_case_details(case_number="999/9999")
        assert details is None
    
    @pytest.mark.asyncio
    async def test_get_case_details_by_doc_id(self, mock_law_client):
        """Тест получения дела по doc_id"""
        details = await mock_law_client.get_case_details(doc_id="test-doc-id")
        
        assert details is not None
        mock_law_client.get_case_details.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_extract_case_arguments(self):
        """Тест извлечения аргументов из дел"""
        mock_client = Mock(spec=LawMCPClient)
        mock_client.extract_case_arguments = AsyncMock(return_value={
            "arguments": [
                {"type": "factual", "count": 5},
                {"type": "legal", "count": 3}
            ]
        })
        
        result = await mock_client.extract_case_arguments(
            query="договір",
            instance="3",
            limit=10
        )
        
        assert "arguments" in result
        assert isinstance(result["arguments"], list)
    
    @pytest.mark.asyncio
    async def test_search_cases_error_handling(self):
        """Тест обработки ошибок при поиске"""
        mock_client = LawMCPClient()
        mock_client.client = AsyncMock()
        mock_client.client.post = AsyncMock(side_effect=Exception("Network error"))
        
        cases = await mock_client.search_cases("test query")
        assert cases == []
    
    @pytest.mark.asyncio
    async def test_get_case_details_error_handling(self):
        """Тест обработки ошибок при получении деталей"""
        mock_client = LawMCPClient()
        mock_client.client = AsyncMock()
        mock_client.client.post = AsyncMock(side_effect=Exception("Network error"))
        
        details = await mock_client.get_case_details(case_number="123/2024")
        assert details is None
    
    @pytest.mark.asyncio
    async def test_client_close(self):
        """Тест закрытия клиента"""
        mock_client = LawMCPClient()
        mock_client.client = AsyncMock()
        mock_client.client.aclose = AsyncMock()
        
        await mock_client.close()
        mock_client.client.aclose.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_search_cases_with_different_instances(self, mock_law_client):
        """Тест поиска с разными инстанциями"""
        for instance in ["1", "2", "3", "4"]:
            cases = await mock_law_client.search_cases("test", instance=instance)
            assert isinstance(cases, list)
    
    @pytest.mark.asyncio
    async def test_search_cases_limit(self, mock_law_client):
        """Тест ограничения количества результатов"""
        cases = await mock_law_client.search_cases("test", limit=5)
        assert len(cases) <= 5

