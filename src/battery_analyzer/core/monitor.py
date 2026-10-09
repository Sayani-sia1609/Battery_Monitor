"""Background battery collection service."""

from __future__ import annotations

import logging
import sqlite3
import threading
from collections.abc import Callable
from pathlib import Path

from battery_analyzer.collectors.system import collect_battery_data
from battery_analyzer.core.sessions import ChargingSessionDetector, detect_sessions
from battery_analyzer.models.battery_data import BatteryData
from battery_analyzer.storage.database import BatteryDatabase

LOGGER = logging.getLogger(__name__)
Collector = Callable[[], BatteryData]


class BatteryMonitor:
    """Periodically collect, persist, and session-process battery readings."""

    def __init__(
        self,
        interval_seconds: float = 60.0,
        database_path: str | Path = "data/battery.db",
        collector: Collector = collect_battery_data,
    ) -> None:
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be greater than zero")
        self.interval_seconds = interval_seconds
        self.database_path = Path(database_path)
        self.collector = collector
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def collect_once(self) -> BatteryData:
        """Collect and persist one reading, including newly completed sessions."""
        measurement = self.collector()
        with BatteryDatabase(self.database_path) as database:
            previous_active = database.get_active_session()
            database.add(measurement)
            measurements = database.get_all()
            for session in ChargingSessionDetector().detect(measurements):
                if database.add_charging_session(session):
                    LOGGER.info(
                        "Charging session ended: %.1f%% to %.1f%% (%s)",
                        session.start_percent,
                        session.end_percent,
                        session.status,
                    )
            for session in detect_sessions(measurements):
                if database.add_session(session):
                    LOGGER.info(
                        "Session ended: %s from %.1f%% to %.1f%%",
                        "charging" if session.is_charging else "discharging",
                        session.start_percent,
                        session.end_percent,
                    )
            if previous_active is None or previous_active.is_charging != measurement.is_charging:
                LOGGER.info(
                    "Session started: %s at %.1f%%",
                    "charging" if measurement.is_charging else "discharging",
                    measurement.charge_percent,
                )
        LOGGER.info(
            "Measurement saved: %.1f%% (%s)",
            measurement.charge_percent,
            "charging" if measurement.is_charging else "discharging",
        )
        return measurement

    def run_forever(self) -> None:
        """Run until stop() is called, recovering from individual failures."""
        LOGGER.info("Battery monitor started; interval=%ss", self.interval_seconds)
        self._stop_event.clear()
        while not self._stop_event.is_set():
            try:
                self.collect_once()
            except (OSError, RuntimeError, ValueError, sqlite3.Error):
                LOGGER.exception("Battery collection failed; will retry")
            self._stop_event.wait(self.interval_seconds)
        LOGGER.info("Battery monitor stopped")

    def start(self) -> None:
        """Start the monitor in a daemon thread."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._thread = threading.Thread(
            target=self.run_forever,
            name="battery-monitor",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        """Request shutdown and wait for the monitor thread to finish."""
        self._stop_event.set()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=self.interval_seconds + 11)

    @property
    def is_running(self) -> bool:
        """Whether the background monitor thread is currently running."""
        return self._thread is not None and self._thread.is_alive()
