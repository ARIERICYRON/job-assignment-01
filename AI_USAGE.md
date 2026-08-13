# AI usage record

## Tools used

- OpenAI Codex desktop coding agent was used to inspect the repository, explain
  findings, edit files, run tests, and manage the local Git workflow.
- Codex terminal and patch tools were used for read-only inspection, focused file
  edits, Python/Node test execution, Git commits, and branch pushes.
- Codex browser control was used with my authenticated GitHub session to create
  the pull requests. GitHub CLI authentication was checked first but was not
  configured. I reviewed the later pull requests from my phone and merged them.
- Additional Codex review agents performed read-only audits of the database
  migrations, realtime task lifecycle, dashboard races, test coverage, packaging,
  and final deliverables. Their findings were verified locally before changes
  were accepted.

## Important prompts or prompt summaries

- Read all assignment instructions and the normative protocol, runtime, and API
  documents before changing code. Preserve audit history, keep the API compatible,
  and remain local-only.
- Fork and detach the repository first, work from `main`, make small explainable
  commits, open focused pull requests, and let me review/merge from my phone.
- Reproduce logical-event identity failures across device boots and design an
  additive SQLite migration that preserves existing audit rows and IDs.
- Test current-state ordering under duplicate delivery, restarts, delayed events,
  out-of-order sequences, and incorrect device clocks; use server generation and
  sequence rather than `deviceTime`.
- Verify the transaction boundary so failed, duplicate, or stale writes cannot
  produce a successful realtime update.
- Design bounded per-client WebSocket delivery so a blocked or broken client
  cannot delay healthy clients, leak tasks, or hang shutdown.
- Execute the real dashboard JavaScript and test startup, reconnect, failed or
  hung snapshots, and snapshot-versus-WebSocket races.
- Perform independent final audits against all six required outcomes, the install
  manifests, documentation deliverables, and the submission workflow.

## Generated output rejected or corrected

- The first implementation work was started before the required fork/read-first
  workflow was established. I rejected that workflow. Codex preserved the work in
  a recovery stash and restored a clean starter tree. I detached the fork and
  renamed its default branch to `main` from my phone; Codex verified those changes,
  configured my repository as `origin`, disabled pushes to the starter remote,
  and rebuilt the fixes step by step through focused branches and PRs.
- A database-test edit initially placed part of the version-1 migration assertion
  under the wrong test. The focused failure exposed it; the test structure was
  corrected before the ordering commit.
- The first dashboard reconnect draft handled overlapping rejected requests but
  not a request that never resolved or a standalone reconnect failure. Review
  also found a collision in colon-delimited device/metric keys and a dashboard
  test that could silently skip without Node. These suggestions were rejected as
  incomplete. The final code adds abort-based timeout/retry, JSON tuple keys, a
  declared test-only Node requirement, and executable tests for each case.
- One JavaScript test fixture created an already-rejected promise, causing an
  unhandled-rejection failure unrelated to application behavior. The fixture was
  changed to reject only after the dashboard began consuming the request.
- The final audit found that the populated development environment contained
  `websockets`, but neither install manifest declared it. The green local tests
  had masked a clean-install failure. An explicit pinned runtime dependency plus
  a real Uvicorn WebSocket upgrade test was added before submission.
- AI review suggestions were not applied blindly. Findings were reproduced with
  focused tests or direct inspection, and non-blocking risks such as concurrent
  multi-process migration startup were documented rather than expanding the
  assignment into a distributed-system rewrite.

## Verification performed

- Used red/green testing for each incident: new focused tests were first run
  against the defective behavior, then rerun after the smallest implementation
  change.
- Database tests cover boot-registration idempotency, same-boot duplicates,
  cross-boot sequence reuse, clock skew, sequence reordering, delayed older boots,
  versioned migration, audit-row/ID preservation, and derived-state rebuilding.
- Service tests record call order and prove publication uses committed state only,
  while duplicate, stale, and failed ingestions publish nothing.
- Realtime tests use blocked, overflowing, and failing fake sockets to prove
  client isolation, bounded queues, close behavior, and pre-accept buffering.
- Dashboard tests execute the shipped `app.js` with Node's built-in test runner.
  Six scenarios cover startup/reconnect refreshes, failed and hung snapshots,
  overlapping refreshes, identifier collisions, and live-update reapplication.
- A runtime integration test starts a real Uvicorn server, completes an actual
  `/ws` upgrade, publishes a state change, and receives the expected JSON message.
- Final local checks completed successfully: `pytest` reported 24 passing tests;
  the direct Node suite reported 6 passing scenarios; `compileall`, `pip check`,
  and `git diff --check` passed.
- Git status and branch comparisons were checked before every commit and PR. The
  fork was verified as detached, the starter remote was fetch-only, and each
  implementation PR contained only its explained commit or commits before merge.
