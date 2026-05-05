from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.repositories.conversation_repository import ConversationRepository, MessageRepository
from app.models.conversation import Conversation, Message


class ConversationService:
    def __init__(self, db: Session):
        self.conv_repo = ConversationRepository(db)
        self.msg_repo = MessageRepository(db)

    def create_conversation(self, user_id: int, title: str) -> Conversation:
        """Create a new conversation for a user."""
        conversation = Conversation(user_id=user_id, title=title)
        return self.conv_repo.save(conversation)

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

    def delete_conversation(self, conversation_id: int, user_id: int) -> None:
        """Delete a conversation (with security check)."""
        conversation = self.get_conversation(conversation_id, user_id)
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

        if not q:
            return [
                {
                    "id": c.id,
                    "user_id": c.user_id,
                    "title": c.title,
                    "created_at": c.created_at,
                    "updated_at": c.updated_at,
                    "match_source": "title",
                    "preview": None,
                }
                for c in conversations
            ]

        lowered_q = q.lower()
        results: list[dict] = []

        for conversation in conversations:
            title = conversation.title or ""
            if lowered_q in title.lower():
                results.append(
                    {
                        "id": conversation.id,
                        "user_id": conversation.user_id,
                        "title": conversation.title,
                        "created_at": conversation.created_at,
                        "updated_at": conversation.updated_at,
                        "match_source": "title",
                        "preview": None,
                    }
                )
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
                results.append(
                    {
                        "id": conversation.id,
                        "user_id": conversation.user_id,
                        "title": conversation.title,
                        "created_at": conversation.created_at,
                        "updated_at": conversation.updated_at,
                        "match_source": "message",
                        "preview": self._build_preview_snippet(matching_message.content, q),
                    }
                )

        return results
