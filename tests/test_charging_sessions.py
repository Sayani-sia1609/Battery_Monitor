from datetime import datetime, timedelta, timezone

from battery_analyzer.core.sessions import ChargingSessionDetector
from battery_analyzer.models.battery_data import BatteryData


def reading(start: datetime, minutes: int, charge: float, charging: bool) -> BatteryData:
    return BatteryData(
        timestamp=start + timedelta(minutes=minutes),
        charge_percent=charge,
        is_charging=charging,
    )


def test_detects_completed_full_charging_session() -> None:
    start = datetime(2026, 10, 8, 12, 30, tzinfo=timezone.utc)
    measurements = [
        reading(start, 0, 42, False),
        reading(start, 5, 42, True),
        reading(start, 20, 72, True),
        reading(start, 40, 100, True),
        reading(start, 45, 100, False),
    ]

    sessions = ChargingSessionDetector().detect(measurements)

    assert len(sessions) == 1
    session = sessions[0]
    assert session.started_at == start + timedelta(minutes=5)
    assert session.ended_at == start + timedelta(minutes=45)
    assert session.start_percent == 42
    assert session.end_percent == 100
    assert session.reached_100 is True
    assert session.status == "completed"
    assert session.duration_seconds == 40 * 60


def test_detects_partial_and_interrupted_sessions() -> None:
    start = datetime(2026, 10, 8, 12, 30, tzinfo=timezone.utc)
    measurements = [
        reading(start, 0, 35, True),
        reading(start, 10, 50, True),
        reading(start, 20, 70, False),
    ]

    session = ChargingSessionDetector().detect(measurements)[0]

    assert session.start_percent == 35
    assert session.end_percent == 70
    assert session.reached_100 is False
    assert session.status == "interrupted"


def test_reconstructs_multiple_sessions_in_chronological_order() -> None:
    start = datetime(2026, 10, 8, 12, 30, tzinfo=timezone.utc)
    measurements = [
        reading(start, 40, 80, False),
        reading(start, 0, 20, True),
        reading(start, 10, 30, False),
        reading(start, 20, 40, True),
        reading(start, 30, 50, False),
    ]

    sessions = ChargingSessionDetector().detect(measurements)

    assert [(item.start_percent, item.end_percent) for item in sessions] == [
        (20, 30),
        (40, 50),
    ]


def test_ignores_duplicate_timestamps_and_keeps_latest_observation() -> None:
    start = datetime(2026, 10, 8, 12, 30, tzinfo=timezone.utc)
    measurements = [
        reading(start, 0, 30, True),
        reading(start, 5, 45, True),
        reading(start, 5, 50, False),
        reading(start, 10, 60, False),
    ]

    sessions = ChargingSessionDetector().detect(measurements)

    assert len(sessions) == 1
    assert sessions[0].end_percent == 50
    assert sessions[0].duration_seconds == 5 * 60


def test_gaps_do_not_create_unobserved_boundaries() -> None:
    start = datetime(2026, 10, 8, 12, 30, tzinfo=timezone.utc)
    measurements = [
        reading(start, 0, 35, True),
        reading(start, 120, 70, True),
        reading(start, 125, 70, False),
    ]

    session = ChargingSessionDetector().detect(measurements)[0]

    assert session.duration_seconds == 125 * 60
    assert session.started_at.tzinfo is not None
    assert session.ended_at.tzinfo is not None
