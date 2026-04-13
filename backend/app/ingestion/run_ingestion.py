"""Master ingestion script — run this to populate the vector store."""

import structlog

from app.config import get_settings
from app.core.vector_store import VectorStoreManager
from app.ingestion.ingest_github import ingest_github
from app.ingestion.ingest_resume import ingest_resume

logger = structlog.get_logger()


def run_full_ingestion():
    """Run the complete data ingestion pipeline."""
    settings = get_settings()
    vector_store_manager = VectorStoreManager(settings)

    logger.info("=" * 60)
    logger.info("Starting full data ingestion pipeline")
    logger.info("=" * 60)

    total_chunks = 0
    
    logger.info("Clearing previous vector store data...")
    vector_store_manager.delete_namespace("")

    logger.info("\n--- Ingesting Resume ---")
    try:
        resume_chunks = ingest_resume(settings, vector_store_manager)
        total_chunks += resume_chunks
        logger.info(f"Resume: {resume_chunks} chunks ingested")
    except FileNotFoundError:
        logger.error(
            "Resume PDF not found. Add a .pdf under backend/data/ or set resume_file "
            "in backend/data/persona_config.yaml"
        )
    except Exception as e:
        logger.error(f"Resume ingestion failed: {e}")

    logger.info("\n--- Ingesting GitHub Repos ---")
    try:
        github_chunks = ingest_github(settings, vector_store_manager)
        total_chunks += github_chunks
        logger.info(f"GitHub: {github_chunks} chunks ingested")
    except Exception as e:
        logger.error(f"GitHub ingestion failed: {e}")

    logger.info("=" * 60)
    logger.info(f"Ingestion complete! Total chunks: {total_chunks}")
    logger.info("=" * 60)


if __name__ == "__main__":
    run_full_ingestion()
