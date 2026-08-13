from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Protocol

from fastapi import WebSocket

from telemetry_gateway.models import DeviceState

Message = dict[str, object]


class StatePublisher(Protocol):
    async def publish(self, state: DeviceState) -> None: ...


@dataclass
class _Client:
    websocket: WebSocket
    queue: asyncio.Queue[Message]
    sender: asyncio.Task[None] | None = None


class RealtimeHub:
    def __init__(self, buffer_limit: int = 32, close_timeout: float = 1.0) -> None:
        if buffer_limit < 1:
            raise ValueError("buffer_limit must be at least 1")
        if close_timeout <= 0:
            raise ValueError("close_timeout must be positive")

        self._buffer_limit = buffer_limit
        self._close_timeout = close_timeout
        self._clients: dict[WebSocket, _Client] = {}
        self._tasks: set[asyncio.Task[object]] = set()
        self._closing = False

    async def connect(self, websocket: WebSocket) -> None:
        if self._closing:
            await self._safe_close(websocket, 1012)
            return

        client = _Client(
            websocket=websocket,
            queue=asyncio.Queue(maxsize=self._buffer_limit),
        )
        self._clients[websocket] = client
        try:
            await websocket.accept()
        except BaseException:
            self._discard(client)
            raise

        if self._clients.get(websocket) is not client:
            return

        sender = asyncio.create_task(self._send_messages(client))
        client.sender = sender
        self._track(sender)

    async def disconnect(self, websocket: WebSocket) -> None:
        client = self._clients.pop(websocket, None)
        if client is not None:
            await self._stop_sender(client)

    async def publish(self, state: DeviceState) -> None:
        message: Message = {
            "type": "device.state.changed",
            "data": state.to_api(),
        }
        for client in tuple(self._clients.values()):
            try:
                client.queue.put_nowait(message)
            except asyncio.QueueFull:
                if self._discard(client):
                    self._schedule_cleanup(client, 1013)

    async def close(self) -> None:
        self._closing = True
        clients = tuple(self._clients.values())
        self._clients.clear()
        cleanups = [self._schedule_cleanup(client, 1001) for client in clients]
        if cleanups:
            await asyncio.gather(*cleanups, return_exceptions=True)
        await self._drain_tasks()

    async def _send_messages(self, client: _Client) -> None:
        try:
            while True:
                message = await client.queue.get()
                await client.websocket.send_json(message)
        except asyncio.CancelledError:
            raise
        except Exception:
            if self._discard(client):
                await self._safe_close(client.websocket, 1011)

    def _discard(self, client: _Client) -> bool:
        if self._clients.get(client.websocket) is not client:
            return False
        del self._clients[client.websocket]
        return True

    def _schedule_cleanup(
        self, client: _Client, close_code: int
    ) -> asyncio.Task[None]:
        task = asyncio.create_task(self._cleanup(client, close_code))
        self._track(task)
        return task

    async def _cleanup(self, client: _Client, close_code: int) -> None:
        await self._stop_sender(client)
        await self._safe_close(client.websocket, close_code)

    async def _stop_sender(self, client: _Client) -> None:
        sender = client.sender
        if sender is None or sender.done() or sender is asyncio.current_task():
            return
        sender.cancel()
        done, _ = await asyncio.wait({sender}, timeout=self._close_timeout)
        for task in done:
            self._consume_exception(task)

    async def _safe_close(self, websocket: WebSocket, code: int) -> None:
        close_task = asyncio.create_task(websocket.close(code=code))
        self._track(close_task)
        try:
            done, pending = await asyncio.wait(
                {close_task}, timeout=self._close_timeout
            )
        except asyncio.CancelledError:
            close_task.cancel()
            raise
        for task in pending:
            task.cancel()
        for task in done:
            self._consume_exception(task)

    async def _drain_tasks(self) -> None:
        current = asyncio.current_task()
        pending = {task for task in self._tasks if task is not current}
        if not pending:
            return

        done, pending = await asyncio.wait(pending, timeout=self._close_timeout)
        for task in pending:
            task.cancel()
        if pending:
            finished, _ = await asyncio.wait(pending, timeout=self._close_timeout)
            done.update(finished)
        for task in done:
            self._consume_exception(task)

    def _track(self, task: asyncio.Task[object]) -> None:
        self._tasks.add(task)
        task.add_done_callback(self._task_finished)

    def _task_finished(self, task: asyncio.Task[object]) -> None:
        self._tasks.discard(task)
        self._consume_exception(task)

    @staticmethod
    def _consume_exception(task: asyncio.Task[object]) -> None:
        if not task.cancelled():
            task.exception()

    @property
    def size(self) -> int:
        return len(self._clients)
