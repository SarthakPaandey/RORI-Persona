"""Cal.com calendar integration (API v2 — v1 is decommissioned)."""

import structlog
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

import httpx

from app.config import Settings

logger = structlog.get_logger()

CALCOM_V2_BASE = "https://api.cal.com"
# https://docs.cal.com/docs/api-reference/v2/slots/get-available-time-slots-for-an-event-type
CAL_SLOTS_API_VERSION = "2024-09-04"
# https://docs.cal.com/docs/api-reference/v2/bookings/create-a-booking
CAL_BOOKINGS_API_VERSION = "2026-02-25"

DEFAULT_TIMEZONE = "America/New_York"


class CalendarService:
    """Handles calendar availability and booking via Cal.com API v2."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.api_key = settings.calcom_api_key
        self.event_type_id = settings.calcom_event_type_id
        self.username = settings.calcom_username
        self.default_timezone = self._normalize_timezone(
            getattr(settings, "calcom_timezone", "") or DEFAULT_TIMEZONE,
            DEFAULT_TIMEZONE,
        )

    @staticmethod
    def _normalize_timezone(timezone: Optional[str], fallback: str) -> str:
        """Return a valid IANA timezone, else fallback."""
        candidate = (timezone or "").strip() or fallback
        try:
            ZoneInfo(candidate)
            return candidate
        except Exception:
            return fallback

    @staticmethod
    def _to_timezone(iso_value: str, timezone: str) -> Optional[datetime]:
        """Parse ISO datetime and convert to requested timezone."""
        try:
            dt = datetime.fromisoformat(iso_value.replace("Z", "+00:00"))
            return dt.astimezone(ZoneInfo(timezone))
        except Exception:
            return None

    def _auth_headers(self, cal_api_version: str) -> Dict[str, str]:
        """Bearer token = Cal API key (e.g. cal_live_...)."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "cal-api-version": cal_api_version,
            "Content-Type": "application/json",
        }

    @staticmethod
    def format_slot_label(iso_start: str, timezone: str = DEFAULT_TIMEZONE) -> str:
        """Human-readable label for a slot start time."""
        try:
            dt = datetime.fromisoformat(iso_start.replace("Z", "+00:00"))
            dt = dt.astimezone(ZoneInfo(timezone))
            return dt.strftime("%a %b %d · %I:%M %p")
        except Exception:
            return iso_start

    async def get_availability(self, timezone: Optional[str] = None) -> str:
        """
        Get human-readable availability for the next 7 days.
        Returns a formatted string suitable for LLM context.
        """
        tz = self._normalize_timezone(timezone, self.default_timezone)
        slots = await self.get_available_slots(timezone=tz)

        if not slots:
            return (
                "No bookable slots found for the next 7 days in the current Cal.com availability schedule. "
                f"Please check https://cal.com/{self.username} for the latest availability "
                f"in timezone {tz}."
            )

        formatted = (
            "Bookable slots from the Cal.com availability schedule "
            f"(next 7 days, timezone: {tz}):\n"
        )
        current_date = None

        for slot in slots:
            start_local = self._to_timezone(slot["start"], tz)
            end_local = self._to_timezone(slot["end"], tz)
            if not start_local or not end_local:
                continue

            slot_date = start_local.date().isoformat()
            if slot_date != current_date:
                current_date = slot_date
                formatted += f"\n📅 {start_local.strftime('%A, %B %d, %Y')}:\n"

            start_time = start_local.strftime("%I:%M %p")
            end_time = end_local.strftime("%I:%M %p")
            formatted += f"  • {start_time} - {end_time}\n"

        return formatted

    def _filter_future_slots(
        self,
        slots: List[Dict],
        timezone: str,
        now_local: Optional[datetime] = None,
    ) -> List[Dict]:
        """Keep only slots that start in the future for the requested timezone."""
        reference = now_local or datetime.now(ZoneInfo(timezone))
        filtered: List[Dict] = []

        for slot in slots:
            start_local = self._to_timezone(slot.get("start", ""), timezone)
            if not start_local:
                continue
            if start_local <= reference:
                continue
            filtered.append(slot)

        return filtered

    def _parse_slots_payload(self, payload: Any, timezone: str) -> List[Dict]:
        """Normalize Cal.com v2 /v2/slots response into {start, end, formatted} dicts."""
        if not isinstance(payload, dict):
            return []
        inner = payload.get("data") or {}
        if not isinstance(inner, dict):
            return []

        all_slots: List[Dict] = []
        for _date_key, slot_list in inner.items():
            if not isinstance(slot_list, list):
                continue
            for slot in slot_list:
                start: Optional[str] = None
                end: Optional[str] = None
                if isinstance(slot, dict):
                    start = slot.get("start")
                    end = slot.get("end")
                elif isinstance(slot, str):
                    start = slot
                if not start:
                    continue
                if not end:
                    try:
                        st = datetime.fromisoformat(start.replace("Z", "+00:00"))
                        end = (st + timedelta(minutes=30)).isoformat()
                    except Exception:
                        end = start

                all_slots.append(
                    {
                        "start": start,
                        "end": end,
                        "formatted": self.format_slot_label(start, timezone=timezone),
                    }
                )

        return sorted(all_slots, key=lambda x: x["start"])

    async def get_available_slots(self, timezone: Optional[str] = None) -> List[Dict]:
        """Fetch available slots from Cal.com API v2."""
        tz = self._normalize_timezone(timezone, self.default_timezone)
        now_local = datetime.now(ZoneInfo(tz))
        start_date = now_local.date()
        end_date = start_date + timedelta(days=7)

        params = {
            "eventTypeId": int(self.event_type_id),
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
            "timeZone": tz,
            "format": "range",
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{CALCOM_V2_BASE}/v2/slots",
                    params=params,
                    headers=self._auth_headers(CAL_SLOTS_API_VERSION),
                    timeout=8.0,
                )
                response.raise_for_status()
                data = response.json()
                parsed = self._parse_slots_payload(data, timezone=tz)
                return self._filter_future_slots(
                    parsed,
                    timezone=tz,
                    now_local=now_local,
                )

            except httpx.HTTPError as e:
                logger.error(
                    "Cal.com v2 slots error",
                    error=str(e),
                    response=e.response.text if e.response is not None else "",
                )
                return []

    async def create_booking(
        self,
        name: str,
        email: str,
        start_time: str,
        timezone: Optional[str] = None,
        notes: str = "",
    ) -> Dict:
        """Create a booking via Cal.com API v2."""
        tz = self._normalize_timezone(timezone, self.default_timezone)
        payload: Dict[str, Any] = {
            "eventTypeId": int(self.event_type_id),
            "start": start_time,
            "attendee": {
                "name": name,
                "email": email,
                "timeZone": tz,
                "language": "en",
            },
            "metadata": {
                "source": "ai-persona",
                "notes": notes or "Booked via AI Persona",
            },
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{CALCOM_V2_BASE}/v2/bookings",
                    headers=self._auth_headers(CAL_BOOKINGS_API_VERSION),
                    json=payload,
                    timeout=10.0,
                )
                response.raise_for_status()
                booking = response.json()

                booking_id = None
                if isinstance(booking.get("data"), dict):
                    booking_id = booking["data"].get("id") or booking["data"].get("uid")
                if booking_id is None:
                    booking_id = booking.get("id")

                logger.info(
                    "Booking created",
                    booking_id=booking_id,
                    attendee=email,
                    time=start_time,
                )

                return booking

            except httpx.HTTPError as e:
                logger.error(
                    "Booking failed",
                    error=str(e),
                    response=e.response.text if e.response is not None else "",
                )
                raise
