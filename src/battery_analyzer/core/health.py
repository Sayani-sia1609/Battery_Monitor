"""Battery health status classification."""

from battery_analyzer.core.battery import health_percent
from battery_analyzer.models.battery_data import BatteryData


def health_status(data: BatteryData) -> str:
    """Classify battery health using capacity relative to design capacity."""
    percentage = health_percent(data)
    if percentage is None:
        return "unknown"
    if percentage >= 80:
        return "good"
    if percentage >= 60:
        return "fair"
    return "poor"
