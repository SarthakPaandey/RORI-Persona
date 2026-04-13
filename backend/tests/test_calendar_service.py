"""Tests for calendar service."""

from datetime import datetime
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest

from app.services.calendar_service import CalendarService


@pytest.fixture
def settings():
    s = MagicMock()
    s.calcom_api_key = "key"
    s.calcom_event_type_id = "42"
    s.calcom_username = "user"
    return s


def test_format_slot_label(settings):
    svc = CalendarService(settings)
    label = svc.format_slot_label("2024-03-15T14:00:00+00:00")
    assert "2024" in label or "Mar" in label


def test_filter_future_slots_excludes_past_and_current(settings):
    svc = CalendarService(settings)
    timezone = "Asia/Kolkata"
    now_local = datetime(2026, 4, 13, 10, 0, tzinfo=ZoneInfo(timezone))

    slots = [
        {
            "start": "2026-04-13T09:00:00+05:30",
            "end": "2026-04-13T10:00:00+05:30",
            "formatted": "Mon Apr 13 · 09:00 AM",
        },
        {
            "start": "2026-04-13T10:00:00+05:30",
            "end": "2026-04-13T11:00:00+05:30",
            "formatted": "Mon Apr 13 · 10:00 AM",
        },
        {
            "start": "2026-04-13T11:00:00+05:30",
            "end": "2026-04-13T12:00:00+05:30",
            "formatted": "Mon Apr 13 · 11:00 AM",
        },
    ]

    filtered = svc._filter_future_slots(slots, timezone=timezone, now_local=now_local)

    assert len(filtered) == 1
    assert filtered[0]["start"] == "2026-04-13T11:00:00+05:30"
