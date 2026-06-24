from abc import ABC, abstractmethod
from typing import List, Dict, Union


class BaseLLMProvider(ABC):
    @abstractmethod
    async def generate(
        self,
        messages: Union[List[Dict[str, str]], str],
        temperature: float = 0.7,
    ) -> str:
        pass