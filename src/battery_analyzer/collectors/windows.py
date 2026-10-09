"""Windows battery collector."""

from __future__ import annotations

import ctypes
import logging

from battery_analyzer.models.battery_data import BatteryData

LOGGER = logging.getLogger(__name__)


class _SystemPowerStatus(ctypes.Structure):
    _fields_ = [
        ("ACLineStatus", ctypes.c_ubyte),
        ("BatteryFlag", ctypes.c_ubyte),
        ("BatteryLifePercent", ctypes.c_ubyte),
        ("Reserved", ctypes.c_ubyte),
        ("BatteryLifeTime", ctypes.c_uint32),
        ("BatteryFullLifeTime", ctypes.c_uint32),
    ]


def _to_battery_data(status: _SystemPowerStatus) -> BatteryData:
    if status.BatteryLifePercent == 255:
        raise RuntimeError("Windows did not provide a valid battery percentage")
    if status.ACLineStatus == 255:
        raise RuntimeError("Windows did not provide a valid charging state")
    return BatteryData(
        charge_percent=float(status.BatteryLifePercent),
        is_charging=status.ACLineStatus == 1,
    )


def collect_windows_battery() -> BatteryData:
    """Collect basic charge and charging state through Win32."""
    status = _SystemPowerStatus()
    try:
        success = ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status))
    except AttributeError as exc:
        raise RuntimeError("Windows battery APIs are unavailable") from exc
    if not success:
        LOGGER.error("GetSystemPowerStatus failed")
        raise OSError("GetSystemPowerStatus failed")
    return _to_battery_data(status)
