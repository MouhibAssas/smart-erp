from typing import Dict, List, Optional, Tuple

from app.mcp_client.agent import agent
from app.services import ocr_service


class ChatService:
    # Handle chat requests and delegate orchestration to the MCP agent.

    async def handle_message(self, message: str, history: Optional[List[Dict[str, str]]] = None) -> str:
        # Process a text-only chat message.
        return await agent.run(user_message=message, history=history or [])

    async def handle_upload(
        self,
        message: str,
        file_bytes: bytes,
        filename: str,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> Tuple[str, Dict[str, str]]:
        # Process a chat message with file upload and return response plus extracted payload.
        response = await agent.run(
            user_message=message,
            history=history or [],
            file_bytes=file_bytes,
            filename=filename,
        )
        extracted_data = agent.last_tool_result or {}
        if not extracted_data and hasattr(ocr_service, "extract") and callable(getattr(ocr_service, "extract")):
            extracted_data = ocr_service.extract(file_bytes=file_bytes, filename=filename)
        return response, extracted_data


chat_service = ChatService()
