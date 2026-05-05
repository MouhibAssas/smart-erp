from pydantic import BaseModel
from typing import Any, Dict, List, Optional


class ChatUploadResponse(BaseModel):
    response: str
    conversation_id: int
    message_id: int
    extracted_data: Optional[dict[str, Any]] = None  # None is now valid
    
class MessageHistory(BaseModel):
    role: str   # "user" or "assistant"
    content: str

class ChatRequest(BaseModel):
    message: str
    history: Optional[List[MessageHistory]] = None
    debug: bool = False

class ChatResponse(BaseModel):
    response: str
    debug: Optional[Dict[str, Any]] = None
