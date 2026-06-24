from app.llm.base import BaseLLMProvider
from groq import AsyncGroq
from typing import List, Dict, Union


class GroqProvider(BaseLLMProvider):

    def __init__(self, api_key: str, model: str = "llama-3.1-8b-instant"):
        self.client = AsyncGroq(api_key=api_key)
        self.model = model

    async def generate(
        self,
        messages: Union[List[Dict[str, str]], str],
        temperature: float = 0.7,
    ) -> str:
        if isinstance(messages, str):
            formatted_messages = [{"role": "user", "content": messages}]
        else:
            formatted_messages = messages

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=formatted_messages,
            temperature=temperature,
        )

        return response.choices[0].message.content