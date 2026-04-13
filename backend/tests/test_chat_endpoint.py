"""Tests for the chat endpoint."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.models.schemas import RAGResponse


@pytest.fixture
def client_with_mocks(mock_rag_engine):
    mock_store = MagicMock()
    mock_store.similarity_search_with_score.return_value = []

    with (
        patch("app.main.VectorStoreManager") as MockVSM,
        patch("app.main.RAGEngine") as MockRAG,
    ):
        MockVSM.return_value.get_store.return_value = mock_store
        MockRAG.return_value = mock_rag_engine

        app = create_app()
        with TestClient(app) as c:
            yield c


def test_chat_returns_message(client_with_mocks, mock_rag_engine):
    res = client_with_mocks.post(
        "/api/chat",
        json={"message": "Tell me about yourself.", "conversation_history": []},
    )
    assert res.status_code == 200
    data = res.json()
    assert "message" in data
    assert len(data["message"]) > 0


def test_chat_booking_intent_returns_link(client_with_mocks, mock_rag_engine):
    with patch("app.api.routes.chat.CalendarService") as MockCal:
        instance = MockCal.return_value
        instance.get_available_slots = AsyncMock(
            return_value=[
                {
                    "start": "2024-03-15T14:00:00Z",
                    "end": "2024-03-15T14:30:00Z",
                    "formatted": "Fri Mar 15 · 2:00 PM",
                }
            ]
        )
        res = client_with_mocks.post(
            "/api/chat",
            json={"message": "Can I book a meeting?", "conversation_history": []},
        )
    assert res.status_code == 200
    data = res.json()
    assert data.get("booking_link") is not None
    assert len(data.get("available_slots", [])) == 1
    instance.get_available_slots.assert_awaited_once()


def test_chat_booking_rejection_hides_slots(client_with_mocks, mock_rag_engine):
    with patch("app.api.routes.chat.CalendarService") as MockCal:
        instance = MockCal.return_value
        instance.get_available_slots = AsyncMock(
            return_value=[
                {
                    "start": "2024-03-15T14:00:00Z",
                    "end": "2024-03-15T14:30:00Z",
                    "formatted": "Fri Mar 15 · 2:00 PM",
                }
            ]
        )

        res = client_with_mocks.post(
            "/api/chat",
            json={
                "message": "I am not free in working hours, don't show those slots.",
                "conversation_history": [],
            },
        )

    assert res.status_code == 200
    data = res.json()
    assert data.get("booking_link") is not None
    assert data.get("available_slots", []) == []
    instance.get_available_slots.assert_not_awaited()


def test_chat_booking_verbose_message_is_compacted(client_with_mocks, mock_rag_engine):
    mock_rag_engine.query = AsyncMock(
        return_value=RAGResponse(
            answer=(
                "Here are the bookable slots configured in Cal.com: "
                "05:30 AM, 06:00 AM, 06:30 AM, 07:00 AM, 07:30 AM, "
                "08:00 AM, 08:30 AM, 09:00 AM, 09:30 AM, 10:00 AM."
            ),
            source_documents=[],
            confidence=0.92,
        )
    )

    with patch("app.api.routes.chat.CalendarService") as MockCal:
        instance = MockCal.return_value
        instance.get_available_slots = AsyncMock(
            return_value=[
                {
                    "start": "2026-04-13T00:00:00+00:00",
                    "end": "2026-04-13T00:30:00+00:00",
                    "formatted": "Mon Apr 13 · 05:30 AM",
                },
                {
                    "start": "2026-04-13T00:30:00+00:00",
                    "end": "2026-04-13T01:00:00+00:00",
                    "formatted": "Mon Apr 13 · 06:00 AM",
                },
                {
                    "start": "2026-04-13T01:00:00+00:00",
                    "end": "2026-04-13T01:30:00+00:00",
                    "formatted": "Mon Apr 13 · 06:30 AM",
                },
            ]
        )

        res = client_with_mocks.post(
            "/api/chat",
            json={"message": "Can we schedule an interview?", "conversation_history": []},
        )

    assert res.status_code == 200
    data = res.json()
    assert "Use the Book an Interview widget below" in data["message"]
    assert "I found 3 future bookable slots" in data["message"]


def test_chat_booking_invalid_email_is_rejected(client_with_mocks, mock_rag_engine):
    with patch("app.api.routes.chat.CalendarService") as MockCal:
        instance = MockCal.return_value
        instance.get_available_slots = AsyncMock(return_value=[])

        res = client_with_mocks.post(
            "/api/chat",
            json={
                "message": "jdisd",
                "conversation_history": [
                    {"role": "user", "content": "Can I book an interview?"},
                    {
                        "role": "assistant",
                        "content": "Please share your full name and email address to confirm booking.",
                    },
                ],
                "timezone": "Asia/Kolkata",
            },
        )

    assert res.status_code == 200
    data = res.json()
    assert "valid email" in data["message"].lower()
    assert data.get("booking_link") is not None
    assert data.get("available_slots", []) == []
    instance.get_available_slots.assert_not_awaited()
    mock_rag_engine.query.assert_not_awaited()


def test_chat_booking_followup_uses_context_without_keyword(
    client_with_mocks,
    mock_rag_engine,
):
    with patch("app.api.routes.chat.CalendarService") as MockCal:
        instance = MockCal.return_value
        instance.get_available_slots = AsyncMock(
            return_value=[
                {
                    "start": "2026-04-13T00:00:00+00:00",
                    "end": "2026-04-13T00:30:00+00:00",
                    "formatted": "Mon Apr 13 · 05:30 AM",
                }
            ]
        )

        res = client_with_mocks.post(
            "/api/chat",
            json={
                "message": "john@example.com",
                "conversation_history": [
                    {"role": "user", "content": "Can I book an interview?"},
                    {
                        "role": "assistant",
                        "content": "Please share your full name and email address to confirm booking.",
                    },
                ],
                "timezone": "Asia/Kolkata",
            },
        )

    assert res.status_code == 200
    data = res.json()
    assert data.get("booking_link") is not None
    assert len(data.get("available_slots", [])) == 1
    instance.get_available_slots.assert_awaited_once()


def test_chat_role_fit_question_does_not_trigger_booking_flow(
    client_with_mocks,
    mock_rag_engine,
):
    with patch("app.api.routes.chat.CalendarService") as MockCal:
        res = client_with_mocks.post(
            "/api/chat",
            json={
                "message": "Why is he the right fit for this role?",
                "conversation_history": [
                    {"role": "user", "content": "Can I book an interview?"},
                    {
                        "role": "assistant",
                        "content": "I can help with booking. Please share your full name and email address.",
                    },
                ],
            },
        )

    assert res.status_code == 200
    data = res.json()
    assert data.get("booking_link") is None
    assert data.get("available_slots", []) == []
    MockCal.assert_not_called()
    mock_rag_engine.query.assert_awaited_once()


def test_health_endpoint(client_with_mocks):
    res = client_with_mocks.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "healthy"


def test_chat_missing_message_returns_422(client_with_mocks):
    res = client_with_mocks.post("/api/chat", json={})
    assert res.status_code == 422


def test_persona_endpoint_returns_metadata(client_with_mocks):
    res = client_with_mocks.get("/api/persona")
    assert res.status_code == 200
    data = res.json()
    assert data.get("name")
    assert data.get("role")
    assert "booking_link" in data


def test_chat_stream_returns_token_events(client_with_mocks, mock_rag_engine):
    async def token_stream():
        for token in ("Captain ", "Sarthak"):
            yield token

    mock_rag_engine.stream_query = AsyncMock(
        return_value=SimpleNamespace(
            token_stream=token_stream(),
            source_documents=[],
            confidence=0.9,
        )
    )

    res = client_with_mocks.post(
        "/api/chat/stream",
        json={"message": "Tell me about your skills", "conversation_history": []},
    )

    assert res.status_code == 200
    events = [json.loads(line) for line in res.text.splitlines() if line.strip()]
    assert events[0].get("type") == "token"
    assert events[-1].get("type") == "done"
    assert "message" in events[-1].get("response", {})
