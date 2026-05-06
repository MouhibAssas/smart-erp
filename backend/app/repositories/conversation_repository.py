from sqlalchemy.orm import Session
from typing import Optional, List
from app.repositories.base_repository import BaseRepository
from app.models.conversation import Conversation, Message


class ConversationRepository(BaseRepository[Conversation]):
    def __init__(self, db: Session):
        super().__init__(Conversation, db)

    def get_by_user(self, user_id: int) -> List[Conversation]:
        """Get all conversations for a user, ordered by most recent first."""
        return self.db.query(Conversation).filter(
            Conversation.user_id == user_id
        ).order_by(Conversation.updated_at.desc()).all()

    def get_by_public_id(self, public_id: str) -> Optional[Conversation]:
        """Get a conversation by its public URL-safe identifier."""
        return self.db.query(Conversation).filter(
            Conversation.public_id == public_id
        ).first()

    def get_by_id_and_user(self, conversation_id: int, user_id: int) -> Optional[Conversation]:
        """Get a conversation only if it belongs to the user (security check)."""
        return self.db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id
        ).first()


class MessageRepository(BaseRepository[Message]):
    def __init__(self, db: Session):
        super().__init__(Message, db)

    def get_by_conversation(self, conversation_id: int) -> List[Message]:
        """Get all messages in a conversation, ordered by creation time."""
        return self.db.query(Message).filter(
            Message.conversation_id == conversation_id
        ).order_by(Message.created_at.asc()).all()

    def save_message(self, conversation_id: int, role: str, content: str) -> Message:
        """Create and save a message."""
        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content
        )
        return self.save(message)
