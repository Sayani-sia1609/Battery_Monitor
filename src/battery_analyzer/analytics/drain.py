"""Battery drain calculations."""

from battery_analyzer.models.battery_data import BatteryData


def drain_percent_points(previous: BatteryData, current: BatteryData) -> float | None:
    """Return percentage points drained, or None for non-discharge samples."""
    if previous.is_charging or current.is_charging:
        return None
    drained = previous.charge_percent - current.charge_percent
    return drained if drained > 0 else None


def drain_rate_per_hour(previous: BatteryData, current: BatteryData) -> float | None:
    """Return percentage points drained per hour for a valid discharge interval."""
    elapsed_hours = (current.timestamp - previous.timestamp).total_seconds() / 3600
    if elapsed_hours <= 0:
        raise ValueError("Measurements must be ordered and at least one second apart")
    drained = drain_percent_points(previous, current)
    return drained / elapsed_hours if drained is not None else None
