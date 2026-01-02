"""
Маршрутизатор запросов для определения источника данных (Stateless)
"""
from typing import Dict, Any, List, Optional
import asyncio
import httpx
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
    
    async def _extract_case_number_llm(self, query: str) -> Optional[str]:
        """
        Извлечение номера дела из запроса через OpenAI
        
        Args:
            query: Запрос пользователя
            
        Returns:
            Номер дела в формате число/число/число или None
        """
        try:
            # Используем кэш для извлечения номера дела
            cache_key = f"extract_case_number:{query[:100]}"
            if self.cache_service:
                cached = await self.cache_service.get(cache_key)
                if cached:
                    logger.debug(f"Case number extraction cache hit for query: {query[:50]}")
                    return cached if cached != "None" else None
            
            # Используем OpenAI для извлечения номера дела
            try:
                llm = LLMProviderFactory.get_provider(LLMProvider.OPENAI)
            except Exception as provider_error:
                logger.error(f"Failed to get OpenAI provider for case number extraction: {provider_error}")
                # Fallback на regex
                import re
                case_number_pattern = r'\d+/\d+/\d+'
                match = re.search(case_number_pattern, query)
                if match:
                    logger.info(f"Fallback to regex: extracted case number {match.group(0)}")
                    return match.group(0)
                return None
            
            # Ограничиваем длину запроса для безопасности
            safe_query = query[:500] if len(query) > 500 else query
            
            extraction_prompt = f"""Проанализируй запрос пользователя и извлеки номер дела, если он упоминается.

Запрос: {safe_query}

Номер дела имеет формат: число/число/число (например: 686/32982/23, 123/456/78)

Если в запросе есть номер дела, верни ТОЛЬКО номер дела в формате число/число/число.
Если номера дела нет, верни "None".

Ответ должен быть ТОЛЬКО номером дела или "None", без дополнительного текста."""

            system_content = "Ты помощник для извлечения номеров дел из запросов. Отвечай только номером дела или 'None'."
            
            # Логируем что отправляем
            logger.debug(f"Extracting case number via OpenAI - Query length: {len(query)}, Safe query: {safe_query[:100]}")
            logger.debug(f"System prompt length: {len(system_content)}, User prompt length: {len(extraction_prompt)}")
            
            messages = [
                LLMMessage(role="system", content=system_content),
                LLMMessage(role="user", content=extraction_prompt)
            ]
            
            try:
                response = await llm.generate(messages, temperature=0.1, max_tokens=50)
                logger.debug(f"OpenAI response received: {response.content[:100]}")
                
                case_number = response.content.strip()
                
                # Очищаем ответ от лишних символов
                case_number = case_number.replace('"', '').replace("'", "").strip()
                
                # Проверяем формат номера дела
                import re
                case_number_pattern = r'\d+/\d+/\d+'
                match = re.search(case_number_pattern, case_number)
                if match:
                    case_number = match.group(0)
                else:
                    if case_number.lower() != "none":
                        logger.warning(f"LLM returned invalid case number format: {case_number}")
                    case_number = None
                
                # Кэшируем результат
                if self.cache_service:
                    await self.cache_service.set(cache_key, case_number if case_number else "None", ttl=3600)
                
                logger.info(f"Extracted case number via LLM: {case_number} from query: {query[:50]}")
                return case_number
                
            except httpx.HTTPStatusError as http_error:
                error_detail = ""
                if hasattr(http_error, 'response') and http_error.response is not None:
                    try:
                        error_detail = http_error.response.text[:1000] if hasattr(http_error.response, 'text') else str(http_error.response.content[:1000])
                    except:
                        error_detail = str(http_error)
                
                logger.error(f"OpenAI API HTTP error during case number extraction: {http_error.response.status_code if hasattr(http_error, 'response') else 'unknown'}")
                logger.error(f"Error details: {error_detail}")
                logger.error(f"Request model: {llm.model}, base_url: {llm.base_url}")
                logger.error(f"Query length: {len(query)}, prompt length: {len(extraction_prompt)}")
                logger.error(f"System message: {system_content}")
                logger.error(f"User message preview: {extraction_prompt[:500]}")
                # Fallback на regex
                import re
                case_number_pattern = r'\d+/\d+/\d+'
                match = re.search(case_number_pattern, query)
                if match:
                    logger.info(f"Fallback to regex: extracted case number {match.group(0)}")
                    return match.group(0)
                return None
            except Exception as api_error:
                logger.error(f"OpenAI API error during case number extraction: {api_error}")
                logger.error(f"Error type: {type(api_error).__name__}")
                logger.error(f"Request model: {llm.model}, messages_count: {len(messages)}")
                # Fallback на regex
                import re
                case_number_pattern = r'\d+/\d+/\d+'
                match = re.search(case_number_pattern, query)
                if match:
                    logger.info(f"Fallback to regex: extracted case number {match.group(0)}")
                    return match.group(0)
                return None
            
        except Exception as e:
            logger.error(f"Error extracting case number via LLM: {e}")
            logger.error(f"Error type: {type(e).__name__}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            # Fallback на regex
            import re
            case_number_pattern = r'\d+/\d+/\d+'
            match = re.search(case_number_pattern, query)
            if match:
                logger.info(f"Fallback to regex: extracted case number {match.group(0)}")
                return match.group(0)
            return None
    
    async def _classify_query_llm(self, query: str) -> Dict[str, Any]:
        """
        Классификация запроса через LLM для определения источника данных
        
        Args:
            query: Запрос пользователя
            
        Returns:
            Информация о типе запроса и необходимых источниках
        """
        try:
            # Используем кэш для классификации
            cache_key = None
            if self.cache_service:
                cache_key = self.cache_service._generate_key(
                    "query_classification",
                    query
                )
                cached = await self.cache_service.get(cache_key)
                if cached is not None:
                    logger.debug(f"Query classification cache hit for: {query[:50]}...")
                    return cached
            
            # Получаем OpenAI провайдер для классификации
            # Используем модель gpt-4o-mini
            try:
                provider = LLMProviderFactory.get_provider(
                    provider_type=LLMProvider.OPENAI,
                    model="gpt-4o-mini"
                )
            except Exception as provider_error:
                logger.warning(f"Failed to get OpenAI provider, trying default model: {provider_error}")
                # Fallback на дефолтную модель
                provider = LLMProviderFactory.get_provider(
                    provider_type=LLMProvider.OPENAI
                )
            
            # Упрощенный промпт для избежания ошибок 400
            # Экранируем запрос пользователя для безопасности и ограничиваем длину
            safe_query = query.replace('"', '\\"').replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')[:300]
            
            # Если запрос слишком длинный, обрезаем его
            if len(query) > 300:
                logger.warning(f"Query too long ({len(query)} chars), truncating to 300")
                safe_query = safe_query[:300] + "..."
            
            classification_prompt = f"""Analyze user query and return JSON only.

Query: {safe_query}

Return JSON with:
- use_law: true if about court cases, laws, case numbers (format: number/number/number like 686/32982/23)
- use_rag: true if about user documents, uploaded files, or document numbers without slashes (like "document 686")
- query_type: "legal", "user_documents", "document_text", "list_documents", "delete_documents", or "general"
- has_case_number: true ONLY if query contains case number in format number/number/number (with slashes, like 686/32982/23)
- is_document_text_query: true if asking for document text (not court case)

IMPORTANT:
- "покажи документ 686" = use_rag=true, has_case_number=false (user document, not court case)
- "покажи дело 686/32982/23" = use_law=true, has_case_number=true (court case with slashes)
- Numbers without slashes are user documents, numbers with slashes are court cases

Example: {{"use_law": true, "use_rag": false, "query_type": "legal", "has_case_number": true, "is_document_text_query": false}}"""

            # Проверяем что контент не пустой
            system_content = "You are a query classifier. Return only valid JSON, no other text."
            if not system_content or not classification_prompt:
                logger.warning("Empty prompt, using regex fallback")
                return self._classify_query_regex(query)
            
            messages = [
                LLMMessage(role="system", content=system_content),
                LLMMessage(role="user", content=classification_prompt)
            ]
            
            try:
                logger.debug(f"Classifying query via OpenAI: {query[:100]}...")
                response = await provider.generate(
                    messages=messages,
                    temperature=0.1,  # Низкая температура для стабильности
                    max_tokens=200   # Короткий ответ
                )
                logger.debug(f"OpenAI classification successful")
            except httpx.HTTPStatusError as http_error:
                error_detail = ""
                if hasattr(http_error, 'response') and http_error.response is not None:
                    try:
                        error_detail = http_error.response.text[:500] if hasattr(http_error.response, 'text') else str(http_error.response.content[:500])
                    except:
                        error_detail = str(http_error)
                
                logger.error(f"OpenAI API HTTP error during classification: {http_error.response.status_code if hasattr(http_error, 'response') else 'unknown'}")
                logger.error(f"Error details: {error_detail}")
                logger.error(f"Request model: {provider.model}, base_url: {provider.base_url}")
                logger.error(f"Query length: {len(query)}, prompt length: {len(classification_prompt)}")
                # Fallback на regex при ошибке API
                return self._classify_query_regex(query)
            except Exception as api_error:
                logger.error(f"OpenAI API error during classification: {api_error}")
                logger.error(f"Error type: {type(api_error).__name__}")
                logger.debug(f"Request payload: model={provider.model}, messages_count={len(messages)}")
                # Fallback на regex при ошибке API
                return self._classify_query_regex(query)
            
            import json
            # Парсим JSON ответ
            response_text = response.content.strip()
            # Убираем markdown код блоки если есть
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
                response_text = response_text.strip()
            
            classification = json.loads(response_text)
            
            # Валидация и нормализация
            result = {
                "use_rag": bool(classification.get("use_rag", False)),
                "use_law": bool(classification.get("use_law", False)),
                "query_type": classification.get("query_type", "general"),
                "has_case_number": bool(classification.get("has_case_number", False)),
                "is_document_text_query": bool(classification.get("is_document_text_query", False)),
                "is_list_query": classification.get("query_type") == "list_documents",
                "is_delete_query": classification.get("query_type") == "delete_documents",
                "document_number": None
            }
            
            # Извлекаем номер документа если это запрос о документе пользователя
            if result["is_document_text_query"] and not result["has_case_number"]:
                import re
                numbers = re.findall(r'\d+', query)
                if numbers:
                    try:
                        result["document_number"] = int(numbers[0])
                    except ValueError:
                        pass
            
            # Сохраняем в кэш
            if self.cache_service and cache_key:
                await self.cache_service.set(cache_key, result, ttl=3600)  # 1 час
            
            logger.debug(f"Query classified via LLM: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error classifying query via LLM: {e}, falling back to regex")
            # Fallback на regex классификацию при ошибке
            return self._classify_query_regex(query)
    
    def _classify_query_regex(self, query: str) -> Dict[str, Any]:
        """
        Классификация запроса через regex (fallback метод)
        
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
            "які файли завантажив", "видишь что загрузил", "бачиш що завантажив",
            "в документах", "из документов", "з документів",
            "в моих документах", "в моїх документах", "в загруженных документах",
            "в завантажених документах", "номер дела в документах", "номер справи в документах",
            "номер дела из документов", "номер справи з документів", "в моих файлах", "в моїх файлах",
            "какой номер", "який номер", "найди номер", "знайди номер",
            "найти номер", "знайти номер", "есть номер", "є номер",
            "против.*в документах", "проти.*в документах", "против.*из документов",
            "проти.*з документів", "против.*в моих", "проти.*в моїх"
        ]
        
        # Фразы, которые указывают на запрос о списке документов (нужно вернуть все документы)
        list_document_phrases = [
            "какие документы", "які документи", "какие документы я", "які документи я",
            "какие документы ты видишь", "які документи ти бачиш", "какие документы видишь",
            "что я загрузил", "що я завантажив", "какие файлы загрузил", "які файли завантажив",
            "список документов", "список файлов", "перелік документів", "перелік файлів"
        ]
        
        # Фразы для удаления документов
        delete_document_phrases = [
            "удали документ", "видали документ", "удалить документ", "видалити документ",
            "удали файл", "видали файл", "удалить файл", "видалити файл",
            "удали все документы", "видали всі документи", "удалить все документы", "видалити всі документи",
            "удали все файлы", "видали всі файли", "удалить все файлы", "видалити всі файли",
            "очисти документы", "очистити документи", "очистить документы", "очистити документи",
            "удали все", "видали все", "удалить все", "видалити все",
            "очисти все", "очистити все", "очистить все", "очистити все"
        ]
        
        # Фразы для запроса текста конкретного документа
        document_text_phrases = [
            "текст документа", "текст документу", "содержимое документа", "зміст документу",
            "покажи документ", "покажи документ", "покажи файл", "покажи файл",
            "покажи текст", "покажи текст", "покажи содержимое", "покажи зміст",
            "выведи документ", "виведи документ", "выведи текст", "виведи текст",
            "покажи мне документ", "покажи мені документ", "покажи мне текст", "покажи мені текст",
            "содержание документа", "зміст документу", "полный текст", "повний текст"
        ]
        
        use_law = any(keyword in query_lower for keyword in law_keywords)
        use_rag = any(keyword in query_lower for keyword in document_keywords)
        
        # Проверяем специальные фразы про документы пользователя (с поддержкой regex)
        is_user_document_query = False
        for phrase in user_document_phrases:
            if '.*' in phrase:
                # Регулярное выражение
                pattern = phrase.replace('.*', '.*')
                if re.search(pattern, query_lower):
                    is_user_document_query = True
                    logger.debug(f"User document query matched by regex pattern: {phrase}")
                    break
            elif phrase in query_lower:
                is_user_document_query = True
                logger.debug(f"User document query matched by phrase: {phrase}")
                break
        
        is_list_documents_query = any(phrase in query_lower for phrase in list_document_phrases)
        is_delete_query = any(phrase in query_lower for phrase in delete_document_phrases)
        is_document_text_query = any(phrase in query_lower for phrase in document_text_phrases)
        
        # Проверяем, есть ли в запросе номер дела (формат: число/число/число)
        import re
        case_number_pattern = r'\d+/\d+/\d+'
        case_number_match = re.search(case_number_pattern, query)
        has_case_number = case_number_match is not None
        
        # Ключевые слова, указывающие на судебное дело
        case_keywords = [
            "справа", "дело", "справа №", "дело №", "справа номер", "дело номер",
            "судова справа", "судебное дело", "рішення по справі", "решение по делу"
        ]
        is_case_query = has_case_number or any(keyword in query_lower for keyword in case_keywords)
        
        # Извлекаем номер документа из запроса (если есть)
        document_number = None
        if is_document_text_query:
            # Ищем числа в запросе (номер документа)
            numbers = re.findall(r'\d+', query)
            if numbers:
                try:
                    document_number = int(numbers[0])
                except ValueError:
                    pass
        
        # Если запрос явно про документы пользователя (например, "номер дела в документах"),
        # приоритет RAG, даже если есть упоминания о судебных делах
        if is_user_document_query:
            use_rag = True
            use_law = False  # Если явно про документы пользователя, не используем MCP Law
            logger.info(f"User document query detected: '{query}' - using RAG only")
        # Если в запросе есть номер дела в формате число/число/число, это точно запрос о судебном деле
        elif has_case_number:
            use_law = True
            use_rag = False  # Номер дела - это точно не документ пользователя
            logger.info(f"Detected case number in query: {case_number_match.group(0)}")
        # Если есть ключевые слова о судебных делах, используем MCP Law
        elif is_case_query:
            use_law = True
            # Если нет явных указаний на документы пользователя, не используем RAG
            if not use_rag:
                use_rag = False
        # Если есть явные указания на документы, приоритет RAG
        elif use_rag and not use_law:
            use_law = False  # Не используем MCP Law если запрос про документы
        # Если нет явных указаний, используем оба источника
        elif not use_law and not use_rag:
            use_law = True
            use_rag = True
        
        # Определяем тип запроса
        if is_delete_query:
            query_type = "delete_documents"
        elif is_document_text_query:
            query_type = "document_text"
        elif is_list_documents_query:
            query_type = "list_documents"
        elif is_user_document_query:
            query_type = "user_documents"
        elif use_law:
            query_type = "legal"
        else:
            query_type = "document"
        
        return {
            "use_rag": use_rag,
            "use_law": use_law,
            "query_type": query_type,
            "has_case_number": has_case_number,
            "is_list_query": is_list_documents_query,
            "is_delete_query": is_delete_query,
            "is_document_text_query": is_document_text_query,
            "document_number": document_number
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
        # Проверяем, является ли это запросом на полный текст дела
        # Если да, возвращаем текст напрямую из MCP, минуя LLM
        import re
        case_number_pattern = r'\d+/\d+/\d+'
        case_number_match = re.search(case_number_pattern, query)
        has_case_number = case_number_match is not None
        
        # Проверяем, запрашивается ли полный текст дела
        full_text_keywords = [
            "полный текст", "повний текст", "полный текст дела", "повний текст справи",
            "весь текст", "весь текст дела", "весь текст справи",
            "текст дела", "текст справи", "покажи текст дела", "покажи текст справи",
            "дай полный текст", "дай мне полный текст", "дай текст дела", "дай мне текст дела",
            "покажи полный текст", "покажи мне полный текст", "покажи весь текст"
        ]
        is_full_text_request = any(keyword in query.lower() for keyword in full_text_keywords)
        
        # Если это запрос на полный текст дела с номером, возвращаем напрямую из MCP
        if has_case_number and is_full_text_request:
            case_number = case_number_match.group(0)
            logger.info(f"Direct full text request detected for case {case_number}, bypassing LLM")
            
            try:
                # Получаем детали дела по номеру
                details = await self.law_client.get_case_details(case_number=case_number)
                if details and details.get('success'):
                    cases_list = details.get('cases', [])
                    if cases_list:
                        case = cases_list[0]
                        doc_id = case.get('doc_id') or case.get('id')
                        
                        if doc_id:
                            # Получаем полный текст
                            full_text_data = await self.law_client.get_case_full_text(str(doc_id))
                            if full_text_data and full_text_data.get('success'):
                                text = full_text_data.get('text', '')
                                if text:
                                    # Форматируем ответ для клиента
                                    title = case.get('title', 'N/A')
                                    answer = f"Вот полный текст дела № {case_number}:\n\n"
                                    answer += f"Заголовок: {title}\n\n"
                                    answer += f"Текст решения:\n{text}\n"
                                    
                                    return {
                                        "answer": answer,
                                        "sources": ["MCP_Law"],
                                        "model": None,  # Не использовали LLM
                                        "metadata": {
                                            "used_rag": False,
                                            "used_law": True,
                                            "bypassed_llm": True,
                                            "case_number": case_number,
                                            "doc_id": str(doc_id)
                                        }
                                    }
            
            except Exception as e:
                logger.error(f"Error getting full text directly from MCP: {e}")
                return {
                    "answer": f"Ошибка при получении полного текста дела: {str(e)}",
                    "sources": [],
                    "error": str(e)
                }
        
        # Проверка наличия документов в RAG
        has_docs = await self.rag_service.has_documents()
        
        # По умолчанию используем оба источника для лучшего контекста
        if use_law is None:
            use_law = True
        if use_rag is None:
            use_rag = True if has_docs else False  # RAG только если есть документы
        
        # Если в запросе есть номер дела, гарантируем использование MCP Law
        if has_case_number:
            use_law = True
            logger.info(f"Case number detected, ensuring MCP Law is enabled: {query}")
        
        # Классификация запроса через LLM
        classification = await self._classify_query_llm(query)
        logger.info(f"LLM classification: query_type={classification.get('query_type')}, use_rag={classification.get('use_rag')}, use_law={classification.get('use_law')}")
        
        # Если это запрос на удаление, обрабатываем его сразу
        if classification.get("is_delete_query"):
            logger.info("Delete documents query detected")
            query_lower = query.lower()
            
            # Проверяем, удалить все или конкретный документ
            delete_all_keywords = ["все", "all", "всі", "все документы", "всі документи", "все файлы", "всі файли"]
            delete_all = any(keyword in query_lower for keyword in delete_all_keywords)
            
            if delete_all:
                # Удаляем все документы
                documents = await self.rag_service.list_documents()
                if not documents:
                    return {
                        "answer": "Нет документов для удаления.",
                        "sources": [],
                        "metadata": {
                            "action": "delete_all",
                            "deleted_count": 0,
                            "total_count": 0
                        }
                    }
                
                deleted_count = 0
                errors = []
                for doc in documents:
                    filename = doc.get('filename') or doc.get('file_path')
                    if filename:
                        try:
                            deleted = await self.rag_service.delete_document(filename)
                            if deleted:
                                deleted_count += 1
                        except Exception as e:
                            errors.append(f"Ошибка при удалении '{filename}': {str(e)}")
                            logger.error(f"Error deleting document '{filename}': {e}")
                
                answer = f"Удалено {deleted_count} из {len(documents)} документов."
                if errors:
                    answer += f"\nОшибки: {len(errors)}"
                
                return {
                    "answer": answer,
                    "sources": ["RAG"],
                    "metadata": {
                        "action": "delete_all",
                        "deleted_count": deleted_count,
                        "total_count": len(documents),
                        "errors": errors if errors else None
                    }
                }
            else:
                # Пытаемся найти конкретный документ для удаления
                documents = await self.rag_service.list_documents()
                if not documents:
                    return {
                        "answer": "Нет документов для удаления.",
                        "sources": [],
                        "metadata": {
                            "action": "delete_one",
                            "deleted": False
                        }
                    }
                
                # Ищем документ по части имени в запросе
                query_words = query_lower.split()
                matched_doc = None
                for doc in documents:
                    filename = (doc.get('filename') or doc.get('file_path', '')).lower()
                    # Проверяем, содержит ли имя файла слова из запроса
                    if any(word in filename for word in query_words if len(word) > 3):
                        matched_doc = doc
                        break
                
                if matched_doc:
                    filename = matched_doc.get('filename') or matched_doc.get('file_path')
                    try:
                        deleted = await self.rag_service.delete_document(filename)
                        if deleted:
                            return {
                                "answer": f"Документ '{filename}' успешно удален.",
                                "sources": ["RAG"],
                                "metadata": {
                                    "action": "delete_one",
                                    "deleted": True,
                                    "filename": filename
                                }
                            }
                        else:
                            return {
                                "answer": f"Не удалось удалить документ '{filename}'.",
                                "sources": ["RAG"],
                                "metadata": {
                                    "action": "delete_one",
                                    "deleted": False,
                                    "filename": filename
                                }
                            }
                    except Exception as e:
                        logger.error(f"Error deleting document '{filename}': {e}")
                        return {
                            "answer": f"Ошибка при удалении документа '{filename}': {str(e)}",
                            "sources": ["RAG"],
                            "metadata": {
                                "action": "delete_one",
                                "deleted": False,
                                "filename": filename,
                                "error": str(e)
                            }
                        }
                else:
                    # Не нашли документ, возвращаем список для выбора
                    doc_list = "\n".join([f"- {doc.get('filename') or doc.get('file_path')}" for doc in documents[:10]])
                    return {
                        "answer": f"Не удалось определить, какой документ удалить. Пожалуйста, укажите точное имя файла.\n\nДоступные документы:\n{doc_list}",
                        "sources": ["RAG"],
                        "metadata": {
                            "action": "delete_one",
                            "deleted": False,
                            "available_documents": [doc.get('filename') or doc.get('file_path') for doc in documents]
                        }
                    }
        
        # Если это запрос о тексте конкретного документа пользователя, обрабатываем его отдельно
        # НО только если это НЕ запрос о судебном деле
        classification_has_case = classification.get("has_case_number", False)
        if classification and classification.get("is_document_text_query") and has_docs and not (has_case_number or classification_has_case):
            logger.info("Document text query detected, getting full document text (using both RAG and MCP Law for context)")
            
            # Получаем список документов
            documents = await self.rag_service.list_documents()
            if not documents:
                return {
                    "answer": "Нет загруженных документов.",
                    "sources": [],
                    "metadata": {
                        "used_rag": True,
                        "used_law": False
                    }
                }
            
            # Определяем, какой документ нужен
            target_document = None
            document_number = classification.get("document_number")
            
            if document_number:
                # Ищем документ по номеру (индекс начинается с 1)
                if 1 <= document_number <= len(documents):
                    target_document = documents[document_number - 1]
                else:
                    return {
                        "answer": f"Документ с номером {document_number} не найден. Всего загружено документов: {len(documents)}.",
                        "sources": ["RAG"],
                        "metadata": {
                            "used_rag": True,
                            "used_law": False,
                            "total_documents": len(documents)
                        }
                    }
            else:
                # Пытаемся найти документ по имени из запроса
                query_lower = query.lower()
                for doc in documents:
                    filename = (doc.get('filename') or doc.get('file_path', '')).lower()
                    # Проверяем, содержит ли имя файла слова из запроса
                    query_words = [w for w in query_lower.split() if len(w) > 3]
                    if any(word in filename for word in query_words):
                        target_document = doc
                        break
                
                # Если не нашли, берем первый документ
                if not target_document and documents:
                    target_document = documents[0]
            
            if target_document:
                filename = target_document.get('filename') or target_document.get('file_path')
                file_path = target_document.get('file_path') or filename
                
                logger.info(f"Looking for document chunks: filename='{filename}', file_path='{file_path}'")
                
                # Пробуем получить чанки по разным вариантам имени файла
                chunks = await self.rag_service.get_document_chunks(filename)
                
                # Если не нашли, пробуем по file_path
                if not chunks and file_path and file_path != filename:
                    logger.debug(f"Chunks not found by filename, trying file_path: '{file_path}'")
                    chunks = await self.rag_service.get_document_chunks(file_path)
                
                # Если все еще не нашли, пробуем по базовому имени файла
                if not chunks:
                    import os
                    basename = os.path.basename(filename)
                    if basename != filename:
                        logger.debug(f"Chunks not found, trying basename: '{basename}'")
                        chunks = await self.rag_service.get_document_chunks(basename)
                
                # Если все еще не нашли, пробуем с нормализованным расширением
                if not chunks:
                    import os
                    basename = os.path.basename(filename)
                    # Пробуем с нижним регистром расширения
                    if basename.upper().endswith('.PDF'):
                        basename_lower = basename[:-4] + '.pdf'
                        logger.debug(f"Chunks not found, trying lowercase extension: '{basename_lower}'")
                        chunks = await self.rag_service.get_document_chunks(basename_lower)
                
                logger.info(f"Found {len(chunks)} chunks for document '{filename}'")
                
                if chunks:
                    # Объединяем все чанки в полный текст
                    full_text = "\n\n".join([chunk.get('text', '') for chunk in chunks if chunk.get('text')])
                    
                    if full_text:
                        return {
                            "answer": f"=== Полный текст документа: {filename} ===\n\n{full_text}",
                            "sources": ["RAG"],
                            "metadata": {
                                "used_rag": True,
                                "used_law": False,
                                "document_filename": filename,
                                "chunks_count": len(chunks),
                                "text_length": len(full_text)
                            }
                        }
                    else:
                        logger.warning(f"Document '{filename}' found but text is empty")
                        return {
                            "answer": f"Документ '{filename}' найден, но текст не извлечен или пуст.",
                            "sources": ["RAG"],
                            "metadata": {
                                "used_rag": True,
                                "used_law": False,
                                "document_filename": filename
                            }
                        }
                else:
                    logger.warning(f"Document '{filename}' found in list but chunks not found. Trying to find by searching all documents...")
                    # Пробуем найти документ в списке всех документов по имени
                    all_docs = await self.rag_service.list_documents()
                    matching_docs = []
                    import os
                    target_basename = os.path.basename(filename).lower()
                    for doc in all_docs:
                        doc_filename = (doc.get('filename') or doc.get('file_path', '')).lower()
                        doc_basename = os.path.basename(doc_filename).lower()
                        if target_basename == doc_basename:
                            matching_docs.append(doc)
                    
                    if matching_docs:
                        # Пробуем получить чанки для найденного документа
                        for doc in matching_docs:
                            alt_filename = doc.get('filename') or doc.get('file_path')
                            logger.debug(f"Trying alternative filename: '{alt_filename}'")
                            chunks = await self.rag_service.get_document_chunks(alt_filename)
                            if chunks:
                                full_text = "\n\n".join([chunk.get('text', '') for chunk in chunks if chunk.get('text')])
                                if full_text:
                                    return {
                                        "answer": f"=== Полный текст документа: {alt_filename} ===\n\n{full_text}",
                                        "sources": ["RAG"],
                                        "metadata": {
                                            "used_rag": True,
                                            "used_law": False,
                                            "document_filename": alt_filename,
                                            "chunks_count": len(chunks),
                                            "text_length": len(full_text)
                                        }
                                    }
                    
                    return {
                        "answer": f"Документ '{filename}' найден в списке, но чанки не найдены. Возможно, документ еще обрабатывается или возникла проблема с индексацией. Попробуйте перезагрузить документ.",
                        "sources": ["RAG"],
                        "metadata": {
                            "used_rag": True,
                            "used_law": False,
                            "document_filename": filename,
                            "document_file_path": file_path
                        }
                    }
            else:
                # Не нашли документ, возвращаем список
                doc_list = "\n".join([f"{i+1}. {doc.get('filename') or doc.get('file_path')}" for i, doc in enumerate(documents[:10])])
                return {
                    "answer": f"Не удалось определить, какой документ показать. Пожалуйста, укажите номер документа (1-{len(documents)}) или имя файла.\n\nДоступные документы:\n{doc_list}",
                    "sources": ["RAG"],
                    "metadata": {
                        "used_rag": True,
                        "used_law": False,
                        "available_documents": [doc.get('filename') or doc.get('file_path') for doc in documents]
                    }
                }
        
        # Специальная обработка для запросов о документах пользователя - обрабатываем каждый документ отдельно через LLM
        if classification and use_rag and has_docs and classification.get("query_type") == "user_documents":
            logger.info(f"User documents query detected, processing each document separately through LLM: '{query[:100]}...'")
            
            documents = await self.rag_service.list_documents()
            if not documents:
                return {
                    "answer": "Нет загруженных документов для поиска.",
                    "sources": ["RAG"],
                    "metadata": {
                        "used_rag": True,
                        "used_law": False,
                        "documents_processed": 0
                    }
                }
            
            logger.info(f"Found {len(documents)} documents, processing each one separately through LLM")
            
            # Получаем LLM провайдер
            llm = LLMProviderFactory.get_provider(llm_provider, model)
            
            # Системный промпт для поиска в документе
            doc_search_prompt = """Ты - помощник для поиска информации в документах.
Пользователь задал вопрос. В контексте предоставлен полный текст одного документа.
Твоя задача - найти ответ на вопрос пользователя в этом документе.

Если ты нашел ответ - укажи его четко и конкретно.
Если ответа нет в этом документе - ответь "Не найдено в этом документе".

Отвечай кратко и по делу."""
            
            all_results = []
            found_answer = None
            
            # Обрабатываем каждый документ отдельно
            for i, doc in enumerate(documents, 1):
                filename = doc.get('filename') or doc.get('file_path', 'Unknown')
                logger.info(f"Processing document {i}/{len(documents)}: {filename}")
                
                # Получаем все чанки документа (полный текст)
                chunks = await self.rag_service.get_document_chunks(filename)
                if not chunks:
                    logger.warning(f"No chunks found for document {i}: {filename}")
                    continue
                
                # Объединяем все чанки в полный текст
                full_text = "\n\n".join([chunk.get('text', '') for chunk in chunks if chunk.get('text')])
                
                if not full_text or not full_text.strip():
                    logger.warning(f"Empty text for document {i}: {filename}")
                    continue
                
                # Ограничиваем длину документа для одного запроса (чтобы не превысить лимиты)
                max_doc_length = 80000  # ~80K символов для одного документа
                if len(full_text) > max_doc_length:
                    logger.warning(f"Document '{filename}' too long ({len(full_text)} chars), truncating to {max_doc_length}")
                    full_text = full_text[:max_doc_length] + "\n\n[Текст документа обрезан из-за ограничений длины]"
                
                # Формируем промпт для LLM
                doc_context = f"=== Полный текст документа {i}: {filename} ===\n\n{full_text}"
                user_message = f"{query}\n\n{doc_context}"
                
                messages = [
                    LLMMessage(role="system", content=doc_search_prompt),
                    LLMMessage(role="user", content=user_message)
                ]
                
                try:
                    # Отправляем запрос в LLM для этого документа
                    logger.info(f"Sending query to LLM for document {i}/{len(documents)}: {filename}")
                    response = await llm.generate(messages, temperature=0.3, max_tokens=2000)
                    answer = response.content.strip()
                    
                    logger.info(f"LLM response for document {i} '{filename}': {answer[:200]}...")
                    
                    # Проверяем, содержит ли ответ полезную информацию (не "не найдено")
                    if answer and answer.lower() not in ["не найдено в этом документе", "не найдено", "not found", "немає в цьому документі"]:
                        if not found_answer:
                            found_answer = {
                                "document": filename,
                                "document_number": i,
                                "answer": answer,
                                "total_documents": len(documents)
                            }
                            logger.info(f"✅ Answer found in document {i}: {filename}")
                        all_results.append({
                            "document": filename,
                            "document_number": i,
                            "answer": answer,
                            "model": response.model,
                            "usage": response.usage
                        })
                    else:
                        logger.debug(f"No answer found in document {i}: {filename}")
                        all_results.append({
                            "document": filename,
                            "document_number": i,
                            "answer": "Не найдено в этом документе"
                        })
                
                except Exception as e:
                    logger.error(f"Error processing document {i} '{filename}' through LLM: {e}")
                    all_results.append({
                        "document": filename,
                        "document_number": i,
                        "answer": f"Ошибка при обработке: {str(e)}"
                    })
            
            # Формируем финальный ответ
            result_model = None
            result_usage = None
            
            if found_answer:
                # Если нашли ответ, возвращаем его, но также упоминаем, что проверили все документы
                result_text = f"Найдено в документе {found_answer['document_number']} ({found_answer['document']}):\n\n{found_answer['answer']}"
                if len(all_results) > 1:
                    result_text += f"\n\n(Проверено документов: {len(documents)})"
                # Получаем model и usage из последнего успешного ответа
                for result in all_results:
                    if result.get('model'):
                        result_model = result.get('model')
                        result_usage = result.get('usage')
                        break
            else:
                # Если не нашли, сообщаем что проверили все документы
                result_text = f"Проверены все {len(documents)} документов, но информация не найдена.\n\n"
                result_text += "Проверенные документы:\n"
                for result in all_results:
                    result_text += f"- {result['document']}\n"
            
            return {
                "answer": result_text,
                "sources": ["RAG"],
                "model": result_model,
                "usage": result_usage,
                "metadata": {
                    "used_rag": True,
                    "used_law": False,
                    "documents_processed": len(documents),
                    "answer_found": found_answer is not None,
                    "all_results": all_results
                }
            }
        
        # Если документов нет, гарантируем использование MCP Law
        if not use_rag and use_law is None:
            use_law = True
        
        # Параллельный сбор контекста из разных источников
        contexts = []
        sources = []
        errors = []
        
        async def get_documents_summary():
            """Получение краткой информации о всех загруженных документах"""
            if not use_rag or not has_docs:
                return None
            try:
                documents = await self.rag_service.list_documents()
                if documents:
                    doc_list = []
                    for i, doc in enumerate(documents, 1):
                        filename = doc.get('filename') or doc.get('file_path', 'Unknown')
                        doc_type = doc.get('document_type') or doc.get('metadata', {}).get('document_type', 'unknown')
                        chunks_count = doc.get('chunks_count', 0)
                        
                        doc_info = f"{i}. {filename}"
                        if doc_type != 'unknown':
                            doc_info += f" (тип: {doc_type})"
                        if chunks_count > 0:
                            doc_info += f" - {chunks_count} частей"
                        doc_list.append(doc_info)
                    
                    summary = f"=== Информация о загруженных документах ===\n"
                    summary += f"Всего загружено документов: {len(documents)}\n\n"
                    summary += "Список документов:\n" + "\n".join(doc_list)
                    return summary
            except Exception as e:
                logger.error(f"Error getting documents summary: {e}")
                return None
        
        async def get_rag_context():
            """Получение RAG контекста"""
            if not use_rag:
                return None
            try:
                # Если это запрос о списке документов, получаем все документы с содержимым
                if classification and classification.get("is_list_query"):
                    logger.info("List documents query detected, getting all documents")
                    documents = await self.rag_service.list_documents()
                    if documents:
                        context_parts = []
                        for i, doc in enumerate(documents, 1):
                            filename = doc.get('filename') or doc.get('file_path', 'Unknown')
                            doc_type = doc.get('document_type') or doc.get('metadata', {}).get('document_type', 'unknown')
                            chunks_count = doc.get('chunks_count', 0)
                            
                            # Получаем первые чанки документа для контекста
                            chunks = await self.rag_service.get_document_chunks(filename)
                            if chunks:
                                # Берем первые 2-3 чанка для каждого документа
                                preview_chunks = chunks[:3]
                                preview_text = "\n".join([chunk.get('text', '')[:500] for chunk in preview_chunks if chunk.get('text')])
                                
                                doc_info = f"Документ {i}: {filename}\n"
                                if doc_type != 'unknown':
                                    doc_info += f"Тип: {doc_type}\n"
                                doc_info += f"Количество частей: {chunks_count}\n"
                                if preview_text:
                                    doc_info += f"Содержание (фрагмент):\n{preview_text}\n"
                                context_parts.append(doc_info)
                            else:
                                # Если чанков нет, просто добавляем информацию о документе
                                doc_info = f"Документ {i}: {filename}\n"
                                if doc_type != 'unknown':
                                    doc_info += f"Тип: {doc_type}\n"
                                context_parts.append(doc_info)
                        
                        if context_parts:
                            return f"=== Список всех загруженных документов ===\n\n" + "\n\n".join(context_parts)
                    return None
                # Для user_documents запросов обработка происходит в process_query до вызова get_rag_context
                # Здесь возвращаем None, так как обработка уже выполнена
                if classification and (classification.get("query_type") == "user_documents" or classification.get("query_type") == "document_text"):
                    logger.debug("User documents query - processing already done in process_query, skipping get_rag_context")
                    return None
                else:
                    # Обычный поиск - увеличиваем top_k для получения большего контекста
                    # Ограничиваем top_k чтобы не превысить лимиты токенов
                    rag_context = await self.rag_service.get_context(query, top_k=10)
                    if rag_context:
                        # Ограничиваем размер RAG контекста
                        max_rag_context_length = 5000  # ~5K символов для RAG контекста
                        if len(rag_context) > max_rag_context_length:
                            logger.warning(f"RAG context too long ({len(rag_context)} chars), truncating to {max_rag_context_length}")
                            rag_context = rag_context[:max_rag_context_length] + "\n\n[Контекст обрезан из-за ограничений длины]"
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
                # Извлекаем номер дела через OpenAI
                case_number = await self._extract_case_number_llm(query)
                
                # Проверяем, запрашивается ли полный текст дела
                full_text_keywords = [
                    "полный текст", "повний текст", "полный текст дела", "повний текст справи",
                    "весь текст", "весь текст дела", "весь текст справи",
                    "текст дела", "текст справи", "покажи текст дела", "покажи текст справи",
                    "дай полный текст", "дай мне полный текст", "дай текст дела", "дай мне текст дела",
                    "покажи полный текст", "покажи мне полный текст", "покажи весь текст"
                ]
                is_full_text_request = any(keyword in query.lower() for keyword in full_text_keywords)
                
                # Если есть номер дела, пытаемся получить детали или полный текст
                if case_number:
                    logger.info(f"Detected case number in query: {case_number}")
                    
                    # Если запрашивается полный текст, получаем его
                    if is_full_text_request:
                        # Сначала получаем детали дела по номеру
                        details = await self.law_client.get_case_details(case_number=case_number)
                        if details and details.get('success'):
                            cases_list = details.get('cases', [])
                            if cases_list:
                                # Берем первое дело из списка
                                case = cases_list[0]
                                doc_id = case.get('doc_id') or case.get('id')
                                
                                if doc_id:
                                    # Получаем полный текст
                                    full_text_data = await self.law_client.get_case_full_text(str(doc_id))
                                    if full_text_data and full_text_data.get('success'):
                                        text = full_text_data.get('text', '')
                                        if text:
                                            # Для запросов на полный текст увеличиваем лимит, чтобы передать больше текста
                                            # gpt-4o-mini имеет лимит 128K токенов (~100K символов)
                                            # Оставляем место для system prompt (~2K) и user query (~1K), итого ~97K для контекста
                                            max_text_length = 95000  # ~95K символов для полного текста (увеличенный лимит)
                                            original_length = len(text)
                                            if len(text) > max_text_length:
                                                logger.warning(f"Full text too long ({original_length} chars), truncating to {max_text_length}")
                                                text = text[:max_text_length] + "\n\n[Текст обрезан из-за ограничений длины. Полный текст доступен по запросу.]"
                                            else:
                                                logger.info(f"Full text retrieved: {original_length} chars for case {case_number}")
                                            
                                            law_context = f"=== Полный текст дела № {case_number} ===\n\n"
                                            law_context += f"Заголовок: {case.get('title', 'N/A')}\n\n"
                                            law_context += f"Текст решения:\n{text}\n"
                                            logger.debug(f"Law context length: {len(law_context)} chars")
                                            return law_context
                    
                    # Если полный текст не запрашивается или не получен, возвращаем детали
                    details = await self.law_client.get_case_details(case_number=case_number)
                    if details and details.get('success'):
                        cases_list = details.get('cases', [])
                        if cases_list:
                            law_context = f"=== Детали дела № {case_number} ===\n"
                            for i, case in enumerate(cases_list[:3], 1):
                                law_context += f"\n{i}. {case.get('title', 'Дело')}\n"
                                if 'description' in case:
                                    law_context += f"   {case['description']}\n"
                                if 'resolution' in case:
                                    law_context += f"   Резолютивная часть: {case['resolution']}\n"
                            return law_context
                
                # Обычный поиск дел
                cases = await self.law_client.search_cases(query, limit=5)
                if cases:
                    law_context = "=== Судебная практика ===\n"
                    for i, case in enumerate(cases[:3], 1):
                        law_context += f"{i}. {case.get('title', 'Дело')}\n"
                        case_num = case.get('cause_num', '')
                        if case_num:
                            law_context += f"   Номер дела: {case_num}\n"
                        if 'description' in case:
                            law_context += f"   {case['description'][:200]}...\n"
                        # Если запрашивается полный текст и есть doc_id, получаем его
                        if is_full_text_request:
                            doc_id = case.get('doc_id') or case.get('id')
                            if doc_id:
                                full_text_data = await self.law_client.get_case_full_text(str(doc_id))
                                if full_text_data and full_text_data.get('success'):
                                    text = full_text_data.get('text', '')
                                    if text:
                                        # Ограничиваем размер для preview
                                        preview_length = 2000
                                        if len(text) > preview_length:
                                            law_context += f"\n   === Полный текст дела (фрагмент) ===\n{text[:preview_length]}...\n[Полный текст слишком длинный, показан только фрагмент]\n"
                                        else:
                                            law_context += f"\n   === Полный текст дела ===\n{text}\n"
                    return law_context
            except Exception as e:
                logger.error(f"Error getting Law MCP context: {e}")
                errors.append(f"Law MCP error: {str(e)}")
                return None
        
        # Получаем информацию о всех документах (всегда, если есть документы)
        documents_summary = await get_documents_summary()
        
        # Параллельное выполнение
        rag_result, law_result = await asyncio.gather(
            get_rag_context(),
            get_law_context(),
            return_exceptions=True
        )
        
        # Добавляем информацию о всех документах в начало контекста
        if documents_summary:
            contexts.insert(0, documents_summary)
        
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
        
        if query_type == "user_documents" or query_type == "document_text":
            system_prompt = """Ты - юридический ассистент, который помогает пользователям с их загруженными документами.
ВАЖНО: Пользователь спрашивает про СВОИ загруженные документы. 

В контексте тебе предоставлена информация:
1. В разделе "=== Информация о загруженных документах ===" - полный список всех загруженных документов с их именами и количеством. Ты ВСЕГДА знаешь, сколько документов загружено и как они называются.
2. В разделе "=== Контекст из документов ===" - релевантные фрагменты из документов по запросу пользователя.
3. В разделе "=== Контекст из документов (полные тексты) ===" - ПОЛНЫЕ ТЕКСТЫ всех загруженных документов. Это означает, что у тебя есть доступ ко всему содержимому документов, и ты можешь найти любую информацию из них, включая номера дел, даты, имена, суммы и т.д.
4. Если пользователь просит показать полный текст документа (например, "текст документа 3", "покажи документ 1"), и в контексте есть раздел "=== Полный текст документа ===", ты должен предоставить этот полный текст пользователю.

Используй эту информацию для ответа:
- Если пользователь спрашивает о количестве документов, используй информацию из раздела "=== Информация о загруженных документах ===".
- Если пользователь спрашивает о содержимом документов (например, "найди номер дела", "какая сумма", "когда подписан"), используй ПОЛНЫЕ ТЕКСТЫ из раздела "=== Контекст из документов (полные тексты) ===" для поиска нужной информации.
- Если в контексте есть полные тексты документов, ты можешь найти в них ЛЮБУЮ информацию, включая номера дел, даты, имена сторон, суммы, адреса и т.д.
- Если пользователь просит показать полный текст документа и он есть в контексте, предоставь его полностью.
- Можешь перечислять имена документов из списка, когда это уместно.

НЕ упоминай судебные дела, судебную практику или статьи из законов, если пользователь не спрашивает об этом явно.
НЕ упоминай техническую информацию о документах (тип файла, формат, OCR и т.д.).
Отвечай только на вопрос пользователя о содержании его документов.
Если в контексте из документов нет информации, честно скажи, что не нашел информацию в загруженных документах."""
        else:
            system_prompt = """Ты - юридический ассистент, который помогает пользователям с юридическими вопросами.

В контексте тебе предоставлена информация:
1. В разделе "=== Информация о загруженных документах ===" - полный список всех загруженных документов с их именами и количеством (если документы загружены).
2. В разделе "=== Контекст из документов ===" - релевантные фрагменты из документов пользователя (если есть).
3. В разделе "=== Судебная практика ===" - информация о судебных делах (если есть).
4. В разделе "=== Полный текст дела № [номер] ===" - полный текст судебного решения (если есть).

ВАЖНО:
- Если пользователь просит показать текст дела (например, "Покажи текст дела 686/32982/23", "текст дела", "полный текст дела", "дай мне полный текст дела") и в контексте есть раздел "=== Полный текст дела № [номер] ===", ты ДОЛЖЕН предоставить этот полный текст пользователю ПОЛНОСТЬЮ, без сокращений и обрезаний.
- Если в контексте есть раздел "=== Полный текст дела ===" или "=== Полный текст дела № [номер] ===", это означает, что полный текст доступен, и ты должен его показать пользователю ПОЛНОСТЬЮ, начиная с заголовка и заканчивая последним словом текста решения.
- НЕ сокращай текст, НЕ обрезай его, НЕ говори "текст слишком длинный" - покажи ВЕСЬ текст, который есть в контексте.
- НЕ говори, что у тебя нет доступа к полному тексту, если он есть в контексте.
- Если пользователь просит "полный текст" или "весь текст", это означает, что он хочет увидеть ВСЁ содержимое, без исключений.

Используй предоставленный контекст для формирования точного и полезного ответа.
Если контекст содержит информацию из загруженных документов пользователя, приоритетно используй её.
Если пользователь спрашивает о количестве или именах документов, используй информацию из раздела "=== Информация о загруженных документах ===".
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
        
        # Проверяем, является ли это запросом на полный текст дела
        # Если в контексте есть полный текст дела, нужно установить большой max_tokens
        is_full_text_request = any("=== Полный текст дела №" in ctx or "=== Полный текст дела ===" in ctx for ctx in contexts)
        
        # Проверяем, является ли это запросом о документах пользователя с полными текстами
        is_user_documents_with_full_texts = any("=== Контекст из документов (полные тексты) ===" in ctx for ctx in contexts)
        
        # Определяем max_tokens в зависимости от типа запроса
        # Для полных текстов дел нужен большой лимит, так как текст может быть очень длинным
        if is_full_text_request:
            # Для полного текста дела устанавливаем большой max_tokens
            # gpt-4o-mini имеет лимит 128K токенов на контекст + ответ
            # Если контекст ~100K символов (~80K токенов), оставляем ~40K токенов для ответа
            max_tokens = 40000  # ~40K токенов для ответа (достаточно для длинного текста)
            logger.info(f"Full text case request detected, setting max_tokens={max_tokens}")
        elif is_user_documents_with_full_texts:
            # Для запросов о документах пользователя с полными текстами также нужен увеличенный лимит
            # Контекст может быть большим (~90K символов), поэтому оставляем достаточно места для ответа
            max_tokens = 30000  # ~30K токенов для ответа (достаточно для анализа документов)
            logger.info(f"User documents query with full texts detected, setting max_tokens={max_tokens}")
        else:
            # Для обычных запросов используем дефолтное значение или разумный лимит
            max_tokens = None  # Используем дефолт модели (обычно 16K для gpt-4o-mini)
        
        # Логируем промпт для отладки (первые 500 символов)
        logger.info(f"Sending to LLM provider: {llm_provider.value if llm_provider else 'default'}, model: {model or 'default'}")
        logger.info(f"RAG enabled: {use_rag}, Law enabled: {use_law}, Contexts count: {len(contexts)}, is_full_text_request: {is_full_text_request}, is_user_documents_with_full_texts: {is_user_documents_with_full_texts}")
        logger.info(f"Query type: {query_type}, Classification: {classification}")
        logger.info(f"Sending to LLM - System prompt length: {len(system_prompt)}, User prompt length: {len(user_prompt)}, max_tokens: {max_tokens}")
        
        # Детальное логирование контекста для запросов о документах пользователя
        if is_user_documents_with_full_texts:
            logger.info(f"=== USER DOCUMENTS QUERY DEBUG ===")
            logger.info(f"Query: '{query}'")
            logger.info(f"Total contexts: {len(contexts)}")
            for i, ctx in enumerate(contexts, 1):
                logger.info(f"Context {i} type: {'Full texts' if 'полные тексты' in ctx else 'Other'}, length: {len(ctx)} chars")
                if 'полные тексты' in ctx:
                    # Логируем количество документов в контексте
                    doc_count = ctx.count('=== Полный текст документа')
                    logger.info(f"  Contains {doc_count} full document texts")
                    logger.info(f"  Preview (first 1000 chars): {ctx[:1000]}...")
        
        logger.debug(f"User prompt preview: {user_prompt[:500]}...")
        
        try:
            response = await llm.generate(messages, temperature=0.7, max_tokens=max_tokens)
            
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
        # Проверяем, является ли это запросом на полный текст дела
        # Если да, возвращаем текст напрямую из MCP, минуя LLM
        import re
        case_number_pattern = r'\d+/\d+/\d+'
        case_number_match = re.search(case_number_pattern, query)
        has_case_number = case_number_match is not None
        
        # Проверяем, запрашивается ли полный текст дела
        full_text_keywords = [
            "полный текст", "повний текст", "полный текст дела", "повний текст справи",
            "весь текст", "весь текст дела", "весь текст справи",
            "текст дела", "текст справи", "покажи текст дела", "покажи текст справи",
            "дай полный текст", "дай мне полный текст", "дай текст дела", "дай мне текст дела",
            "покажи полный текст", "покажи мне полный текст", "покажи весь текст"
        ]
        is_full_text_request = any(keyword in query.lower() for keyword in full_text_keywords)
        
        # Если это запрос на полный текст дела с номером, возвращаем напрямую из MCP
        if has_case_number and is_full_text_request:
            case_number = case_number_match.group(0)
            logger.info(f"Direct full text request detected for case {case_number}, bypassing LLM")
            
            try:
                # Получаем детали дела по номеру
                details = await self.law_client.get_case_details(case_number=case_number)
                if details and details.get('success'):
                    cases_list = details.get('cases', [])
                    if cases_list:
                        case = cases_list[0]
                        doc_id = case.get('doc_id') or case.get('id')
                        
                        if doc_id:
                            # Получаем полный текст
                            full_text_data = await self.law_client.get_case_full_text(str(doc_id))
                            if full_text_data and full_text_data.get('success'):
                                text = full_text_data.get('text', '')
                                if text:
                                    # Форматируем ответ для клиента
                                    title = case.get('title', 'N/A')
                                    response = f"Вот полный текст дела № {case_number}:\n\n"
                                    response += f"Заголовок: {title}\n\n"
                                    response += f"Текст решения:\n{text}\n"
                                    
                                    # Отправляем ответ по частям для streaming
                                    chunk_size = 1000  # Отправляем по 1000 символов за раз
                                    for i in range(0, len(response), chunk_size):
                                        chunk = response[i:i + chunk_size]
                                        yield chunk
                                    return
            
            except Exception as e:
                logger.error(f"Error getting full text directly from MCP: {e}")
                yield f"Ошибка при получении полного текста дела: {str(e)}\n"
                return
        
        # Проверка наличия документов в RAG
        has_docs = await self.rag_service.has_documents()
        
        # По умолчанию используем оба источника для лучшего контекста
        if use_law is None:
            use_law = True
        if use_rag is None:
            use_rag = True if has_docs else False  # RAG только если есть документы
        
        # Если в запросе есть номер дела, гарантируем использование MCP Law
        if has_case_number:
            use_law = True
            logger.info(f"Case number detected, ensuring MCP Law is enabled: {query}")
        
        # Классификация запроса через LLM
        classification = await self._classify_query_llm(query)
        logger.info(f"LLM classification in stream: query_type={classification.get('query_type')}, use_rag={classification.get('use_rag')}, use_law={classification.get('use_law')}")
        
        # Специальная обработка для запросов о документах пользователя - обрабатываем каждый документ отдельно через LLM
        if classification and use_rag and has_docs and classification.get("query_type") == "user_documents":
            logger.info(f"User documents query detected in stream, processing each document separately through LLM: '{query[:100]}...'")
            
            documents = await self.rag_service.list_documents()
            if not documents:
                yield "Нет загруженных документов для поиска."
                return
            
            logger.info(f"Found {len(documents)} documents, processing each one separately through LLM")
            
            # Получаем LLM провайдер
            llm = LLMProviderFactory.get_provider(llm_provider, model)
            
            # Системный промпт для поиска в документе
            doc_search_prompt = """Ты - помощник для поиска информации в документах.
Пользователь задал вопрос. В контексте предоставлен полный текст одного документа.
Твоя задача - найти ответ на вопрос пользователя в этом документе.

Если ты нашел ответ - укажи его четко и конкретно.
Если ответа нет в этом документе - ответь "Не найдено в этом документе".

Отвечай кратко и по делу."""
            
            found_answer = False
            
            # Обрабатываем каждый документ отдельно
            for i, doc in enumerate(documents, 1):
                filename = doc.get('filename') or doc.get('file_path', 'Unknown')
                logger.info(f"Processing document {i}/{len(documents)}: {filename}")
                
                # Получаем все чанки документа (полный текст)
                chunks = await self.rag_service.get_document_chunks(filename)
                if not chunks:
                    logger.warning(f"No chunks found for document {i}: {filename}")
                    continue
                
                # Объединяем все чанки в полный текст
                full_text = "\n\n".join([chunk.get('text', '') for chunk in chunks if chunk.get('text')])
                
                if not full_text or not full_text.strip():
                    logger.warning(f"Empty text for document {i}: {filename}")
                    continue
                
                # Ограничиваем длину документа для одного запроса
                max_doc_length = 80000  # ~80K символов для одного документа
                if len(full_text) > max_doc_length:
                    logger.warning(f"Document '{filename}' too long ({len(full_text)} chars), truncating to {max_doc_length}")
                    full_text = full_text[:max_doc_length] + "\n\n[Текст документа обрезан из-за ограничений длины]"
                
                # Формируем промпт для LLM
                doc_context = f"=== Полный текст документа {i}: {filename} ===\n\n{full_text}"
                user_message = f"{query}\n\n{doc_context}"
                
                messages = [
                    LLMMessage(role="system", content=doc_search_prompt),
                    LLMMessage(role="user", content=user_message)
                ]
                
                try:
                    # Отправляем запрос в LLM для этого документа
                    logger.info(f"Sending query to LLM for document {i}/{len(documents)}: {filename}")
                    
                    # Для stream используем stream_generate
                    answer_parts = []
                    async for chunk in llm.stream_generate(messages, temperature=0.3, max_tokens=2000):
                        answer_parts.append(chunk)
                        # Если еще не нашли ответ, отправляем чанки пользователю
                        if not found_answer:
                            yield chunk
                    
                    answer = "".join(answer_parts).strip()
                    logger.info(f"LLM response for document {i} '{filename}': {answer[:200]}...")
                    
                    # Проверяем, содержит ли ответ полезную информацию
                    if answer and answer.lower() not in ["не найдено в этом документе", "не найдено", "not found", "немає в цьому документі"]:
                        found_answer = True
                        logger.info(f"✅ Answer found in document {i}: {filename}")
                        # Если нашли ответ, продолжаем до последнего документа, но уже не отправляем результаты
                        # (они уже отправлены выше через yield)
                    else:
                        logger.debug(f"No answer found in document {i}: {filename}")
                
                except Exception as e:
                    logger.error(f"Error processing document {i} '{filename}' through LLM: {e}")
                    if not found_answer:
                        yield f"\n\n[Ошибка при обработке документа {i}: {filename}]\n"
            
            # После обработки всех документов отправляем финальное сообщение
            if found_answer:
                yield f"\n\n(Проверено документов: {len(documents)})"
            else:
                yield f"\n\nПроверены все {len(documents)} документов, но информация не найдена."
            
            return
        
        # Если это запрос на удаление, обрабатываем его сразу (для stream возвращаем текст)
        if classification.get("is_delete_query"):
            logger.info("Delete documents query detected in stream")
            query_lower = query.lower()
            
            # Проверяем, удалить все или конкретный документ
            delete_all_keywords = ["все", "all", "всі", "все документы", "всі документи", "все файлы", "всі файли"]
            delete_all = any(keyword in query_lower for keyword in delete_all_keywords)
            
            if delete_all:
                # Удаляем все документы
                documents = await self.rag_service.list_documents()
                if not documents:
                    yield "Нет документов для удаления."
                    return
                
                deleted_count = 0
                errors = []
                for doc in documents:
                    filename = doc.get('filename') or doc.get('file_path')
                    if filename:
                        try:
                            deleted = await self.rag_service.delete_document(filename)
                            if deleted:
                                deleted_count += 1
                        except Exception as e:
                            errors.append(f"Ошибка при удалении '{filename}': {str(e)}")
                            logger.error(f"Error deleting document '{filename}': {e}")
                
                result = f"Удалено {deleted_count} из {len(documents)} документов."
                if errors:
                    result += f"\nОшибки: {len(errors)}"
                yield result
                return
            else:
                # Пытаемся найти конкретный документ для удаления
                documents = await self.rag_service.list_documents()
                if not documents:
                    yield "Нет документов для удаления."
                    return
                
                # Ищем документ по части имени в запросе
                query_words = query_lower.split()
                matched_doc = None
                for doc in documents:
                    filename = (doc.get('filename') or doc.get('file_path', '')).lower()
                    # Проверяем, содержит ли имя файла слова из запроса
                    if any(word in filename for word in query_words if len(word) > 3):
                        matched_doc = doc
                        break
                
                if matched_doc:
                    filename = matched_doc.get('filename') or matched_doc.get('file_path')
                    try:
                        deleted = await self.rag_service.delete_document(filename)
                        if deleted:
                            yield f"Документ '{filename}' успешно удален."
                        else:
                            yield f"Не удалось удалить документ '{filename}'."
                    except Exception as e:
                        logger.error(f"Error deleting document '{filename}': {e}")
                        yield f"Ошибка при удалении документа '{filename}': {str(e)}"
                    return
                else:
                    # Не нашли документ, возвращаем список для выбора
                    doc_list = "\n".join([f"- {doc.get('filename') or doc.get('file_path')}" for doc in documents[:10]])
                    yield f"Не удалось определить, какой документ удалить. Пожалуйста, укажите точное имя файла.\n\nДоступные документы:\n{doc_list}"
                    return
        
        # Если это запрос о тексте конкретного документа пользователя, обрабатываем его отдельно
        # НО только если это НЕ запрос о судебном деле
        # При этом используем оба источника для контекста
        classification_has_case = classification.get("has_case_number", False)
        if classification and classification.get("is_document_text_query") and has_docs and not (has_case_number or classification_has_case):
            logger.info("Document text query detected in stream, getting full document text (using both RAG and MCP Law for context)")
            
            # Получаем список документов
            documents = await self.rag_service.list_documents()
            if not documents:
                yield "Нет загруженных документов."
                return
            
            # Определяем, какой документ нужен
            target_document = None
            document_number = classification.get("document_number")
            
            if document_number:
                # Ищем документ по номеру (индекс начинается с 1)
                if 1 <= document_number <= len(documents):
                    target_document = documents[document_number - 1]
                else:
                    yield f"Документ с номером {document_number} не найден. Всего загружено документов: {len(documents)}."
                    return
            else:
                # Пытаемся найти документ по имени из запроса
                query_lower = query.lower()
                for doc in documents:
                    filename = (doc.get('filename') or doc.get('file_path', '')).lower()
                    # Проверяем, содержит ли имя файла слова из запроса
                    query_words = [w for w in query_lower.split() if len(w) > 3]
                    if any(word in filename for word in query_words):
                        target_document = doc
                        break
                
                # Если не нашли, берем первый документ
                if not target_document and documents:
                    target_document = documents[0]
            
            if target_document:
                filename = target_document.get('filename') or target_document.get('file_path')
                file_path = target_document.get('file_path') or filename
                
                logger.info(f"Looking for document chunks in stream: filename='{filename}', file_path='{file_path}'")
                
                # Пробуем получить чанки по разным вариантам имени файла
                chunks = await self.rag_service.get_document_chunks(filename)
                
                # Если не нашли, пробуем по file_path
                if not chunks and file_path and file_path != filename:
                    logger.debug(f"Chunks not found by filename, trying file_path: '{file_path}'")
                    chunks = await self.rag_service.get_document_chunks(file_path)
                
                # Если все еще не нашли, пробуем по базовому имени файла
                if not chunks:
                    import os
                    basename = os.path.basename(filename)
                    if basename != filename:
                        logger.debug(f"Chunks not found, trying basename: '{basename}'")
                        chunks = await self.rag_service.get_document_chunks(basename)
                
                # Если все еще не нашли, пробуем с нормализованным расширением
                if not chunks:
                    import os
                    basename = os.path.basename(filename)
                    # Пробуем с нижним регистром расширения
                    if basename.upper().endswith('.PDF'):
                        basename_lower = basename[:-4] + '.pdf'
                        logger.debug(f"Chunks not found, trying lowercase extension: '{basename_lower}'")
                        chunks = await self.rag_service.get_document_chunks(basename_lower)
                
                logger.info(f"Found {len(chunks)} chunks for document '{filename}' in stream")
                
                if chunks:
                    # Объединяем все чанки в полный текст
                    full_text = "\n\n".join([chunk.get('text', '') for chunk in chunks if chunk.get('text')])
                    
                    if full_text:
                        yield f"=== Полный текст документа: {filename} ===\n\n{full_text}"
                    else:
                        yield f"Документ '{filename}' найден, но текст не извлечен или пуст."
                else:
                    logger.warning(f"Document '{filename}' found in list but chunks not found in stream. Trying to find by searching all documents...")
                    # Пробуем найти документ в списке всех документов по имени
                    all_docs = await self.rag_service.list_documents()
                    matching_docs = []
                    import os
                    target_basename = os.path.basename(filename).lower()
                    for doc in all_docs:
                        doc_filename = (doc.get('filename') or doc.get('file_path', '')).lower()
                        doc_basename = os.path.basename(doc_filename).lower()
                        if target_basename == doc_basename:
                            matching_docs.append(doc)
                    
                    if matching_docs:
                        # Пробуем получить чанки для найденного документа
                        for doc in matching_docs:
                            alt_filename = doc.get('filename') or doc.get('file_path')
                            logger.debug(f"Trying alternative filename in stream: '{alt_filename}'")
                            chunks = await self.rag_service.get_document_chunks(alt_filename)
                            if chunks:
                                full_text = "\n\n".join([chunk.get('text', '') for chunk in chunks if chunk.get('text')])
                                if full_text:
                                    yield f"=== Полный текст документа: {alt_filename} ===\n\n{full_text}"
                                    return
                    
                    yield f"Документ '{filename}' найден в списке, но чанки не найдены. Возможно, документ еще обрабатывается или возникла проблема с индексацией. Попробуйте перезагрузить документ."
            else:
                # Не нашли документ, возвращаем список
                doc_list = "\n".join([f"{i+1}. {doc.get('filename') or doc.get('file_path')}" for i, doc in enumerate(documents[:10])])
                yield f"Не удалось определить, какой документ показать. Пожалуйста, укажите номер документа (1-{len(documents)}) или имя файла.\n\nДоступные документы:\n{doc_list}"
            return
        
        # Используем оба источника для запросов о документах пользователя
        if classification and use_rag and has_docs and classification.get("query_type") == "user_documents":
            logger.info("User document query detected in stream, using both RAG and MCP Law for context")
        
        # Если документов нет, гарантируем использование MCP Law
        if not use_rag and use_law is None:
            use_law = True
        
        contexts = []
        
        async def get_documents_summary():
            """Получение краткой информации о всех загруженных документах"""
            if not use_rag or not has_docs:
                return None
            try:
                documents = await self.rag_service.list_documents()
                if documents:
                    doc_list = []
                    for i, doc in enumerate(documents, 1):
                        filename = doc.get('filename') or doc.get('file_path', 'Unknown')
                        doc_type = doc.get('document_type') or doc.get('metadata', {}).get('document_type', 'unknown')
                        chunks_count = doc.get('chunks_count', 0)
                        
                        doc_info = f"{i}. {filename}"
                        if doc_type != 'unknown':
                            doc_info += f" (тип: {doc_type})"
                        if chunks_count > 0:
                            doc_info += f" - {chunks_count} частей"
                        doc_list.append(doc_info)
                    
                    summary = f"=== Информация о загруженных документах ===\n"
                    summary += f"Всего загружено документов: {len(documents)}\n\n"
                    summary += "Список документов:\n" + "\n".join(doc_list)
                    return summary
            except Exception as e:
                logger.error(f"Error getting documents summary: {e}")
                return None
        
        async def get_rag_context():
            if not use_rag:
                return None
            try:
                # Если это запрос о списке документов, получаем все документы
                if classification and classification.get("is_list_query"):
                    logger.info("List documents query detected in stream, getting all documents")
                    documents = await self.rag_service.list_documents()
                    if documents:
                        context_parts = []
                        for i, doc in enumerate(documents, 1):
                            filename = doc.get('filename') or doc.get('file_path', 'Unknown')
                            doc_type = doc.get('document_type') or doc.get('metadata', {}).get('document_type', 'unknown')
                            chunks_count = doc.get('chunks_count', 0)
                            
                            # Получаем первые чанки документа для контекста
                            chunks = await self.rag_service.get_document_chunks(filename)
                            if chunks:
                                # Берем первые 2-3 чанка для каждого документа
                                preview_chunks = chunks[:3]
                                preview_text = "\n".join([chunk.get('text', '')[:500] for chunk in preview_chunks if chunk.get('text')])
                                
                                doc_info = f"Документ {i}: {filename}\n"
                                if doc_type != 'unknown':
                                    doc_info += f"Тип: {doc_type}\n"
                                doc_info += f"Количество частей: {chunks_count}\n"
                                if preview_text:
                                    doc_info += f"Содержание (фрагмент):\n{preview_text}\n"
                                context_parts.append(doc_info)
                            else:
                                # Если чанков нет, просто добавляем информацию о документе
                                doc_info = f"Документ {i}: {filename}\n"
                                if doc_type != 'unknown':
                                    doc_info += f"Тип: {doc_type}\n"
                                context_parts.append(doc_info)
                        
                        if context_parts:
                            return f"=== Список всех загруженных документов ===\n\n" + "\n\n".join(context_parts)
                    return None
                # Для user_documents запросов обработка происходит в stream_process_query до вызова get_rag_context
                # Здесь возвращаем None, так как обработка уже выполнена
                if classification and (classification.get("query_type") == "user_documents" or classification.get("query_type") == "document_text"):
                    logger.debug("User documents query in stream - processing already done, skipping get_rag_context")
                    return None
                else:
                    # Обычный поиск - увеличиваем top_k для получения большего контекста
                    # Ограничиваем top_k чтобы не превысить лимиты токенов
                    rag_context = await self.rag_service.get_context(query, top_k=10)
                    if rag_context:
                        # Ограничиваем размер RAG контекста
                        max_rag_context_length = 5000  # ~5K символов для RAG контекста
                        if len(rag_context) > max_rag_context_length:
                            logger.warning(f"RAG context too long ({len(rag_context)} chars), truncating to {max_rag_context_length}")
                            rag_context = rag_context[:max_rag_context_length] + "\n\n[Контекст обрезан из-за ограничений длины]"
                        return f"=== Контекст из документов ===\n{rag_context}"
            except Exception as e:
                logger.error(f"Error getting RAG context: {e}")
                return None
        async def get_law_context():
            if not use_law:
                return None
            try:
                # Извлекаем номер дела через OpenAI
                case_number = await self._extract_case_number_llm(query)
                
                # Проверяем, запрашивается ли полный текст дела
                full_text_keywords = [
                    "полный текст", "повний текст", "полный текст дела", "повний текст справи",
                    "весь текст", "весь текст дела", "весь текст справи",
                    "текст дела", "текст справи", "покажи текст дела", "покажи текст справи",
                    "дай полный текст", "дай мне полный текст", "дай текст дела", "дай мне текст дела",
                    "покажи полный текст", "покажи мне полный текст", "покажи весь текст"
                ]
                is_full_text_request = any(keyword in query.lower() for keyword in full_text_keywords)
                
                # Если есть номер дела, пытаемся получить детали или полный текст
                if case_number:
                    logger.info(f"Detected case number in query: {case_number}")
                    
                    # Если запрашивается полный текст, получаем его
                    if is_full_text_request:
                        # Сначала получаем детали дела по номеру
                        details = await self.law_client.get_case_details(case_number=case_number)
                        if details and details.get('success'):
                            cases_list = details.get('cases', [])
                            if cases_list:
                                # Берем первое дело из списка
                                case = cases_list[0]
                                doc_id = case.get('doc_id') or case.get('id')
                                
                                if doc_id:
                                    # Получаем полный текст
                                    full_text_data = await self.law_client.get_case_full_text(str(doc_id))
                                    if full_text_data and full_text_data.get('success'):
                                        text = full_text_data.get('text', '')
                                        if text:
                                            # Для запросов на полный текст увеличиваем лимит, чтобы передать больше текста
                                            # gpt-4o-mini имеет лимит 128K токенов (~100K символов)
                                            # Оставляем место для system prompt (~2K) и user query (~1K), итого ~97K для контекста
                                            max_text_length = 95000  # ~95K символов для полного текста (увеличенный лимит)
                                            original_length = len(text)
                                            if len(text) > max_text_length:
                                                logger.warning(f"Full text too long ({original_length} chars), truncating to {max_text_length}")
                                                text = text[:max_text_length] + "\n\n[Текст обрезан из-за ограничений длины. Полный текст доступен по запросу.]"
                                            else:
                                                logger.info(f"Full text retrieved: {original_length} chars for case {case_number}")
                                            
                                            law_context = f"=== Полный текст дела № {case_number} ===\n\n"
                                            law_context += f"Заголовок: {case.get('title', 'N/A')}\n\n"
                                            law_context += f"Текст решения:\n{text}\n"
                                            logger.debug(f"Law context length: {len(law_context)} chars")
                                            return law_context
                    
                    # Если полный текст не запрашивается или не получен, возвращаем детали
                    details = await self.law_client.get_case_details(case_number=case_number)
                    if details and details.get('success'):
                        cases_list = details.get('cases', [])
                        if cases_list:
                            law_context = f"=== Детали дела № {case_number} ===\n"
                            for i, case in enumerate(cases_list[:3], 1):
                                law_context += f"\n{i}. {case.get('title', 'Дело')}\n"
                                if 'description' in case:
                                    law_context += f"   {case['description']}\n"
                                if 'resolution' in case:
                                    law_context += f"   Резолютивная часть: {case['resolution']}\n"
                            return law_context
                
                # Обычный поиск дел
                cases = await self.law_client.search_cases(query, limit=3)
                if cases:
                    law_context = "=== Судебная практика ===\n"
                    for i, case in enumerate(cases, 1):
                        law_context += f"{i}. {case.get('title', 'Дело')}\n"
                        case_num = case.get('cause_num', '')
                        if case_num:
                            law_context += f"   Номер дела: {case_num}\n"
                        if 'description' in case:
                            law_context += f"   {case['description'][:200]}...\n"
                        # Если запрашивается полный текст и есть doc_id, получаем его
                        if is_full_text_request:
                            doc_id = case.get('doc_id') or case.get('id')
                            if doc_id:
                                full_text_data = await self.law_client.get_case_full_text(str(doc_id))
                                if full_text_data and full_text_data.get('success'):
                                    text = full_text_data.get('text', '')
                                    if text:
                                        # Ограничиваем размер для preview
                                        preview_length = 2000
                                        if len(text) > preview_length:
                                            law_context += f"\n   === Полный текст дела (фрагмент) ===\n{text[:preview_length]}...\n[Полный текст слишком длинный, показан только фрагмент]\n"
                                        else:
                                            law_context += f"\n   === Полный текст дела ===\n{text}\n"
                    return law_context
            except Exception as e:
                logger.error(f"Error getting Law MCP context: {e}")
                return None
        
        # Получаем информацию о всех документах (всегда, если есть документы)
        documents_summary = await get_documents_summary()
        
        # Параллельное выполнение
        rag_result, law_result = await asyncio.gather(
            get_rag_context(),
            get_law_context(),
            return_exceptions=True
        )
        
        # Добавляем информацию о всех документах в начало контекста
        if documents_summary:
            contexts.insert(0, documents_summary)
        
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
        
        if query_type == "user_documents" or query_type == "document_text":
            system_prompt = """Ты - юридический ассистент, который помогает пользователям с их загруженными документами.
ВАЖНО: Пользователь спрашивает про СВОИ загруженные документы. 

В контексте тебе предоставлена информация:
1. В разделе "=== Информация о загруженных документах ===" - полный список всех загруженных документов с их именами и количеством. Ты ВСЕГДА знаешь, сколько документов загружено и как они называются.
2. В разделе "=== Контекст из документов ===" - релевантные фрагменты из документов по запросу пользователя.
3. Если пользователь просит показать полный текст документа (например, "текст документа 3", "покажи документ 1"), и в контексте есть раздел "=== Полный текст документа ===", ты должен предоставить этот полный текст пользователю.

Используй эту информацию для ответа:
- Если пользователь спрашивает о количестве документов, используй информацию из раздела "=== Информация о загруженных документах ===".
- Если пользователь спрашивает о содержимом документов, используй информацию из раздела "=== Контекст из документов ===".
- Если пользователь просит показать полный текст документа и он есть в контексте, предоставь его полностью.
- Можешь перечислять имена документов из списка, когда это уместно.

НЕ упоминай судебные дела, судебную практику или статьи из законов, если пользователь не спрашивает об этом явно.
НЕ упоминай техническую информацию о документах (тип файла, формат, OCR и т.д.).
Отвечай только на вопрос пользователя о содержании его документов.
Если в контексте из документов нет информации, честно скажи, что не нашел информацию в загруженных документах.
В конце ответа можешь предложить пользователю варианты дальнейших действий, если это уместно."""
        else:
            system_prompt = """Ты - юридический ассистент, который помогает пользователям с юридическими вопросами.

В контексте тебе предоставлена информация:
1. В разделе "=== Информация о загруженных документах ===" - полный список всех загруженных документов с их именами и количеством (если документы загружены).
2. В разделе "=== Контекст из документов ===" - релевантные фрагменты из документов пользователя (если есть).
3. В разделе "=== Судебная практика ===" - информация о судебных делах (если есть).
4. В разделе "=== Полный текст дела № [номер] ===" - полный текст судебного решения (если есть).

ВАЖНО:
- Если пользователь просит показать текст дела (например, "Покажи текст дела 686/32982/23", "текст дела", "полный текст дела", "дай мне полный текст дела") и в контексте есть раздел "=== Полный текст дела № [номер] ===", ты ДОЛЖЕН предоставить этот полный текст пользователю ПОЛНОСТЬЮ, без сокращений и обрезаний.
- Если в контексте есть раздел "=== Полный текст дела ===" или "=== Полный текст дела № [номер] ===", это означает, что полный текст доступен, и ты должен его показать пользователю ПОЛНОСТЬЮ, начиная с заголовка и заканчивая последним словом текста решения.
- НЕ сокращай текст, НЕ обрезай его, НЕ говори "текст слишком длинный" - покажи ВЕСЬ текст, который есть в контексте.
- НЕ говори, что у тебя нет доступа к полному тексту, если он есть в контексте.
- Если пользователь просит "полный текст" или "весь текст", это означает, что он хочет увидеть ВСЁ содержимое, без исключений.

Используй предоставленный контекст для формирования точного и полезного ответа.
Если контекст содержит информацию из загруженных документов пользователя, приоритетно используй её.
Если пользователь спрашивает о количестве или именах документов, используй информацию из раздела "=== Информация о загруженных документах ===".
Если контекст не содержит нужной информации, честно об этом скажи."""
        
        user_prompt = query
        if contexts:
            user_prompt += "\n\n" + "\n\n".join(contexts)
            # Логируем контекст для отладки
            logger.debug(f"Stream context length: {sum(len(c) for c in contexts)} chars, contexts count: {len(contexts)}")
        
        # Проверяем длину промпта - OpenAI имеет лимиты
        # gpt-4o-mini имеет лимит 128K токенов (~100K символов), но ограничиваем для безопасности
        # Оставляем место для system prompt (~2K), user query (~1K) и ответа (~5K), итого ~92K для контекста
        max_user_prompt_length = 92000  # ~92K символов для user prompt (увеличенный лимит для полных текстов дел)
        if len(user_prompt) > max_user_prompt_length:
            logger.warning(f"User prompt too long ({len(user_prompt)} chars), truncating to {max_user_prompt_length}")
            user_prompt = user_prompt[:max_user_prompt_length] + "\n\n[Текст обрезан из-за ограничений длины]"
        
        if len(system_prompt) > 5000:
            logger.warning(f"System prompt too long ({len(system_prompt)} chars), truncating to 5000")
            system_prompt = system_prompt[:5000]
        
        # Проверяем общую длину всех контекстов (128K токенов = ~100K символов, но оставляем запас)
        # Увеличиваем лимит для запросов на полный текст дела
        total_context_length = len(user_prompt) + len(system_prompt)
        max_total_length = 120000  # ~120K символов (увеличенный лимит для полных текстов дел)
        if total_context_length > max_total_length:
            logger.warning(f"Total context too long ({total_context_length} chars), truncating user prompt to fit {max_total_length}")
            # Обрезаем user_prompt чтобы общая длина была в пределах лимита
            max_user_len = max_total_length - len(system_prompt) - 2000  # -2000 для буфера и ответа
            if max_user_len > 0:
                user_prompt = user_prompt[:max_user_len] + "\n\n[Текст обрезан из-за ограничений длины]"
            else:
                logger.error(f"System prompt too long ({len(system_prompt)} chars), cannot fit user prompt")
                user_prompt = query[:500]  # Минимальный промпт
        
        llm = LLMProviderFactory.get_provider(llm_provider, model)
        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=user_prompt)
        ]
        
        # Проверяем, является ли это запросом на полный текст дела
        # Если в контексте есть полный текст дела, нужно установить большой max_tokens
        is_full_text_request = any("=== Полный текст дела №" in ctx or "=== Полный текст дела ===" in ctx for ctx in contexts)
        
        # Проверяем, является ли это запросом о документах пользователя с полными текстами
        is_user_documents_with_full_texts = any("=== Контекст из документов (полные тексты) ===" in ctx for ctx in contexts)
        
        # Определяем max_tokens в зависимости от типа запроса
        # Для полных текстов дел нужен большой лимит, так как текст может быть очень длинным
        if is_full_text_request:
            # Для полного текста дела устанавливаем большой max_tokens
            # gpt-4o-mini имеет лимит 128K токенов на контекст + ответ
            # Если контекст ~100K символов (~80K токенов), оставляем ~40K токенов для ответа
            max_tokens = 40000  # ~40K токенов для ответа (достаточно для длинного текста)
            logger.info(f"Full text case request detected, setting max_tokens={max_tokens}")
        elif is_user_documents_with_full_texts:
            # Для запросов о документах пользователя с полными текстами также нужен увеличенный лимит
            # Контекст может быть большим (~90K символов), поэтому оставляем достаточно места для ответа
            max_tokens = 30000  # ~30K токенов для ответа (достаточно для анализа документов)
            logger.info(f"User documents query with full texts detected in stream, setting max_tokens={max_tokens}")
        else:
            # Для обычных запросов используем дефолтное значение или разумный лимит
            max_tokens = None  # Используем дефолт модели (обычно 16K для gpt-4o-mini)
        
        # Логируем промпт для отладки
        logger.info(f"Stream sending to LLM provider: {llm_provider.value if llm_provider else 'default'}, model: {model or 'default'}")
        logger.info(f"RAG enabled: {use_rag}, Law enabled: {use_law}, Contexts count: {len(contexts)}, is_full_text_request: {is_full_text_request}, is_user_documents_with_full_texts: {is_user_documents_with_full_texts}")
        logger.debug(f"Stream sending to LLM - System prompt length: {len(system_prompt)}, User prompt length: {len(user_prompt)}, contains context: {bool(contexts)}, max_tokens: {max_tokens}")
        
        try:
            # Для stream мы не можем вернуть suggested_actions в потоке,
            # но можем добавить их в метаданные через специальный формат
            # Пока просто генерируем поток ответа
            async for chunk in llm.stream_generate(messages, temperature=0.7, max_tokens=max_tokens):
                yield chunk
        except Exception as e:
            logger.error(f"Error streaming LLM response: {e}")
            yield f"Ошибка: {str(e)}"
