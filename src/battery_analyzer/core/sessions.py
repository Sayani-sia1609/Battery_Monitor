"""Battery session tracking and charging-session reconstruction."""

from battery_analyzer.models.battery_data import BatteryData, BatterySession, ChargingSession


def start_session(data: BatteryData) -> BatterySession:
    return BatterySession(
        started_at=data.timestamp,
        start_percent=data.charge_percent,
        is_charging=data.is_charging,
    )


def end_session(session: BatterySession, data: BatteryData) -> BatterySession:
    return session.model_copy(
        update={"ended_at": data.timestamp, "end_percent": data.charge_percent}
    )


def detect_discharge_sessions(measurements: list[BatteryData]) -> list[BatterySession]:
    """Build completed discharge sessions from chronologically ordered readings."""
    return [session for session in detect_sessions(measurements) if not session.is_charging]


def detect_active_session(measurements: list[BatteryData]) -> BatterySession | None:
    """Return the current contiguous session, if at least one reading exists."""
    active: BatterySession | None = None

    for measurement in sorted(measurements, key=lambda item: item.timestamp):
        if active is None or measurement.is_charging != active.is_charging:
            active = start_session(measurement)

    return active


def detect_sessions(measurements: list[BatteryData]) -> list[BatterySession]:
    """Build completed contiguous charging and discharging sessions."""
    sessions: list[BatterySession] = []
    active: BatterySession | None = None

    for measurement in sorted(measurements, key=lambda item: item.timestamp):
        if active is None:
            active = start_session(measurement)
            continue

        if measurement.is_charging != active.is_charging:
            sessions.append(end_session(active, measurement))
            active = start_session(measurement)

    return sessions


class ChargingSessionDetector:
    """Reconstruct completed charging sessions from raw measurements."""

    def detect(self, measurements: list[BatteryData]) -> list[ChargingSession]:
        """Return sessions bounded by observed charging state transitions."""
        sessions: list[ChargingSession] = []
        active: list[BatteryData] = []

        for measurement in self._deduplicate(measurements):
            if measurement.is_charging:
                active.append(measurement)
            elif active:
                sessions.append(self._build_session(active, measurement))
                active = []

        return sessions

    @staticmethod
    def _deduplicate(measurements: list[BatteryData]) -> list[BatteryData]:
        """Sort readings and keep the last reading for each timestamp."""
        return list(
            {
                measurement.timestamp: measurement
                for measurement in sorted(measurements, key=lambda item: item.timestamp)
            }.values()
        )

    @staticmethod
    def _build_session(
        charging_measurements: list[BatteryData],
        ending_measurement: BatteryData,
    ) -> ChargingSession:
        start = charging_measurements[0]
        reached_100 = (
            any(measurement.charge_percent >= 100 for measurement in charging_measurements)
            or ending_measurement.charge_percent >= 100
        )
        return ChargingSession(
            started_at=start.timestamp,
            ended_at=ending_measurement.timestamp,
            start_percent=start.charge_percent,
            end_percent=ending_measurement.charge_percent,
            reached_100=reached_100,
            status="completed" if reached_100 else "interrupted",
        )
