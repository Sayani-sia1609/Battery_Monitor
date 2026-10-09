"""macOS battery collector."""

from __future__ import annotations

import logging
import re
import subprocess
from datetime import datetime, timezone

from battery_analyzer.models.battery_data import BatteryData

LOGGER = logging.getLogger(__name__)
_BATTERY_LINE = re.compile(
    r"^\s*-\S*InternalBattery\S*\s+\(id=[^)]+\)\s+"
    r"(?P<charge>\d+(?:\.\d+)?)%;\s*(?P<state>[^;]+);",
    re.IGNORECASE,
)


def parse_pmset_battery(output: str, *, timestamp: datetime | None = None) -> BatteryData:
    """Parse one battery measurement from ``pmset -g batt`` output."""
    for line in output.splitlines():
        match = _BATTERY_LINE.match(line)
        if not match:
            continue

        state = match.group("state").strip().lower()
        if state not in {"charging", "discharging", "charged"}:
            raise ValueError(f"Unsupported battery state: {state}")

        return BatteryData(
            timestamp=timestamp or datetime.now(timezone.utc),
            charge_percent=float(match.group("charge")),
            is_charging=state in {"charging", "charged"},
        )

    raise ValueError("Battery information not found in pmset output")


def collect_macos_battery() -> BatteryData:
    """Collect basic battery information through macOS pmset."""

    try:
        result = subprocess.run(
            ["pmset", "-g", "batt"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        return parse_pmset_battery(result.stdout)
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        LOGGER.error("Failed to collect macOS battery information: %s", exc)
        raise RuntimeError("Failed to collect macOS battery information") from exc
