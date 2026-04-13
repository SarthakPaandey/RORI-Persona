"""GitHub repository ingestion pipeline."""

import structlog

from app.config import Settings
from app.core.vector_store import VectorStoreManager
from app.ingestion.chunking import chunk_text
from app.services.github_service import GitHubService

logger = structlog.get_logger()


def _create_repos_summary(repos) -> str:
    """Create a summary document listing all repositories."""
    lines = ["GitHub Portfolio Summary:\n"]

    for repo in repos:
        lines.append(f"• {repo.name}: {repo.description}")
        lines.append(f"  Tech: {', '.join(repo.tech_stack[:5])}")
        lines.append(f"  Last Code Push: {repo.pushed_at}")
        lines.append(f"  URL: {repo.url}")
        lines.append("")

    lines.append(f"\nTotal public repositories: {len(repos)}")

    languages = {}
    for repo in repos:
        lang = repo.language
        if lang:
            languages[lang] = languages.get(lang, 0) + 1

    lines.append("\nLanguage distribution:")
    for lang, count in sorted(languages.items(), key=lambda x: -x[1]):
        lines.append(f"  {lang}: {count} repos")

    return "\n".join(lines)


def ingest_github(settings: Settings, vector_store_manager: VectorStoreManager):
    """Fetch GitHub repos and ingest into vector store."""
    logger.info("Starting GitHub ingestion")

    github_service = GitHubService(settings)
    repos = github_service.fetch_all_repos()

    all_chunks = []

    for repo in repos:
        repo_text = github_service.format_repo_for_embedding(repo)

        chunks = chunk_text(
            text=repo_text,
            source=f"github:{repo.name}",
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
            metadata={
                "document_type": "github",
                "repo_name": repo.name,
                "repo_url": repo.url,
                "language": repo.language,
                "tech_stack": ", ".join(repo.tech_stack[:10]),
                "last_updated": repo.last_updated,
                "pushed_at": repo.pushed_at,
            },
        )
        all_chunks.extend(chunks)

    summary = _create_repos_summary(repos)
    summary_chunks = chunk_text(
        text=summary,
        source="github:summary",
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        metadata={"document_type": "github", "repo_name": "all_repos_summary"},
    )
    all_chunks.extend(summary_chunks)

    vector_store_manager.add_documents(all_chunks, namespace="")
    logger.info("GitHub ingestion complete", repos=len(repos), chunks=len(all_chunks))

    return len(all_chunks)
