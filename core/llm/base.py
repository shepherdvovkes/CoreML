"""
Базовый класс для LLM провайдеров
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any
from pydantic import BaseModel


class LLMMessage(BaseModel):
    """Модель сообщения для LLM"""
    role: str  # system, user, assistant
    content: str


class LLMResponse(BaseModel):
    """Ответ от LLM"""
    content: str
    model: str
    usage: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


class BaseLLMProvider(ABC):
    """Базовый класс для всех LLM провайдеров"""
    
    def __init__(self, base_url: str, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
    
    @abstractmethod
    async def generate(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Генерация ответа от LLM
        
        Args:
            messages: Список сообщений
            temperature: Температура генерации
            max_tokens: Максимальное количество токенов
            **kwargs: Дополнительные параметры
            
        Returns:
            LLMResponse: Ответ от модели
        """
        pass
    
    @abstractmethod
    async def stream_generate(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ):
        """
        Потоковая генерация ответа
        
        Args:
            messages: Список сообщений
            temperature: Температура генерации
            max_tokens: Максимальное количество токенов
            **kwargs: Дополнительные параметры
            
        Yields:
            str: Части ответа
        """
        pass

