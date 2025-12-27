"""
Клиент для MCP сервера Закон онлайн
"""
import httpx
from typing import List, Dict, Any, Optional
from loguru import logger
from config import settings
from core.resilience import resilient_mcp


class LawMCPClient:
    """Клиент для работы с MCP сервером Закон онлайн"""
    
    def __init__(self):
        self.base_url = settings.mcp_law_server_url
        self.api_key = settings.mcp_law_api_key
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}" if self.api_key else None,
                "Content-Type": "application/json"
            },
            timeout=30.0
        )
    
    @resilient_mcp(name="mcp_search_cases")
    async def search_cases(
        self,
        query: str,
        instance: str = "3",
        limit: int = 25
    ) -> List[Dict[str, Any]]:
        """
        Поиск судебных дел
        
        Args:
            query: Поисковый запрос
            instance: Инстанция суда (1, 2, 3, 4)
            limit: Максимальное количество результатов
            
        Returns:
            Список найденных дел
        """
        try:
            response = await self.client.post(
                "/mcp/zakononline/search_cases",
                json={
                    "query": query,
                    "instance": instance,
                    "limit": limit
                }
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error searching cases: {e}")
            return []
    
    @resilient_mcp(name="mcp_get_case_details")
    async def get_case_details(
        self,
        case_number: Optional[str] = None,
        doc_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Получение деталей дела
        
        Args:
            case_number: Номер дела
            doc_id: ID документа
            
        Returns:
            Детали дела или None
        """
        try:
            params = {}
            if case_number:
                params["caseNumber"] = case_number
            if doc_id:
                params["docId"] = doc_id
            
            response = await self.client.post(
                "/mcp/zakononline/get_case_details",
                json=params
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error getting case details: {e}")
            return None
    
    @resilient_mcp(name="mcp_extract_case_arguments", timeout_seconds=90)
    async def extract_case_arguments(
        self,
        query: str,
        instance: str = "3",
        limit: int = 50,
        year: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Извлечение аргументов из судебных решений
        
        Args:
            query: Поисковый запрос
            instance: Инстанция суда
            limit: Максимальное количество дел для анализа
            year: Год для фильтрации
            
        Returns:
            Структурированная информация об аргументах
        """
        try:
            payload = {
                "query": query,
                "instance": instance,
                "limit": limit
            }
            if year:
                payload["year"] = year
            
            response = await self.client.post(
                "/mcp/zakononline/extract_case_arguments",
                json=payload
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error extracting case arguments: {e}")
            return {}
    
    async def close(self):
        """Закрытие клиента"""
        await self.client.aclose()

