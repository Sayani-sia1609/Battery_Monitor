import sqlite3
from datetime import datetime, timedelta, timezone

from battery_analyzer.models.battery_data import BatteryData, BatterySession, ChargingSession
from battery_analyzer.storage.database import BatteryDatabase


def test_database_stores_measurements(tmp_path) -> None:
    database = BatteryDatabase(tmp_path / "battery.db")
    database.add(BatteryData(charge_percent=75, is_charging=True))
    count = database.connection.execute("SELECT COUNT(*) FROM measurements").fetchone()[0]
    database.close()
    assert count == 1


def test_database_retrieves_latest_and_time_range(tmp_path) -> None:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    database = BatteryDatabase(tmp_path / "battery.db")
    first = BatteryData(timestamp=start, charge_percent=80, is_charging=False)
    second = BatteryData(
        timestamp=start + timedelta(minutes=5), charge_percent=79, is_charging=False
    )
    database.add(first)
    database.add(second)

    assert database.get_latest() == second
    assert database.get_all() == [first, second]
    assert database.get_between(start, second.timestamp) == [first, second]
    assert database.get_recent(1) == [second]
    database.close()


def test_database_persists_sessions_and_health_history(tmp_path) -> None:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    database = BatteryDatabase(tmp_path / "battery.db")
    measurement = BatteryData(
        timestamp=start,
        charge_percent=80,
        is_charging=True,
        energy_full_wh=80,
        energy_design_wh=100,
    )
    database.add(measurement)
    session = BatterySession(
        started_at=start,
        ended_at=start + timedelta(minutes=30),
        start_percent=40,
        end_percent=80,
        is_charging=True,
    )
    assert database.add_session(session) is True
    assert database.add_session(session) is False
    assert database.get_sessions() == [session]
    assert database.get_recent_sessions(1) == [session]
    assert database.get_health_history() == [measurement]
    database.close()


def test_database_derives_active_session_from_measurements(tmp_path) -> None:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    database = BatteryDatabase(tmp_path / "battery.db")
    database.add(BatteryData(timestamp=start, charge_percent=40, is_charging=True))
    database.add(
        BatteryData(
            timestamp=start + timedelta(minutes=30),
            charge_percent=80,
            is_charging=False,
        )
    )

    session = database.get_active_session()

    assert session is not None
    assert session.is_charging is False
    assert session.start_percent == 80
    assert session.ended_at is None
    database.close()


def test_database_persists_and_retrieves_charging_sessions(tmp_path) -> None:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    database = BatteryDatabase(tmp_path / "battery.db")
    session = ChargingSession(
        started_at=start,
        ended_at=start + timedelta(minutes=30),
        start_percent=40,
        end_percent=100,
        reached_100=True,
        status="completed",
    )
    assert database.add_charging_session(session) is True

    sessions = database.get_recent_charging_sessions()

    assert len(sessions) == 1
    assert sessions[0].reached_100 is True
    assert sessions[0].duration_seconds == 30 * 60
    assert database.get_session(sessions[0].id) == sessions[0]
    assert database.get_sessions_between(start, start + timedelta(hours=1)) == sessions
    database.close()


def test_database_migrates_legacy_session_columns(tmp_path) -> None:
    path = tmp_path / "legacy.db"
    connection = sqlite3.connect(path)
    connection.execute(
        """
        CREATE TABLE charging_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT NOT NULL,
            ended_at TEXT NOT NULL,
            start_percent REAL NOT NULL,
            end_percent REAL NOT NULL,
            is_charging INTEGER NOT NULL,
            UNIQUE(started_at, is_charging)
        )
        """
    )
    connection.commit()
    connection.close()

    database = BatteryDatabase(path)
    columns = {
        row["name"] for row in database.connection.execute("PRAGMA table_info(charging_sessions)")
    }

    assert {"reached_100", "status"} <= columns
    database.close()
