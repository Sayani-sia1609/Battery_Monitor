from battery_analyzer.core.battery import health_percent
from battery_analyzer.core.health import health_status
from battery_analyzer.models.battery_data import BatteryData


def test_health_is_calculated_from_capacity() -> None:
    data = BatteryData(
        charge_percent=50,
        is_charging=False,
        energy_full_wh=80,
        energy_design_wh=100,
    )
    assert health_percent(data) == 80
    assert health_status(data) == "good"


def test_health_is_unavailable_for_invalid_capacity() -> None:
    data = BatteryData(
        charge_percent=50,
        is_charging=False,
        energy_full_wh=120,
        energy_design_wh=0,
    )

    assert health_percent(data) is None
    assert health_status(data) == "unknown"
