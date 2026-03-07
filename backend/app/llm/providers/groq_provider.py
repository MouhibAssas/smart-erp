from app.llm.base import BaseLLMProvider
from groq import Groq

class GroqProvider(BaseLLMProvider):

    def __init__(self, api_key):
        self.client = Groq(api_key=api_key)

    def generate(self, prompt: str):

        response = self.client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}]
        )

        return response.choices[0].message.content