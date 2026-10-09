from datetime import datetime, timedelta, timezone

from battery_analyzer.analytics.drain import drain_rate_per_hour
from battery_analyzer.models.battery_data import BatteryData


def test_drain_rate() -> None:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    previous = BatteryData(timestamp=start, charge_percent=90, is_charging=False)
    current = BatteryData(
        timestamp=start + timedelta(hours=2),
        charge_percent=70,
        is_charging=False,
    )
    assert drain_rate_per_hour(previous, current) == 10


def test_drain_ignores_charging_or_increasing_readings() -> None:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    charging = BatteryData(timestamp=start, charge_percent=50, is_charging=True)
    charged = BatteryData(timestamp=start + timedelta(hours=1), charge_percent=60, is_charging=True)
    assert drain_rate_per_hour(charging, charged) is None
