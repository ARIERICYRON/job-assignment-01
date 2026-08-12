# Runtime contract

This document is normative. Code that conflicts with this document is defective.

## Database and realtime publication

The database is the source of truth.

For each telemetry request:

1. Validate the request.
2. Complete the database transaction.
3. Determine whether authoritative current state changed.
4. Publish a realtime message only after a successful commit and only when current state changed.

A failed transaction must not produce a successful realtime update.

## WebSocket delivery

WebSocket messages are a low-latency notification channel. They are not the source of truth and are not guaranteed to be replayed.

The dashboard must:

- Fetch the current-state snapshot when it starts.
- Fetch the snapshot again after every successful WebSocket reconnection.
- Treat incoming messages as updates to that snapshot.

The server must:

- Isolate clients from each other.
- Keep memory use bounded for a client that cannot receive data fast enough.
- Close or drop a slow client when a configured buffer limit is exceeded.
- Continue serving healthy clients when another client is slow or broken.

The dashboard needs current state. It does not need every raw telemetry event.

## Health endpoints

`GET /health/live` answers whether the process is running. It must not depend on database availability.

`GET /health/ready` answers whether the service can perform database-backed work. It may return a non-200 response when the database is unavailable.

## Runtime scope

All runtime components must execute on the local machine. The application must not depend on a cloud service, hosted database, remote queue, or paid API.
