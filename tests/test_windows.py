import ctypes

import pytest

from battery_analyzer.collectors.windows import _to_battery_data


def make_status(*, percent: int = 75, ac_status: int = 1) -> ctypes.Structure:
    from battery_analyzer.collectors.windows import _SystemPowerStatus

    status = _SystemPowerStatus()
    status.BatteryLifePercent = percent
    status.ACLineStatus = ac_status
    return status


def test_windows_status_is_normalized() -> None:
    data = _to_battery_data(make_status(percent=75, ac_status=1))

    assert data.charge_percent == 75
    assert data.is_charging is True
    assert data.timestamp.tzinfo is not None


@pytest.mark.parametrize(
    ("percent", "ac_status"),
    [(255, 1), (75, 255)],
)
def test_windows_unknown_sentinel_values_are_rejected(percent: int, ac_status: int) -> None:
    with pytest.raises(RuntimeError):
        _to_battery_data(make_status(percent=percent, ac_status=ac_status))
