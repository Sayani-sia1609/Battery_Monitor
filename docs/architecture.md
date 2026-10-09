# Architecture

The application is split into collectors, models, core services, analytics, storage, and UI.

- `collectors/` contains platform-specific OS integrations. Collectors return normalized
  `BatteryData` and never fabricate unavailable values.
- `storage/` owns SQLite initialization, migrations, persistence, and retrieval. Measurement
  timestamps are normalized to timezone-aware UTC before storage.
- `core/` contains monitoring, state-transition session detection, health helpers, and macOS
  launch-agent integration.
- `analytics/` contains drain, summary, and capacity-based health calculations.
- `ui/` contains the Tkinter dashboard. It reads SQLite and does not call OS collectors or start
  a second monitor.

Charging-session duration represents the interval between observed measurements. Missing
observations are not converted into invented boundary timestamps.
