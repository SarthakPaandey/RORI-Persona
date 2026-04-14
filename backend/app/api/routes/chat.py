"""Chat endpoint for the web interface."""

import json
from dataclasses import dataclass
from datetime import datetime
import re
from typing import AsyncIterator, Optional
from zoneinfo import ZoneInfo

import structlog
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.core.rag_engine import RAGEngine, RAGStreamResult
from app.models.schemas import ChatRequest, ChatResponse, SourceDocument
from app.services.calendar_service import CalendarService

logger = structlog.get_logger()
router = APIRouter()

DEFAULT_BOOKING_TIMEZONE = "Asia/Kolkata"
EMAIL_PATTERN = re.compile(r"\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[A-Za-z]{2,}\b")


@dataclass
class PreparedChatContext:
    """Normalized booking/context state shared by sync and streaming endpoints."""

    conversation_history: list
    is_booking_flow: bool
    rejected_slots: bool
    available_slots: list
    timezone: Optional[str]
    booking_link: Optional[str]
    booking_context: str = ""
    early_response: Optional[ChatResponse] = None


@router.post(
    "/chat",
    response_model=ChatResponse,
    responses={500: {"description": "Failed to process message"}},
)
async def chat(request: Request, chat_request: ChatRequest):
    """
    Process a chat message through the RAG pipeline.

    Handles:
    - General questions about background, skills, experience
    - GitHub repo questions
    - Resume questions
    - Calendar/booking requests
    - Edge cases with honest "I don't know" responses
    """
    rag_engine: RAGEngine = request.app.state.rag_engine
    settings = request.app.state.settings

    try:
        prepared = await _prepare_chat_context(chat_request, settings)
        if prepared.early_response is not None:
            return prepared.early_response

        if prepared.is_booking_flow:
            response = await rag_engine.query(
                query=chat_request.message,
                conversation_history=prepared.conversation_history,
                additional_context=prepared.booking_context,
            )
        else:
            response = await rag_engine.query(
                query=chat_request.message,
                conversation_history=prepared.conversation_history,
            )

        message = _finalize_message(
            query=chat_request.message,
            answer=response.answer,
            source_documents=response.source_documents,
            prepared=prepared,
            settings=settings,
        )

        return _build_chat_response(
            message=message,
            source_documents=response.source_documents,
            conversation_id=chat_request.conversation_id,
            booking_link=prepared.booking_link,
            available_slots=prepared.available_slots,
            timezone=prepared.timezone,
        )

    except Exception as e:
        logger.exception("Chat endpoint error")
        raise HTTPException(status_code=500, detail=_chat_error_detail(settings, e)) from e


@router.post(
    "/chat/stream",
    responses={500: {"description": "Failed to process message"}},
)
async def chat_stream(request: Request, chat_request: ChatRequest):
    """Stream chat tokens as NDJSON for lower perceived latency in the UI."""
    rag_engine: RAGEngine = request.app.state.rag_engine
    settings = request.app.state.settings

    try:
        prepared = await _prepare_chat_context(chat_request, settings)
    except Exception as exc:
        logger.exception("Chat stream setup error")
        raise HTTPException(status_code=500, detail=_chat_error_detail(settings, exc)) from exc

    async def event_stream() -> AsyncIterator[str]:
        try:
            if prepared.early_response is not None:
                yield _ndjson_event(
                    {
                        "type": "done",
                        "response": prepared.early_response.model_dump(mode="json"),
                    }
                )
                return

            if prepared.is_booking_flow:
                stream_result: RAGStreamResult = await rag_engine.stream_query(
                    query=chat_request.message,
                    conversation_history=prepared.conversation_history,
                    additional_context=prepared.booking_context,
                )
            else:
                stream_result = await rag_engine.stream_query(
                    query=chat_request.message,
                    conversation_history=prepared.conversation_history,
                )

            chunks: list[str] = []
            async for token in stream_result.token_stream:
                chunks.append(token)
                yield _ndjson_event({"type": "token", "token": token})

            message = _finalize_message(
                query=chat_request.message,
                answer="".join(chunks),
                source_documents=stream_result.source_documents,
                prepared=prepared,
                settings=settings,
            )
            final_response = _build_chat_response(
                message=message,
                source_documents=stream_result.source_documents,
                conversation_id=chat_request.conversation_id,
                booking_link=prepared.booking_link,
                available_slots=prepared.available_slots,
                timezone=prepared.timezone,
            )
            yield _ndjson_event(
                {
                    "type": "done",
                    "response": final_response.model_dump(mode="json"),
                }
            )
        except Exception as exc:
            logger.exception("Chat stream error")
            yield _ndjson_event(
                {
                    "type": "error",
                    "error": _chat_error_detail(settings, exc),
                }
            )

    return StreamingResponse(
        event_stream(),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


def _chat_error_detail(settings, error: Exception) -> str:
    """Return safe error details (verbose only in development)."""
    if settings.environment == "development":
        return f"{type(error).__name__}: {error}"[:1000]
    return "Failed to process message"


def _ndjson_event(payload: dict) -> str:
    """Serialize one NDJSON event line."""
    return json.dumps(payload, ensure_ascii=False) + "\n"


def _build_chat_response(
    *,
    message: str,
    source_documents: list,
    conversation_id: Optional[str],
    booking_link: Optional[str],
    available_slots: list,
    timezone: Optional[str],
) -> ChatResponse:
    """Construct a standard ChatResponse payload."""
    return ChatResponse(
        message=message,
        sources=[
            SourceDocument(
                content=doc.page_content[:200],
                source=doc.metadata.get("source", "unknown"),
                relevance_score=doc.metadata.get("score", 0.0),
            )
            for doc in source_documents
        ],
        conversation_id=conversation_id,
        booking_link=booking_link,
        available_slots=available_slots,
        timezone=timezone,
    )


def _finalize_message(
    *,
    query: str,
    answer: str,
    source_documents: list,
    prepared: PreparedChatContext,
    settings,
) -> str:
    """Apply deterministic post-processing to assistant output."""
    message = _sanitize_github_project_answer(
        query=query,
        answer=answer,
        source_documents=source_documents,
    )

    if prepared.is_booking_flow and (
        prepared.rejected_slots or _is_verbose_slot_dump(message)
    ):
        return _build_compact_booking_message(
            available_slots=prepared.available_slots,
            timezone=prepared.timezone or DEFAULT_BOOKING_TIMEZONE,
            booking_link=prepared.booking_link or f"https://cal.com/{settings.calcom_username}",
            rejected_slots=prepared.rejected_slots,
        )
    return message


async def _prepare_chat_context(chat_request: ChatRequest, settings) -> PreparedChatContext:
    """Prepare booking flow state and additional context for RAG execution."""
    conversation_history = chat_request.conversation_history or []
    is_role_fit_query = _is_role_fit_query(chat_request.message)
    is_booking_intent = _detect_booking_intent(chat_request.message) and not is_role_fit_query
    is_booking_flow = (
        is_booking_intent or _is_booking_context(chat_request.message, conversation_history)
    ) and not is_role_fit_query

    rejected_slots = _is_slot_rejection(chat_request.message)
    available_slots: list = []
    timezone: Optional[str] = None
    booking_link: Optional[str] = None
    booking_context = ""

    if not is_booking_flow:
        return PreparedChatContext(
            conversation_history=conversation_history,
            is_booking_flow=False,
            rejected_slots=False,
            available_slots=available_slots,
            timezone=timezone,
            booking_link=booking_link,
        )

    calendar_service = CalendarService(settings)
    timezone = _resolve_timezone(
        chat_request.timezone,
        getattr(settings, "calcom_timezone", DEFAULT_BOOKING_TIMEZONE),
    )
    booking_link = f"https://cal.com/{settings.calcom_username}"

    if (
        _assistant_requested_email(conversation_history)
        and not _email_already_provided(conversation_history, chat_request.message)
        and not _is_new_non_booking_question(chat_request.message)
        and not _extract_first_email(chat_request.message)
    ):
        return PreparedChatContext(
            conversation_history=conversation_history,
            is_booking_flow=True,
            rejected_slots=rejected_slots,
            available_slots=[],
            timezone=timezone,
            booking_link=booking_link,
            early_response=ChatResponse(
                message=_build_invalid_email_message(
                    timezone=timezone,
                    booking_link=booking_link,
                ),
                sources=[],
                conversation_id=chat_request.conversation_id,
                booking_link=booking_link,
                available_slots=[],
                timezone=timezone,
            ),
        )

    if rejected_slots:
        availability = (
            "The user said the currently shown slots do not work for them. "
            "Do not repeat those slots as available. Ask for their preferred time window "
            "(for example evening IST) and then guide them to the booking link."
        )
    else:
        try:
            available_slots = await calendar_service.get_available_slots(timezone=timezone)
            availability = _summarize_available_slots(
                available_slots,
                timezone=timezone,
            )
        except Exception as exc:
            logger.warning("Calendar context unavailable", error=str(exc))
            availability = (
                "Calendar availability could not be loaded right now. "
                "Offer the direct booking link as a fallback."
            )

    booking_context = f"""
The user wants to book a meeting. Here are bookable windows currently returned by Cal.com:
{availability}

Booking link: {booking_link}
User timezone for showing slots and booking: {timezone}

Important wording rule: describe these as "bookable slots configured in Cal.com".
Do NOT insist the candidate is absolutely free unless explicitly confirmed elsewhere.
Do NOT enumerate all slots in prose. Mention at most 3 example options and ask the user to use the booking widget for the full list.
If the user says a shown slot is not actually possible, apologize and suggest updating Cal.com availability or using the direct booking link.

Guide them to pick a time. If slots are available, invite them to choose one in chat.
Before confirming any booking, ask for the user's full name and email address explicitly.
If the chat widget is visible, ask them to fill the name and email fields and click "Confirm Interview Slot".
If calendar data is unavailable, share the direct booking link.
"""

    return PreparedChatContext(
        conversation_history=conversation_history,
        is_booking_flow=True,
        rejected_slots=rejected_slots,
        available_slots=available_slots,
        timezone=timezone,
        booking_link=booking_link,
        booking_context=booking_context,
    )


def _detect_booking_intent(message: str) -> bool:
    """Detect if the user wants to book a meeting/call."""
    message_lower = (message or "").lower()
    booking_patterns = [
        r"\bbook(?:ing)?\b",
        r"\bschedule\b",
        r"\bmeeting\b",
        r"\binterview\b",
        r"\bcalendar\b",
        r"\bslot(?:s)?\b",
        r"\bset\s+up\b",
        r"\barrange\b",
        r"\bavailability\b",
        r"\b(book|schedule)\b.*\b(call|meeting|interview|slot)\b",
        r"\b(call|meeting|interview|slot)\b.*\b(book|schedule)\b",
    ]
    return any(re.search(pattern, message_lower) for pattern in booking_patterns)


def _is_slot_rejection(message: str) -> bool:
    """Detect when user says shown slots do not work for them."""
    m = message.lower()
    rejection_markers = [
        "not free",
        "not available",
        "doesn't work",
        "does not work",
        "working hours",
        "outside working hours",
        "after work",
        "can't do",
        "cannot do",
        "not possible",
    ]
    return any(marker in m for marker in rejection_markers)


def _is_booking_context(message: str, conversation_history: list) -> bool:
    """Continue booking flow only when the latest user message is booking-related."""
    if not conversation_history:
        return False

    # If user is clearly asking a non-booking question, always exit booking flow
    if _is_new_non_booking_question(message):
        return False

    # If we already asked for email and the user already provided one earlier,
    # don't keep looping — exit booking flow unless the current message is
    # explicitly booking-related.
    if _assistant_requested_email(conversation_history):
        if _email_already_provided(conversation_history, message):
            return _detect_booking_intent(message)
        return True

    assistant_message = _latest_assistant_message(conversation_history)
    if not assistant_message:
        return False

    booking_prompt_markers = [
        "book",
        "booking",
        "interview",
        "calendar",
        "slot",
        "cal.com",
        "confirm interview slot",
        "name and email",
        "full name and email",
        "preferred time",
    ]
    assistant_lower = assistant_message.lower()
    assistant_is_booking_prompt = any(
        marker in assistant_lower for marker in booking_prompt_markers
    )
    if not assistant_is_booking_prompt:
        return False

    return _is_booking_followup_message(message)


def _latest_assistant_message(conversation_history: list) -> str:
    """Return the latest assistant content in history if present."""
    for item in reversed(conversation_history):
        role = str(getattr(item, "role", "")).lower()
        if role == "assistant":
            return str(getattr(item, "content", ""))
    return ""


def _is_booking_followup_message(message: str) -> bool:
    """Detect user replies that should stay in booking mode."""
    if not message:
        return False

    lowered = message.lower().strip()
    if _extract_first_email(message):
        return True
    if _detect_booking_intent(message):
        return True

    if re.search(r"\b\d{1,2}(?::\d{2})?\s?(?:am|pm)\b", lowered):
        return True
    if re.search(
        r"\b(today|tomorrow|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
        lowered,
    ):
        return True

    short_booking_confirms = {
        "yes",
        "yep",
        "sure",
        "ok",
        "okay",
        "book it",
        "confirm",
        "that works",
        "works",
    }
    return lowered in short_booking_confirms


def _is_role_fit_query(message: str) -> bool:
    """Detect role-fit/hireability questions that should not trigger booking flow."""
    q = (message or "").lower()
    role_fit_markers = [
        "right fit",
        "good fit",
        "fit for this role",
        "fit for the role",
        "why should we hire",
        "why hire",
        "why him",
        "why is he",
        "why is she",
        "for this role",
    ]
    if any(marker in q for marker in role_fit_markers):
        return True
    return ("fit" in q and "role" in q) or ("why" in q and "role" in q)


def _is_new_non_booking_question(message: str) -> bool:
    """Detect clear topic shifts that should exit booking follow-up mode."""
    lowered = (message or "").lower().strip()
    if not lowered:
        return False
    if _detect_booking_intent(message) or _is_booking_followup_message(message):
        return False

    question_cues = [
        "?",
        "why ",
        "what ",
        "how ",
        "who ",
        "when ",
        "where ",
        "tell me",
        "explain",
        "can you",
        "could you",
    ]
    if any(cue in lowered for cue in question_cues):
        return True

    non_booking_topics = [
        "project",
        "github",
        "repo",
        "resume",
        "experience",
        "skills",
        "background",
        "right fit",
        "good fit",
        "for this role",
    ]
    return any(topic in lowered for topic in non_booking_topics)


def _assistant_requested_email(conversation_history: list) -> bool:
    """Check if the most recent assistant message *explicitly* asks the user for email in a booking context.

    We require both an email-related marker AND a booking-action marker to avoid
    false positives from generic mentions of the word 'email' in non-booking
    responses.
    """
    if not conversation_history:
        return False

    email_markers = [
        "email address",
        "full name and email",
        "name and email",
        "provide your email",
        "share your email",
        "share a valid email",
        "your email",
    ]

    booking_context_markers = [
        "book",
        "interview",
        "booking",
        "confirm",
        "schedule",
        "slot",
        "cal.com",
        "rendezvous",
    ]

    for item in reversed(conversation_history):
        role = str(getattr(item, "role", "")).lower()
        if role != "assistant":
            continue
        content = str(getattr(item, "content", "")).lower()
        has_email = any(marker in content for marker in email_markers)
        has_booking = any(marker in content for marker in booking_context_markers)
        return has_email and has_booking

    return False


def _email_already_provided(conversation_history: list, current_message: str = "") -> bool:
    """Check if the user has already provided an email in the conversation.

    Scans all previous user messages AND the current message. If an email was
    already given, the system should not keep re-prompting.
    """
    if _extract_first_email(current_message):
        return True

    for item in conversation_history:
        role = str(getattr(item, "role", "")).lower()
        if role != "user":
            continue
        content = str(getattr(item, "content", ""))
        if _extract_first_email(content):
            return True

    return False


def _extract_first_email(message: str) -> Optional[str]:
    """Extract first valid-looking email from message."""
    match = EMAIL_PATTERN.search(message or "")
    if not match:
        return None
    return match.group(0)


def _build_invalid_email_message(timezone: str, booking_link: str) -> str:
    """Deterministic correction prompt when user provides invalid email."""
    return (
        "That does not look like a valid email address yet. "
        "Please share a valid email in the format name@example.com so I can proceed with booking. "
        "You can also send both details together like: Your Name, name@example.com. "
        f"Timezone: {timezone}. Direct booking link: {booking_link}"
    )


def _is_github_project_query(message: str) -> bool:
    """Detect GitHub/project-oriented questions."""
    q = message.lower()
    return any(
        token in q
        for token in (
            "github",
            "repo",
            "repository",
            "project",
            "portfolio",
            "open source",
        )
    )


def _has_github_sources(source_documents: list) -> bool:
    for doc in source_documents:
        source = str(getattr(doc, "metadata", {}).get("source", ""))
        if source.startswith("github:"):
            return True
    return False


def _sanitize_github_project_answer(query: str, answer: str, source_documents: list) -> str:
    """Remove contradictory no-knowledge disclaimers when GitHub sources are present."""
    if not _is_github_project_query(query):
        return answer
    if not _has_github_sources(source_documents):
        return answer

    patterns = [
        r"I don['’]t have specific information[^.]*\.\s*",
        r"I don't have specific information about that in my knowledge base\.\s*",
        r"You could ask .*? directly in an interview\.\s*",
    ]

    cleaned = answer
    for pattern in patterns:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)

    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned or answer


def _resolve_timezone(timezone: Optional[str], fallback: str) -> str:
    """Validate requested timezone, else fallback."""
    candidate = (timezone or "").strip() or (fallback or DEFAULT_BOOKING_TIMEZONE)
    try:
        ZoneInfo(candidate)
        return candidate
    except Exception:
        return fallback or DEFAULT_BOOKING_TIMEZONE


def _parse_local_datetime(iso_value: str, timezone: str) -> Optional[datetime]:
    """Parse an ISO datetime and convert it to requested timezone."""
    if not iso_value:
        return None
    try:
        dt = datetime.fromisoformat(iso_value.replace("Z", "+00:00"))
        return dt.astimezone(ZoneInfo(timezone))
    except Exception:
        return None


def _slot_example_labels(slots: list, timezone: str, limit: int = 3) -> list[str]:
    labels: list[str] = []
    for slot in slots:
        formatted = str(slot.get("formatted", "")).strip()
        if formatted:
            labels.append(formatted)
            if len(labels) >= limit:
                return labels

    for slot in slots:
        local_start = _parse_local_datetime(str(slot.get("start", "")), timezone)
        if not local_start:
            continue
        labels.append(local_start.strftime("%a %b %d · %I:%M %p"))
        if len(labels) >= limit:
            break
    return labels


def _summarize_available_slots(slots: list, timezone: str) -> str:
    """Build compact slot summary for LLM context without dumping every slot."""
    if not slots:
        return (
            "No future bookable slots found in the next 7 days. "
            "Offer the direct booking link and ask for a preferred time window."
        )

    day_counts: dict[str, int] = {}
    for slot in slots:
        local_start = _parse_local_datetime(str(slot.get("start", "")), timezone)
        if not local_start:
            continue
        day_key = local_start.strftime("%A, %b %d")
        day_counts[day_key] = day_counts.get(day_key, 0) + 1

    lines = [f"Found {len(slots)} future bookable slots in the next 7 days."]
    if day_counts:
        lines.append("Daily slot counts:")
        items = list(day_counts.items())
        for day_label, count in items[:4]:
            lines.append(f"- {day_label}: {count} slot(s)")
        if len(items) > 4:
            lines.append(f"- +{len(items) - 4} more day(s)")

    examples = _slot_example_labels(slots, timezone=timezone, limit=3)
    if examples:
        lines.append(f"Example options (max 3): {' | '.join(examples)}")

    lines.append(
        "Never enumerate all slots. Mention at most 3 examples and point to the booking widget for the full list."
    )
    return "\n".join(lines)


def _is_verbose_slot_dump(message: str) -> bool:
    """Heuristic for overly long booking replies that enumerate many slot times."""
    lowered = message.lower()
    time_mentions = len(re.findall(r"\b\d{1,2}:\d{2}\s?(?:am|pm)\b", lowered))
    slot_markers = (
        "bookable slots" in lowered
        or "slots configured" in lowered
        or "available slots" in lowered
    )
    return time_mentions >= 8 or (slot_markers and len(message) >= 900)


def _build_compact_booking_message(
    available_slots: list,
    timezone: str,
    booking_link: str,
    rejected_slots: bool,
) -> str:
    """Return deterministic concise booking copy for chat."""
    if rejected_slots:
        return (
            "Understood. I will not repeat those slots. "
            f"Please share your preferred date/time window in {timezone}, and include your full name and email address. "
            f"You can also book directly here: {booking_link}"
        )

    if not available_slots:
        return (
            "I can help schedule the interview, but I could not fetch live slots right now. "
            "Please share your preferred date/time window along with your full name and email address, "
            f"or book directly here: {booking_link}"
        )

    examples = _slot_example_labels(available_slots, timezone=timezone, limit=3)
    examples_text = " | ".join(examples) if examples else "Use the selector below for options."

    return (
        "I can help you book an interview with Sarthak. "
        f"I found {len(available_slots)} future bookable slots in the next 7 days ({timezone}). "
        f"A few options: {examples_text}. "
        "Use the Book an Interview widget below to view all slots and pick one. "
        "To confirm, please provide your full name and email address. "
        f"Direct booking link: {booking_link}"
    )
