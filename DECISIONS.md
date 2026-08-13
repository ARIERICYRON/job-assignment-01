# Engineering decisions

## Invariants identified

- A boot is identified by `(deviceId, bootId)`. Registering it again returns the
  original server-assigned generation, while a new boot receives a generation
  greater than every earlier boot for that device.
- A telemetry event is identified by `(deviceId, bootId, sequence)`. At-least-once
  redelivery must not create another audit row, change current state, or publish
  another realtime update.
- Raw telemetry is audit history. Accepted rows are retained even when they are
  delayed or cannot become current state.
- Current state is selected per `(deviceId, metric)` by the greatest
  `(generation, sequence)`. `deviceTime` is diagnostic metadata and never an
  ordering input.
- SQLite is the source of truth. Realtime publication occurs only after a
  successful commit and only when authoritative current state changed.
- WebSockets are bounded, non-durable notifications. A slow or broken client
  cannot block ingestion or another client, and the dashboard repairs missed
  notifications from an authoritative snapshot.
- The service, database, simulator, and dashboard remain local-only.

## Incidents fixed

- The original raw-event unique key omitted `bootId`, so sequence numbers reused
  after a restart were incorrectly discarded as duplicates. Migration 2 installs
  the full logical identity and preserves existing event IDs and rows.
- Current-state updates compared `deviceTime`. Clock skew and delayed delivery
  could therefore move state backward. Ingestion now compares generation and
  sequence, and migration 3 rebuilds previously derived current state from audit
  history using the same ordering.
- The service previously published a preview before calling the repository. It
  could publish duplicates, stale events, or writes that later failed. It now
  publishes only the state returned by a completed ingestion transaction.
- The realtime hub awaited each socket in the publication loop. One blocked
  socket delayed healthy clients and ingestion, with no bounded buffering. Each
  client now has an independent sender and bounded queue; overflow and send
  failure remove only that client.
- A client was added to the hub only after WebSocket acceptance, leaving a window
  in which an update could be absent from both its reconnect snapshot and its
  notification stream. The queue is now registered before acceptance completes.
- The dashboard fetched a snapshot only at startup. It now refreshes after every
  successful connection, retries failed or timed-out snapshots, and reapplies
  newer live updates received while a snapshot is in flight.

## Design choices and trade-offs

- Migration 1 was left unchanged. New behavior is installed by migrations 2 and
  3 so an existing database has an auditable upgrade path. SQLite requires a
  table rebuild to change a unique constraint; the rebuild copies explicit IDs
  and recreates the received-time index inside the migration transaction.
- `current_state` is derived data, so repairing it from `telemetry_events` is
  safer than trying to patch possibly incorrect rows in place. Raw events are not
  deleted during this repair.
- Ingestion uses the exact `ON CONFLICT(device_id, boot_id, sequence)` target.
  This avoids masking unrelated constraint or database failures.
- The default WebSocket queue holds 32 updates per client and is configurable via
  `WS_BUFFER_LIMIT`. Overflow closes the slow client with code 1013; a send error
  closes it with 1011. Sender cancellation and socket close operations have
  bounded waits so application shutdown cannot wait forever on a client.
- Publication is deliberately not backed by an outbox. The database remains
  authoritative, and the reconnect snapshot is the recovery mechanism for a
  missed notification. This keeps the repair within the local assignment scope.
- Dashboard updates that arrive during a snapshot are coalesced in a map by a
  collision-free JSON encoding of `(deviceId, metric)`. This bounds pending data
  to the latest state per key rather than retaining every message. Reapplication
  uses the same generation/sequence ordering as the backend.
- Snapshot requests time out after five seconds and retry after one second while
  realtime is connected. The executable dashboard tests use Node's built-in test
  runner, so no browser-test package or application dependency was added.

## Schema or API compatibility concerns

- Existing HTTP paths, request bodies, response bodies, status codes, and the
  WebSocket message shape are unchanged.
- Existing databases migrate automatically on startup. The event-table rebuild
  can briefly require extra disk space and a write transaction.
- Rows already rejected by the old `(device_id, sequence)` constraint cannot be
  reconstructed because they were never stored. The migration preserves every
  row that still exists.
- `WS_BUFFER_LIMIT` is an optional configuration addition; its default requires
  no deployment change. Node.js is required only to run dashboard behavior tests,
  not to run the gateway or dashboard.

## Remaining risks or incomplete work

- There is no durable transaction-to-WebSocket outbox. A process failure after a
  commit but before enqueue can omit a live notification; reconnect snapshots
  recover current state as required, but not the missed notification itself.
- Migrations assume the shipped single-process local runtime. Concurrent startup
  by multiple gateway processes is not a supported or tested deployment mode.
- Very large future audit tables would make the table rebuild and current-state
  recomputation slower. The assignment's local SQLite scale was prioritized over
  an online migration strategy.
- Socket close is best-effort after its bounded timeout. The client is removed
  from the hub immediately, so it cannot continue consuming buffer capacity or
  block healthy clients even if the underlying close stalls.
