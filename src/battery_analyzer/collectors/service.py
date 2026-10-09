"""Application service for collecting and persisting measurements."""

from __future__ import annotations

from pathlib import Path

from battery_analyzer.core.monitor import BatteryMonitor
from battery_analyzer.models.battery_data import BatteryData


def collect_and_store(database_path: str | Path = "data/battery.db") -> BatteryData:
    """Collect one real platform measurement and persist it."""
    return BatteryMonitor(database_path=database_path).collect_once()
