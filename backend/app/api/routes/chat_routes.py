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
    message: str = Form(default=""),
    file: UploadFile = File(...),
):
    try:
        service = ChatService(agent=request.app.state.agent)
        extraction_service = request.app.state.extraction_service

        file_bytes = await file.read()
        filename = file.filename or "uploaded_file"

        # Step 1 — extraction always runs first (with graceful fallback)
        extracted_data = None
        enriched_message = message

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
                
                # Even if confidence is low, return extracted data for user to validate
                # Only add agent instruction if confidence is high
                if canonical.confidence_score >= 0.7:
                    json_only_instruction = (
                        "Return only valid JSON. "
                        "Do not include explanations, greetings, markdown, or any extra text."
                    )
                    enriched_message = (
                        f"{message}\n\n"
                        f"[EXTRACTED INVOICE]\n"
                        f"{canonical.model_dump_json(indent=2)}\n\n"
                        f"[OUTPUT_FORMAT]\n{json_only_instruction}"
                    )
                
            except Exception as exc:
                logger.warning("⚠ Extraction failed (user will see validation form): %s", exc)
                # Don't fail the upload — return empty extracted_data so user gets validation form
                extracted_data = None

        # Step 2 — agent can run on enriched message if extraction was high-confidence
        # Otherwise just return success and let UI show validation form
        response = message
        if enriched_message != message:
            response = await service.handle_message(
                enriched_message,
                history=[],
                debug=False,
                enforce_tool_only=False,
            )

        return ChatUploadResponse(response=response, extracted_data=extracted_data)

    except Exception as e:
        logger.exception("Upload error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))