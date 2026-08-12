# job-assignment-01

A local device-to-dashboard telemetry system used for a full-stack engineering take-home assignment.

The repository contains:

- A Python FastAPI HTTP and WebSocket service
- A local SQLite database with versioned migrations
- A browser dashboard served by the application
- A configurable local device simulator
- Unit and API tests

No cloud account, paid API, remote database, deployment, or physical device is required. After dependencies are installed, all runtime work is local.

## Requirements

- Python 3.11 or newer

## Install

Linux and macOS:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
```

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Run the application

```bash
python -m telemetry_gateway
```

Open `http://127.0.0.1:3000`.

## Run the simulator

In another terminal:

```bash
python simulator.py --devices 4
```

Use chaos mode to introduce duplicates, delayed events, restarts, and clock skew:

```bash
python simulator.py --devices 4 --chaos
```

## Run all local checks

```bash
./scripts/check.sh
```

The equivalent cross-platform commands are:

```bash
python -m compileall -q telemetry_gateway simulator.py tests
python -m pytest
```

The included tests cover the basic path. Passing them does not prove that the production incidents in [TASK.md](TASK.md) are fixed.

## Assignment

Read these files before editing code:

1. [TASK.md](TASK.md)
2. [docs/protocol.md](docs/protocol.md)
3. [docs/runtime-contract.md](docs/runtime-contract.md)
4. [docs/api.md](docs/api.md)

## Local endpoints

- Application and dashboard: `http://127.0.0.1:3000`
- WebSocket: `ws://127.0.0.1:3000/ws`
- Liveness: `http://127.0.0.1:3000/health/live`
- Readiness: `http://127.0.0.1:3000/health/ready`
