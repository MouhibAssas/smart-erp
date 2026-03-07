from pydantic import BaseModel
from typing import Dict, List, Optional

class MessageHistory(BaseModel):
    role: str   # "user" or "assistant"
    content: str

class ChatRequest(BaseModel):
    message: str
    history: Optional[List[MessageHistory]] = None

class ChatResponse(BaseModel):
    response: str


class ChatUploadResponse(BaseModel):
    response: str
    extracted_data: Dict