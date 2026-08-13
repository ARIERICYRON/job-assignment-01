import asyncio
from datetime import datetime, timezone

import pytest

from telemetry_gateway.models import (
    BootRegistrationResult,
    DeviceState,
    IngestResult,
    TelemetryInput,
)
from telemetry_gateway.service import TelemetryService


class FakeRepository:
    def __init__(
        self,
        result: IngestResult,
        preview: DeviceState,
        calls: list[str],
        error: Exception | None = None,
    ) -> None:
        self.result = result
        self.preview = preview
        self.calls = calls
        self.error = error
        self.ingest_calls = 0

    def register_boot(self, _event):
        return BootRegistrationResult("device-01", "boot-a", 1, True)

    def preview_state(self, _event, _received_at):
        return self.preview

    def ingest(self, _event, _received_at):
        self.calls.append("ingest")
        self.ingest_calls += 1
        if self.error is not None:
            raise self.error
        return self.result

    def list_current_states(self):
        return []

    def list_events(self, _limit):
        return []

    def ping(self):
        return True


class RecordingPublisher:
    def __init__(self, calls: list[str]) -> None:
        self.states: list[DeviceState] = []
        self.calls = calls

    async def publish(self, state: DeviceState) -> None:
        self.calls.append("publish")
        self.states.append(state)


def event() -> TelemetryInput:
    return TelemetryInput.model_validate(
        {
            "deviceId": "device-01",
            "bootId": "boot-a",
            "sequence": 1,
            "deviceTime": "2026-08-12T09:00:00Z",
            "metric": "temperature",
            "value": 21.4,
        }
    )


def state(value: float = 21.4) -> DeviceState:
    return DeviceState(
        device_id="device-01",
        boot_id="boot-a",
        generation=1,
        sequence=1,
        device_time="2026-08-12T09:00:00+00:00",
        received_at="2026-08-12T09:00:01+00:00",
        metric="temperature",
        value=value,
    )


def service_for(
    repository: FakeRepository,
    publisher: RecordingPublisher,
) -> TelemetryService:
    return TelemetryService(
        repository,
        publisher,
        now=lambda: datetime(2026, 8, 12, 9, 0, 1, tzinfo=timezone.utc),
    )


def test_service_publishes_committed_state_after_ingestion() -> None:
    calls: list[str] = []
    committed_state = state()
    repository = FakeRepository(
        result=IngestResult(False, True, committed_state),
        preview=state(value=-1.0),
        calls=calls,
    )
    publisher = RecordingPublisher(calls)
    service = TelemetryService(
        repository,
        publisher,
        now=lambda: datetime(2026, 8, 12, 9, 0, 1, tzinfo=timezone.utc),
    )

    result = asyncio.run(service.ingest(event()))

    assert result.current_changed is True
    assert publisher.states == [committed_state]
    assert calls == ["ingest", "publish"]
    assert repository.ingest_calls == 1


@pytest.mark.parametrize(
    "result",
    [
        pytest.param(IngestResult(True, False), id="duplicate"),
        pytest.param(IngestResult(False, False), id="stale"),
    ],
)
def test_service_does_not_publish_when_current_state_did_not_change(
    result: IngestResult,
) -> None:
    calls: list[str] = []
    repository = FakeRepository(result=result, preview=state(), calls=calls)
    publisher = RecordingPublisher(calls)

    returned = asyncio.run(service_for(repository, publisher).ingest(event()))

    assert returned is result
    assert publisher.states == []
    assert calls == ["ingest"]


def test_service_does_not_publish_when_repository_ingestion_fails() -> None:
    calls: list[str] = []
    failure = RuntimeError("database write failed")
    repository = FakeRepository(
        result=IngestResult(False, True, state()),
        preview=state(),
        calls=calls,
        error=failure,
    )
    publisher = RecordingPublisher(calls)

    with pytest.raises(RuntimeError, match="database write failed"):
        asyncio.run(service_for(repository, publisher).ingest(event()))

    assert publisher.states == []
    assert calls == ["ingest"]
