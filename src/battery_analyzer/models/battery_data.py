"""Battery measurement models."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class BatteryData(BaseModel):
    """A point-in-time battery measurement."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    charge_percent: float = Field(ge=0, le=100)
    is_charging: bool
    voltage: float | None = Field(default=None, ge=0)
    current: float | None = None
    temperature_celsius: float | None = None
    energy_full_wh: float | None = Field(default=None, ge=0)
    energy_design_wh: float | None = Field(default=None, ge=0)

    @field_validator("timestamp")
    @classmethod
    def require_timezone_aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)


class BatterySession(BaseModel):
    """A continuous period of battery use or charging."""

    started_at: datetime
    ended_at: datetime | None = None
    start_percent: float = Field(ge=0, le=100)
    end_percent: float | None = Field(default=None, ge=0, le=100)
    is_charging: bool

    @field_validator("started_at", "ended_at")
    @classmethod
    def require_timezone_aware_session_timestamp(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("session timestamps must be timezone-aware")
        return value.astimezone(timezone.utc) if value is not None else None

    @model_validator(mode="after")
    def validate_session_order(self) -> BatterySession:
        if self.ended_at is not None and self.ended_at < self.started_at:
            raise ValueError("ended_at must not be earlier than started_at")
        return self

    @property
    def duration_seconds(self) -> float | None:
        if self.ended_at is None:
            return None
        return (self.ended_at - self.started_at).total_seconds()

    @property
    def percentage_change(self) -> float | None:
        if self.end_percent is None:
            return None
        return self.end_percent - self.start_percent

    @property
    def percentage_drained(self) -> float | None:
        if self.end_percent is None or self.is_charging:
            return None
        return max(0.0, self.start_percent - self.end_percent)


class ChargingSession(BaseModel):
    """An observed period during which the operating system reported charging."""

    id: int | None = None
    started_at: datetime
    ended_at: datetime
    start_percent: float = Field(ge=0, le=100)
    end_percent: float = Field(ge=0, le=100)
    reached_100: bool
    status: Literal["completed", "interrupted"]

    @field_validator("started_at", "ended_at")
    @classmethod
    def require_timezone_aware_charging_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("charging session timestamps must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_charging_session_order(self) -> ChargingSession:
        if self.ended_at < self.started_at:
            raise ValueError("ended_at must not be earlier than started_at")
        return self

    @property
    def duration_seconds(self) -> float:
        return (self.ended_at - self.started_at).total_seconds()
