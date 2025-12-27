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
    
    def __init__(self, base_url: str, api_key: str, model: str = "gpt-3.5-turbo"):
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
            logger.error(f"OpenAI streaming error: {e}")
            raise
    
    async def close(self):
        """Закрытие клиента"""
        await self.client.aclose()

