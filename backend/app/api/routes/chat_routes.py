import logging

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from app.schemas.chat_schema import ChatRequest, ChatResponse, ChatUploadResponse
from app.services.chat_service import ChatService

router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger(__name__)


@router.post("", response_model=ChatResponse)
async def chat(request: Request, body: ChatRequest):
    try:
        service = ChatService(agent=request.app.state.agent)
        history = [m.model_dump() for m in body.history] if body.history else []
        response = await service.handle_message(body.message, history)
        return ChatResponse(response=response)
    except Exception as e:
        logger.exception("Chat error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload", response_model=ChatUploadResponse)
async def chat_upload(
    request: Request,
    message: str = Form(default=""),
    file: UploadFile = File(...),
):
    try:
        service = ChatService(agent=request.app.state.agent)
        extraction_service = request.app.state.extraction_service

        file_bytes = await file.read()
        filename = file.filename or "uploaded_file"

        # Step 1 — extraction always runs first
        extracted_data = None
        enriched_message = message

        if extraction_service is not None:
            try:
                canonical = await extraction_service.extract_from_file(
                    file_bytes=file_bytes,
                    filename=filename,
                )
                extracted_data = canonical.model_dump()
                # Force agent output format to strict JSON only (no human text, no markdown).
                json_only_instruction = (
                    "Return only valid JSON. "
                    "Do not include explanations, greetings, markdown, or any extra text."
                )
                enriched_message = (
                    f"{message}\n\n"
                    f"[EXTRACTED INVOICE]\n"
                    f"{canonical.model_dump_json(indent=2)}\n\n"
                    # This block is what enforces JSON-only response after extraction.
                    f"[OUTPUT_FORMAT]\n{json_only_instruction}"
                )
                logger.info(
                    "Extraction complete — confidence: %s, missing: %s",
                    canonical.confidence_score,
                    canonical.missing_fields,
                )
            except Exception as exc:
                logger.warning("Extraction failed, agent runs on plain message: %s", exc)

        # Step 2 — agent runs on enriched message
        response = await service.handle_message(enriched_message, history=[])

        return ChatUploadResponse(response=response, extracted_data=extracted_data)

    except Exception as e:
        logger.exception("Upload error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))