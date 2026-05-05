from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from typing import List
from app.database.session import get_db
from app.middleware.dependencies import get_current_user
from app.models.user import User
from app.services.conversation_service import ConversationService
from app.schemas.conversation_schema import ConversationResponse, ConversationDetailResponse
from pydantic import BaseModel

router = APIRouter(prefix="/conversations", tags=["conversations"])


class ConversationTitleUpdate(BaseModel):
    title: str


@router.get("", response_model=List[ConversationResponse])
def list_conversations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all conversations for the current user."""
    service = ConversationService(db)
    conversations = service.get_user_conversations(current_user.id)
    return conversations


@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
def get_conversation(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific conversation with all its messages."""
    service = ConversationService(db)
    conversation = service.get_conversation(conversation_id, current_user.id)
    return conversation


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a conversation."""
    service = ConversationService(db)
    service.delete_conversation(conversation_id, current_user.id)


@router.patch("/{conversation_id}/title", response_model=ConversationResponse)
def update_conversation_title(
    conversation_id: int,
    payload: ConversationTitleUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a conversation's title."""
    service = ConversationService(db)
    conversation = service.update_title(conversation_id, current_user.id, payload.title)
    return conversation
