from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status
from app.repositories.conversation_repository import ConversationRepository, MessageRepository
from app.models.conversation import Conversation, Message, generate_public_id


class ConversationService:
    def __init__(self, db: Session):
        self.conv_repo = ConversationRepository(db)
        self.msg_repo = MessageRepository(db)

    def _generate_unique_public_id(self) -> str:
        for _ in range(20):
            public_id = generate_public_id()
            if not self.conv_repo.db.query(Conversation).filter(Conversation.public_id == public_id).first():
                return public_id
        raise RuntimeError("Unable to generate a unique conversation public_id")

    def create_conversation(self, user_id: int, title: str) -> Conversation:
        """Create a new conversation for a user."""
        for _ in range(5):
            conversation = Conversation(
                user_id=user_id,
                title=title,
                public_id=self._generate_unique_public_id(),
            )
            try:
                return self.conv_repo.save(conversation)
            except IntegrityError:
                self.conv_repo.db.rollback()
        raise RuntimeError("Unable to persist a unique conversation")

    def get_user_conversations(self, user_id: int) -> list[Conversation]:
        """Get all conversations for a user, most recent first."""
        return self.conv_repo.get_by_user(user_id)

    def get_conversation(self, conversation_id: int, user_id: int) -> Conversation:
        """Get a specific conversation (with security check that it belongs to the user)."""
        conversation = self.conv_repo.get_by_id_and_user(conversation_id, user_id)
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            )
        return conversation

    def get_conversation_by_public_id(self, public_id: str, user_id: int) -> Conversation:
        """Get a specific conversation by public identifier with ownership enforcement."""
        conversation = self.conv_repo.get_by_public_id(public_id)
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            )
        if conversation.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this conversation"
            )
        return conversation

    def delete_conversation(self, conversation_id: int, user_id: int) -> None:
        """Delete a conversation (with security check)."""
        conversation = self.get_conversation(conversation_id, user_id)
        self.conv_repo.delete(conversation)

    def delete_conversation_by_public_id(self, public_id: str, user_id: int) -> None:
        """Delete a conversation by public identifier."""
        conversation = self.get_conversation_by_public_id(public_id, user_id)
        self.conv_repo.delete(conversation)

    def add_message(self, conversation_id: int, role: str, content: str) -> Message:
        """Add a message to a conversation."""
        return self.msg_repo.save_message(conversation_id, role, content)

    def get_conversation_messages(self, conversation_id: int, user_id: int) -> list[Message]:
        """Get all messages in a conversation (with security check)."""
        # Verify user owns this conversation
        self.get_conversation(conversation_id, user_id)
        return self.msg_repo.get_by_conversation(conversation_id)

    def update_title(self, conversation_id: int, user_id: int, new_title: str) -> Conversation:
        """Update conversation title."""
        conversation = self.get_conversation(conversation_id, user_id)
        conversation.title = new_title
        self.conv_repo.db.commit()
        self.conv_repo.db.refresh(conversation)
        return conversation

    def update_title_by_public_id(self, public_id: str, user_id: int, new_title: str) -> Conversation:
        """Update conversation title by public identifier."""
        conversation = self.get_conversation_by_public_id(public_id, user_id)
        conversation.title = new_title
        self.conv_repo.db.commit()
        self.conv_repo.db.refresh(conversation)
        return conversation

    def _build_preview_snippet(self, text: str, query: str, radius: int = 40) -> str:
        """Build a short preview around the first case-insensitive match."""
        if not text:
            return ""

        lower_text = text.lower()
        lower_query = query.lower()
        index = lower_text.find(lower_query)
        if index < 0:
            compact = " ".join(text.split())
            return compact[: radius * 2].strip()

        start = max(0, index - radius)
        end = min(len(text), index + len(query) + radius)
        snippet = " ".join(text[start:end].split())
        if start > 0:
            snippet = f"...{snippet}"
        if end < len(text):
            snippet = f"{snippet}..."
        return snippet

    def search_user_conversations(self, user_id: int, query: str) -> list[dict]:
        """Search conversations by title and messages, returning match metadata."""
        conversations = self.get_user_conversations(user_id)
        q = (query or "").strip()

        def _payload(conversation: Conversation, match_source: str, preview: str | None = None) -> dict:
            return {
                "id": conversation.id,
                "conversation_id": conversation.id,
                "public_id": conversation.public_id,
                "user_id": conversation.user_id,
                "title": conversation.title,
                "created_at": conversation.created_at,
                "updated_at": conversation.updated_at,
                "match_source": match_source,
                "preview": preview,
            }

        if not q:
            return [_payload(c, "title") for c in conversations]

        lowered_q = q.lower()
        results: list[dict] = []

        for conversation in conversations:
            title = conversation.title or ""
            if lowered_q in title.lower():
                results.append(_payload(conversation, "title"))
                continue

            messages = self.msg_repo.get_by_conversation(conversation.id)
            matching_message = next(
                (
                    m
                    for m in messages
                    if m.content and lowered_q in m.content.lower()
                ),
                None,
            )
            if matching_message:
                results.append(_payload(conversation, "message", self._build_preview_snippet(matching_message.content, q)))

        return results
