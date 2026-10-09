from datetime import datetime, timedelta, timezone

from battery_analyzer.core.sessions import (
    detect_active_session,
    detect_discharge_sessions,
    detect_sessions,
)
from battery_analyzer.models.battery_data import BatteryData


def test_detect_discharge_session() -> None:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    readings = [
        BatteryData(timestamp=start, charge_percent=100, is_charging=True),
        BatteryData(timestamp=start + timedelta(minutes=5), charge_percent=95, is_charging=False),
        BatteryData(timestamp=start + timedelta(minutes=35), charge_percent=85, is_charging=False),
        BatteryData(timestamp=start + timedelta(minutes=40), charge_percent=90, is_charging=True),
    ]
    sessions = detect_discharge_sessions(readings)
    assert len(sessions) == 1
    assert sessions[0].start_percent == 95
    assert sessions[0].end_percent == 90
    assert sessions[0].duration_seconds == 35 * 60


def test_detect_charging_session_boundary() -> None:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    readings = [
        BatteryData(timestamp=start, charge_percent=40, is_charging=True),
        BatteryData(timestamp=start + timedelta(minutes=30), charge_percent=80, is_charging=True),
        BatteryData(timestamp=start + timedelta(minutes=35), charge_percent=80, is_charging=False),
    ]
    sessions = detect_sessions(readings)
    assert len(sessions) == 1
    assert sessions[0].is_charging is True
    assert sessions[0].start_percent == 40
    assert sessions[0].end_percent == 80


def test_detect_active_session_returns_latest_contiguous_state() -> None:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    readings = [
        BatteryData(timestamp=start, charge_percent=40, is_charging=True),
        BatteryData(timestamp=start + timedelta(minutes=30), charge_percent=80, is_charging=False),
        BatteryData(timestamp=start + timedelta(minutes=40), charge_percent=75, is_charging=False),
    ]

    session = detect_active_session(readings)

    assert session is not None
    assert session.is_charging is False
    assert session.started_at == start + timedelta(minutes=30)
    assert session.start_percent == 80
    assert session.ended_at is None
