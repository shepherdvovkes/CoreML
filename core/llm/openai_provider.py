"""
Провайдер для OpenAI API
"""
import httpx
from typing import List, Optional, AsyncIterator
from .base import BaseLLMProvider, LLMMessage, LLMResponse
from loguru import logger
from core.resilience import resilient_llm


class OpenAIProvider(BaseLLMProvider):
    """Провайдер для работы с OpenAI API"""
    
    def __init__(self, base_url: str, api_key: str, model: str = "gpt-4o-mini"):
        super().__init__(base_url, api_key, model)
        self.client = httpx.AsyncClient(
            base_url=base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            timeout=60.0
        )
    
    @resilient_llm(name="openai_generate")
    async def generate(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """Генерация ответа через OpenAI API"""
        try:
            # Формируем сообщения, проверяя что content не None
            formatted_messages = []
            for msg in messages:
                if msg.content is None:
                    logger.warning(f"Message with None content: {msg.role}")
                    continue
                formatted_messages.append({
                    "role": msg.role,
                    "content": str(msg.content)
                })
            
            if not formatted_messages:
                raise ValueError("No valid messages to send")
            
            payload = {
                "model": self.model,
                "messages": formatted_messages,
                "temperature": temperature,
            }
            
            if max_tokens:
                payload["max_tokens"] = max_tokens
            
            payload.update(kwargs)
            
            # Логируем payload для отладки (без API ключа)
            logger.debug(f"OpenAI API request: model={self.model}, messages_count={len(formatted_messages)}, temperature={temperature}, max_tokens={max_tokens}")
            if len(str(payload)) < 1000:  # Логируем только короткие payload
                logger.debug(f"Payload: {payload}")
            
            response = await self.client.post("/chat/completions", json=payload)
            
            # Логируем детали ошибки если есть
            if response.status_code == 400:
                error_text = response.text[:1000] if hasattr(response, 'text') else str(response.content[:1000])
                logger.error(f"OpenAI API 400 Bad Request: {error_text}")
                logger.error(f"Request model: {self.model}, base_url: {self.base_url}")
                logger.error(f"Messages preview: {[{'role': m['role'], 'content_len': len(str(m['content']))} for m in formatted_messages[:3]]}")
            
            response.raise_for_status()
            
            data = response.json()
            choice = data["choices"][0]
            
            return LLMResponse(
                content=choice["message"]["content"],
                model=data["model"],
                usage=data.get("usage"),
                metadata={"finish_reason": choice.get("finish_reason")}
            )
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise
    
    @resilient_llm(name="openai_stream_generate", timeout_seconds=180)
    async def stream_generate(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """Потоковая генерация ответа"""
        try:
            # Формируем сообщения, проверяя что content не None
            formatted_messages = []
            for msg in messages:
                if msg.content is None:
                    logger.warning(f"Message with None content: {msg.role}")
                    continue
                formatted_messages.append({
                    "role": msg.role,
                    "content": str(msg.content)
                })
            
            if not formatted_messages:
                raise ValueError("No valid messages to send")
            
            payload = {
                "model": self.model,
                "messages": formatted_messages,
                "temperature": temperature,
                "stream": True,
            }
            
            if max_tokens:
                payload["max_tokens"] = max_tokens
            
            payload.update(kwargs)
            
            # Логируем payload для отладки
            total_content_len = sum(len(str(m.get('content', ''))) for m in formatted_messages)
            logger.debug(f"OpenAI stream request: model={self.model}, messages_count={len(formatted_messages)}, total_content_len={total_content_len}")
            logger.debug(f"Messages preview: {[{'role': m['role'], 'content_len': len(str(m.get('content', '')))} for m in formatted_messages[:3]]}")
            
            async with self.client.stream("POST", "/chat/completions", json=payload) as response:
                # Проверяем статус перед чтением потока
                if response.status_code == 400:
                    # Пытаемся прочитать текст ошибки из потока
                    error_parts = []
                    try:
                        async for chunk in response.aiter_bytes():
                            error_parts.append(chunk)
                            if len(b''.join(error_parts)) > 2000:  # Ограничиваем размер
                                break
                        error_text = b''.join(error_parts).decode('utf-8', errors='ignore')[:1000]
                        logger.error(f"OpenAI API 400 Bad Request in stream: {error_text}")
                    except Exception as read_error:
                        logger.error(f"OpenAI API 400 Bad Request in stream (could not read error: {read_error})")
                    
                    logger.error(f"Request model: {self.model}, base_url: {self.base_url}")
                    logger.error(f"Messages count: {len(formatted_messages)}, total_content_len: {total_content_len}")
                    logger.error(f"System message length: {len([m for m in formatted_messages if m['role'] == 'system'][0]['content']) if any(m['role'] == 'system' for m in formatted_messages) else 0}")
                    logger.error(f"User message length: {len([m for m in formatted_messages if m['role'] == 'user'][0]['content']) if any(m['role'] == 'user' for m in formatted_messages) else 0}")
                    
                    # Создаем HTTPStatusError для правильной обработки
                    raise httpx.HTTPStatusError(
                        "400 Bad Request", 
                        request=response.request, 
                        response=response
                    )
                
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            import json
                            data = json.loads(data_str)
                            if "choices" in data and len(data["choices"]) > 0:
                                delta = data["choices"][0].get("delta", {})
                                if "content" in delta:
                                    yield delta["content"]
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            logger.error(f"OpenAI streaming error: {e}")
            raise
    
    async def close(self):
        """Закрытие клиента"""
        await self.client.aclose()

