"""FastAPI application entry point."""

from __future__ import annotations

import structlog
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.middleware.cors import build_cors_origins
from app.api.routes import calendar, chat, health, persona, voice
from app.config import get_settings
from app.core.rag_engine import RAGEngine
from app.core.vector_store import VectorStoreManager

logger = structlog.get_logger()

rag_engine: RAGEngine | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown."""
    global rag_engine

    settings = get_settings()
    logger.info("Starting AI Persona backend", environment=settings.environment)

    vector_store_manager = VectorStoreManager(settings)
    vector_store = vector_store_manager.get_store()

    rag_engine = RAGEngine(settings, vector_store)

    app.state.rag_engine = rag_engine
    app.state.settings = settings
    app.state.vector_store_manager = vector_store_manager

    logger.info("Backend initialized successfully")
    yield

    logger.info("Shutting down AI Persona backend")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    application = FastAPI(
        title="AI Persona API",
        description=f"AI representative for {settings.persona_name}",
        version="1.0.0",
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=build_cors_origins(settings),
        allow_origin_regex=r"https://.*\.vercel\.app",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(health.router, tags=["Health"])
    application.include_router(chat.router, prefix="/api", tags=["Chat"])
    application.include_router(persona.router, prefix="/api", tags=["Persona"])
    application.include_router(voice.router, prefix="/api/voice", tags=["Voice"])
    application.include_router(calendar.router, prefix="/api/calendar", tags=["Calendar"])

    return application


app = create_app()
