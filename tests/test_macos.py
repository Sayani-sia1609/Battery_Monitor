from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from battery_analyzer.collectors.macos import (
    collect_macos_battery,
    parse_pmset_battery,
)

PMSET_OUTPUT = (
    "Now drawing from 'Battery Power'\n"
    " -InternalBattery-0 (id=8192099) 97%; discharging; "
    "20:00 remaining present: true\n"
)


def test_parse_pmset_discharge() -> None:
    timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
    data = parse_pmset_battery(PMSET_OUTPUT, timestamp=timestamp)
    assert data.charge_percent == 97
    assert data.is_charging is False
    assert data.timestamp == timestamp


@pytest.mark.parametrize("state, expected", [("charging", True), ("charged", True)])
def test_parse_pmset_charging_states(state: str, expected: bool) -> None:
    output = PMSET_OUTPUT.replace("discharging", state)
    assert parse_pmset_battery(output).is_charging is expected


def test_parse_pmset_rejects_missing_battery() -> None:
    with pytest.raises(ValueError, match="not found"):
        parse_pmset_battery("Now drawing from 'AC Power'\n")


def test_collect_macos_wraps_command_failure() -> None:
    with (
        patch(
            "battery_analyzer.collectors.macos.subprocess.run",
            side_effect=OSError("pmset unavailable"),
        ),
        pytest.raises(RuntimeError, match="Failed to collect"),
    ):
        collect_macos_battery()
