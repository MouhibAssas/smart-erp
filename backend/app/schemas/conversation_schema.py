from pydantic import BaseModel, field_validator
from typing import Optional, List
from datetime import datetime


class MessageSchema(BaseModel):
    id: int
    role: str  # "user" or "ai"
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationResponse(BaseModel):
    id: int
    user_id: int
    title: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}

    @field_validator("updated_at", mode="before")
    @classmethod
    def set_updated_at(cls, v, info):
        # If updated_at is None, use created_at as fallback
        if v is None and "created_at" in info.data:
            return info.data["created_at"]
        return v


class ConversationDetailResponse(BaseModel):
    id: int
    user_id: int
    title: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    messages: List[MessageSchema]

    model_config = {"from_attributes": True}

    @field_validator("updated_at", mode="before")
    @classmethod
    def set_updated_at(cls, v, info):
        # If updated_at is None, use created_at as fallback
        if v is None and "created_at" in info.data:
            return info.data["created_at"]
        return v


class ConversationSearchResponse(BaseModel):
    id: int
    user_id: int
    title: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    match_source: str  # "title" or "message"
    preview: Optional[str] = None

    model_config = {"from_attributes": True}

    @field_validator("updated_at", mode="before")
    @classmethod
    def set_updated_at(cls, v, info):
        if v is None and "created_at" in info.data:
            return info.data["created_at"]
        return v


class ChatPersistentRequest(BaseModel):
    message: str
    conversation_id: Optional[int] = None


class ChatPersistentResponse(BaseModel):
    conversation_id: int
    message_id: int
    response: str
