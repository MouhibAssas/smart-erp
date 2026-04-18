from typing import Any, Dict, Optional, Tuple, Union
from app.mcp_client.agent import Agent


class ChatService:
    def __init__(self, agent: Agent):
        self.agent = agent

    async def handle_message(
        self,
        message: str,
        history: Optional[list] = None,
        debug: bool = False,
        enforce_tool_only: bool = True,
    ) -> Union[str, Tuple[str, Dict[str, Any]]]:
        if debug:
            return await self.agent.run_with_trace(
                user_message=message,
                history=history or [],
                enforce_tool_only=enforce_tool_only,
            )

        return await self.agent.run(
            user_message=message,
            history=history or [],
            enforce_tool_only=enforce_tool_only,
        )