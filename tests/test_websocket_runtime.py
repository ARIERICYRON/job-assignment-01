from __future__ import annotations

import asyncio
import json
import socket
import threading
import time
import tomllib
from pathlib import Path

import uvicorn
import websockets

from telemetry_gateway.api import create_app
from telemetry_gateway.models import DeviceState

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEBSOCKET_DEPENDENCY = "websockets==16.1.1"


def test_install_manifests_include_websocket_transport() -> None:
    project = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text("utf-8"))
    requirements = {
        line.strip()
        for line in (PROJECT_ROOT / "requirements.txt").read_text("utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }

    assert WEBSOCKET_DEPENDENCY in project["project"]["dependencies"]
    assert WEBSOCKET_DEPENDENCY in requirements


def test_uvicorn_serves_realtime_websocket_updates(tmp_path: Path) -> None:
    app = create_app(str(tmp_path / "gateway.db"))
    listening_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listening_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listening_socket.bind(("127.0.0.1", 0))
    port = listening_socket.getsockname()[1]
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host="127.0.0.1",
            port=port,
            lifespan="on",
            log_level="critical",
        )
    )
    thread = threading.Thread(
        target=server.run,
        kwargs={"sockets": [listening_socket]},
        daemon=True,
    )
    thread.start()

    deadline = time.monotonic() + 5
    while not server.started:
        if not thread.is_alive():
            raise AssertionError("Uvicorn stopped before startup completed")
        if time.monotonic() >= deadline:
            raise AssertionError("Uvicorn did not start within five seconds")
        time.sleep(0.01)

    async def receive_update() -> dict:
        async with websockets.connect(
            f"ws://127.0.0.1:{port}/ws",
            open_timeout=2,
            close_timeout=2,
        ) as websocket:
            state = DeviceState(
                device_id="device-01",
                boot_id="boot-a",
                generation=1,
                sequence=1,
                device_time="2026-08-12T09:00:00+00:00",
                received_at="2026-08-12T09:00:01+00:00",
                metric="temperature",
                value=21.4,
            )
            await app.state.hub.publish(state)
            payload = await asyncio.wait_for(websocket.recv(), timeout=2)
            return json.loads(payload)

    try:
        message = asyncio.run(receive_update())
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        listening_socket.close()

    assert not thread.is_alive()
    assert message == {
        "type": "device.state.changed",
        "data": {
            "deviceId": "device-01",
            "bootId": "boot-a",
            "generation": 1,
            "sequence": 1,
            "deviceTime": "2026-08-12T09:00:00+00:00",
            "receivedAt": "2026-08-12T09:00:01+00:00",
            "metric": "temperature",
            "value": 21.4,
        },
    }
