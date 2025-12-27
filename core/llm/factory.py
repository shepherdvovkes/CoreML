"""
Фабрика для создания LLM провайдеров
"""
from typing import Optional
from config import settings, LLMProvider
from .base import BaseLLMProvider
from .openai_provider import OpenAIProvider
from .lmstudio_provider import LMStudioProvider
from .custom_provider import CustomProvider
from loguru import logger


class LLMProviderFactory:
    """Фабрика для создания LLM провайдеров"""
    
    _providers: dict[str, BaseLLMProvider] = {}
    
    @classmethod
    def get_provider(
        cls,
        provider_type: Optional[LLMProvider] = None,
        model: Optional[str] = None
    ) -> BaseLLMProvider:
        """
        Получить провайдер LLM
        
        Args:
            provider_type: Тип провайдера (если None, используется default)
            model: Название модели
            
        Returns:
            BaseLLMProvider: Экземпляр провайдера
        """
        provider_type = provider_type or settings.default_llm_provider
        cache_key = f"{provider_type.value}_{model or 'default'}"
        
        if cache_key in cls._providers:
            return cls._providers[cache_key]
        
        provider = cls._create_provider(provider_type, model)
        cls._providers[cache_key] = provider
        return provider
    
    @classmethod
    def _create_provider(
        cls,
        provider_type: LLMProvider,
        model: Optional[str] = None
    ) -> BaseLLMProvider:
        """Создать новый провайдер"""
        if provider_type == LLMProvider.OPENAI:
            return OpenAIProvider(
                base_url=settings.openai_base_url,
                api_key=settings.openai_api_key,
                model=model or "gpt-3.5-turbo"
            )
        elif provider_type == LLMProvider.LMSTUDIO:
            return LMStudioProvider(
                base_url=settings.lmstudio_base_url,
                api_key="lm-studio",
                model=model or "local-model"
            )
        elif provider_type == LLMProvider.CUSTOM:
            return CustomProvider(
                base_url=settings.custom_llm_base_url,
                api_key=settings.mcp_law_api_key,
                model=model or "custom-model"
            )
        else:
            raise ValueError(f"Unknown provider type: {provider_type}")
    
    @classmethod
    async def close_all(cls):
        """Закрыть все провайдеры"""
        for provider in cls._providers.values():
            if hasattr(provider, 'close'):
                await provider.close()
        cls._providers.clear()

