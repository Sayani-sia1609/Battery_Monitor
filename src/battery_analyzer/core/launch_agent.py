"""macOS launchd integration for running the battery monitor in background."""

from __future__ import annotations

import os
import plistlib
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

LAUNCH_AGENT_LABEL = "com.battery-analyzer.monitor"


@dataclass(frozen=True)
class LaunchAgentStatus:
    """Current launch agent installation/runtime state."""

    label: str
    plist_path: Path
    installed: bool
    loaded: bool


def _ensure_macos() -> None:
    if sys.platform != "darwin":
        raise RuntimeError("Launch agent commands are only available on macOS")


def launch_agent_plist_path() -> Path:
    """Return the default user LaunchAgent plist path."""
    return Path.home() / "Library" / "LaunchAgents" / f"{LAUNCH_AGENT_LABEL}.plist"


def build_launch_agent_config(
    *,
    python_executable: str,
    project_root: Path,
    interval_seconds: float,
    database_path: Path,
) -> dict[str, object]:
    """Build launchd property list payload for battery monitor."""
    logs_dir = Path.home() / "Library" / "Logs" / "battery-analyzer"
    stdout_path = logs_dir / "monitor.stdout.log"
    stderr_path = logs_dir / "monitor.stderr.log"
    return {
        "Label": LAUNCH_AGENT_LABEL,
        "ProgramArguments": [
            python_executable,
            "-m",
            "battery_analyzer.main",
            "monitor",
            "--interval",
            str(interval_seconds),
            "--database-path",
            str(database_path),
        ],
        "WorkingDirectory": str(project_root),
        "RunAtLoad": True,
        "KeepAlive": True,
        "ProcessType": "Background",
        "StandardOutPath": str(stdout_path),
        "StandardErrorPath": str(stderr_path),
    }


def _launchctl(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["launchctl", *args],
        text=True,
        capture_output=True,
        check=False,
    )


def _is_loaded(label: str = LAUNCH_AGENT_LABEL) -> bool:
    domain = f"gui/{os.getuid()}/{label}"
    return _launchctl("print", domain).returncode == 0


def get_launch_agent_status() -> LaunchAgentStatus:
    """Inspect whether the launch agent is installed and loaded."""
    _ensure_macos()
    plist_path = launch_agent_plist_path()
    return LaunchAgentStatus(
        label=LAUNCH_AGENT_LABEL,
        plist_path=plist_path,
        installed=plist_path.exists(),
        loaded=_is_loaded(),
    )


def install_launch_agent(
    *,
    interval_seconds: float,
    database_path: Path,
    project_root: Path,
    python_executable: str = sys.executable,
) -> Path:
    """Create or update the launch agent plist."""
    _ensure_macos()
    if interval_seconds <= 0:
        raise ValueError("interval_seconds must be greater than zero")
    plist_path = launch_agent_plist_path()
    plist_path.parent.mkdir(parents=True, exist_ok=True)
    logs_dir = Path.home() / "Library" / "Logs" / "battery-analyzer"
    logs_dir.mkdir(parents=True, exist_ok=True)
    config = build_launch_agent_config(
        python_executable=python_executable,
        project_root=project_root,
        interval_seconds=interval_seconds,
        database_path=database_path,
    )
    plist_path.write_bytes(plistlib.dumps(config, fmt=plistlib.FMT_XML))
    return plist_path


def start_launch_agent() -> None:
    """Load and start the launch agent."""
    _ensure_macos()
    status = get_launch_agent_status()
    if not status.installed:
        raise RuntimeError(f"Launch agent is not installed: {status.plist_path}")

    if status.loaded:
        result = _launchctl("kickstart", "-k", f"gui/{os.getuid()}/{status.label}")
    else:
        result = _launchctl("bootstrap", f"gui/{os.getuid()}", str(status.plist_path))

    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "launchctl failed"
        raise RuntimeError(f"Failed to start launch agent: {message}")


def stop_launch_agent() -> None:
    """Stop/unload the launch agent if currently loaded."""
    _ensure_macos()
    status = get_launch_agent_status()
    if not status.loaded:
        return
    result = _launchctl("bootout", f"gui/{os.getuid()}/{status.label}")
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "launchctl failed"
        raise RuntimeError(f"Failed to stop launch agent: {message}")


def uninstall_launch_agent() -> None:
    """Stop and remove the launch agent plist."""
    _ensure_macos()
    stop_launch_agent()
    status = get_launch_agent_status()
    if status.installed:
        status.plist_path.unlink()
