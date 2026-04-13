"""Tests for the RAG engine."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.documents import Document

from app.core.rag_engine import RAGEngine
from app.models.schemas import ConversationMessage


@pytest.fixture
def settings():
    s = MagicMock()
    s.persona_name = "Test User"
    s.persona_role = "AI Engineer"
    s.retrieval_top_k = 5
    s.similarity_threshold = 0.7
    return s


@pytest.fixture
def mock_vector_store():
    vs = MagicMock()
    vs.similarity_search_with_score.return_value = [
        (
            Document(
                page_content="I have RAG experience.",
                metadata={"source": "resume:experience"},
            ),
            0.9,
        ),
    ]
    return vs


@pytest.fixture
def mock_llm():
    llm = MagicMock()
    llm.ainvoke = AsyncMock(return_value=MagicMock(content="Mocked LLM response."))
    return llm


@pytest.mark.asyncio
async def test_rag_query_returns_answer(settings, mock_vector_store, mock_llm):
    with patch("app.core.rag_engine.get_llm", return_value=mock_llm):
        engine = RAGEngine(settings, mock_vector_store)
        result = await engine.query("What is your experience?", [])

    assert result.answer == "Mocked LLM response."
    assert len(result.source_documents) > 0


@pytest.mark.asyncio
async def test_rag_query_with_history(settings, mock_vector_store, mock_llm):
    with patch("app.core.rag_engine.get_llm", return_value=mock_llm):
        engine = RAGEngine(settings, mock_vector_store)
        history = [
            ConversationMessage(role="user", content="Hi"),
            ConversationMessage(role="assistant", content="Hello!"),
        ]
        result = await engine.query("Tell me more", history)

    assert result.answer is not None


@pytest.mark.asyncio
async def test_rag_handles_empty_retrieval(settings, mock_vector_store, mock_llm):
    mock_vector_store.similarity_search_with_score.return_value = []
    with patch("app.core.rag_engine.get_llm", return_value=mock_llm):
        engine = RAGEngine(settings, mock_vector_store)
        result = await engine.query("Unknown topic", [])

    assert result.confidence == 0.0
