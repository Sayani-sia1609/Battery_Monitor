from datetime import datetime, timedelta, timezone
from threading import Event
from time import monotonic, sleep

from battery_analyzer.core.monitor import BatteryMonitor
from battery_analyzer.models.battery_data import BatteryData
from battery_analyzer.storage.database import BatteryDatabase


def test_monitor_collect_once_persists_measurement_and_session(tmp_path) -> None:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    readings = iter(
        [
            BatteryData(timestamp=start, charge_percent=40, is_charging=True),
            BatteryData(
                timestamp=start + timedelta(minutes=30),
                charge_percent=80,
                is_charging=False,
            ),
        ]
    )
    monitor = BatteryMonitor(
        interval_seconds=60,
        database_path=tmp_path / "battery.db",
        collector=lambda: next(readings),
    )

    monitor.collect_once()
    monitor.collect_once()

    with BatteryDatabase(tmp_path / "battery.db") as database:
        assert len(database.get_all()) == 2
        sessions = database.get_sessions(charging=True)
        assert len(sessions) == 1
        assert sessions[0].start_percent == 40


def test_monitor_rejects_invalid_interval(tmp_path) -> None:
    try:
        BatteryMonitor(interval_seconds=0, database_path=tmp_path / "battery.db")
    except ValueError:
        pass
    else:
        raise AssertionError("Expected invalid interval to raise ValueError")


def test_monitor_repeats_collection_until_stopped(tmp_path) -> None:
    collected = Event()
    calls = 0

    def collector() -> BatteryData:
        nonlocal calls
        calls += 1
        collected.set()
        return BatteryData(charge_percent=75, is_charging=False)

    monitor = BatteryMonitor(
        interval_seconds=0.01,
        database_path=tmp_path / "battery.db",
        collector=collector,
    )
    monitor.start()

    assert collected.wait(timeout=1)
    assert monitor.is_running is True
    deadline = monotonic() + 1
    while calls < 2 and monotonic() < deadline:
        sleep(0.01)
    monitor.stop()
    monitor.stop()

    assert calls >= 2
    assert monitor.is_running is False
    with BatteryDatabase(tmp_path / "battery.db") as database:
        assert len(database.get_all()) == calls


def test_monitor_recovers_from_collection_failure(tmp_path) -> None:
    attempts = 0
    collected = Event()

    def collector() -> BatteryData:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("temporary collector failure")
        collected.set()
        return BatteryData(charge_percent=70, is_charging=False)

    monitor = BatteryMonitor(
        interval_seconds=0.01,
        database_path=tmp_path / "battery.db",
        collector=collector,
    )
    monitor.start()

    assert collected.wait(timeout=1)
    monitor.stop()

    assert attempts >= 2
    with BatteryDatabase(tmp_path / "battery.db") as database:
        assert len(database.get_all()) == 1
        assert database.get_latest().charge_percent == 70


def test_monitor_preserves_timezone_aware_measurement(tmp_path) -> None:
    timestamp = datetime(2026, 10, 8, 6, 30, tzinfo=timezone.utc)
    monitor = BatteryMonitor(
        database_path=tmp_path / "battery.db",
        collector=lambda: BatteryData(
            timestamp=timestamp,
            charge_percent=80,
            is_charging=False,
        ),
    )

    measurement = monitor.collect_once()

    assert measurement.timestamp.tzinfo is not None
    with BatteryDatabase(tmp_path / "battery.db") as database:
        assert database.get_latest().timestamp == timestamp
