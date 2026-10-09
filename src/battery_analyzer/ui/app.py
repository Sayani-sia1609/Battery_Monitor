"""Native Tkinter dashboard backed by the existing SQLite database."""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from itertools import pairwise
from pathlib import Path
from statistics import mean
from typing import Any
from zoneinfo import ZoneInfo

from battery_analyzer.analytics.drain import drain_percent_points, drain_rate_per_hour
from battery_analyzer.models.battery_data import BatteryData, BatterySession, ChargingSession
from battery_analyzer.storage.database import BatteryDatabase

LOGGER = logging.getLogger(__name__)
DISPLAY_TIMEZONE = ZoneInfo("Asia/Kolkata")


def format_local_timestamp(timestamp: datetime) -> str:
    """Format an aware timestamp in India Standard Time."""
    return timestamp.astimezone(DISPLAY_TIMEZONE).strftime("%d %b %Y, %I:%M:%S %p")


def format_duration(seconds: float | None) -> str:
    """Format a duration without inventing a value when it is unavailable."""
    if seconds is None or seconds < 0:
        return "N/A"
    minutes = round(seconds / 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes:02d}m" if hours else f"{minutes}m"


def current_session_summary(
    session: BatterySession | None,
    latest: BatteryData | None,
) -> dict[str, str]:
    """Build display values for the current contiguous session."""
    if session is None or latest is None:
        return {
            "state": "No session data",
            "start": "N/A",
            "charge": "N/A",
            "change": "N/A",
            "duration": "N/A",
            "rate": "N/A",
        }
    change = latest.charge_percent - session.start_percent
    rate = None
    if session.started_at < latest.timestamp:
        rate = abs(change) / ((latest.timestamp - session.started_at).total_seconds() / 3600)
    return {
        "state": "Charging" if session.is_charging else "Discharging",
        "start": format_local_timestamp(session.started_at),
        "charge": f"{session.start_percent:.1f}% -> {latest.charge_percent:.1f}%",
        "change": f"{change:+.1f}%",
        "duration": format_duration((latest.timestamp - session.started_at).total_seconds()),
        "rate": f"{rate:.1f}%/hr" if rate is not None else "N/A",
    }


def drain_summary(measurements: list[BatteryData]) -> dict[str, str]:
    """Calculate conservative drain statistics from real measurements."""
    today = datetime.now(timezone.utc).astimezone(DISPLAY_TIMEZONE).date()
    today_measurements = [
        item for item in measurements if item.timestamp.astimezone(DISPLAY_TIMEZONE).date() == today
    ]
    ordered = sorted(today_measurements, key=lambda item: item.timestamp)
    rates: list[float] = []
    consumed = 0.0
    discharge_seconds = 0.0
    for previous, current in pairwise(ordered):
        elapsed = (current.timestamp - previous.timestamp).total_seconds()
        if elapsed <= 0 or previous.is_charging or current.is_charging:
            continue
        drained = drain_percent_points(previous, current)
        if drained is not None:
            consumed += drained
            discharge_seconds += elapsed
            rates.append(drain_rate_per_hour(previous, current) or 0.0)
    return {
        "usage": f"{consumed:.1f}%" if ordered and rates else "N/A",
        "time": format_duration(discharge_seconds) if rates else "N/A",
        "rate": f"{mean(rates):.1f}%/hr" if rates else "N/A",
        "session": f"{consumed:.1f}%" if rates else "N/A",
    }


def full_charge_summary(sessions: list[ChargingSession]) -> list[dict[str, str]]:
    """Return real sessions that reached 100%, newest first."""
    result = []
    for session in reversed(sessions):
        if not session.reached_100 and session.end_percent < 100:
            continue
        result.append(
            {
                "date": session.ended_at.astimezone(DISPLAY_TIMEZONE).strftime("%d %b %Y"),
                "time": session.ended_at.astimezone(DISPLAY_TIMEZONE).strftime("%I:%M %p"),
                "charge": f"{session.start_percent:.0f}% -> 100%",
                "duration": format_duration(session.duration_seconds),
            }
        )
    return result


class BatteryApp:
    """Read-only desktop dashboard; collection remains the monitor's responsibility."""

    def __init__(
        self,
        root: Any,
        *,
        database_path: str | Path = "data/battery.db",
        refresh_seconds: float = 7.0,
    ) -> None:
        import tkinter as tk
        from tkinter import ttk

        if refresh_seconds <= 0:
            raise ValueError("refresh_seconds must be greater than zero")
        self.root = root
        self.tk = tk
        self.ttk = ttk
        self.database_path = Path(database_path)
        self.refresh_ms = int(refresh_seconds * 1000)
        self.range_days = 1
        self._refresh_job: str | None = None
        self.root.title("Battery Health Analyzer")
        self.root.minsize(980, 720)
        self.root.configure(bg="#111827")
        self.vars = {
            name: tk.StringVar(value=value)
            for name, value in {
                "charge": "N/A",
                "state": "N/A",
                "time": "N/A",
                "full_charge": "No full charge recorded",
                "health": "Health data unavailable",
                "last_reading": "Last stored reading: N/A",
                "session": "No session data",
                "session_start": "Start: N/A",
                "session_change": "Change: N/A",
                "session_duration": "Duration: N/A",
                "session_rate": "Rate: N/A",
                "usage": "N/A",
                "discharge_time": "N/A",
                "average_rate": "N/A",
                "status": "Waiting for battery history...",
            }.items()
        }
        self._build_widgets()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.after(0, self.refresh)

    def _build_widgets(self) -> None:
        tk, ttk = self.tk, self.ttk
        style = ttk.Style(self.root)
        style.configure("Card.TLabelframe", padding=12, background="#1f2937")
        style.configure("Card.TLabelframe.Label", background="#1f2937", foreground="#cbd5e1")
        style.configure(
            "Title.TLabel",
            font=("TkDefaultFont", 22, "bold"),
            background="#111827",
            foreground="#f8fafc",
        )
        style.configure("Subtitle.TLabel", background="#111827", foreground="#94a3b8")
        style.configure(
            "Metric.TLabel",
            font=("TkDefaultFont", 27, "bold"),
            background="#1f2937",
            foreground="#f8fafc",
        )
        style.configure("TLabel", background="#1f2937", foreground="#e5e7eb")
        style.configure("TButton", background="#334155", foreground="#f8fafc")
        style.map("TButton", background=[("active", "#475569")])

        outer = ttk.Frame(self.root, padding=20)
        outer.configure(style="Dashboard.TFrame")
        style.configure("Dashboard.TFrame", background="#111827")
        outer.pack(fill=tk.BOTH, expand=True)
        header = tk.Canvas(outer, height=86, bg="#111827", highlightthickness=0)
        header.pack(fill=tk.X, pady=(0, 14))
        self._draw_header_gradient(header)
        ttk.Label(
            outer,
            textvariable=self.vars["last_reading"],
            style="Subtitle.TLabel",
        ).pack(anchor=tk.W, pady=(0, 14))
        ttk.Label(
            outer,
            textvariable=self.vars["status"],
            style="Subtitle.TLabel",
        ).pack(anchor=tk.W, pady=(0, 14))

        summary = ttk.Frame(outer)
        summary.pack(fill=tk.X, pady=(0, 12))
        self._card(
            summary,
            "Current battery",
            [("charge", "Metric.TLabel"), ("state", "TLabel"), ("time", "TLabel")],
            0,
        )
        self._card(summary, "Last charged to 100%", [("full_charge", "Metric.TLabel")], 1)
        self._card(summary, "Battery health", [("health", "Metric.TLabel")], 2)
        self._card(
            summary,
            "Current session",
            [
                ("session", "TLabel"),
                ("session_start", "TLabel"),
                ("session_change", "TLabel"),
                ("session_duration", "TLabel"),
                ("session_rate", "TLabel"),
            ],
            3,
        )

        chart_frame = ttk.LabelFrame(outer, text="Battery charge", style="Card.TLabelframe")
        chart_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 12))
        controls = ttk.Frame(chart_frame)
        controls.pack(fill=tk.X)
        for label, days in (("Today", 1), ("Last 7 days", 7), ("Last 30 days", 30)):
            ttk.Button(
                controls, text=label, command=lambda value=days: self._set_range(value)
            ).pack(side=tk.LEFT, padx=(0, 6))
        self.charge_canvas = tk.Canvas(chart_frame, height=260, bg="#172033", highlightthickness=0)
        self.charge_canvas.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        full_frame = ttk.LabelFrame(outer, text="Previous full charges", style="Card.TLabelframe")
        full_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 12))
        self.full_charge_list = tk.Listbox(
            full_frame,
            height=4,
            bg="#172033",
            fg="#e5e7eb",
            selectbackground="#2563eb",
            highlightthickness=0,
            relief="flat",
            font=("TkDefaultFont", 11),
        )
        self.full_charge_list.pack(fill=tk.BOTH, expand=True)

        health_frame = ttk.LabelFrame(
            outer, text="Battery health history", style="Card.TLabelframe"
        )
        health_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 12))
        self.health_canvas = tk.Canvas(health_frame, height=150, bg="#172033", highlightthickness=0)
        self.health_canvas.pack(fill=tk.BOTH, expand=True)

        lower = ttk.Frame(outer)
        lower.pack(fill=tk.BOTH, expand=True)
        history = ttk.LabelFrame(lower, text="Recent charging", style="Card.TLabelframe")
        history.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))
        columns = ("date", "start", "end", "levels", "duration")
        self.history = ttk.Treeview(history, columns=columns, show="headings", height=6)
        for column, heading, width in zip(
            columns,
            ("Date", "Start", "End", "Charge", "Duration"),
            (90, 90, 90, 110, 90),
        ):
            self.history.heading(column, text=heading)
            self.history.column(column, width=width, anchor="center")
        self.history.pack(fill=tk.BOTH, expand=True)

        analytics = ttk.LabelFrame(lower, text="Drain analytics", style="Card.TLabelframe")
        analytics.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(6, 0))
        for key, label in (
            ("usage", "Today's usage"),
            ("discharge_time", "Discharge time"),
            ("average_rate", "Average drain"),
        ):
            ttk.Label(analytics, text=label, font=("TkDefaultFont", 10, "bold")).pack(anchor=tk.W)
            ttk.Label(analytics, textvariable=self.vars[key]).pack(anchor=tk.W, pady=(0, 8))

    def _card(self, parent: Any, title: str, fields: list[tuple[str, str]], column: int) -> None:
        card = self.ttk.LabelFrame(parent, text=title, style="Card.TLabelframe")
        card.grid(row=0, column=column, sticky="nsew", padx=6)
        parent.columnconfigure(column, weight=1)
        for key, style in fields:
            self.ttk.Label(card, textvariable=self.vars[key], style=style).pack(anchor=self.tk.W)

    @staticmethod
    def _draw_header_gradient(canvas: Any) -> None:
        """Draw a lightweight blue-to-violet header gradient."""
        width = 1100
        height = 86
        bands = 30
        for index in range(bands):
            ratio = index / (bands - 1)
            red = int(37 + (124 - 37) * ratio)
            green = int(99 + (58 - 99) * ratio)
            blue = int(235 + (237 - 235) * ratio)
            color = f"#{red:02x}{green:02x}{blue:02x}"
            y0 = index * height / bands
            y1 = (index + 1) * height / bands
            canvas.create_rectangle(0, y0, width, y1, fill=color, outline="")
        canvas.create_text(
            24,
            27,
            text="Battery Health Analyzer",
            anchor="w",
            fill="#ffffff",
            font=("TkDefaultFont", 22, "bold"),
        )
        canvas.create_text(
            25,
            60,
            text="Real-time battery insights from your local history",
            anchor="w",
            fill="#dbeafe",
            font=("TkDefaultFont", 10),
        )

    def _set_range(self, days: int) -> None:
        self.range_days = days
        self.refresh()

    def refresh(self) -> None:
        """Refresh from SQLite only; never starts a collector or monitor."""
        try:
            with BatteryDatabase(self.database_path) as database:
                latest = database.get_latest()
                active = database.get_active_session()
                measurements = database.get_between(
                    datetime.now(timezone.utc) - timedelta(days=self.range_days),
                    datetime.now(timezone.utc),
                )
                all_sessions = database.reconstruct_sessions()
                history = all_sessions[-10:]
            self._update_values(latest, active, measurements, history, all_sessions)
            self.vars["status"].set("Updated from SQLite")
        except (OSError, RuntimeError, ValueError, sqlite3.Error) as exc:
            LOGGER.exception("Dashboard refresh failed")
            self.vars["status"].set(f"Unable to read battery history: {exc}")
        finally:
            self._refresh_job = self.root.after(self.refresh_ms, self.refresh)

    def _update_values(
        self,
        latest: BatteryData | None,
        active: BatterySession | None,
        measurements: list[BatteryData],
        history: list[ChargingSession],
        all_sessions: list[ChargingSession],
    ) -> None:
        if latest is not None:
            self.vars["charge"].set(f"{latest.charge_percent:.1f}%")
            self.vars["state"].set("Charging" if latest.is_charging else "Discharging")
            self.vars["time"].set(format_local_timestamp(latest.timestamp))
            age_seconds = (datetime.now(timezone.utc) - latest.timestamp).total_seconds()
            stale = age_seconds > max(self.refresh_ms / 1000 * 3, 180)
            suffix = " • stale" if stale else ""
            self.vars["last_reading"].set(
                f"Last stored reading: {format_local_timestamp(latest.timestamp)}{suffix}"
            )
        current = current_session_summary(active, latest)
        self.vars["session"].set(current["state"])
        self.vars["session_start"].set(f"Start: {current['start']}")
        self.vars["session_change"].set(f"Change: {current['change']}")
        self.vars["session_duration"].set(f"Duration: {current['duration']}")
        self.vars["session_rate"].set(f"Rate: {current['rate']}")
        full_charges = full_charge_summary(all_sessions)
        if full_charges:
            self.vars["full_charge"].set(full_charges[0]["date"])
        else:
            self.vars["full_charge"].set("No full charge recorded")
        with BatteryDatabase(self.database_path) as database:
            health_history = database.get_health_history()
        if health_history:
            latest_health = health_history[-1]
            if latest_health.energy_design_wh and latest_health.energy_full_wh is not None:
                health = latest_health.energy_full_wh / latest_health.energy_design_wh * 100
                self.vars["health"].set(f"{health:.1f}%")
            else:
                self.vars["health"].set("Health data unavailable")
        else:
            self.vars["health"].set("Health data unavailable")
        drain = drain_summary(measurements)
        self.vars["usage"].set(drain["usage"])
        self.vars["discharge_time"].set(drain["time"])
        self.vars["average_rate"].set(drain["rate"])
        self._draw_charge_chart(measurements)
        self._draw_health_chart()
        self._update_history(history)
        self._update_full_charge_history(full_charges)

    def _update_history(self, sessions: list[ChargingSession]) -> None:
        for item in self.history.get_children():
            self.history.delete(item)
        for session in reversed(sessions):
            local_start = session.started_at.astimezone(DISPLAY_TIMEZONE)
            local_end = session.ended_at.astimezone(DISPLAY_TIMEZONE)
            self.history.insert(
                "",
                self.tk.END,
                values=(
                    local_start.strftime("%d %b"),
                    local_start.strftime("%I:%M %p"),
                    local_end.strftime("%I:%M %p"),
                    f"{session.start_percent:.0f}% -> {session.end_percent:.0f}%",
                    format_duration(session.duration_seconds),
                ),
            )

    def _update_full_charge_history(self, entries: list[dict[str, str]]) -> None:
        self.full_charge_list.delete(0, self.tk.END)
        if not entries:
            self.full_charge_list.insert(self.tk.END, "No charging session has reached 100% yet.")
            return
        for entry in entries[:6]:
            self.full_charge_list.insert(
                self.tk.END,
                f"{entry['date']}  •  {entry['time']}  •  "
                f"{entry['charge']}  •  {entry['duration']}",
            )

    def _draw_charge_chart(self, measurements: list[BatteryData]) -> None:
        canvas = self.charge_canvas
        canvas.delete("all")
        if not measurements:
            canvas.create_text(300, 100, text="No battery history yet.", fill="#94a3b8")
            return
        width = max(canvas.winfo_width(), 500)
        height = max(canvas.winfo_height(), 220)
        left, top, right, bottom = 48, 18, width - 18, height - 32
        canvas.create_line(left, top, left, bottom, fill="#64748b")
        canvas.create_line(left, bottom, right, bottom, fill="#64748b")
        for value in (0, 25, 50, 75, 100):
            y = bottom - (value / 100) * (bottom - top)
            canvas.create_line(left, y, right, y, fill="#273449")
            canvas.create_text(left - 8, y, text=f"{value}%", anchor="e", fill="#94a3b8")
        start, end = measurements[0].timestamp, measurements[-1].timestamp
        span = max((end - start).total_seconds(), 1)
        points: list[float] = []
        for item in measurements:
            x = left + (item.timestamp - start).total_seconds() / span * (right - left)
            y = bottom - item.charge_percent / 100 * (bottom - top)
            points.extend((x, y))
        if len(points) >= 4:
            self._draw_gradient_line(canvas, points)
        for x, y in zip(points[::2], points[1::2]):
            canvas.create_oval(x - 3, y - 3, x + 3, y + 3, fill="#2563eb", outline="")
        canvas.create_text(left, bottom + 16, text=format_local_timestamp(start), anchor="w")
        canvas.create_text(right, bottom + 16, text=format_local_timestamp(end), anchor="e")

    def _draw_health_chart(self) -> None:
        canvas = self.health_canvas
        canvas.delete("all")
        with BatteryDatabase(self.database_path) as database:
            measurements = database.get_health_history()
        valid = [
            item
            for item in measurements
            if item.energy_design_wh and item.energy_full_wh is not None
        ]
        if not valid:
            canvas.create_text(
                300,
                65,
                text="Health data unavailable on this system.",
                fill="#94a3b8",
            )
            return
        width = max(canvas.winfo_width(), 500)
        height = max(canvas.winfo_height(), 150)
        left, top, right, bottom = 48, 18, width - 18, height - 28
        values = [
            item.energy_full_wh / item.energy_design_wh * 100
            for item in valid
            if item.energy_design_wh
        ]
        low, high = min(values), max(values)
        padding = max((high - low) * 0.2, 1.0)
        low = max(0.0, low - padding)
        high = min(100.0, high + padding)
        start, end = valid[0].timestamp, valid[-1].timestamp
        span = max((end - start).total_seconds(), 1)
        points: list[float] = []
        for item, value in zip(valid, values):
            x = left + (item.timestamp - start).total_seconds() / span * (right - left)
            y = bottom - (value - low) / max(high - low, 1) * (bottom - top)
            points.extend((x, y))
        canvas.create_line(left, top, left, bottom, fill="#64748b")
        canvas.create_line(left, bottom, right, bottom, fill="#64748b")
        if len(points) >= 4:
            self._draw_gradient_line(canvas, points)
        canvas.create_text(left - 8, top, text=f"{high:.1f}%", anchor="e", fill="#94a3b8")
        canvas.create_text(left - 8, bottom, text=f"{low:.1f}%", anchor="e", fill="#94a3b8")
        canvas.create_text(left, bottom + 14, text=format_local_timestamp(start), anchor="w")
        canvas.create_text(right, bottom + 14, text=format_local_timestamp(end), anchor="e")

    @staticmethod
    def _draw_gradient_line(canvas: Any, points: list[float]) -> None:
        """Approximate a gradient by drawing short colored segments."""
        if len(points) < 4:
            return
        for index in range(0, len(points) - 2, 2):
            ratio = index / max(len(points) - 4, 1)
            color = "#38bdf8" if ratio < 0.5 else "#8b5cf6"
            canvas.create_line(
                points[index],
                points[index + 1],
                points[index + 2],
                points[index + 3],
                fill=color,
                width=3,
                smooth=True,
            )

    def close(self) -> None:
        """Close the dashboard without stopping the backend monitor."""
        if self._refresh_job is not None:
            self.root.after_cancel(self._refresh_job)
            self._refresh_job = None
        self.root.destroy()


def run_app(
    database_path: str | Path = "data/battery.db",
    refresh_seconds: float = 7.0,
) -> None:
    """Start the native desktop dashboard."""
    try:
        import tkinter as tk
    except ImportError as exc:
        raise RuntimeError(
            "Tkinter is unavailable in this Python installation; install Python with Tk support"
        ) from exc
    root = tk.Tk()
    BatteryApp(root, database_path=database_path, refresh_seconds=refresh_seconds)
    root.mainloop()
