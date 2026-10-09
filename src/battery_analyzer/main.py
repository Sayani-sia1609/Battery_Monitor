"""Command-line entry point for Battery Analyzer."""

from __future__ import annotations

import argparse
import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from battery_analyzer import __version__
from battery_analyzer.collectors.service import collect_and_store
from battery_analyzer.core.launch_agent import (
    get_launch_agent_status,
    install_launch_agent,
    start_launch_agent,
    stop_launch_agent,
    uninstall_launch_agent,
)
from battery_analyzer.core.monitor import BatteryMonitor
from battery_analyzer.ui.app import run_app

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
LOGGER = logging.getLogger(__name__)
DISPLAY_TIMEZONE = ZoneInfo("Asia/Kolkata")


def format_local_timestamp(timestamp: datetime) -> str:
    """Format a UTC-aware timestamp for display in India Standard Time."""
    return timestamp.astimezone(DISPLAY_TIMEZONE).isoformat(timespec="seconds")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect battery health and usage.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "command",
        nargs="?",
        choices=("collect", "monitor", "sessions", "ui", "agent"),
        default="collect",
        help="Collect once, run monitor, inspect sessions/UI, or manage macOS launch agent.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print collected battery data as JSON.",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=60.0,
        help="Monitor collection interval in seconds (default: 60).",
    )
    parser.add_argument(
        "--refresh-interval",
        type=float,
        default=7.0,
        help="Desktop UI refresh interval in seconds (default: 7).",
    )
    parser.add_argument(
        "--database-path",
        default="data/battery.db",
        help="SQLite file path (default: data/battery.db).",
    )
    parser.add_argument(
        "--agent-action",
        choices=("status", "install", "start", "stop", "uninstall"),
        default="status",
        help="Launch agent action when command is 'agent' (default: status).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Number of recent sessions to display (default: 10).",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    database_path = Path(args.database_path)
    if args.command == "agent":
        try:
            if args.agent_action == "install":
                plist_path = install_launch_agent(
                    interval_seconds=args.interval,
                    database_path=database_path,
                    project_root=Path.cwd(),
                )
                print(f"Installed launch agent: {plist_path}")
            elif args.agent_action == "start":
                start_launch_agent()
                print("Launch agent started.")
            elif args.agent_action == "stop":
                stop_launch_agent()
                print("Launch agent stopped.")
            elif args.agent_action == "uninstall":
                uninstall_launch_agent()
                print("Launch agent uninstalled.")

            status = get_launch_agent_status()
            print(
                "Agent status: "
                f"installed={'yes' if status.installed else 'no'}, "
                f"loaded={'yes' if status.loaded else 'no'}"
            )
        except (RuntimeError, ValueError) as exc:
            LOGGER.error("Launch agent operation failed: %s", exc)
            return 1
        return 0
    if args.command == "ui":
        try:
            run_app(
                database_path=database_path,
                refresh_seconds=args.refresh_interval,
            )
        except (RuntimeError, OSError) as exc:
            LOGGER.error("Unable to start desktop UI: %s", exc)
            return 1
        return 0
    if args.command == "sessions":
        from battery_analyzer.storage.database import BatteryDatabase

        if args.limit < 1:
            LOGGER.error("Session limit must be greater than zero")
            return 1
        try:
            with BatteryDatabase(database_path) as database:
                sessions = database.reconstruct_sessions()
                for session in sessions[-args.limit :]:
                    print(
                        f"{session.id or '-'} "
                        f"{format_local_timestamp(session.started_at)} -> "
                        f"{format_local_timestamp(session.ended_at)} "
                        f"{session.start_percent:.1f}% -> {session.end_percent:.1f}% "
                        f"{session.status} "
                        f"({session.duration_seconds / 60:.1f} min)"
                    )
        except (OSError, ValueError) as exc:
            LOGGER.error("Unable to inspect charging sessions: %s", exc)
            return 1
        return 0
    if args.command == "monitor":
        try:
            monitor = BatteryMonitor(
                interval_seconds=args.interval,
                database_path=database_path,
            )
            monitor.run_forever()
        except KeyboardInterrupt:
            monitor.stop()
        except ValueError as exc:
            LOGGER.error("Unable to start monitor: %s", exc)
            return 1
        return 0

    try:
        data = collect_and_store(database_path=database_path)
    except RuntimeError as exc:
        LOGGER.error("%s", exc)
        return 1
    if args.json:
        print(data.model_dump_json(indent=2))
    else:
        status = "Charging" if data.is_charging else "Discharging"
        print("Battery status:")
        print(f"Charge: {data.charge_percent:.1f}%")
        print(f"Status: {status}")
        print(f"Time: {format_local_timestamp(data.timestamp)}")
        print("Measurement saved.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
