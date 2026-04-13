"""Calendar availability and booking endpoints."""

import structlog
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Request

from app.models.schemas import AvailabilityResponse, BookingRequest, BookingResponse, TimeSlot
from app.services.calendar_service import CalendarService

logger = structlog.get_logger()
router = APIRouter()


@router.get("/availability", response_model=AvailabilityResponse)
async def get_availability(request: Request, timezone: Optional[str] = None):
    """Get available time slots."""
    settings = request.app.state.settings
    calendar_service = CalendarService(settings)
    resolved_timezone = _resolve_timezone(
        timezone,
        calendar_service.default_timezone,
    )

    try:
        slots = await calendar_service.get_available_slots(timezone=resolved_timezone)
        return AvailabilityResponse(
            slots=[
                TimeSlot(
                    start=s["start"],
                    end=s["end"],
                    formatted=s.get(
                        "formatted",
                        calendar_service.format_slot_label(
                            s["start"],
                            timezone=resolved_timezone,
                        ),
                    ),
                )
                for s in slots
            ],
            booking_link=f"https://cal.com/{settings.calcom_username}",
            timezone=resolved_timezone,
        )
    except Exception as e:
        logger.error("Failed to get availability", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to fetch availability") from e


@router.post("/book", response_model=BookingResponse)
async def book_meeting(request: Request, booking: BookingRequest):
    """Book a meeting slot."""
    settings = request.app.state.settings
    calendar_service = CalendarService(settings)

    try:
        result = await calendar_service.create_booking(
            name=booking.name,
            email=booking.email,
            start_time=booking.start_time,
            timezone=booking.timezone,
            notes=booking.notes,
        )
        return BookingResponse(
            success=True,
            booking_id=str(result.get("id", "")) or None,
            confirmed_time=booking.start_time,
            message=f"Meeting booked! Confirmation sent to {booking.email}",
        )
    except Exception as e:
        logger.error("Failed to book meeting", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to book meeting") from e


def _resolve_timezone(timezone: Optional[str], fallback: str) -> str:
    """Validate timezone value with fallback."""
    candidate = (timezone or "").strip() or fallback
    try:
        ZoneInfo(candidate)
        return candidate
    except Exception:
        return fallback
