
from typing import Any, Dict, List, Optional


class Agent:
    def __init__(self):
        self.last_tool_result: Optional[Dict[str, Any]] = None

    async def run(
        self,
        user_message: str,
        history: Optional[List[Dict[str, str]]] = None,
        file_bytes: Optional[bytes] = None,
        filename: Optional[str] = None,
    ) -> str:
        """
        Simple placeholder agent that just echoes the message.
        """
        if history is None:
            history = []

        return f"Agent received: {user_message}"


# Create a global agent instance
agent = Agent()