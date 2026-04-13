"""Pydantic models for request/response schemas."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field


class ConversationMessage(BaseModel):
    """A single message in conversation history."""

    role: str
    content: str


class ChatRequest(BaseModel):
    """Chat request payload."""

    message: str
    conversation_id: Optional[str] = None
    conversation_history: Optional[List[ConversationMessage]] = None
    timezone: Optional[str] = None


class SourceDocument(BaseModel):
    """A source document used for the response."""

    content: str
    source: str
    relevance_score: float = 0.0


class TimeSlot(BaseModel):
    """An available time slot."""

    start: datetime
    end: datetime
    formatted: str


class ChatResponse(BaseModel):
    """Chat response payload."""

    message: str
    sources: List[SourceDocument] = Field(default_factory=list)
    conversation_id: Optional[str] = None
    booking_link: Optional[str] = None
    available_slots: List[TimeSlot] = Field(default_factory=list)
    timezone: Optional[str] = None


class AvailabilityResponse(BaseModel):
    """Calendar availability response."""

    slots: List[TimeSlot]
    booking_link: str
    timezone: str


class BookingRequest(BaseModel):
    """Meeting booking request."""

    name: str
    email: EmailStr
    start_time: str
    timezone: Optional[str] = None
    notes: Optional[str] = None


class BookingResponse(BaseModel):
    """Meeting booking response."""

    success: bool
    booking_id: Optional[str] = None
    confirmed_time: Optional[str] = None
    message: str


class PersonaResponse(BaseModel):
    """Public persona metadata for the chat UI."""

    name: str
    role: str
    booking_link: str
    github_username: str
    resume_configured: bool
    voice_enabled: bool


class RAGResponse(BaseModel):
    """Internal RAG pipeline response (used in tests/mocks)."""

    answer: str
    source_documents: list = Field(default_factory=list)
    confidence: float = 0.0
