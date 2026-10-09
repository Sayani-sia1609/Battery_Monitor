"""Long-term battery degradation calculations."""

from battery_analyzer.models.battery_data import BatteryData


def degradation_percent(data: BatteryData) -> float | None:
    """Return capacity lost relative to the design capacity."""
    if data.energy_design_wh in (None, 0) or data.energy_full_wh is None:
        return None
    return max(0.0, (1 - data.energy_full_wh / data.energy_design_wh) * 100)
