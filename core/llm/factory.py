"""
Фабрика для создания LLM провайдеров
"""
from typing import Optional
from config import settings, LLMProvider
from .base import BaseLLMProvider, LLMMessage
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
                model=model or "gpt-4o-mini"
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
                api_key="",
                model=model or "custom-model"
            )
        elif provider_type == LLMProvider.OLLAMA:
            # Ollama uses OpenAI-compatible API, so we use CustomProvider
            # Ollama doesn't require a real API key, but some clients expect it
            return CustomProvider(
                base_url=settings.ollama_base_url,
                api_key="ollama",  # Ollama doesn't require real key
                model=model or settings.ollama_model
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
    
    @classmethod
    async def validate_provider(
        cls,
        provider_type: LLMProvider,
        model: Optional[str] = None
    ) -> dict:
        """
        Проверка валидности провайдера (простой тест)
        
        Args:
            provider_type: Тип провайдера
            model: Название модели (опционально)
            
        Returns:
            dict: Результат проверки с полями:
                - valid: bool - валиден ли провайдер
                - error: str - сообщение об ошибке (если есть)
                - model: str - используемая модель
        """
        import httpx
        import asyncio
        
        try:
            provider = cls._create_provider(provider_type, model)
            
            # Сначала проверяем доступность сервера (быстрая проверка)
            base_url = provider.base_url
            try:
                # Пытаемся подключиться к базовому URL с коротким таймаутом
                async with httpx.AsyncClient(timeout=5.0) as client:
                    # Проверяем доступность базового URL
                    health_check_url = base_url.rstrip('/') + '/health' if not base_url.endswith('/health') else base_url
                    try:
                        await client.get(health_check_url)
                    except:
                        # Если /health недоступен, пробуем базовый URL
                        try:
                            await client.get(base_url.rstrip('/'))
                        except:
                            pass  # Продолжаем с основным тестом
            except Exception as health_error:
                logger.debug(f"Health check failed for {provider_type.value}: {health_error}")
                # Продолжаем с основным тестом
            
            # Простой тест - отправляем короткий запрос с коротким таймаутом
            test_messages = [
                LLMMessage(role="user", content="Hi")
            ]
            
            # Пытаемся сгенерировать ответ с коротким таймаутом
            try:
                # Устанавливаем короткий таймаут для валидации
                if hasattr(provider, 'client'):
                    original_timeout = provider.client.timeout
                    provider.client.timeout = httpx.Timeout(10.0)  # 10 секунд для валидации
                
                response = await asyncio.wait_for(
                    provider.generate(
                        test_messages,
                        temperature=0.7,
                        max_tokens=10
                    ),
                    timeout=15.0  # Общий таймаут 15 секунд
                )
                
                # Восстанавливаем таймаут
                if hasattr(provider, 'client'):
                    provider.client.timeout = original_timeout
                
                if response and response.content:
                    return {
                        "valid": True,
                        "error": None,
                        "model": response.model or (model or "default")
                    }
                else:
                    return {
                        "valid": False,
                        "error": "Empty response from provider",
                        "model": None
                    }
            except asyncio.TimeoutError:
                return {
                    "valid": False,
                    "error": "Connection timeout - сервер не отвечает",
                    "model": None
                }
            except httpx.ConnectError as e:
                return {
                    "valid": False,
                    "error": f"Не удалось подключиться к серверу: {str(e)}",
                    "model": None
                }
            except httpx.HTTPStatusError as e:
                return {
                    "valid": False,
                    "error": f"HTTP ошибка {e.response.status_code}: {str(e)}",
                    "model": None
                }
        except Exception as e:
            error_msg = str(e)
            # Улучшаем сообщения об ошибках
            if "Connection refused" in error_msg or "connect" in error_msg.lower():
                error_msg = "Сервер недоступен или не запущен"
            elif "timeout" in error_msg.lower():
                error_msg = "Таймаут подключения - сервер не отвечает"
            elif "404" in error_msg or "Not Found" in error_msg:
                error_msg = "Endpoint не найден - проверьте URL"
            elif "401" in error_msg or "403" in error_msg or "Unauthorized" in error_msg:
                error_msg = "Ошибка авторизации - проверьте API ключ"
            
            logger.warning(f"Provider validation failed for {provider_type.value}: {error_msg}")
            return {
                "valid": False,
                "error": error_msg,
                "model": None
            }
    
    @classmethod
    def get_available_providers(cls) -> list:
        """
        Получить список всех доступных провайдеров
        
        Returns:
            list: Список словарей с информацией о провайдерах
        """
        from config import settings
        
        providers = []
        for provider in LLMProvider:
            provider_info = {
                "name": provider.value,
                "display_name": provider.value.upper(),
                "default_model": None,
                "base_url": None
            }
            
            if provider == LLMProvider.OPENAI:
                provider_info["default_model"] = "gpt-4o-mini"
                provider_info["base_url"] = settings.openai_base_url
                provider_info["requires_api_key"] = bool(settings.openai_api_key)
            elif provider == LLMProvider.LMSTUDIO:
                provider_info["default_model"] = "local-model"
                provider_info["base_url"] = settings.lmstudio_base_url
                provider_info["requires_api_key"] = False
            elif provider == LLMProvider.CUSTOM:
                provider_info["default_model"] = "custom-model"
                provider_info["base_url"] = settings.custom_llm_base_url
                provider_info["requires_api_key"] = False
            elif provider == LLMProvider.OLLAMA:
                provider_info["default_model"] = settings.ollama_model
                provider_info["base_url"] = settings.ollama_base_url
                provider_info["requires_api_key"] = False
            
            providers.append(provider_info)
        
        return providers

