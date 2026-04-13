"""Vapi webhook handlers for the voice agent."""

import asyncio
import json
import re
import time as time_module
from datetime import datetime, time, timedelta
from threading import Lock
import structlog
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Request
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.services.calendar_service import CalendarService

logger = structlog.get_logger()
router = APIRouter()

# Vapi has a hard 20-second webhook timeout.
# Our total budget per webhook must stay under ~15s to leave network headroom.
VOICE_LLM_TIMEOUT_SECONDS = 12
VOICE_DEFAULT_TIMEZONE = "Asia/Kolkata"

# Aggressive timeouts to stay well under Vapi's 20s limit
_CALENDAR_FETCH_TIMEOUT = 5     # seconds — slots fetch
_CALENDAR_BOOK_TIMEOUT  = 8     # seconds — booking creation

# Short-lived, in-memory tool execution cache. Vapi can retry or redeliver the
# same tool call, so we return the original result instead of re-booking.
_TOOL_RESULT_TTL_SECONDS = 10 * 60
_ACTIVE_CALLS: Dict[str, asyncio.Task[str]] = {}
_RECENT_TOOL_RESULTS: Dict[str, tuple[float, str]] = {}
_RECENT_AVAILABILITY_CONTEXT: Dict[str, tuple[float, List[Dict[str, Any]], str]] = {}
_TOOL_CACHE_LOCK = Lock()

_MONTH_NAME_TO_NUMBER = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}

_ORDINAL_WORD_TO_DAY = {
    "first": 1,
    "second": 2,
    "third": 3,
    "fourth": 4,
    "fifth": 5,
    "sixth": 6,
    "seventh": 7,
    "eighth": 8,
    "ninth": 9,
    "tenth": 10,
    "eleventh": 11,
    "twelfth": 12,
    "thirteenth": 13,
    "fourteenth": 14,
    "fifteenth": 15,
    "sixteenth": 16,
    "seventeenth": 17,
    "eighteenth": 18,
    "nineteenth": 19,
    "twentieth": 20,
    "twenty first": 21,
    "twenty-first": 21,
    "twenty second": 22,
    "twenty-second": 22,
    "twenty third": 23,
    "twenty-third": 23,
    "twenty fourth": 24,
    "twenty-fourth": 24,
    "twenty fifth": 25,
    "twenty-fifth": 25,
    "twenty sixth": 26,
    "twenty-sixth": 26,
    "twenty seventh": 27,
    "twenty-seventh": 27,
    "twenty eighth": 28,
    "twenty-eighth": 28,
    "twenty ninth": 29,
    "twenty-ninth": 29,
    "thirtieth": 30,
    "thirty first": 31,
    "thirty-first": 31,
}

# ---------------------------------------------------------------------------
# Profile facts baked in — the LLM can answer *any* common voice question
# from this block alone, without doing a slow Pinecone retrieval.
# ---------------------------------------------------------------------------
SARTHAK_PROFILE = """
CAPTAIN SARTHAK PANDEY — PROFILE BRIEF (use this to answer any question)

Role target: AI/ML Engineer at Scaler (or similar AI-first company)
Current student: Bachelor of Science in  CS, Scaler School Of Technology, enrolled 2023 (Scaler AI/ML track)

TECHNICAL SKILLS:
- Languages: Python (production-quality, async, typed), TypeScript, JavaScript
- AI/ML: RAG pipelines, LLM integration (OpenAI, Groq, NVIDIA NIM), LangChain, LangGraph, LlamaIndex
- Voice AI: Vapi, ElevenLabs, Deepgram — built this voice assistant you are running on right now
- Vector DBs: Pinecone, Chroma, Weaviate
- Full-stack: FastAPI, Next.js, React, Node.js, PostgreSQL, MongoDB
- Cloud/Infra: Railway, Vercel, Docker, GitHub Actions
- Agentic Systems: Multi-step reasoning pipelines, function calling, autonomous agents

KEY PROJECTS:
1. FinTracker — Personal finance management app built with Next.js with AI-driven insights for expense and budget tracking
2. SSTBORROWING — Unified campus booking system for facilities and equipment with QR-based check-ins and penalty management
3. MrBully — Android accountability app using AI interventions and strict phrase-based unlocks to stop distractions
4. Tradinguiz — Flutter-based mobile quiz application with a Golang backend for interactive multiple-choice quizzes
5. StoryTeller — Interactive web-based storytelling game where AI generates stories based on user prompts
6. AnonymChat — Real-time anonymous chat app built with React, MUI, and Firebase for secure, private communication
7. portfolio — AI-powered portfolio site with this voice agent and RAG chatbot (the one you are running on)

WHY SARTHAK IS A STRONG FIT:
- He has SHIPPED production AI agents to real users — not just notebooks or demos
- He built a complete RAG pipeline from scratch (Pinecone, LangChain, streaming responses)
- He built voice AI from scratch using Vapi + ElevenLabs + Deepgram (you are the proof)
- He works in Python production-quality async code — exactly what Scaler needs
- He has hands-on experience with LLM APIs (OpenAI, Groq, NVIDIA), function calling, and context management
- He understands agentic systems: the portfolio site runs autonomous tool-calling agents
- He cares about user experience — the voice agent, the chat UI, the booking flow are all polished
- He ships fast under real constraints — this entire AI persona system was built and deployed to production
- He is a Scaler AI/ML student — he knows the platform, the learner journey, and the culture from the inside
- He is available immediately and is passionate about building AI that actually helps people learn

EDUCATION:
- Bachelor of Science in  CS, Scaler School Of Technology, enrolled 2023 (Scaler AI/ML track)
- Scaler structured curriculum: ML fundamentals, deep learning, NLP, applied AI systems

CONTACT / BOOKING:
- Book via the AI system this assistant is connected to
- The assistant can check real calendar availability and book meetings end-to-end
"""


def _build_voice_llm(settings) -> ChatOpenAI:
    """Build the fastest available LLM for voice responses (Groq preferred for low latency)."""
    if settings.groq_api_key and settings.groq_api_key.strip():
        return ChatOpenAI(
            model="llama-3.1-8b-instant",
            openai_api_key=settings.groq_api_key,
            openai_api_base=settings.groq_api_base.rstrip("/"),
            temperature=0.3,
            max_tokens=300,  # Keep voice responses short
            request_timeout=VOICE_LLM_TIMEOUT_SECONDS - 2,
        )
    # Fallback to OpenAI gpt-4o-mini (fast and cheap)
    return ChatOpenAI(
        model="gpt-4o-mini",
        openai_api_key=settings.openai_api_key,
        temperature=0.3,
        max_tokens=300,
        request_timeout=VOICE_LLM_TIMEOUT_SECONDS - 2,
    )


async def _fast_voice_answer(settings, question: str) -> str:
    """
    Answer a voice question in <10 seconds using a direct LLM call
    with Sarthak's profile embedded — no slow Pinecone retrieval.
    """
    persona_name = settings.persona_name
    system = f"""You are RORI, Captain {persona_name}'s loyal ship AI.

You represent Captain {persona_name} to recruiters and hiring managers on voice calls.

{SARTHAK_PROFILE}

RULES:
- Keep answers to 2-3 sentences max (this is a voice call, people are listening)
- Be warm, specific, and confident
- Use "his" / "he" when referring to Captain {persona_name}, NEVER "they" / "their"
- Only state facts from the profile above — never invent anything
- If asked something not in the profile, say it concisely and don't apologize excessively
"""
    llm = _build_voice_llm(settings)
    messages = [SystemMessage(content=system), HumanMessage(content=question)]
    try:
        response = await asyncio.wait_for(
            llm.ainvoke(messages),
            timeout=VOICE_LLM_TIMEOUT_SECONDS,
        )
        content = getattr(response, "content", "") or ""
        if isinstance(content, list):
            content = "".join(
                str(b.get("text", "") if isinstance(b, dict) else b) for b in content
            )
        return content.strip()
    except asyncio.TimeoutError:
        logger.error("voice_llm_timeout", question=question[:100])
        return (
            f"Captain {persona_name} is a skilled AI Engineer specializing in "
            "production RAG systems, voice AI, and full-stack Python applications. "
            "He has shipped real AI agents to production and is an ideal fit for "
            "AI Engineer roles at companies like Scaler."
        )
    except Exception as e:
        logger.error("voice_llm_error", error=str(e), question=question[:100])
        return (
            f"Captain {persona_name} is a highly skilled AI/ML Engineer "
            "with hands-on production experience in RAG, voice AI, and agentic systems."
        )


# ---------------------------------------------------------------------------
# Tool-call parsing
# ---------------------------------------------------------------------------

def _extract_tool_call_info(tool_call: Dict[str, Any]):
    """
    Extract (call_id, fn_name, arguments) from a Vapi tool call.

    Vapi/OpenAI can send two layouts:
      Flat:   {"id": "...", "name": "fn", "arguments": {...}}
      Nested: {"id": "...", "type": "function",
               "function": {"name": "fn", "arguments": "{...}"}}
    """
    call_id = tool_call.get("id", "")

    # Flat format
    fn_name = tool_call.get("name", "")
    arguments = tool_call.get("arguments", {})

    # Nested OpenAI format
    if not fn_name:
        fn_obj = tool_call.get("function", {})
        if isinstance(fn_obj, dict):
            fn_name = fn_obj.get("name", "")
            raw_args = fn_obj.get("arguments", fn_obj.get("parameters", {}))
            if isinstance(raw_args, str):
                try:
                    arguments = json.loads(raw_args)
                except (json.JSONDecodeError, TypeError):
                    arguments = {}
            elif isinstance(raw_args, dict):
                arguments = raw_args

    # JSON-string arguments in flat format
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except (json.JSONDecodeError, TypeError):
            arguments = {}

    logger.info(
        "vapi_tool_call_parsed",
        call_id=call_id,
        fn_name=fn_name,
        arguments=arguments,
        raw_keys=list(tool_call.keys()),
    )
    return call_id, fn_name, arguments


def _extract_request_scope_id(body: Dict[str, Any]) -> str:
    """Best-effort call/session identifier for idempotent tool execution."""
    message = body.get("message", {})

    candidates = [
        body.get("call"),
        message.get("call"),
        body.get("callId"),
        body.get("call_id"),
        message.get("callId"),
        message.get("call_id"),
    ]

    for candidate in candidates:
        if isinstance(candidate, dict):
            scope_id = str(candidate.get("id", "")).strip()
            if scope_id:
                return scope_id
        elif isinstance(candidate, str):
            scope_id = candidate.strip()
            if scope_id:
                return scope_id

    return ""


def _cleanup_tool_cache(now: Optional[float] = None) -> None:
    """Drop expired cached tool results."""
    reference = now if now is not None else time_module.monotonic()
    expired_keys = [
        key
        for key, (completed_at, _result) in _RECENT_TOOL_RESULTS.items()
        if reference - completed_at > _TOOL_RESULT_TTL_SECONDS
    ]
    for key in expired_keys:
        _RECENT_TOOL_RESULTS.pop(key, None)

    expired_context_keys = [
        key
        for key, (captured_at, _slots, _query) in _RECENT_AVAILABILITY_CONTEXT.items()
        if reference - captured_at > _TOOL_RESULT_TTL_SECONDS
    ]
    for key in expired_context_keys:
        _RECENT_AVAILABILITY_CONTEXT.pop(key, None)


def _tool_execution_key(
    body: Dict[str, Any],
    fn_name: str,
    call_id: str,
    arguments: Dict[str, Any],
) -> str:
    """Build a stable key so duplicate webhook deliveries reuse prior results."""
    scope_id = _extract_request_scope_id(body)
    args_key = (
        json.dumps(arguments, sort_keys=True, default=str)
        if arguments
        else ""
    )

    # Booking must be idempotent even if the model reissues the same call with a
    # fresh toolCallId, so prefer the confirmed slot fingerprint within a call.
    if fn_name == "book_meeting" and scope_id and args_key:
        return f"{scope_id}::{fn_name}::{args_key}"

    if call_id:
        prefix = f"{scope_id}::" if scope_id else ""
        return f"{prefix}{fn_name}::{call_id}"

    if not args_key:
        return f"{scope_id}::{fn_name}" if scope_id else fn_name

    if scope_id:
        return f"{scope_id}::{fn_name}::{args_key}"
    return f"{fn_name}::{args_key}"


def _reset_tool_execution_state() -> None:
    """Test helper to clear in-memory tool dedupe state."""
    _ACTIVE_CALLS.clear()
    _RECENT_TOOL_RESULTS.clear()
    _RECENT_AVAILABILITY_CONTEXT.clear()


async def _dispatch_idempotently(
    request: Request,
    body: Dict[str, Any],
    fn_name: str,
    params: Dict[str, Any],
    call_id: str = "",
) -> str:
    """Execute a tool once per logical call, reusing in-flight/completed results."""
    execution_key = _tool_execution_key(
        body=body,
        fn_name=fn_name,
        call_id=call_id,
        arguments=params,
    )

    with _TOOL_CACHE_LOCK:
        now = time_module.monotonic()
        _cleanup_tool_cache(now)

        cached = _RECENT_TOOL_RESULTS.get(execution_key)
        if cached is not None:
            logger.info(
                "vapi_tool_result_cache_hit",
                fn_name=fn_name,
                call_id=call_id,
                execution_key=execution_key,
            )
            return cached[1]

        task = _ACTIVE_CALLS.get(execution_key)
        created_task = task is None
        if created_task:
            task = asyncio.create_task(_dispatch(request, fn_name, params))
            _ACTIVE_CALLS[execution_key] = task
        else:
            logger.info(
                "vapi_tool_call_joined_inflight",
                fn_name=fn_name,
                call_id=call_id,
                execution_key=execution_key,
            )

    assert task is not None

    try:
        result = await task
    finally:
        if created_task:
            with _TOOL_CACHE_LOCK:
                if task.done() and not task.cancelled() and task.exception() is None:
                    _RECENT_TOOL_RESULTS[execution_key] = (
                        time_module.monotonic(),
                        task.result(),
                    )
                if _ACTIVE_CALLS.get(execution_key) is task:
                    _ACTIVE_CALLS.pop(execution_key, None)

    return result


def _safe_timezone_name(candidate: str) -> str:
    """Return a valid timezone name or the default timezone."""
    try:
        ZoneInfo(candidate)
        return candidate
    except Exception:
        return VOICE_DEFAULT_TIMEZONE


def _parse_iso_datetime(value: str, timezone: str) -> Optional[datetime]:
    """Parse an ISO datetime string, attaching timezone when naive."""
    raw = (value or "").strip()
    if not raw:
        return None

    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo(timezone))

    return parsed.astimezone(ZoneInfo(timezone))


def _extract_requested_day_offset(text: str) -> Optional[int]:
    """Infer day offset from natural-language requests."""
    lowered = (text or "").lower()
    if "day after tomorrow" in lowered:
        return 2
    if "tomorrow" in lowered:
        return 1
    if "today" in lowered:
        return 0
    return None


def _extract_explicit_month_day(text: str) -> Optional[tuple[int, int]]:
    """Parse explicit month/day phrases like 'April fifteenth'."""
    lowered = (text or "").lower()
    month_match = re.search(
        r"\b("
        + "|".join(_MONTH_NAME_TO_NUMBER.keys())
        + r")\s+([a-z-]+(?:\s+[a-z-]+)?|\d{1,2}(?:st|nd|rd|th)?)\b",
        lowered,
    )
    if not month_match:
        return None

    month = _MONTH_NAME_TO_NUMBER[month_match.group(1)]
    day_token = month_match.group(2).strip()

    day: Optional[int] = None
    numeric_match = re.fullmatch(r"(\d{1,2})(?:st|nd|rd|th)?", day_token)
    if numeric_match:
        day = int(numeric_match.group(1))
    else:
        day = _ORDINAL_WORD_TO_DAY.get(day_token)

    if day is None:
        return None
    return month, day


def _extract_after_time(text: str) -> Optional[time]:
    """Extract phrases like "after 3 PM" into a time constraint."""
    match = re.search(
        r"\bafter\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b",
        text or "",
        flags=re.IGNORECASE,
    )
    if not match:
        return None

    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    meridiem = (match.group(3) or "").lower()

    if meridiem:
        if hour == 12:
            hour = 0
        if meridiem == "pm":
            hour += 12

    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        return None
    return time(hour=hour, minute=minute)


def _parse_clock_time(hour_text: str, minute_text: str, meridiem: str) -> Optional[time]:
    """Convert loose spoken clock fragments into a time object."""
    hour = int(hour_text)
    minute = int(minute_text or 0)
    suffix = (meridiem or "").lower()

    if suffix:
        if hour == 12:
            hour = 0
        if suffix == "pm":
            hour += 12

    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        return None
    return time(hour=hour, minute=minute)


def _extract_time_range(text: str) -> tuple[Optional[time], Optional[time]]:
    """Parse phrases like 'from 5 30 PM to 6 PM' into start/end times."""
    lowered = (text or "").lower()
    pattern = re.compile(
        r"\b(?:from\s+)?(\d{1,2})(?:(?::|\s+)(\d{2}))?\s*(am|pm)\s+to\s+"
        r"(\d{1,2})(?:(?::|\s+)(\d{2}))?\s*(am|pm)\b"
    )
    match = pattern.search(lowered)
    if not match:
        return None, None

    start = _parse_clock_time(match.group(1), match.group(2) or "", match.group(3))
    end = _parse_clock_time(match.group(4), match.group(5) or "", match.group(6))
    return start, end


def _extract_exact_time(text: str) -> Optional[time]:
    """Parse a single exact time like 'at 5:30 PM' or '5 30 PM'."""
    lowered = (text or "").lower()
    range_start, _range_end = _extract_time_range(lowered)
    if range_start is not None:
        return range_start

    match = re.search(
        r"\b(?:at\s+)?(\d{1,2})(?:(?::|\s+)(\d{2}))?\s*(am|pm)\b",
        lowered,
    )
    if not match:
        return None
    return _parse_clock_time(match.group(1), match.group(2) or "", match.group(3))


def _slot_datetime(slot: Dict[str, Any], timezone: str) -> Optional[datetime]:
    """Parse a slot's start timestamp in the target timezone."""
    return _parse_iso_datetime(str(slot.get("start", "")), timezone=timezone)


def _build_slot_pairs(
    slots: List[Dict[str, Any]],
    timezone: str,
) -> List[tuple[datetime, Dict[str, Any]]]:
    """Build (slot_datetime, slot_payload) pairs for valid slots only."""
    pairs: List[tuple[datetime, Dict[str, Any]]] = []
    for slot in slots:
        slot_dt = _slot_datetime(slot, timezone=timezone)
        if slot_dt is not None:
            pairs.append((slot_dt, slot))
    return pairs


def _pick_slot_from_iso_request(
    requested_dt: datetime,
    slot_pairs: List[tuple[datetime, Dict[str, Any]]],
) -> Optional[Dict[str, Any]]:
    """Pick an exact slot match first, else the closest future slot."""
    for slot_dt, slot in slot_pairs:
        if abs((slot_dt - requested_dt).total_seconds()) < 60:
            return slot

    future = [pair for pair in slot_pairs if pair[0] >= requested_dt]
    if not future:
        return None
    return min(future, key=lambda pair: pair[0])[1]


def _matches_phrase_constraints(
    slot_dt: datetime,
    slot_end_dt: Optional[datetime],
    timezone: str,
    target_date,
    explicit_month_day: Optional[tuple[int, int]],
    after_time: Optional[time],
    exact_start_time: Optional[time],
    exact_end_time: Optional[time],
) -> bool:
    """Return True when a slot matches phrase-derived date/time constraints."""
    local_dt = slot_dt.astimezone(ZoneInfo(timezone))
    local_end = slot_end_dt.astimezone(ZoneInfo(timezone)) if slot_end_dt else None

    if target_date is not None and local_dt.date() != target_date:
        return False
    if explicit_month_day is not None and (
        local_dt.month != explicit_month_day[0] or local_dt.day != explicit_month_day[1]
    ):
        return False
    if exact_start_time is not None and local_dt.time() != exact_start_time:
        return False
    if exact_end_time is not None and (local_end is None or local_end.time() != exact_end_time):
        return False
    if after_time is not None and local_dt.time() < after_time:
        return False
    return True


def _slot_end_datetime(slot: Dict[str, Any], timezone: str) -> Optional[datetime]:
    """Parse a slot's end timestamp in the target timezone."""
    return _parse_iso_datetime(str(slot.get("end", "")), timezone=timezone)


def _pick_slot_from_phrase_request(
    requested: str,
    slot_pairs: List[tuple[datetime, Dict[str, Any]]],
    timezone: str,
) -> Optional[Dict[str, Any]]:
    """Pick a slot from natural-language phrasing like 'tomorrow after 3 PM'."""
    lowered = (requested or "").lower()
    day_offset = _extract_requested_day_offset(lowered)
    after_time = _extract_after_time(lowered)
    exact_start_time, exact_end_time = _extract_time_range(lowered)
    if exact_start_time is None and after_time is None:
        exact_start_time = _extract_exact_time(lowered)

    explicit_month_day = _extract_explicit_month_day(lowered)
    target_date = None
    if explicit_month_day is None and day_offset is not None:
        now_local = datetime.now(ZoneInfo(timezone))
        target_date = (now_local + timedelta(days=day_offset)).date()

    matches = [
        (slot_dt, slot)
        for slot_dt, slot in slot_pairs
        if _matches_phrase_constraints(
            slot_dt,
            _slot_end_datetime(slot, timezone),
            timezone,
            target_date,
            explicit_month_day,
            after_time,
            exact_start_time,
            exact_end_time,
        )
    ]
    if not matches:
        return None
    return min(matches, key=lambda pair: pair[0])[1]


def _select_best_slot(
    requested: str,
    slots: List[Dict[str, Any]],
    timezone: str,
) -> Optional[Dict[str, Any]]:
    """Map a requested datetime phrase to the closest valid available slot."""
    if not slots:
        return None

    slot_pairs = _build_slot_pairs(slots, timezone=timezone)
    if not slot_pairs:
        return None

    requested_dt = _parse_iso_datetime(requested, timezone=timezone)
    if requested_dt is not None:
        return _pick_slot_from_iso_request(requested_dt, slot_pairs)

    return _pick_slot_from_phrase_request(requested, slot_pairs, timezone)


def _format_slot_suggestions(
    calendar_service: CalendarService,
    slots: List[Dict[str, Any]],
    timezone: str,
    limit: int = 3,
) -> str:
    """Format a short, human-readable list of slot suggestions."""
    labels: List[str] = []
    for slot in slots[:limit]:
        start = str(slot.get("start", ""))
        label = slot.get("formatted") or calendar_service.format_slot_label(
            start,
            timezone=timezone,
        )
        labels.append(label)

    return ", ".join(labels)


def _format_availability_response(
    calendar_service: CalendarService,
    slots: List[Dict[str, Any]],
    timezone: str,
    heading: str,
) -> str:
    """Render grouped slot text for the voice model."""
    if not slots:
        return heading

    lines = [heading, ""]
    current_date = None
    for slot in slots:
        start_local = _slot_datetime(slot, timezone)
        end_local = _slot_end_datetime(slot, timezone)
        if not start_local or not end_local:
            continue

        slot_date = start_local.date().isoformat()
        if slot_date != current_date:
            current_date = slot_date
            lines.append(f"📅 {start_local.strftime('%A, %B %d, %Y')}:")

        lines.append(
            f" • {start_local.strftime('%I:%M %p')} - {end_local.strftime('%I:%M %p')}"
        )

    return "\n".join(lines).strip()


def _store_recent_availability_context(
    scope_id: str,
    slots: List[Dict[str, Any]],
    request_text: str,
) -> None:
    """Remember the most recently surfaced slots for this call."""
    if not scope_id:
        return

    with _TOOL_CACHE_LOCK:
        _cleanup_tool_cache()
        _RECENT_AVAILABILITY_CONTEXT[scope_id] = (
            time_module.monotonic(),
            slots,
            request_text,
        )


def _recent_availability_slots(scope_id: str) -> List[Dict[str, Any]]:
    """Return the last slots offered during this call, if any."""
    if not scope_id:
        return []

    with _TOOL_CACHE_LOCK:
        _cleanup_tool_cache()
        context = _RECENT_AVAILABILITY_CONTEXT.get(scope_id)
        if context is None:
            return []
        return list(context[1])


def _filter_slots_for_request(
    requested: str,
    slots: List[Dict[str, Any]],
    timezone: str,
) -> List[Dict[str, Any]]:
    """Reduce slots to those matching the scheduling request when possible."""
    if not requested.strip():
        return slots

    lowered = requested.lower()
    day_offset = _extract_requested_day_offset(lowered)
    after_time = _extract_after_time(lowered)
    exact_start_time, exact_end_time = _extract_time_range(lowered)
    if exact_start_time is None and after_time is None:
        exact_start_time = _extract_exact_time(lowered)

    explicit_month_day = _extract_explicit_month_day(lowered)
    target_date = None
    if explicit_month_day is None and day_offset is not None:
        now_local = datetime.now(ZoneInfo(timezone))
        target_date = (now_local + timedelta(days=day_offset)).date()

    if (
        target_date is None
        and explicit_month_day is None
        and after_time is None
        and exact_start_time is None
        and exact_end_time is None
    ):
        return slots

    filtered: List[Dict[str, Any]] = []
    for slot in slots:
        slot_dt = _slot_datetime(slot, timezone)
        if slot_dt is None:
            continue
        if not _matches_phrase_constraints(
            slot_dt,
            _slot_end_datetime(slot, timezone),
            timezone,
            target_date,
            explicit_month_day,
            after_time,
            exact_start_time,
            exact_end_time,
        ):
            continue
        filtered.append(slot)

    return filtered or slots


# ---------------------------------------------------------------------------
# Main webhook
# ---------------------------------------------------------------------------

@router.post("/vapi/webhook")
async def vapi_webhook(request: Request):
    body = await request.json()
    request.state.vapi_body = body
    message = body.get("message", {})
    message_type = message.get("type", "")

    logger.info("vapi_webhook", type=message_type)

    if message_type == "tool-calls":
        return await _handle_tool_calls(request, body)
    if message_type == "function-call":
        return await _handle_function_call(request, body)
    if message_type == "assistant-request":
        return _handle_assistant_request(request)
    if message_type == "end-of-call-report":
        return _handle_call_report(body)
    if message_type == "status-update":
        return _handle_status_update(body)

    logger.warning("vapi_unknown_type", type=message_type)
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Tool-calls handler (modern Vapi format)
# ---------------------------------------------------------------------------

async def _handle_tool_calls(request: Request, body: Dict[str, Any]):
    message = body.get("message", {})
    tool_call_list = message.get("toolCallList", [])

    # Also check toolWithToolCallList (some Vapi versions send it here)
    if not tool_call_list:
        for item in message.get("toolWithToolCallList", []):
            tc = item.get("toolCall", {})
            if tc:
                tool_call_list.append(tc)

    logger.info("vapi_tool_calls", count=len(tool_call_list))

    # ── Deduplicate by function name ──────────────────────────────────
    # Vapi / the LLM sometimes sends the SAME tool call 20-30 times in one
    # webhook when the model is uncertain.  We execute each unique
    # (fn_name, args) combination exactly once and reuse the result for
    # all duplicates.  For parameterless functions like get_availability
    # we further deduplicate by name alone.
    results = []
    cached_results: Dict[str, str] = {}          # cache_key → result
    for tc in tool_call_list:
        call_id, fn_name, arguments = _extract_tool_call_info(tc)

        # For parameterless functions, dedup by name only.
        # For others, include args in the key.
        if not arguments or arguments == {}:
            cache_key = fn_name
        else:
            args_key = json.dumps(arguments, sort_keys=True, default=str)
            cache_key = f"{fn_name}::{args_key}"

        if cache_key in cached_results:
            logger.info("vapi_tool_call_deduped", call_id=call_id, fn_name=fn_name)
            result_text = cached_results[cache_key]
        else:
            result_text = await _dispatch_idempotently(
                request,
                body,
                fn_name,
                arguments,
                call_id=call_id,
            )
            cached_results[cache_key] = result_text

        results.append({"toolCallId": call_id, "result": result_text})

    return {"results": results}


# ---------------------------------------------------------------------------
# Legacy function-call handler
# ---------------------------------------------------------------------------

async def _handle_function_call(request: Request, body: Dict[str, Any]):
    fc = body["message"].get("functionCall", {})
    call_id = str(fc.get("id", "")).strip()
    fn_name = fc.get("name", "")
    parameters = fc.get("parameters", {})
    logger.info("vapi_legacy_function_call", name=fn_name)
    result = await _dispatch_idempotently(
        request,
        body,
        fn_name,
        parameters,
        call_id=call_id,
    )
    return {"result": result}


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

async def _dispatch(request: Request, fn_name: str, params: Dict[str, Any]) -> str:
    logger.info("vapi_dispatch", fn_name=fn_name)
    if fn_name == "get_background_info":
        return await _get_background_info(request, params)
    if fn_name == "get_github_info":
        return await _get_github_info(request, params)
    if fn_name == "get_availability":
        return await _get_availability(request, params)
    if fn_name == "book_meeting":
        return await _book_meeting(request, params)
    logger.error("vapi_unknown_fn", fn_name=fn_name)
    return f"I don't have a handler for '{fn_name}'."


# ---------------------------------------------------------------------------
# Tool implementations — all use _fast_voice_answer, not slow RAG
# ---------------------------------------------------------------------------

async def _get_background_info(request: Request, parameters: Dict[str, Any]) -> str:
    """Answer background/role-fit questions fast — no Pinecone, direct LLM call."""
    settings = request.app.state.settings
    question = parameters.get("question", "Tell me about Captain Sarthak Pandey")
    return await _fast_voice_answer(settings, question)


async def _get_github_info(request: Request, parameters: Dict[str, Any]) -> str:
    """Answer project/repo questions fast — no Pinecone, direct LLM call."""
    settings = request.app.state.settings
    repo_name = parameters.get("repo_name", "")
    question = parameters.get("question", f"Tell me about the {repo_name} project")
    full_q = f"Tell me about the GitHub repository '{repo_name}': {question}" if repo_name else question
    return await _fast_voice_answer(settings, full_q)


async def _get_availability(request: Request, parameters: Optional[Dict[str, Any]] = None) -> str:
    settings = request.app.state.settings
    calendar_service = CalendarService(settings)
    params = parameters or {}
    request_text = str(params.get("request", "")).strip()
    scope_id = _extract_request_scope_id(getattr(request.state, "vapi_body", {}) or {})
    timezone = calendar_service.default_timezone
    try:
        slots = await asyncio.wait_for(
            calendar_service.get_available_slots(timezone=timezone),
            timeout=_CALENDAR_FETCH_TIMEOUT,
        )
        filtered_slots = _filter_slots_for_request(
            request_text,
            slots,
            timezone=timezone,
        )
        _store_recent_availability_context(scope_id, filtered_slots, request_text)
        if not filtered_slots:
            return (
                f"I could not find a matching slot in the next 7 days. "
                f"You can also book directly at https://cal.com/{settings.calcom_username}"
            )
        if request_text:
            return _format_availability_response(
                calendar_service,
                filtered_slots,
                timezone,
                heading=(
                    f"Matching bookable slots for '{request_text}' "
                    f"(next 7 days, timezone: {timezone}):"
                ),
            )

        return _format_availability_response(
            calendar_service,
            filtered_slots,
            timezone,
            heading=(
                "Bookable slots from the Cal.com availability schedule "
                f"(next 7 days, timezone: {timezone}):"
            ),
        )
    except asyncio.TimeoutError:
        logger.warning("availability_timeout")
        return (
            f"Calendar is taking a moment — you can also book directly at "
            f"https://cal.com/{settings.calcom_username}"
        )
    except Exception as e:
        logger.error("availability_error", error=str(e))
        return (
            f"I'm having trouble accessing the calendar. "
            f"You can book directly at https://cal.com/{settings.calcom_username}"
        )


async def _book_meeting(request: Request, parameters: Dict[str, Any]) -> str:
    settings = request.app.state.settings
    calendar_service = CalendarService(settings)
    requested_time = str(parameters.get("datetime", "")).strip()
    selection_text = str(parameters.get("selection", "")).strip()
    timezone = _safe_timezone_name(getattr(settings, "calcom_timezone", VOICE_DEFAULT_TIMEZONE))
    scope_id = _extract_request_scope_id(getattr(request.state, "vapi_body", {}) or {})

    # ── Fetch available slots (best-effort, short timeout) ────────────
    available_slots: List[Dict[str, Any]] = []
    try:
        scoped_slots = _recent_availability_slots(scope_id)
        if scoped_slots:
            available_slots = scoped_slots
        else:
            available_slots = await asyncio.wait_for(
                calendar_service.get_available_slots(timezone=timezone),
                timeout=_CALENDAR_FETCH_TIMEOUT,
            )
    except asyncio.TimeoutError:
        logger.warning("book_meeting_slots_timeout")
    except Exception as e:
        logger.warning("book_meeting_slots_unavailable", error=str(e))

    if not requested_time and not selection_text:
        if available_slots:
            suggestions = _format_slot_suggestions(calendar_service, available_slots, timezone)
            return (
                "I need one exact time to lock the booking. "
                f"The next bookable options are: {suggestions}. "
                "Tell me which one you want."
            )
        return "I need an exact date and time to book. Could you share that slot?"

    selected_slot: Optional[Dict[str, Any]] = None
    if selection_text:
        selected_slot = _select_best_slot(
            requested=selection_text,
            slots=available_slots,
            timezone=timezone,
        )

    if selected_slot is None and requested_time:
        selected_slot = _select_best_slot(
            requested=requested_time,
            slots=available_slots,
            timezone=timezone,
        )

    if selected_slot is None and available_slots:
        suggestions = _format_slot_suggestions(calendar_service, available_slots, timezone)
        return (
            "I could not match that exact request to a currently bookable slot. "
            f"Please choose one of these: {suggestions}."
        )

    start_time = str(selected_slot.get("start")) if selected_slot else requested_time
    attendee_name = str(parameters.get("name", "")).strip() or "Interviewer (Voice)"
    attendee_email = (
        str(parameters.get("email", "")).strip() or "interviewer-voice@example.com"
    )

    booked_label = (
        str(selected_slot.get("formatted", ""))
        if selected_slot
        else calendar_service.format_slot_label(start_time, timezone=timezone)
    )

    try:
        await asyncio.wait_for(
            calendar_service.create_booking(
                name=attendee_name,
                email=attendee_email,
                start_time=start_time,
                timezone=timezone,
                notes=f"Voice booking request: {selection_text or requested_time}",
            ),
            timeout=_CALENDAR_BOOK_TIMEOUT,
        )
        return (
            f"Locked in! I have booked your meeting for {booked_label} ({timezone}). "
            "Only confirm the booked slot. Do not promise reminders, emails, or meeting links unless a tool explicitly returned them."
        )
    except asyncio.TimeoutError:
        logger.error("book_meeting_timeout", start_time=start_time)
        return (
            f"The booking is being processed but took longer than expected. "
            f"Please verify at https://cal.com/{settings.calcom_username}"
        )
    except Exception as e:
        logger.error("book_meeting_error", error=str(e))
        if available_slots:
            suggestions = _format_slot_suggestions(calendar_service, available_slots, timezone)
            return (
                "I could not lock that exact slot because it may no longer be available. "
                f"The next bookable options are: {suggestions}. "
                "Tell me which one to book."
            )
        return (
            f"I had trouble booking that slot. "
            f"Please try at https://cal.com/{settings.calcom_username}"
        )


# ---------------------------------------------------------------------------
# Non-tool webhook handlers
# ---------------------------------------------------------------------------

def _handle_assistant_request(request: Request):
    settings = request.app.state.settings
    return {
        "assistant": {
            "firstMessage": (
                f"I am RORI, Captain {settings.persona_name}'s loyal ship AI. "
                "Ask me about his skills, projects, why he is the right fit, "
                "or schedule a meeting."
            ),
        }
    }


def _handle_call_report(body: Dict[str, Any]):
    report = body.get("message", {})
    logger.info(
        "vapi_call_ended",
        duration=report.get("duration"),
        summary=report.get("summary"),
        cost=report.get("cost"),
    )
    return {"status": "ok"}


def _handle_status_update(body: Dict[str, Any]):
    status = body.get("message", {}).get("status", "")
    logger.info("vapi_status", status=status)
    return {"status": "ok"}
