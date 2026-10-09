"""Platform selection for battery collection."""

import platform

from battery_analyzer.collectors.macos import collect_macos_battery
from battery_analyzer.collectors.windows import collect_windows_battery
from battery_analyzer.models.battery_data import BatteryData


def collect_battery_data() -> BatteryData:
    """Collect a measurement using the current operating system."""
    system = platform.system()
    if system == "Darwin":
        return collect_macos_battery()
    if system == "Windows":
        return collect_windows_battery()
    raise RuntimeError(f"Unsupported operating system: {system}")
