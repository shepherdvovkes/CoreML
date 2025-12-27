"""
Маршрутизатор запросов для определения источника данных (Stateless)
"""
from typing import Dict, Any, List, Optional
import asyncio
from loguru import logger
from core.rag.rag_service import RAGService
from core.mcp.law_client import LawMCPClient
from core.llm.factory import LLMProviderFactory
from core.llm.base import LLMMessage
from core.services.cache_service import CacheService
from config import LLMProvider


class QueryRouter:
    """Stateless маршрутизатор для определения источника данных и обработки запросов"""
    
    def __init__(
        self,
        rag_service: Optional[RAGService] = None,
        law_client: Optional[LawMCPClient] = None,
        cache_service: Optional[CacheService] = None
    ):
        """
        Инициализация маршрутизатора
        
        Args:
            rag_service: Сервис RAG (создается если не передан)
            law_client: Клиент MCP Law (создается если не передан)
            cache_service: Сервис кэширования (опционально)
        """
        self.rag_service = rag_service or RAGService(cache_service=cache_service)
        self.law_client = law_client or LawMCPClient()
        self.cache_service = cache_service
    
    def _classify_query(self, query: str) -> Dict[str, Any]:
        """
        Классификация запроса для определения источника данных
        
        Args:
            query: Запрос пользователя
            
        Returns:
            Информация о типе запроса и необходимых источниках
        """
        query_lower = query.lower()
        
        # Ключевые слова для определения типа запроса
        law_keywords = [
            "суд", "судова", "справа", "рішення", "закон", "стаття",
            "кодекс", "норма", "юридична", "правова", "законодавство"
        ]
        
        document_keywords = [
            "договір", "контракт", "справка", "чек", "наклад",
            "документ", "файл", "архів"
        ]
        
        use_law = any(keyword in query_lower for keyword in law_keywords)
        use_rag = any(keyword in query_lower for keyword in document_keywords)
        
        # Если нет явных указаний, используем оба источника
        if not use_law and not use_rag:
            use_law = True
            use_rag = True
        
        return {
            "use_rag": use_rag,
            "use_law": use_law,
            "query_type": "legal" if use_law else "document"
        }
    
    async def process_query(
        self,
        query: str,
        llm_provider: Optional[LLMProvider] = None,
        model: Optional[str] = None,
        use_rag: Optional[bool] = None,
        use_law: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Обработка запроса пользователя с параллельной обработкой источников
        
        Args:
            query: Запрос пользователя
            llm_provider: Провайдер LLM
            model: Модель для использования
            use_rag: Использовать ли RAG (если None, определяется автоматически)
            use_law: Использовать ли MCP Law (если None, определяется автоматически)
            
        Returns:
            Ответ с результатами обработки
        """
        # Классификация запроса
        if use_rag is None or use_law is None:
            classification = self._classify_query(query)
            use_rag = use_rag if use_rag is not None else classification["use_rag"]
            use_law = use_law if use_law is not None else classification["use_law"]
        
        # Параллельный сбор контекста из разных источников
        contexts = []
        sources = []
        errors = []
        
        async def get_rag_context():
            """Получение RAG контекста"""
            if not use_rag:
                return None
            try:
                rag_context = await self.rag_service.get_context(query, top_k=5)
                if rag_context:
                    return f"=== Контекст из документов ===\n{rag_context}"
            except Exception as e:
                logger.error(f"Error getting RAG context: {e}")
                errors.append(f"RAG error: {str(e)}")
                return None
        
        async def get_law_context():
            """Получение Law MCP контекста"""
            if not use_law:
                return None
            try:
                cases = await self.law_client.search_cases(query, limit=5)
                if cases:
                    law_context = "=== Судебная практика ===\n"
                    for i, case in enumerate(cases[:3], 1):
                        law_context += f"{i}. {case.get('title', 'Дело')}\n"
                        if 'description' in case:
                            law_context += f"   {case['description'][:200]}...\n"
                    return law_context
            except Exception as e:
                logger.error(f"Error getting Law MCP context: {e}")
                errors.append(f"Law MCP error: {str(e)}")
                return None
        
        # Параллельное выполнение
        rag_result, law_result = await asyncio.gather(
            get_rag_context(),
            get_law_context(),
            return_exceptions=True
        )
        
        # Обработка результатов
        if isinstance(rag_result, Exception):
            logger.error(f"RAG context error: {rag_result}")
        elif rag_result:
            contexts.append(rag_result)
            sources.append("RAG")
        
        if isinstance(law_result, Exception):
            logger.error(f"Law context error: {law_result}")
        elif law_result:
            contexts.append(law_result)
            sources.append("MCP_Law")
        
        # Кэширование LLM запроса
        llm_cache_key = None
        if self.cache_service:
            llm_cache_key = self.cache_service._generate_key(
                "llm:query",
                query,
                llm_provider=llm_provider.value if llm_provider else "default",
                model=model or "default",
                use_rag=use_rag,
                use_law=use_law,
                context_hash=hash(str(contexts))
            )
            cached_response = await self.cache_service.get(llm_cache_key)
            if cached_response is not None:
                logger.debug(f"LLM response cache hit for query: {query[:50]}...")
                return cached_response
        
        # Формирование промпта для LLM
        system_prompt = """Ты - юридический ассистент, который помогает пользователям с юридическими вопросами.
Используй предоставленный контекст для формирования точного и полезного ответа.
Если контекст не содержит нужной информации, честно об этом скажи."""
        
        user_prompt = query
        if contexts:
            user_prompt += "\n\n" + "\n\n".join(contexts)
        
        # Генерация ответа через LLM
        llm = LLMProviderFactory.get_provider(llm_provider, model)
        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=user_prompt)
        ]
        
        try:
            response = await llm.generate(messages, temperature=0.7)
            
            result = {
                "answer": response.content,
                "sources": sources,
                "model": response.model,
                "usage": response.usage,
                "metadata": {
                    "used_rag": use_rag,
                    "used_law": use_law,
                    "context_count": len(contexts),
                    "errors": errors if errors else None
                }
            }
            
            # Сохранение в кэш
            if self.cache_service and llm_cache_key:
                await self.cache_service.set(llm_cache_key, result, ttl=1800)  # 30 минут
            
            return result
        except Exception as e:
            logger.error(f"Error generating LLM response: {e}")
            return {
                "answer": f"Ошибка при обработке запроса: {str(e)}",
                "sources": sources,
                "error": str(e),
                "metadata": {
                    "used_rag": use_rag,
                    "used_law": use_law,
                    "context_count": len(contexts),
                    "errors": errors + [f"LLM error: {str(e)}"]
                }
            }
    
    async def stream_process_query(
        self,
        query: str,
        llm_provider: Optional[LLMProvider] = None,
        model: Optional[str] = None,
        use_rag: Optional[bool] = None,
        use_law: Optional[bool] = None
    ):
        """
        Потоковая обработка запроса
        
        Args:
            query: Запрос пользователя
            llm_provider: Провайдер LLM
            model: Модель для использования
            use_rag: Использовать ли RAG
            use_law: Использовать ли MCP Law
            
        Yields:
            Части ответа
        """
        # Классификация и параллельный сбор контекста
        if use_rag is None or use_law is None:
            classification = self._classify_query(query)
            use_rag = use_rag if use_rag is not None else classification["use_rag"]
            use_law = use_law if use_law is not None else classification["use_law"]
        
        contexts = []
        
        async def get_rag_context():
            if not use_rag:
                return None
            try:
                rag_context = await self.rag_service.get_context(query, top_k=5)
                if rag_context:
                    return f"=== Контекст из документов ===\n{rag_context}"
            except Exception as e:
                logger.error(f"Error getting RAG context: {e}")
                return None
        
        async def get_law_context():
            if not use_law:
                return None
            try:
                cases = await self.law_client.search_cases(query, limit=3)
                if cases:
                    law_context = "=== Судебная практика ===\n"
                    for i, case in enumerate(cases, 1):
                        law_context += f"{i}. {case.get('title', 'Дело')}\n"
                    return law_context
            except Exception as e:
                logger.error(f"Error getting Law MCP context: {e}")
                return None
        
        # Параллельное выполнение
        rag_result, law_result = await asyncio.gather(
            get_rag_context(),
            get_law_context(),
            return_exceptions=True
        )
        
        if isinstance(rag_result, str):
            contexts.append(rag_result)
        if isinstance(law_result, str):
            contexts.append(law_result)
        
        system_prompt = """Ты - юридический ассистент, который помогает пользователям с юридическими вопросами.
Используй предоставленный контекст для формирования точного и полезного ответа."""
        
        user_prompt = query
        if contexts:
            user_prompt += "\n\n" + "\n\n".join(contexts)
        
        llm = LLMProviderFactory.get_provider(llm_provider, model)
        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=user_prompt)
        ]
        
        try:
            async for chunk in llm.stream_generate(messages, temperature=0.7):
                yield chunk
        except Exception as e:
            logger.error(f"Error streaming LLM response: {e}")
            yield f"Ошибка: {str(e)}"
