"""
Маршрутизатор запросов для определения источника данных (Stateless)
"""
from typing import Dict, Any, List, Optional
import asyncio
from loguru import logger
from core.rag.rag_service import RAGService
from core.rag.document_classifier import DocumentClassifier
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
            "кодекс", "норма", "юридична", "правова", "законодавство",
            "судебн", "приговор", "постанов"
        ]
        
        document_keywords = [
            "договір", "контракт", "справка", "чек", "наклад",
            "документ", "файл", "архів", "мої документи", "мои документы",
            "твої документи", "твои документы", "завантажен", "загружен"
        ]
        
        # Специальные фразы, которые явно указывают на документы пользователя
        user_document_phrases = [
            "какие документы", "які документи", "какие мои документы",
            "які мої документи", "что в документах", "що в документах",
            "видишь документы", "бачиш документи", "мои файлы", "мої файли",
            "какие данные", "які дані", "что загрузил", "що завантажив",
            "что я загрузил", "що я завантажив", "какие файлы загрузил",
            "які файли завантажив", "видишь что загрузил", "бачиш що завантажив"
        ]
        
        use_law = any(keyword in query_lower for keyword in law_keywords)
        use_rag = any(keyword in query_lower for keyword in document_keywords)
        
        # Проверяем специальные фразы про документы пользователя
        is_user_document_query = any(phrase in query_lower for phrase in user_document_phrases)
        
        # Если запрос явно про документы пользователя, используем только RAG
        if is_user_document_query:
            use_rag = True
            use_law = False
        # Если есть явные указания на документы, приоритет RAG
        elif use_rag and not use_law:
            use_law = False  # Не используем MCP Law если запрос про документы
        # Если нет явных указаний, используем оба источника
        elif not use_law and not use_rag:
            use_law = True
            use_rag = True
        
        return {
            "use_rag": use_rag,
            "use_law": use_law,
            "query_type": "user_documents" if is_user_document_query else ("legal" if use_law else "document")
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
        # Проверка наличия документов в RAG
        has_docs = await self.rag_service.has_documents()
        if use_rag is None:
            if not has_docs:
                logger.info("No documents in vector store, using only MCP Law server")
                use_rag = False
                # Если документов нет, используем только закон онлайн
                if use_law is None:
                    use_law = True
            else:
                # Если документы есть и use_rag не передан явно, используем RAG по умолчанию
                logger.info("Documents found in vector store, using RAG by default")
                use_rag = True
        
        # Классификация запроса (если use_law еще не определен)
        classification = None
        if use_law is None:
            classification = self._classify_query(query)
            use_law = classification["use_law"]
            # Если классификация определила, что это запрос про документы пользователя,
            # убеждаемся, что use_rag включен (если документы есть)
            if classification.get("query_type") == "user_documents" and has_docs:
                use_rag = True
                logger.info("User document query detected, ensuring RAG is enabled")
        
        # Если есть документы в RAG и запрос про документы пользователя, используем только RAG
        if classification and use_rag and has_docs and classification.get("query_type") == "user_documents":
            use_law = False
            logger.info("User document query detected, using only RAG")
        
        # Если документов нет, гарантируем использование MCP Law
        if not use_rag and use_law is None:
            use_law = True
        
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
        rag_context_text = None
        if isinstance(rag_result, Exception):
            logger.error(f"RAG context error: {rag_result}")
        elif rag_result:
            contexts.append(rag_result)
            sources.append("RAG")
            # Извлекаем текст контекста для анализа типа документа
            if "=== Контекст из документов ===" in rag_result:
                rag_context_text = rag_result.split("=== Контекст из документов ===")[1].strip()
        
        if isinstance(law_result, Exception):
            logger.error(f"Law context error: {law_result}")
        elif law_result:
            contexts.append(law_result)
            sources.append("MCP_Law")
        
        # Анализ типа документа и генерация предложенных действий
        suggested_actions = None
        if rag_context_text and use_rag:
            # Сначала пытаемся получить тип документа из метаданных результатов поиска
            doc_type = None
            try:
                search_results = await self.rag_service.search(query, top_k=5)
                # Ищем document_type в метаданных результатов
                for result in search_results:
                    metadata = result.get('metadata', {})
                    if 'document_type' in metadata:
                        doc_type = metadata['document_type']
                        logger.debug(f"Found document_type in metadata: {doc_type}")
                        break
            except Exception as e:
                logger.debug(f"Could not get document_type from metadata: {e}")
            
            # Если не нашли в метаданных, определяем из текста
            if not doc_type:
                doc_type_info = DocumentClassifier.detect_document_type(rag_context_text)
                doc_type = doc_type_info.get("type", "unknown")
                logger.debug(f"Detected document type from text: {doc_type} (confidence: {doc_type_info.get('confidence', 0):.2f})")
            
            # Получаем предложенные действия на основе типа документа
            suggested_actions = DocumentClassifier.get_suggested_actions(doc_type, query)
            logger.info(f"Suggested {len(suggested_actions)} actions for document type: {doc_type}")
        
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
        # Определяем тип запроса для более точного промпта
        query_type = classification.get("query_type") if classification else None
        
        if query_type == "user_documents":
            system_prompt = """Ты - юридический ассистент, который помогает пользователям с их загруженными документами.
ВАЖНО: Пользователь спрашивает про СВОИ загруженные документы. Отвечай ТОЛЬКО на основе контекста из раздела "=== Контекст из документов ===".
НЕ упоминай судебные дела, судебную практику или статьи из законов, если пользователь не спрашивает об этом явно.
НЕ упоминай техническую информацию о документах (тип файла, формат, OCR и т.д.).
Отвечай только на вопрос пользователя о содержании его документов.
Если в контексте из документов нет информации, честно скажи, что не нашел информацию в загруженных документах."""
        else:
            system_prompt = """Ты - юридический ассистент, который помогает пользователям с юридическими вопросами.
Используй предоставленный контекст для формирования точного и полезного ответа.
Если контекст содержит информацию из загруженных документов пользователя, приоритетно используй её.
Если контекст не содержит нужной информации, честно об этом скажи."""
        
        user_prompt = query
        if contexts:
            user_prompt += "\n\n" + "\n\n".join(contexts)
            # Логируем контекст для отладки
            logger.debug(f"Context length: {sum(len(c) for c in contexts)} chars, contexts count: {len(contexts)}")
            for i, ctx in enumerate(contexts, 1):
                logger.debug(f"Context {i} preview: {ctx[:200]}...")
        
        # Генерация ответа через LLM
        llm = LLMProviderFactory.get_provider(llm_provider, model)
        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=user_prompt)
        ]
        
        # Логируем промпт для отладки (первые 500 символов)
        logger.info(f"Sending to LLM provider: {llm_provider.value if llm_provider else 'default'}, model: {model or 'default'}")
        logger.info(f"RAG enabled: {use_rag}, Law enabled: {use_law}, Contexts count: {len(contexts)}")
        logger.debug(f"Sending to LLM - System prompt length: {len(system_prompt)}, User prompt length: {len(user_prompt)}")
        logger.debug(f"User prompt preview: {user_prompt[:500]}...")
        
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
                },
                "suggested_actions": suggested_actions
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
        # Проверка наличия документов в RAG
        has_docs = await self.rag_service.has_documents()
        if use_rag is None:
            if not has_docs:
                logger.info("No documents in vector store, using only MCP Law server")
                use_rag = False
                if use_law is None:
                    use_law = True
            else:
                # Если документы есть и use_rag не передан явно, используем RAG по умолчанию
                logger.info("Documents found in vector store, using RAG by default")
                use_rag = True
        
        # Классификация запроса (если use_law еще не определен)
        classification = None
        if use_law is None:
            classification = self._classify_query(query)
            use_law = classification["use_law"]
            # Если классификация определила, что это запрос про документы пользователя,
            # убеждаемся, что use_rag включен (если документы есть)
            if classification.get("query_type") == "user_documents" and has_docs:
                use_rag = True
                logger.info("User document query detected in stream, ensuring RAG is enabled")
        
        # Если есть документы в RAG и запрос про документы пользователя, используем только RAG
        if classification and use_rag and has_docs and classification.get("query_type") == "user_documents":
            use_law = False
            logger.info("User document query detected in stream, using only RAG")
        
        # Если документов нет, гарантируем использование MCP Law
        if not use_rag and use_law is None:
            use_law = True
        
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
        
        rag_context_text = None
        if isinstance(rag_result, str):
            contexts.append(rag_result)
            # Извлекаем текст контекста для анализа типа документа
            if "=== Контекст из документов ===" in rag_result:
                rag_context_text = rag_result.split("=== Контекст из документов ===")[1].strip()
        
        if isinstance(law_result, str):
            contexts.append(law_result)
        
        # Анализ типа документа и генерация предложенных действий (для stream)
        # Примечание: suggested_actions для stream можно передать через специальный формат в конце потока
        suggested_actions = None
        if rag_context_text and use_rag:
            # Сначала пытаемся получить тип документа из метаданных результатов поиска
            doc_type = None
            try:
                search_results = await self.rag_service.search(query, top_k=5)
                # Ищем document_type в метаданных результатов
                for result in search_results:
                    metadata = result.get('metadata', {})
                    if 'document_type' in metadata:
                        doc_type = metadata['document_type']
                        logger.debug(f"Stream: Found document_type in metadata: {doc_type}")
                        break
            except Exception as e:
                logger.debug(f"Stream: Could not get document_type from metadata: {e}")
            
            # Если не нашли в метаданных, определяем из текста
            if not doc_type:
                doc_type_info = DocumentClassifier.detect_document_type(rag_context_text)
                doc_type = doc_type_info.get("type", "unknown")
                logger.debug(f"Stream: Detected document type from text: {doc_type}")
            
            # Получаем предложенные действия на основе типа документа
            suggested_actions = DocumentClassifier.get_suggested_actions(doc_type, query)
            logger.debug(f"Stream: Suggested {len(suggested_actions)} actions for document type: {doc_type}")
        
        # Определяем тип запроса для более точного промпта
        query_type = classification.get("query_type") if classification else None
        
        if query_type == "user_documents":
            system_prompt = """Ты - юридический ассистент, который помогает пользователям с их загруженными документами.
ВАЖНО: Пользователь спрашивает про СВОИ загруженные документы. Отвечай ТОЛЬКО на основе контекста из раздела "=== Контекст из документов ===".
НЕ упоминай судебные дела, судебную практику или статьи из законов, если пользователь не спрашивает об этом явно.
НЕ упоминай техническую информацию о документах (тип файла, формат, OCR и т.д.).
Отвечай только на вопрос пользователя о содержании его документов.
Если в контексте из документов нет информации, честно скажи, что не нашел информацию в загруженных документах.
В конце ответа можешь предложить пользователю варианты дальнейших действий, если это уместно."""
        else:
            system_prompt = """Ты - юридический ассистент, который помогает пользователям с юридическими вопросами.
Используй предоставленный контекст для формирования точного и полезного ответа.
Если контекст содержит информацию из загруженных документов пользователя, приоритетно используй её.
Если контекст не содержит нужной информации, честно об этом скажи."""
        
        user_prompt = query
        if contexts:
            user_prompt += "\n\n" + "\n\n".join(contexts)
            # Логируем контекст для отладки
            logger.debug(f"Stream context length: {sum(len(c) for c in contexts)} chars, contexts count: {len(contexts)}")
        
        llm = LLMProviderFactory.get_provider(llm_provider, model)
        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=user_prompt)
        ]
        
        # Логируем промпт для отладки
        logger.info(f"Stream sending to LLM provider: {llm_provider.value if llm_provider else 'default'}, model: {model or 'default'}")
        logger.info(f"RAG enabled: {use_rag}, Law enabled: {use_law}, Contexts count: {len(contexts)}")
        logger.debug(f"Stream sending to LLM - User prompt length: {len(user_prompt)}, contains context: {bool(contexts)}")
        
        try:
            # Для stream мы не можем вернуть suggested_actions в потоке,
            # но можем добавить их в метаданные через специальный формат
            # Пока просто генерируем поток ответа
            async for chunk in llm.stream_generate(messages, temperature=0.7):
                yield chunk
        except Exception as e:
            logger.error(f"Error streaming LLM response: {e}")
            yield f"Ошибка: {str(e)}"
