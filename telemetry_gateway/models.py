from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

IDENTIFIER_PATTERN = r"^[A-Za-z0-9._:-]+$"
Identifier = str


class BootRegistrationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    deviceId: Identifier = Field(min_length=1, max_length=128, pattern=IDENTIFIER_PATTERN)
    bootId: Identifier = Field(min_length=1, max_length=128, pattern=IDENTIFIER_PATTERN)


class TelemetryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    deviceId: Identifier = Field(min_length=1, max_length=128, pattern=IDENTIFIER_PATTERN)
    bootId: Identifier = Field(min_length=1, max_length=128, pattern=IDENTIFIER_PATTERN)
    sequence: int = Field(gt=0, le=9_007_199_254_740_991)
    deviceTime: datetime
    metric: Identifier = Field(min_length=1, max_length=128, pattern=IDENTIFIER_PATTERN)
    value: float

    @field_validator("deviceTime")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("deviceTime must include a UTC offset")
        return value


@dataclass(frozen=True, slots=True)
class BootRegistrationResult:
    device_id: str
    boot_id: str
    generation: int
    created: bool

    def to_api(self) -> dict[str, Any]:
        return {
            "deviceId": self.device_id,
            "bootId": self.boot_id,
            "generation": self.generation,
            "created": self.created,
        }


@dataclass(frozen=True, slots=True)
class DeviceState:
    device_id: str
    boot_id: str
    generation: int
    sequence: int
    device_time: str
    received_at: str
    metric: str
    value: float

    def to_api(self) -> dict[str, Any]:
        return {
            "deviceId": self.device_id,
            "bootId": self.boot_id,
            "generation": self.generation,
            "sequence": self.sequence,
            "deviceTime": self.device_time,
            "receivedAt": self.received_at,
            "metric": self.metric,
            "value": self.value,
        }


@dataclass(frozen=True, slots=True)
class TelemetryEvent:
    event_id: int
    state: DeviceState

    def to_api(self) -> dict[str, Any]:
        return {"id": self.event_id, **self.state.to_api()}


@dataclass(frozen=True, slots=True)
class IngestResult:
    duplicate: bool
    current_changed: bool
    state: DeviceState | None = None

    def to_api(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "accepted": True,
            "duplicate": self.duplicate,
            "currentChanged": self.current_changed,
        }
        if self.state is not None:
            result["state"] = self.state.to_api()
        return result
