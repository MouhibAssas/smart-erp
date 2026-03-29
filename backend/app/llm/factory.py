from app.llm.providers.groq_provider import GroqProvider
from app.config import settings
from app.llm.base import BaseLLMProvider

def get_llm(provider: str = "groq") -> BaseLLMProvider:
    providers = {
        "groq": lambda: GroqProvider(api_key=settings.GROQ_API_KEY),
    }

    if provider not in providers:
        raise ValueError(f"Unknown provider: {provider}")

    return providers[provider]()