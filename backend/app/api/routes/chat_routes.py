from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from app.schemas.chat_schema import ChatRequest, ChatResponse, ChatUploadResponse
from app.services.chat_service import chat_service

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest):
    # Handle text-only chat requests.
    try:
        history = [m.model_dump() for m in request.history] if request.history else []
        response = await chat_service.handle_message(
            message=request.message,
            history=history
        )
        return ChatResponse(response=response)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload", response_model=ChatUploadResponse)
async def chat_upload(message: str = Form(...), file: UploadFile = File(...)):
    # Handle chat requests with an uploaded file.
    try:
        file_bytes = await file.read()
        response, extracted_data = await chat_service.handle_upload(
            message=message,
            file_bytes=file_bytes,
            filename=file.filename or "uploaded_file",
            history=[]
        )
        return ChatUploadResponse(response=response, extracted_data=extracted_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))