# Battery Health Analyzer

A local-first Python desktop application for monitoring battery performance, analyzing charging and discharging behavior, and tracking battery health using real operating-system telemetry.

Battery Health Analyzer collects battery measurements, stores historical data locally in SQLite, reconstructs charging sessions, and presents insights through a native Tkinter dashboard.

**Key principles:** Real telemetry · Local storage · No fabricated data · Privacy-first design

---

## Table of Contents

- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Command-Line Interface](#command-line-interface)
- [Desktop Dashboard](#desktop-dashboard)
- [How It Works](#how-it-works)
- [Data and Calculations](#data-and-calculations)
- [Architecture](#architecture)
- [Database and Privacy](#database-and-privacy)
- [Development and Testing](#development-and-testing)
- [Troubleshooting](#troubleshooting)
- [Limitations](#limitations)
- [Roadmap](#roadmap)
- [License](#license)

---

## Features

### Battery Monitoring
- Collects real battery measurements from macOS and Windows.
- Supports configurable background collection intervals.
- Stores measurements persistently in SQLite.
- Handles temporary collection failures without fabricating readings.

### Charging Session Analysis
- Reconstructs charging sessions from recorded measurements.
- Tracks full and partial charging sessions.
- Identifies interrupted sessions and handles gaps in historical data.
- Provides access to previous charging sessions.

### Battery Drain Analytics
- Calculates discharge rates in percentage points per hour.
- Analyzes charge consumption over recorded intervals.
- Provides session-level and historical drain information.
- Handles missing measurements and uncertain intervals.

### Battery Health Tracking
- Calculates battery health when valid full-charge and design-capacity measurements are available.
- Keeps battery health separate from current charge percentage.
- Supports historical capacity-based health reporting when sufficient data exists.
- Reports unavailable measurements honestly rather than inventing values.

### Desktop Dashboard
- Displays current battery charge and charging status.
- Visualizes historical charge levels.
- Provides Today, Last 7 Days, and Last 30 Days views.
- Displays charging-session history and drain analytics.
- Shows battery-health information when supported by available telemetry.

### Privacy-First Design
- Stores measurements locally.
- Uses SQLite for historical data.
- Requires no account, login, cloud service, or external telemetry service.
- Preserves existing measurement history during supported database migrations.

---

## Requirements

| Requirement | Details |
|---|---|
| Python | 3.10 or newer |
| Operating systems | macOS and Windows |
| Database | SQLite |
| Desktop interface | Tkinter |
| Development tools | pytest and Ruff |

**Platform note:** Available battery measurements vary by operating system and hardware. Windows runtime validation and graphical-interface testing should be completed on their respective target environments before claiming full platform compatibility.

---

## Installation

### macOS

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install the project and development dependencies:

```bash
python -m pip install -e ".[dev]"
```

Verify the installation:

```bash
battery-analyzer --version
```

Expected output:

```text
battery-analyzer 1.0.0
```

### Windows

Open PowerShell in the project directory.

Create and activate a virtual environment:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
```

Install the project:

```powershell
python -m pip install -e ".[dev]"
```

Verify the installation:

```powershell
battery-analyzer --version
```

### Runtime-only installation

If you do not need the development tools:

```bash
python -m pip install -e .
```

**Note:** The desktop dashboard requires a Python installation with Tkinter support.

---

## Quick Start

Battery Health Analyzer separates background collection from the desktop dashboard.

### 1. Start battery monitoring

Open a terminal and run:

```bash
battery-analyzer monitor --interval 60
```

The application collects battery measurements every 60 seconds and saves successful readings to SQLite.

### 2. Launch the dashboard

Open a second terminal with the project environment activated:

```bash
battery-analyzer ui --refresh-interval 7
```

The dashboard refreshes its display every seven seconds and reads the stored history.

The dashboard does not start another monitoring process.

### 3. Stop monitoring

Press `Ctrl+C` in the monitoring terminal.

The monitor handles shutdown gracefully.

---

## Command-Line Interface

Commands can be executed using either the installed console script:

```bash
battery-analyzer <command>
```

Or the Python module:

```bash
python -m battery_analyzer.main <command>
```

### Collect a measurement

Collect one battery reading and store it in the database:

```bash
battery-analyzer collect
```

Print the measurement as JSON:

```bash
battery-analyzer collect --json
```

The default command is `collect`, so running the application without a command also performs a single collection.

### Run background monitoring

Start monitoring with the default interval:

```bash
battery-analyzer monitor
```

Specify a custom interval in seconds:

```bash
battery-analyzer monitor --interval 30
```

The monitor:
- Collects real operating-system telemetry.
- Saves successful measurements.
- Handles temporary collection failures.
- Avoids storing fabricated fallback readings.
- Supports graceful shutdown.

### View charging sessions

Display the ten most recent reconstructed charging sessions:

```bash
battery-analyzer sessions
```

Display up to 25 sessions:

```bash
battery-analyzer sessions --limit 25
```

Session boundaries are derived from observed charging-state transitions. They do not necessarily represent the exact physical times a charger was connected or disconnected.

### Launch the desktop dashboard

```bash
battery-analyzer ui
```

Set the refresh interval:

```bash
battery-analyzer ui --refresh-interval 5
```

### Use a custom database

Specify an alternative SQLite database location:

```bash
battery-analyzer monitor --database-path /path/to/battery.db
```

```bash
battery-analyzer sessions --database-path /path/to/battery.db
```

```bash
battery-analyzer ui --database-path /path/to/battery.db
```

### Manage the macOS launch agent

On macOS, the optional launch-agent integration can manage background collection through `launchd`.

Check its status:

```bash
battery-analyzer agent --agent-action status
```

Install the launch agent:

```bash
battery-analyzer agent --agent-action install --interval 60
```

Start it:

```bash
battery-analyzer agent --agent-action start
```

Stop it:

```bash
battery-analyzer agent --agent-action stop
```

Uninstall it:

```bash
battery-analyzer agent --agent-action uninstall
```

The launch agent is optional. You can run the monitor manually instead.

---

## Desktop Dashboard

The application provides a native Tkinter dashboard for viewing battery information and historical analytics.

### Dashboard Components

| Component | Purpose |
|---|---|
| Current Battery | Displays the latest recorded charge and charging status. |
| Current Session | Summarizes the current or most recent relevant session. |
| Battery Charge | Visualizes charge history over different time periods. |
| Charging History | Displays previous charging sessions. |
| Drain Analytics | Summarizes recorded discharge behavior. |
| Battery Health | Displays capacity-based health information when valid measurements are available. |

### Historical Views

The battery-charge graph supports:

- Today
- Last 7 Days
- Last 30 Days

Historical graphs use recorded measurements. Empty history is not filled with synthetic data.

### Data Availability

Some operating systems and hardware configurations do not expose full-charge capacity or design capacity.

When those measurements are unavailable, the application reports battery health as unavailable instead of substituting the current charge percentage.

---

## How It Works

Battery Health Analyzer follows a modular data-processing pipeline:

```text
Operating System
       |
       v
Battery Collectors
       |
       v
Normalized Battery Measurements
       |
       v
SQLite Database
       |
       v
Monitoring and Session Reconstruction
       |
       v
Drain Analytics and Battery Health
       |
       v
Tkinter Desktop Dashboard
```

The collector obtains measurements from the operating system. The storage layer persists them, the core modules reconstruct sessions, and the analytics layer derives summaries for the dashboard.

The UI reads backend data rather than implementing its own battery collection or analytics logic.

---

## Data and Calculations

### Timestamp Handling

- Measurements use timezone-aware timestamps.
- Database timestamps are normalized to UTC.
- User-facing timestamps use `Asia/Kolkata` (`UTC+05:30`).
- Timezone conversion uses Python's `zoneinfo` rather than manually adding an offset.

### Charging Sessions

Charging sessions are reconstructed from recorded measurements and charging-state transitions.

The implementation accounts for:
- Full and partial charging sessions.
- Interrupted sessions.
- Multiple sessions on the same day.
- Missing measurements.
- Duplicate timestamps.
- Gaps between observations.

Session durations and boundaries are limited by the available observations. Missing measurements are not replaced with invented timestamps or charge percentages.

### Battery Health

Battery charge and battery health describe different things.

**Current charge** indicates the battery's present charge level.

**Battery health** estimates remaining full-charge capacity relative to design capacity.

When valid capacity measurements are available, the health percentage is calculated as:

```text
health_percentage = (full_charge_capacity / design_capacity) * 100
```

The calculation is only meaningful when both values are available and valid.

Battery health is not inferred from current charge percentage or charging-session behavior.

### Drain Analytics

Discharge analytics measure charge-percentage changes over time.

For a valid discharge interval:

```text
drain_rate = charge_consumed_percentage_points / duration_hours
```

The result is expressed in **percentage points per hour**.

For example, a decrease from 80% to 70% over two hours corresponds to an average discharge rate of 5 percentage points per hour.

This does not necessarily represent energy consumption in watt-hours. Energy-based analysis requires suitable energy telemetry.

---

## Architecture

The source code follows a modular Python package structure.

```text
src/battery_analyzer/
├── collectors/    # macOS and Windows telemetry
├── models/        # Validated data models
├── storage/       # SQLite persistence and migrations
├── core/          # Monitoring, sessions, launch-agent integration
├── analytics/     # Drain statistics and battery health
├── ui/            # Tkinter desktop interface
└── main.py        # Command-line entry point

tests/             # Automated tests
docs/              # Architecture and design documentation
data/              # Local database storage
```

| Module | Responsibility |
|---|---|
| `collectors/` | Reads and normalizes operating-system telemetry. |
| `models/` | Defines the data structures used throughout the application. |
| `storage/` | Manages SQLite initialization, persistence, retrieval, and migrations. |
| `core/` | Implements background monitoring, charging sessions, and launch-agent integration. |
| `analytics/` | Calculates discharge statistics and capacity-based battery health. |
| `ui/` | Displays collected data and analytics through Tkinter. |
| `tests/` | Tests collection, storage, calculations, CLI behavior, and UI helpers. |

For more details, see [`docs/architecture.md`](docs/architecture.md).

---

## Database and Privacy

The default database location is:

```text
data/battery.db
```

Battery measurements and derived session information are stored locally in SQLite.

The application:
- Does not upload battery telemetry.
- Does not require an account or login.
- Does not use cloud storage.
- Does not require a runtime network connection.
- Preserves existing databases during supported additive schema migrations.

Database files are excluded from version control.

**Privacy principle:** Your battery history stays on your machine unless you explicitly choose to share it.

---

## Development and Testing

### Install development dependencies

```bash
python -m pip install -e ".[dev]"
```

### Run the test suite

```bash
python -m pytest -v
```

### Run Ruff lint checks

```bash
python -m ruff check .
```

### Verify formatting

```bash
python -m ruff format --check .
```

### Build the package

```bash
python -m pip wheel . --no-deps
```

The test suite uses fixtures and mocks where appropriate. It is designed to avoid requiring a real battery, network access, a graphical display, or modifications to the user's live database.

### Platform Validation

The current development validation includes automated tests for macOS and Windows collector behavior.

Windows runtime validation on an actual Windows host and manual GUI validation should be completed separately before claiming full platform compatibility.

---

## Troubleshooting

### Unsupported operating system

Only macOS and Windows collectors are implemented. Unsupported platforms should report an explicit error rather than save fabricated measurements.

### macOS collection fails

Check whether the native battery command works:

```bash
pmset -g batt
```

If it fails, investigate the operating-system environment before retrying the application.

### The dashboard displays stale data

Start the monitor in a separate terminal:

```bash
battery-analyzer monitor --interval 60
```

The dashboard displays collected data and cannot refresh historical measurements that have not been recorded.

### Battery health is unavailable

The operating system or hardware may not provide valid full-charge and design-capacity measurements.

This is an expected limitation on some devices.

### Tkinter is unavailable

Install a Python distribution that includes Tkinter support.

On macOS, ensure the selected Python installation includes the required Tk components. Recreate the virtual environment if you switch Python installations.

### The database contains little historical data

The application requires time to collect measurements before meaningful historical comparisons can be made.

Leave monitoring enabled during normal use to build a reliable history.

---

## Limitations

- Available battery telemetry varies by operating system and hardware.
- Windows runtime behavior has not yet been validated on a Windows host in the current development environment.
- The dashboard requires Tkinter and a graphical desktop session.
- Charging-session boundaries and durations depend on observed measurements.
- Battery-health reporting requires valid capacity telemetry.
- Long-term degradation analysis requires sufficient historical capacity measurements.
- No redistribution license has been selected yet.

---

## Roadmap

Potential future improvements include:

- Expanded platform-specific capacity telemetry.
- Additional historical analytics and reporting.
- Data export functionality.
- Improved application packaging and installation.
- More extensive cross-platform runtime testing.

The current scope intentionally excludes cloud synchronization, user accounts, app-level battery attribution, machine-learning attribution, and remote database services.

---

## License

No license has been selected or included yet.

Until a license is added, do not assume that the project is available for redistribution or reuse under an open-source license.

---

**Battery Health Analyzer v1.0.0**

A local-first approach to understanding battery behavior through real measurements and transparent analytics.
