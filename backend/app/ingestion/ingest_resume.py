"""Resume ingestion pipeline."""

import structlog

from app.config import Settings
from app.core.vector_store import VectorStoreManager
from app.ingestion.chunking import chunk_resume_sections, chunk_text
from app.services.resume_service import ResumeService
from app.utils.resume_path import resolve_resume_pdf_path

logger = structlog.get_logger()


def ingest_resume(settings: Settings, vector_store_manager: VectorStoreManager):
    """Parse resume and ingest into vector store."""
    logger.info("Starting resume ingestion")

    resolved = resolve_resume_pdf_path("data")
    if not resolved:
        raise FileNotFoundError(
            "No resume PDF found. Add a PDF under backend/data/, "
            "or set resume_file in data/persona_config.yaml (see .env.example)."
        )

    resume_service = ResumeService(resume_path=str(resolved))

    sections = resume_service.parse_resume_sections()
    section_chunks = chunk_resume_sections(
        sections,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )

    full_text = resume_service.parse_resume()
    full_chunks = chunk_text(
        text=full_text,
        source="resume:full",
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        metadata={"document_type": "resume", "section": "full"},
    )

    all_chunks = section_chunks + full_chunks

    try:
        vector_store_manager.delete_namespace("resume")
    except Exception:
        pass

    vector_store_manager.add_documents(all_chunks, namespace="")
    logger.info("Resume ingestion complete", chunks=len(all_chunks))

    return len(all_chunks)
