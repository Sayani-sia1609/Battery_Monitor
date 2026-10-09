"""Summary statistics for measurements."""

from itertools import pairwise
from statistics import mean

from battery_analyzer.analytics.drain import drain_rate_per_hour
from battery_analyzer.core.sessions import detect_discharge_sessions
from battery_analyzer.models.battery_data import BatteryData


def average_charge(measurements: list[BatteryData]) -> float:
    if not measurements:
        raise ValueError("At least one measurement is required")
    return mean(item.charge_percent for item in measurements)


def summarize(measurements: list[BatteryData]) -> dict[str, float | int | None]:
    """Return conservative historical statistics from real measurements."""
    if not measurements:
        return {
            "measurement_count": 0,
            "average_charge": None,
            "minimum_charge": None,
            "maximum_charge": None,
            "average_drain_rate": None,
            "session_count": 0,
            "average_session_duration_seconds": None,
        }

    ordered = sorted(measurements, key=lambda item: item.timestamp)
    rates = [
        rate
        for previous, current in pairwise(ordered)
        if (rate := drain_rate_per_hour(previous, current)) is not None
    ]
    sessions = detect_discharge_sessions(ordered)
    durations = [
        session.duration_seconds for session in sessions if session.duration_seconds is not None
    ]
    return {
        "measurement_count": len(ordered),
        "average_charge": average_charge(ordered),
        "minimum_charge": min(item.charge_percent for item in ordered),
        "maximum_charge": max(item.charge_percent for item in ordered),
        "average_drain_rate": mean(rates) if rates else None,
        "session_count": len(sessions),
        "average_session_duration_seconds": mean(durations) if durations else None,
    }
