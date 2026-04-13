"""Shared test fixtures."""

import os
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.schemas import RAGResponse

# Required env vars before Settings loads
os.environ.setdefault("OPENAI_API_KEY", "sk-test")
# Isolate from developer .env so persona metadata tests are deterministic
os.environ["PERSONA_NAME"] = "Your Name"
os.environ["PERSONA_ROLE"] = "AI/ML Engineer"
os.environ.setdefault("PINECONE_API_KEY", "test-pinecone")
os.environ.setdefault("CALCOM_API_KEY", "test-cal")
os.environ.setdefault("CALCOM_EVENT_TYPE_ID", "1")
os.environ.setdefault("CALCOM_USERNAME", "testuser")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("GITHUB_USERNAME", "testuser")


@pytest.fixture(autouse=True)
def clear_settings_cache():
    from app.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def mock_rag_engine():
    engine = MagicMock()
    engine.query = AsyncMock(
        return_value=RAGResponse(
            answer="I have 3 years of experience building AI systems.",
            source_documents=[],
            confidence=0.85,
        )
    )
    return engine
