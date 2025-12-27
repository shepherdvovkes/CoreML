"""
Провайдер для LMStudio API (OpenAI-совместимый)
"""
from .openai_provider import OpenAIProvider


class LMStudioProvider(OpenAIProvider):
    """Провайдер для работы с LMStudio (использует OpenAI-совместимый API)"""
    
    def __init__(self, base_url: str, api_key: str = "lm-studio", model: str = "local-model"):
        # LMStudio использует OpenAI-совместимый API, но обычно не требует API ключ
        super().__init__(base_url, api_key or "lm-studio", model)

