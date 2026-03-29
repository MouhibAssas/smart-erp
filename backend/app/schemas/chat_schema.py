from pydantic import BaseModel
from typing import  Any,Dict, List, Optional


class ChatUploadResponse(BaseModel):
    response: str
    extracted_data: Optional[dict[str, Any]] = None  # None is now valid
    
class MessageHistory(BaseModel):
    role: str   # "user" or "assistant"
    content: str

class ChatRequest(BaseModel):
    message: str
    history: Optional[List[MessageHistory]] = None

class ChatResponse(BaseModel):
    response: str
