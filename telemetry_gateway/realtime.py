from __future__ import annotations

from typing import Protocol

from fastapi import WebSocket

from telemetry_gateway.models import DeviceState


class StatePublisher(Protocol):
    async def publish(self, state: DeviceState) -> None: ...


class RealtimeHub:
    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()

    async def connect(self, client: WebSocket) -> None:
        await client.accept()
        self._clients.add(client)

    def disconnect(self, client: WebSocket) -> None:
        self._clients.discard(client)

    async def publish(self, state: DeviceState) -> None:
        message = {"type": "device.state.changed", "data": state.to_api()}
        for client in tuple(self._clients):
            try:
                await client.send_json(message)
            except Exception:
                self._clients.discard(client)

    @property
    def size(self) -> int:
        return len(self._clients)
