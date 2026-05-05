import logging

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, Depends
from sqlalchemy.orm import Session
from app.schemas.chat_schema import ChatRequest, ChatResponse, ChatUploadResponse
from app.schemas.conversation_schema import ChatPersistentRequest, ChatPersistentResponse
from app.services.chat_service import ChatService
from app.services.conversation_service import ConversationService
from app.middleware.dependencies import get_current_user
from app.database.session import get_db
from app.models.user import User

router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger(__name__)


@router.post("", response_model=ChatResponse)
async def chat(request: Request, body: ChatRequest):
    try:
        service = ChatService(agent=request.app.state.agent)
        history = [m.model_dump() for m in body.history] if body.history else []
        result = await service.handle_message(body.message, history, debug=body.debug)

        if body.debug:
            response, trace = result
            return ChatResponse(response=response, debug=trace)

        return ChatResponse(response=result)
    except Exception as e:
        logger.exception("Chat error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload", response_model=ChatUploadResponse)
async def chat_upload(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    message: str = Form(default=""),
    conversation_id: int | None = Form(default=None),
    file: UploadFile = File(...),
):
    try:
        extraction_service = request.app.state.extraction_service
        conv_service = ConversationService(db)

        file_bytes = await file.read()
        filename = file.filename or "uploaded_file"

        if conversation_id is None:
            title = message[:100] if len(message) > 100 else message
            if not title.strip():
                title = filename
            conversation = conv_service.create_conversation(current_user.id, title)
            conversation_id = conversation.id
        else:
            conv_service.get_conversation(conversation_id, current_user.id)

        user_content = message.strip() or "Please analyze this invoice document."
        if filename and filename not in user_content:
            user_content = f"{user_content}\n[File: {filename}]"

        conv_service.add_message(conversation_id, "user", user_content)

        # Step 1 — extraction always runs first (with graceful fallback)
        extracted_data = None
        response = "Extraction failed. Please fill the invoice manually."

        if extraction_service is not None:
            try:
                canonical = await extraction_service.extract_from_file(
                    file_bytes=file_bytes,
                    filename=filename,
                )
                extracted_data = canonical.model_dump()
                logger.info(
                    "✓ Extraction complete — confidence: %s, missing: %s",
                    canonical.confidence_score,
                    canonical.missing_fields,
                )
                
            except Exception as exc:
                logger.warning("⚠ Extraction failed (user will see validation form): %s", exc)
                # Don't fail the upload — return empty extracted_data so user gets validation form
                extracted_data = None

        if extracted_data:
            response = (
                f"Invoice extracted (confidence: {canonical.confidence_score:.2f}). "
                f"Please review and confirm the details."
            )

        ai_msg = conv_service.add_message(conversation_id, "ai", response)
        return ChatUploadResponse(
            response=response,
            conversation_id=conversation_id,
            message_id=ai_msg.id,
            extracted_data=extracted_data,
        )

    except Exception as e:
        logger.exception("Upload error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ── Persistent Chat (with conversations) ───────────────────────────────────────

@router.post("/persistent", response_model=ChatPersistentResponse)
async def chat_persistent(
    body: ChatPersistentRequest,
    current_user: User = Depends(get_current_user),
    request: Request = None,
    db: Session = Depends(get_db),
):
    """
    Send a message in a persistent conversation.
    - If conversation_id is None, creates a new conversation with first message as title.
    - Saves user message and AI response to database.
    """
    try:
        conv_service = ConversationService(db)
        chat_service = ChatService(agent=request.app.state.agent)
        
        # Handle conversation creation/retrieval
        conversation_id = body.conversation_id
        if conversation_id is None:
            # Create new conversation with first message as title (first 100 chars)
            title = body.message[:100] if len(body.message) > 100 else body.message
            conversation = conv_service.create_conversation(current_user.id, title)
            conversation_id = conversation.id
        else:
            # Verify user owns this conversation
            conv_service.get_conversation(conversation_id, current_user.id)
        
        # Load conversation history from database and normalize roles for LLM
        messages_in_db = conv_service.get_conversation_messages(conversation_id, current_user.id)
        def _map_role(r: str) -> str:
            return "assistant" if r == "ai" else r

        history = [{"role": _map_role(m.role), "content": m.content} for m in messages_in_db]
        
        # Save user message to database
        user_msg = conv_service.add_message(conversation_id, "user", body.message)
        
        # Get AI response
        ai_response = await chat_service.handle_message(body.message, history, debug=False)
        
        # Save AI response to database
        ai_msg = conv_service.add_message(conversation_id, "ai", ai_response)
        
        return ChatPersistentResponse(
            conversation_id=conversation_id,
            message_id=ai_msg.id,
            response=ai_response
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Persistent chat error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


