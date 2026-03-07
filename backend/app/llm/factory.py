from app.llm.providers.groq_provider import GroqProvider
from app.config import settings

def get_llm():

    return GroqProvider(api_key=settings.GROQ_API_KEY)