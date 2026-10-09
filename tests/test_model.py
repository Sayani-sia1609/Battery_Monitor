from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from battery_analyzer.main import format_local_timestamp
from battery_analyzer.models.battery_data import BatteryData, BatterySession, ChargingSession


def test_optional_values_remain_none() -> None:
    data = BatteryData(charge_percent=50, is_charging=False)
    assert data.voltage is None
    assert data.energy_full_wh is None


@pytest.mark.parametrize("charge", [-1, 101])
def test_charge_percent_is_validated(charge: float) -> None:
    with pytest.raises(ValidationError):
        BatteryData(charge_percent=charge, is_charging=False)


def test_timestamp_must_be_timezone_aware() -> None:
    with pytest.raises(ValidationError):
        BatteryData(
            timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc).replace(tzinfo=None),
            charge_percent=50,
            is_charging=False,
        )


def test_timestamp_is_displayed_in_india_time() -> None:
    timestamp = datetime(2026, 10, 8, 6, 30, tzinfo=timezone.utc)
    assert format_local_timestamp(timestamp) == "2026-10-08T12:00:00+05:30"
    assert timestamp.astimezone(ZoneInfo("Asia/Kolkata")).hour == 12


def test_session_end_cannot_precede_start() -> None:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with pytest.raises(ValidationError):
        BatterySession(
            started_at=start,
            ended_at=start.replace(year=2025),
            start_percent=50,
            end_percent=40,
            is_charging=False,
        )
    with pytest.raises(ValidationError):
        ChargingSession(
            started_at=start,
            ended_at=start.replace(year=2025),
            start_percent=50,
            end_percent=100,
            reached_100=True,
            status="completed",
        )
