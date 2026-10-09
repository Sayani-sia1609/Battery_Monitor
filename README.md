# Battery Health Analyzer

Battery Health Analyzer is a local-first Python application for collecting, storing, and
understanding real battery telemetry on macOS and Windows.

It provides:

- Real battery measurements from the operating system.
- A configurable background monitor.
- SQLite persistence for local history.
- Charging-session reconstruction from observed measurements.
- Discharge and usage analytics.
- A native Tkinter desktop dashboard.
- Capacity-based battery-health reporting when the operating system provides valid capacity data.

No cloud service, account, login, or fake battery data is required.

## Contents

- [Requirements](#requirements)
- [Installation](#installation)
- [Quick start](#quick-start)
- [Command-line usage](#command-line-usage)
- [Desktop dashboard](#desktop-dashboard)
- [How data is interpreted](#how-data-is-interpreted)
- [Project architecture](#project-architecture)
- [Database and privacy](#database-and-privacy)
- [Development](#development)
- [Troubleshooting](#troubleshooting)
- [Limitations](#limitations)
- [Roadmap](#roadmap)
- [License](#license)

## Requirements

- Python 3.10 or newer.
- macOS or Windows.
- Tkinter support for the desktop dashboard.
- Permission to read the operating system's battery information.

The application has no runtime network dependency. Platform telemetry availability varies by
operating system and hardware.

## Installation

### macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

### Windows PowerShell

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

The `dev` extra installs the test and lint tools used by the project. For a runtime-only
installation, use:

```bash
python -m pip install -e .
```

Verify the installation:

```bash
python -m battery_analyzer.main --version
```

Expected output:

```text
battery-analyzer 1.0.0
```

## Quick start

Open two terminals with the virtual environment activated.

In the first terminal, start the background monitor:

```bash
python -m battery_analyzer.main monitor --interval 60
```

In the second terminal, start the dashboard:

```bash
python -m battery_analyzer.main ui --refresh-interval 7
```

The monitor collects real measurements every 60 seconds. The dashboard reads the stored SQLite
history and refreshes its display every 7 seconds. The dashboard does not start another monitor.

Stop the monitor with `Ctrl+C`. It handles shutdown gracefully.

## Command-line usage

The installed console script and the Python module are equivalent:

```bash
battery-analyzer <command>
python -m battery_analyzer.main <command>
```

### Collect one measurement

Collect one real reading, save it to SQLite, and print the result:

```bash
battery-analyzer collect
```

Print the collected measurement as JSON:

```bash
battery-analyzer collect --json
```

The default command is `collect`, so this is also valid:

```bash
battery-analyzer
```

### Run the background monitor

Use the default 60-second interval:

```bash
battery-analyzer monitor
```

Choose a different interval in seconds:

```bash
battery-analyzer monitor --interval 30
```

The monitor:

- Collects real platform telemetry.
- Saves successful readings to SQLite.
- Logs collection results.
- Continues after temporary collector failures.
- Does not save fabricated `0%` or fallback measurements.
- Stops cleanly on `Ctrl+C`.

### Inspect charging sessions

Reconstruct historical charging sessions and display the ten most recent sessions:

```bash
battery-analyzer sessions
```

Display a different number of sessions:

```bash
battery-analyzer sessions --limit 25
```

Session boundaries are derived from observed charging-state transitions in stored measurements.
They are not claims about exact physical plug or unplug times.

### Launch the desktop dashboard

```bash
battery-analyzer ui
```

Choose the dashboard refresh interval:

```bash
battery-analyzer ui --refresh-interval 5
```

### Use another database file

All commands that read or write measurements accept a custom SQLite path:

```bash
battery-analyzer monitor --database-path /path/to/battery.db
battery-analyzer sessions --database-path /path/to/battery.db
battery-analyzer ui --database-path /path/to/battery.db
```

### Manage the macOS launch agent

The optional launch-agent integration can run collection through macOS `launchd`:

```bash
battery-analyzer agent --agent-action status
battery-analyzer agent --agent-action install --interval 60
battery-analyzer agent --agent-action start
battery-analyzer agent --agent-action stop
battery-analyzer agent --agent-action uninstall
```

The launch agent is optional and is not required when running the monitor manually.

## Desktop dashboard

The Tkinter dashboard is a visualization layer over the existing backend and SQLite database.
It displays:

- Current charge and charging status.
- Current timestamp.
- Current or recent session information.
- Battery percentage history for today, 7 days, or 30 days.
- Recent charging sessions.
- Discharge and drain analytics.
- The most recent and previous sessions that reached 100%.
- Capacity-based battery health when valid capacity telemetry exists.

Unavailable values are shown as unavailable rather than estimated or fabricated. For example,
when the operating system does not expose capacity information, the dashboard reports that
battery-health data is unavailable.

## How data is interpreted

### Time handling

- Measurements are required to use timezone-aware timestamps.
- Database timestamps are normalized to UTC for unambiguous storage.
- User-facing timestamps are displayed in `Asia/Kolkata` (`UTC+05:30`).
- No manual five-hour-thirty-minute offset is applied.

### Charging sessions

A charging session is reconstructed from stored measurements showing a transition into charging
and the subsequent observed charging measurements.

The detector supports:

- Full sessions that reach 100%.
- Partial sessions that end before 100%.
- Interrupted sessions.
- Multiple sessions on the same day.
- Missing measurements and time gaps.
- Duplicate timestamps.
- Historical reconstruction after the application starts.

Durations represent the interval supported by observed measurements. Missing observations do not
create invented timestamps or percentages.

### Battery health

Current charge and battery health are separate concepts:

- **Current charge:** the present battery level, such as `93%`.
- **Charging session:** a period during which charging was observed.
- **Battery health:** remaining full-charge capacity relative to design capacity.

Health is calculated only when both values are valid:

```text
health = energy_full_wh / energy_design_wh * 100
```

Health is not inferred from the current charge percentage or from charging-session behavior.

### Drain analytics

Drain analytics report percentage-point usage over time. They do not claim watt-hour precision
unless the required energy telemetry is available.

## Project architecture

```text
Operating system
       |
       v
collectors/  ->  BatteryData  ->  storage/ SQLite
                                      |
                                      v
                           core monitoring and sessions
                                      |
                                      v
                              analytics/ summaries
                                      |
                                      v
                                ui/ Tkinter
```

| Area | Responsibility |
| --- | --- |
| `collectors/` | Reads macOS or Windows battery telemetry and normalizes it into `BatteryData`. |
| `models/` | Defines validated battery measurements and charging-session models. |
| `storage/` | Owns SQLite initialization, migrations, persistence, retrieval, and reconstruction. |
| `core/` | Implements monitoring, retries, session detection, and launch-agent integration. |
| `analytics/` | Calculates drain summaries and capacity-based health. |
| `ui/` | Displays backend data in the Tkinter dashboard; it does not call OS APIs directly. |
| `tests/` | Covers collectors, models, storage, monitoring, sessions, analytics, CLI behavior, and UI helpers. |

See [`docs/architecture.md`](docs/architecture.md) for the backend data flow and design notes.

## Database and privacy

The default database is:

```text
data/battery.db
```

The database is local and is ignored by version control. It contains locally collected battery
measurements and derived charging-session data.

Existing databases are preserved. Schema migrations are additive and only add missing fields
when required. The application does not upload telemetry, use cloud storage, or send data to a
remote service.

## Development

Create the development environment and install the project:

```bash
python -m pip install -e ".[dev]"
```

Run the complete test suite:

```bash
python -m pytest -q
```

Run Ruff lint checks:

```bash
python -m ruff check .
```

Check formatting:

```bash
python -m ruff format --check .
```

Build the package without downloading runtime dependencies:

```bash
python -m pip wheel . --no-deps
```

Tests use fixtures and mocks. They do not require a real battery, network access, a graphical
display, or the user's live database.

## Troubleshooting

### Collection reports an unsupported operating system

Only macOS and Windows collectors are currently implemented. No fabricated measurement is stored
when the platform is unsupported.

### macOS collection fails

Verify that the native command works:

```bash
pmset -g batt
```

If it fails, check the macOS environment and permissions before retrying the application.

### Windows data is unavailable

The Windows collector uses the native system power-status API. Unknown Windows sentinel values
are rejected instead of being stored as valid telemetry.

### The dashboard shows stale data

Start the monitor in another terminal:

```bash
battery-analyzer monitor --interval 60
```

The dashboard only displays data that has been successfully collected and saved.

### Battery health is unavailable

The operating system or hardware did not provide both valid full-charge and design-capacity
values. This is expected on systems where capacity telemetry is unavailable.

### Tkinter cannot be imported

Install a Python distribution that includes Tk support. On macOS, a Python installation from
python.org or Homebrew may be required.

## Limitations

- Windows runtime validation has been covered by tests but not performed on a Windows host in the
  current development environment.
- Battery telemetry fields differ between operating systems and hardware.
- Charging-session duration is based on observed measurements and can be affected by gaps.
- The dashboard requires Tkinter support and a graphical desktop session.
- No license has been selected for redistribution.

## Roadmap

Possible future improvements include:

- More platform-specific capacity telemetry.
- Additional historical analytics.
- More detailed export and reporting tools.
- Packaging and installation improvements.

The following are intentionally outside the current scope:

- Machine-learning attribution.
- Cloud synchronization.
- Notifications.
- User accounts and login.
- App-level battery attribution.
- PostgreSQL or MongoDB storage.

## License

No license file is currently included. Do not assume that the project may be redistributed under
an open-source license until an explicit license is selected and added.
