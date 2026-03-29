from typing import Optional
from app.mcp_client.agent import Agent


class ChatService:
    def __init__(self, agent: Agent):
        self.agent = agent

    async def handle_message(
        self,
        message: str,
        history: Optional[list] = None,
    ) -> str:
        return await self.agent.run(
            user_message=message,
            history=history or [],
        )