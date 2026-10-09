"""SQLite persistence for battery measurements and sessions."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Self

from battery_analyzer.core.sessions import ChargingSessionDetector, detect_active_session
from battery_analyzer.models.battery_data import BatteryData, BatterySession, ChargingSession


class BatteryDatabase:
    """Store and retrieve battery measurements and completed sessions."""

    def __init__(self, path: str | Path = "data/battery.db") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS measurements (
                timestamp TEXT NOT NULL,
                charge_percent REAL NOT NULL,
                is_charging INTEGER NOT NULL,
                voltage REAL,
                current REAL,
                temperature_celsius REAL,
                energy_full_wh REAL,
                energy_design_wh REAL
            )
            """
        )
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS charging_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                ended_at TEXT NOT NULL,
                start_percent REAL NOT NULL,
                end_percent REAL NOT NULL,
                is_charging INTEGER NOT NULL DEFAULT 1,
                reached_100 INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'interrupted',
                UNIQUE(started_at, is_charging)
            )
            """
        )
        self.connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_measurements_timestamp ON measurements(timestamp)"
        )
        self.connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_sessions_started_at ON charging_sessions(started_at)"
        )
        self.connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_sessions_ended_at ON charging_sessions(ended_at)"
        )
        self._migrate_session_columns()
        self.connection.commit()

    def _migrate_session_columns(self) -> None:
        columns = {
            row["name"] for row in self.connection.execute("PRAGMA table_info(charging_sessions)")
        }
        if "reached_100" not in columns:
            self.connection.execute(
                "ALTER TABLE charging_sessions ADD COLUMN reached_100 INTEGER NOT NULL DEFAULT 0"
            )
        if "status" not in columns:
            self.connection.execute(
                "ALTER TABLE charging_sessions "
                "ADD COLUMN status TEXT NOT NULL DEFAULT 'interrupted'"
            )

    def add(self, measurement: BatteryData) -> None:
        self.connection.execute(
            "INSERT INTO measurements VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                measurement.timestamp.isoformat(),
                measurement.charge_percent,
                int(measurement.is_charging),
                measurement.voltage,
                measurement.current,
                measurement.temperature_celsius,
                measurement.energy_full_wh,
                measurement.energy_design_wh,
            ),
        )
        self.connection.commit()

    def add_session(self, session: BatterySession) -> bool:
        """Persist a completed session, returning False if it already exists."""
        if session.ended_at is None or session.end_percent is None:
            raise ValueError("Only completed sessions can be persisted")
        cursor = self.connection.execute(
            """
            INSERT OR IGNORE INTO charging_sessions
            (started_at, ended_at, start_percent, end_percent, is_charging, reached_100, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session.started_at.isoformat(),
                session.ended_at.isoformat(),
                session.start_percent,
                session.end_percent,
                int(session.is_charging),
                int(session.is_charging and session.end_percent >= 100),
                "completed"
                if session.is_charging and session.end_percent >= 100
                else "interrupted",
            ),
        )
        self.connection.commit()
        return cursor.rowcount == 1

    def add_charging_session(self, session: ChargingSession) -> bool:
        """Persist a reconstructed charging session if it is not already stored."""
        cursor = self.connection.execute(
            """
            INSERT OR IGNORE INTO charging_sessions
            (started_at, ended_at, start_percent, end_percent, is_charging, reached_100, status)
            VALUES (?, ?, ?, ?, 1, ?, ?)
            """,
            (
                session.started_at.isoformat(),
                session.ended_at.isoformat(),
                session.start_percent,
                session.end_percent,
                int(session.reached_100),
                session.status,
            ),
        )
        self.connection.commit()
        return cursor.rowcount == 1

    @staticmethod
    def _row_to_model(row: sqlite3.Row) -> BatteryData:
        return BatteryData(
            timestamp=datetime.fromisoformat(row["timestamp"]),
            charge_percent=row["charge_percent"],
            is_charging=bool(row["is_charging"]),
            voltage=row["voltage"],
            current=row["current"],
            temperature_celsius=row["temperature_celsius"],
            energy_full_wh=row["energy_full_wh"],
            energy_design_wh=row["energy_design_wh"],
        )

    @staticmethod
    def _row_to_session(row: sqlite3.Row) -> BatterySession:
        return BatterySession(
            started_at=datetime.fromisoformat(row["started_at"]),
            ended_at=datetime.fromisoformat(row["ended_at"]),
            start_percent=row["start_percent"],
            end_percent=row["end_percent"],
            is_charging=bool(row["is_charging"]),
        )

    @staticmethod
    def _row_to_charging_session(row: sqlite3.Row) -> ChargingSession:
        return ChargingSession(
            id=row["id"],
            started_at=datetime.fromisoformat(row["started_at"]),
            ended_at=datetime.fromisoformat(row["ended_at"]),
            start_percent=row["start_percent"],
            end_percent=row["end_percent"],
            reached_100=bool(row["reached_100"]),
            status=row["status"],
        )

    def get_latest(self) -> BatteryData | None:
        row = self.connection.execute(
            "SELECT * FROM measurements ORDER BY timestamp DESC LIMIT 1"
        ).fetchone()
        return self._row_to_model(row) if row else None

    def get_recent(self, limit: int = 10) -> list[BatteryData]:
        if limit < 1:
            raise ValueError("limit must be greater than zero")
        rows = self.connection.execute(
            "SELECT * FROM measurements ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [self._row_to_model(row) for row in reversed(rows)]

    def get_between(self, start: datetime, end: datetime) -> list[BatteryData]:
        if start.tzinfo is None or end.tzinfo is None:
            raise ValueError("start and end must be timezone-aware")
        if end < start:
            raise ValueError("end must not be earlier than start")
        rows = self.connection.execute(
            """
            SELECT * FROM measurements
            WHERE timestamp >= ? AND timestamp <= ?
            ORDER BY timestamp ASC
            """,
            (start.isoformat(), end.isoformat()),
        ).fetchall()
        return [self._row_to_model(row) for row in rows]

    def get_all(self) -> list[BatteryData]:
        rows = self.connection.execute(
            "SELECT * FROM measurements ORDER BY timestamp ASC"
        ).fetchall()
        return [self._row_to_model(row) for row in rows]

    def get_sessions(self, *, charging: bool | None = None) -> list[BatterySession]:
        query = "SELECT * FROM charging_sessions"
        parameters: tuple[int, ...] = ()
        if charging is not None:
            query += " WHERE is_charging = ?"
            parameters = (int(charging),)
        query += " ORDER BY started_at ASC"
        rows = self.connection.execute(query, parameters).fetchall()
        return [self._row_to_session(row) for row in rows]

    def get_recent_sessions(self, limit: int = 10) -> list[BatterySession]:
        if limit < 1:
            raise ValueError("limit must be greater than zero")
        rows = self.connection.execute(
            "SELECT * FROM charging_sessions ORDER BY started_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [self._row_to_session(row) for row in reversed(rows)]

    def get_session(self, session_id: int) -> ChargingSession | None:
        row = self.connection.execute(
            "SELECT * FROM charging_sessions WHERE id = ? AND is_charging = 1",
            (session_id,),
        ).fetchone()
        return self._row_to_charging_session(row) if row else None

    def get_recent_charging_sessions(self, limit: int = 10) -> list[ChargingSession]:
        if limit < 1:
            raise ValueError("limit must be greater than zero")
        rows = self.connection.execute(
            """
            SELECT * FROM charging_sessions
            WHERE is_charging = 1
            ORDER BY started_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [self._row_to_charging_session(row) for row in reversed(rows)]

    def get_sessions_between(
        self,
        start: datetime,
        end: datetime,
    ) -> list[ChargingSession]:
        if start.tzinfo is None or end.tzinfo is None:
            raise ValueError("start and end must be timezone-aware")
        if end < start:
            raise ValueError("end must not be earlier than start")
        rows = self.connection.execute(
            """
            SELECT * FROM charging_sessions
            WHERE is_charging = 1 AND started_at >= ? AND started_at <= ?
            ORDER BY started_at ASC
            """,
            (start.isoformat(), end.isoformat()),
        ).fetchall()
        return [self._row_to_charging_session(row) for row in rows]

    def reconstruct_sessions(self) -> list[ChargingSession]:
        """Rebuild charging sessions from all raw historical measurements."""
        return ChargingSessionDetector().detect(self.get_all())

    def get_active_session(self) -> BatterySession | None:
        """Return the current open session derived from the raw measurements."""
        return detect_active_session(self.get_all())

    def get_health_history(self) -> list[BatteryData]:
        rows = self.connection.execute(
            """
            SELECT * FROM measurements
            WHERE energy_full_wh IS NOT NULL AND energy_design_wh IS NOT NULL
            ORDER BY timestamp ASC
            """
        ).fetchall()
        return [self._row_to_model(row) for row in rows]

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()
