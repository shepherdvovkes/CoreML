"""
Провайдер для кастомных LLM API
"""
import httpx
from typing import List, Optional, AsyncIterator
from .base import BaseLLMProvider, LLMMessage, LLMResponse
from loguru import logger
from core.resilience import resilient_llm


class CustomProvider(BaseLLMProvider):
    """Провайдер для работы с кастомными LLM API"""
    
    def __init__(self, base_url: str, api_key: Optional[str] = None, model: str = "custom-model"):
        super().__init__(base_url, api_key, model)
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        
        self.client = httpx.AsyncClient(
            base_url=base_url,
            headers=headers,
            timeout=60.0
        )
    
    @resilient_llm(name="custom_llm_generate")
    async def generate(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """Генерация ответа через кастомный API"""
        try:
            # Предполагаем OpenAI-совместимый формат, но можно адаптировать
            payload = {
                "model": self.model,
                "messages": [{"role": msg.role, "content": msg.content} for msg in messages],
                "temperature": temperature,
            }
            
            if max_tokens:
                payload["max_tokens"] = max_tokens
            
            payload.update(kwargs)
            
            response = await self.client.post("/chat/completions", json=payload)
            response.raise_for_status()
            
            data = response.json()
            
            # Адаптация под разные форматы ответов
            if "choices" in data:
                choice = data["choices"][0]
                content = choice["message"]["content"]
            elif "text" in data:
                content = data["text"]
            elif "response" in data:
                content = data["response"]
            else:
                content = str(data)
            
            return LLMResponse(
                content=content,
                model=data.get("model", self.model),
                usage=data.get("usage"),
                metadata=data
            )
        except Exception as e:
            logger.error(f"Custom LLM API error: {e}")
            raise
    
    @resilient_llm(name="custom_llm_stream_generate", timeout_seconds=180)
    async def stream_generate(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """Потоковая генерация ответа"""
        try:
            payload = {
                "model": self.model,
                "messages": [{"role": msg.role, "content": msg.content} for msg in messages],
                "temperature": temperature,
                "stream": True,
            }
            
            if max_tokens:
                payload["max_tokens"] = max_tokens
            
            payload.update(kwargs)
            
            async with self.client.stream("POST", "/chat/completions", json=payload) as response:
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
            logger.error(f"Custom LLM streaming error: {e}")
            raise
    
    async def close(self):
        """Закрытие клиента"""
        await self.client.aclose()

