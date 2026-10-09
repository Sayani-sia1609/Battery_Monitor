# Battery Health Analyzer 1.0.0

## Highlights

Battery Health Analyzer is a local-first desktop application for monitoring
real battery telemetry, preserving historical measurements, reconstructing
charging sessions, and reviewing battery drain.

## Included in this release

- macOS collection through `pmset -g batt`.
- Windows collection through `GetSystemPowerStatus`.
- SQLite storage under `data/battery.db` by default.
- Background monitoring with configurable intervals and graceful shutdown.
- Charging-session history reconstructed from observed state transitions.
- Percentage-point drain analytics.
- Capacity-based battery health when both capacity values are provided by the OS.
- Native Tkinter dashboard with IST display timestamps and historical charts.

## Known limitations

- Windows collector behavior has been covered by unit tests but not executed on
  a Windows host in this development environment.
- macOS `pmset` exposes less capacity telemetry than some platform-specific APIs;
  health may therefore be unavailable.
- A session duration is based on the first and last observed boundary
  measurements. It does not claim the exact physical plug/unplug time.
- The UI reads the latest stored measurement. It does not start collection.
- Tkinter must be available in the Python installation for the desktop UI.

## Privacy

Telemetry remains local in SQLite. The application does not upload battery data.
