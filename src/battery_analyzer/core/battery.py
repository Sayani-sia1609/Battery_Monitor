"""Battery health calculations."""

from battery_analyzer.models.battery_data import BatteryData


def health_percent(data: BatteryData) -> float | None:
    """Return remaining design health as a percentage when capacity is known."""
    if (
        data.energy_design_wh is None
        or data.energy_design_wh <= 0
        or data.energy_full_wh is None
        or data.energy_full_wh < 0
    ):
        return None
    return data.energy_full_wh / data.energy_design_wh * 100
