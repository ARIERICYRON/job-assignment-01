# Device protocol contract

This document is normative. Code that conflicts with this document is defective.

## Boot registration

A device creates a new opaque `bootId` every time its process starts.

Before telemetry is accepted for that boot, the device calls:

```http
POST /api/boots
Content-Type: application/json
```

```json
{
  "deviceId": "device-17",
  "bootId": "c5a8f8f8-4f4f-44be-9153-e968fb0cbc52"
}
```

The backend assigns a monotonically increasing server-side `generation` for each device.

Rules:

- Registering the same `(deviceId, bootId)` more than once is idempotent.
- A duplicate registration returns the original generation.
- A newly accepted boot receives a generation greater than all earlier boots for that device.
- `bootId` is opaque. Its text has no ordering meaning.
- Telemetry for an unregistered boot is rejected with `409 unknown_boot`.

## Telemetry event

```http
POST /api/telemetry
Content-Type: application/json
```

```json
{
  "deviceId": "device-17",
  "bootId": "c5a8f8f8-4f4f-44be-9153-e968fb0cbc52",
  "sequence": 12,
  "deviceTime": "2026-08-12T09:00:00.000Z",
  "metric": "temperature",
  "value": 21.4
}
```

Rules:

- The transport is at-least-once. The same logical event can arrive many times.
- Requests can be delayed and can arrive out of order.
- `sequence` starts at `1` for each boot and increases for every telemetry event from that device process.
- One sequence number identifies one event. A device does not use the same sequence for two metrics.
- The logical event identity is `(deviceId, bootId, sequence)`.
- The raw audit table contains at most one row for each logical event.
- A duplicate request returns success and reports that it was a duplicate.
- A duplicate does not change current state and does not produce a realtime state-change message.

## Current-state ordering

Current state is stored per `(deviceId, metric)`.

To compare two accepted events for the same device and metric:

1. The event with the higher server-assigned boot generation is newer.
2. If the generation is equal, the event with the higher sequence is newer.
3. If both are equal, the events are the same logical event.

`deviceTime` is diagnostic metadata only. Device clocks can be early, late, or far in the future. Do not use `deviceTime` to decide current state.

An event from an older boot remains in raw history but must not replace current state from a newer boot.
