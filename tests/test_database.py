import sqlite3
from pathlib import Path

from telemetry_gateway.database import TelemetryStore
from telemetry_gateway.migrations import migration_001
from telemetry_gateway.models import BootRegistrationInput, TelemetryInput


def telemetry(**overrides) -> TelemetryInput:
    values = {
        "deviceId": "device-01",
        "bootId": "boot-a",
        "sequence": 1,
        "deviceTime": "2026-08-12T09:00:00+00:00",
        "metric": "temperature",
        "value": 21.4,
    }
    values.update(overrides)
    return TelemetryInput.model_validate(values)


def test_registers_a_boot_idempotently() -> None:
    store = TelemetryStore(":memory:")
    try:
        event = BootRegistrationInput(deviceId="device-01", bootId="boot-a")

        first = store.register_boot(event)
        second = store.register_boot(event)

        assert first.to_api() == {
            "deviceId": "device-01",
            "bootId": "boot-a",
            "generation": 1,
            "created": True,
        }
        assert second.to_api() == {
            "deviceId": "device-01",
            "bootId": "boot-a",
            "generation": 1,
            "created": False,
        }
    finally:
        store.close()


def test_stores_a_basic_event_and_calculates_current_state() -> None:
    store = TelemetryStore(":memory:")
    try:
        store.register_boot(BootRegistrationInput(deviceId="device-01", bootId="boot-a"))

        result = store.ingest(telemetry(), "2026-08-12T09:00:01+00:00")

        assert result.duplicate is False
        assert result.current_changed is True
        assert store.list_current_states()[0].to_api() == {
            "deviceId": "device-01",
            "bootId": "boot-a",
            "generation": 1,
            "sequence": 1,
            "deviceTime": "2026-08-12T09:00:00+00:00",
            "receivedAt": "2026-08-12T09:00:01+00:00",
            "metric": "temperature",
            "value": 21.4,
        }
        assert len(store.list_events(10)) == 1
    finally:
        store.close()


def test_repeated_event_from_same_boot_is_a_duplicate() -> None:
    store = TelemetryStore(":memory:")
    try:
        store.register_boot(BootRegistrationInput(deviceId="device-01", bootId="boot-a"))
        store.ingest(telemetry(), "2026-08-12T09:00:01+00:00")

        duplicate = store.ingest(telemetry(), "2026-08-12T09:00:02+00:00")

        assert duplicate.to_api() == {
            "accepted": True,
            "duplicate": True,
            "currentChanged": False,
        }
        assert len(store.list_events(10)) == 1
    finally:
        store.close()


def test_same_sequence_from_different_boots_is_not_a_duplicate() -> None:
    store = TelemetryStore(":memory:")
    try:
        store.register_boot(BootRegistrationInput(deviceId="device-01", bootId="boot-a"))
        store.register_boot(BootRegistrationInput(deviceId="device-01", bootId="boot-b"))
        store.ingest(telemetry(), "2026-08-12T09:00:01+00:00")

        second_boot = store.ingest(
            telemetry(
                bootId="boot-b",
                deviceTime="2026-08-12T09:01:00+00:00",
                value=22.0,
            ),
            "2026-08-12T09:01:01+00:00",
        )

        assert second_boot.duplicate is False
        assert {event.state.boot_id for event in store.list_events(10)} == {
            "boot-a",
            "boot-b",
        }
    finally:
        store.close()


def test_event_identity_migration_preserves_existing_audit_rows(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "telemetry-v1.db"
    connection = sqlite3.connect(database_path)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            """
            CREATE TABLE schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL
            )
            """
        )
        migration_001(connection)
        connection.execute(
            "INSERT INTO schema_migrations (version, applied_at) VALUES (1, datetime('now'))"
        )
        connection.executemany(
            """
            INSERT INTO device_boots
                (device_id, boot_id, generation, registered_at)
            VALUES (?, ?, ?, ?)
            """,
            [
                ("device-01", "boot-a", 1, "2026-08-12T09:00:00+00:00"),
                ("device-01", "boot-b", 2, "2026-08-12T09:01:00+00:00"),
            ],
        )
        connection.execute(
            """
            INSERT INTO telemetry_events
                (id, device_id, boot_id, generation, sequence, device_time,
                 received_at, metric, value)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                41,
                "device-01",
                "boot-a",
                1,
                1,
                "2026-08-12T09:00:00+00:00",
                "2026-08-12T09:00:01+00:00",
                "temperature",
                21.4,
            ),
        )
        connection.commit()
    finally:
        connection.close()

    store = TelemetryStore(str(database_path))
    try:
        second_boot = store.ingest(
            telemetry(
                bootId="boot-b",
                deviceTime="2026-08-12T09:01:00+00:00",
                value=22.0,
            ),
            "2026-08-12T09:01:01+00:00",
        )
        events = store.list_events(10)

        assert second_boot.duplicate is False
        assert len(events) == 2
        assert next(
            event.event_id for event in events if event.state.boot_id == "boot-a"
        ) == 41
    finally:
        store.close()

    connection = sqlite3.connect(database_path)
    try:
        versions = connection.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        ).fetchall()
        assert versions == [(1,), (2,)]
    finally:
        connection.close()
