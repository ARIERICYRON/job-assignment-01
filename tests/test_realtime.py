import asyncio
from collections.abc import Callable

from telemetry_gateway.models import DeviceState
from telemetry_gateway.realtime import RealtimeHub


class FakeWebSocket:
    def __init__(
        self,
        *,
        accept_gate: asyncio.Event | None = None,
        send_gate: asyncio.Event | None = None,
        fail_send: bool = False,
    ) -> None:
        self.accept_gate = accept_gate
        self.send_gate = send_gate
        self.fail_send = fail_send
        self.accept_started = asyncio.Event()
        self.send_started = asyncio.Event()
        self.accepted = False
        self.send_attempts = 0
        self.sent: list[dict] = []
        self.close_codes: list[int] = []

    async def accept(self) -> None:
        self.accept_started.set()
        if self.accept_gate is not None:
            await self.accept_gate.wait()
        self.accepted = True

    async def send_json(self, message: dict) -> None:
        self.send_attempts += 1
        self.send_started.set()
        if self.fail_send:
            raise RuntimeError("socket write failed")
        if self.send_gate is not None:
            await self.send_gate.wait()
        self.sent.append(message)

    async def close(self, code: int = 1000, reason: str | None = None) -> None:
        del reason
        self.close_codes.append(code)


def state(sequence: int = 1) -> DeviceState:
    return DeviceState(
        device_id="device-01",
        boot_id="boot-a",
        generation=1,
        sequence=sequence,
        device_time=f"2026-08-12T09:00:{sequence:02d}+00:00",
        received_at=f"2026-08-12T09:01:{sequence:02d}+00:00",
        metric="temperature",
        value=20.0 + sequence,
    )


async def wait_until(condition: Callable[[], bool]) -> None:
    for _ in range(100):
        if condition():
            return
        await asyncio.sleep(0)
    raise AssertionError("condition did not become true")


def test_slow_client_does_not_block_fast_client_or_publisher() -> None:
    async def scenario() -> None:
        hub = RealtimeHub()
        slow_gate = asyncio.Event()
        slow = FakeWebSocket(send_gate=slow_gate)
        fast = FakeWebSocket()
        publish_task: asyncio.Task[None] | None = None

        await hub.connect(slow)  # type: ignore[arg-type]
        await hub.connect(fast)  # type: ignore[arg-type]
        try:
            publish_task = asyncio.create_task(hub.publish(state()))
            await slow.send_started.wait()
            await wait_until(lambda: len(fast.sent) == 1)

            assert publish_task.done()
            assert fast.sent == [
                {"type": "device.state.changed", "data": state().to_api()}
            ]
        finally:
            slow_gate.set()
            if publish_task is not None:
                await publish_task
            close = getattr(hub, "close", None)
            if close is not None:
                await close()

    asyncio.run(scenario())


def test_overflowing_client_is_disconnected_at_buffer_limit() -> None:
    async def scenario() -> None:
        hub = RealtimeHub(buffer_limit=1)
        send_gate = asyncio.Event()
        client = FakeWebSocket(send_gate=send_gate)

        await hub.connect(client)  # type: ignore[arg-type]
        await hub.publish(state(1))
        await client.send_started.wait()
        await hub.publish(state(2))
        await hub.publish(state(3))
        await wait_until(lambda: bool(client.close_codes))

        assert hub.size == 0
        assert client.close_codes == [1013]
        send_gate.set()
        await hub.close()

    asyncio.run(scenario())


def test_broken_client_is_closed_without_affecting_healthy_client() -> None:
    async def scenario() -> None:
        hub = RealtimeHub()
        broken = FakeWebSocket(fail_send=True)
        healthy = FakeWebSocket()

        await hub.connect(broken)  # type: ignore[arg-type]
        await hub.connect(healthy)  # type: ignore[arg-type]
        await hub.publish(state(1))
        await wait_until(
            lambda: len(healthy.sent) == 1 and bool(broken.close_codes)
        )

        assert hub.size == 1
        assert broken.close_codes == [1011]

        await hub.publish(state(2))
        await wait_until(lambda: len(healthy.sent) == 2)
        assert broken.send_attempts == 1
        await hub.close()

    asyncio.run(scenario())


def test_client_is_registered_before_acceptance_completes() -> None:
    async def scenario() -> None:
        hub = RealtimeHub()
        accept_gate = asyncio.Event()
        client = FakeWebSocket(accept_gate=accept_gate)
        connect_task = asyncio.create_task(
            hub.connect(client)  # type: ignore[arg-type]
        )

        await client.accept_started.wait()
        try:
            assert hub.size == 1
            await hub.publish(state())
            assert client.sent == []
        finally:
            accept_gate.set()
            await connect_task

        await wait_until(lambda: len(client.sent) == 1)
        await hub.close()

    asyncio.run(scenario())
