from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import chat_routes
from app.api.routes import invoice_routes
from app.api.routes import dashboard_routes
from app.api.routes import auth_routes
from app.api.routes import conversation_routes
from app.services.extraction_service import ExtractionService
from app.mcp_client.agent import Agent
from app.api.routes import user_routes


import app.models.user
import app.models.invoice
import app.models.conversation  

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize shared services at startup.
    app.state.agent = Agent()
    logger.info("Agent initialized in app.state")

    # Schema migrations are managed by Alembic; no startup migration required here.
    
    try:
        app.state.extraction_service = ExtractionService()
        logger.info("ExtractionService initialized")
    except Exception as exc:
        # Keep app bootable; upload route will fall back if service is unavailable.
        app.state.extraction_service = None
        logger.exception("Failed to initialize ExtractionService: %s", exc)

    yield


app = FastAPI(title="SMART-ERP ", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_routes.router)
app.include_router(chat_routes.router)
app.include_router(conversation_routes.router)
app.include_router(invoice_routes.router)
app.include_router(dashboard_routes.router)
app.include_router(user_routes.router)

@app.get("/health")
async def health():
    return {"status": "ok"}