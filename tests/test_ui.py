from datetime import datetime, timezone

from battery_analyzer.models.battery_data import BatteryData, BatterySession, ChargingSession
from battery_analyzer.ui.app import (
    current_session_summary,
    format_duration,
    format_local_timestamp,
    full_charge_summary,
)


def test_ui_formats_timestamps_in_india_time() -> None:
    timestamp = datetime(2026, 10, 8, 6, 30, tzinfo=timezone.utc)
    assert format_local_timestamp(timestamp) == "08 Oct 2026, 12:00:00 PM"


def test_ui_formats_unavailable_duration() -> None:
    assert format_duration(None) == "N/A"
    assert format_duration(135 * 60) == "2h 15m"


def test_current_session_summary_uses_real_measurements() -> None:
    start = datetime(2026, 10, 8, 6, 0, tzinfo=timezone.utc)
    session = BatterySession(
        started_at=start,
        start_percent=100,
        is_charging=False,
    )
    latest = BatteryData(
        timestamp=start.replace(hour=8),
        charge_percent=93,
        is_charging=False,
    )

    summary = current_session_summary(session, latest)

    assert summary["state"] == "Discharging"
    assert summary["charge"] == "100.0% -> 93.0%"
    assert summary["change"] == "-7.0%"
    assert summary["duration"] == "2h 00m"
    assert summary["rate"] == "3.5%/hr"


def test_full_charge_summary_shows_newest_full_charge_first() -> None:
    start = datetime(2026, 10, 8, 6, 0, tzinfo=timezone.utc)
    sessions = [
        ChargingSession(
            started_at=start,
            ended_at=start.replace(hour=7),
            start_percent=40,
            end_percent=100,
            reached_100=True,
            status="completed",
        ),
        ChargingSession(
            started_at=start.replace(day=9),
            ended_at=start.replace(day=9, hour=8),
            start_percent=55,
            end_percent=80,
            reached_100=False,
            status="interrupted",
        ),
    ]

    result = full_charge_summary(sessions)

    assert len(result) == 1
    assert result[0]["charge"] == "40% -> 100%"
    assert result[0]["duration"] == "1h 00m"
