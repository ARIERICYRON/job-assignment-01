# Take-home assignment: repair an environmental telemetry gateway

## Time box

Spend no more than three hours.

A focused partial solution with clear risk analysis is better than a large rewrite that you cannot explain.

## Submission

1. Fork this repository.
2. Work in your fork.
3. Send the repository URL and final commit SHA.
4. Keep normal, understandable Git commits.
5. Complete `DECISIONS.md` and `AI_USAGE.md`.

Do not deploy the application. Everything must run locally.

## Background

Remote environmental sensors send temperature readings to a local gateway. The gateway stores an audit history, calculates current sensor state, and publishes state changes to a browser dashboard.

The basic path works. Production-style testing found failures under duplicate delivery, device restart, message reordering, database failure, and slow or reconnecting WebSocket clients.

## Required outcomes

Repair the system so that it follows the protocol and runtime contracts in `docs/`.

Your solution must address these areas:

### 1. Event identity and device restart

A repeated event must be idempotent. A valid event from a new registered boot must not be mistaken for an event from an older boot.

### 2. Current-state ordering

A delayed event must not move current state backward. An incorrect device clock must not block later valid readings.

### 3. Transaction and publication boundary

The dashboard must not receive a successful state update when the database transaction fails. Duplicate or stale events must not produce false state-change messages.

### 4. Realtime client safety

One slow WebSocket client must not create unbounded server memory use or block healthy clients. A reconnecting dashboard must recover the authoritative current state.

## Engineering constraints

- Keep the repository runnable on one local machine.
- Do not add cloud services or paid dependencies.
- Do not replace the full application or framework.
- Preserve the raw telemetry audit history.
- Do not solve data problems by deleting the local database on every start.
- Keep API behavior compatible unless a change is necessary and documented.
- Add tests that prove the behavior you changed.
- You may change the schema, service boundaries, API implementation, and frontend logic.

## Expected deliverables

### Code

A working implementation with focused tests.

### `DECISIONS.md`

Describe:

- The invariants you identified
- The incidents you fixed
- Important design choices and trade-offs
- Any schema or API compatibility concerns
- Remaining risks or incomplete work

### `AI_USAGE.md`

Describe:

- AI tools used
- Important prompts or prompt summaries
- Incorrect or unsuitable AI output you rejected
- How you verified generated changes

AI use is allowed. You are responsible for every submitted change.

## Evaluation

The evaluation is behavior-based. There is no required internal architecture.

We will assess:

- System and data-model reasoning
- Correctness under failure and reordering
- Tests and debugging method
- Scope control and maintainability
- Risk prioritization
- Ability to direct and verify AI-generated work
