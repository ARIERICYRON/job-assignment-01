from __future__ import annotations

import argparse
import json
import random
import threading
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass
class Device:
    device_id: str
    boot_id: str
    sequence: int
    temperature: float


def post_json(url: str, payload: dict) -> tuple[int, str]:
    request = urllib.request.Request(
        url,
        method="POST",
        headers={"content-type": "application/json"},
        data=json.dumps(payload).encode("utf-8"),
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8")


def register_boot(base_url: str, device: Device) -> None:
    status, body = post_json(
        f"{base_url}/api/boots",
        {"deviceId": device.device_id, "bootId": device.boot_id},
    )
    if status not in (200, 201):
        raise RuntimeError(f"Boot registration failed: {status} {body}")


def send_telemetry(base_url: str, event: dict, mode: str) -> None:
    try:
        status, body = post_json(f"{base_url}/api/telemetry", event)
        print(
            f"{event['deviceId']} {mode} boot={event['bootId'][:8]} "
            f"seq={event['sequence']} value={event['value']} status={status} {body}",
            flush=True,
        )
    except Exception as error:
        print(f"{event['deviceId']} {mode} request failed: {error}", flush=True)


def make_event(device: Device, chaos: bool) -> dict:
    device.sequence += 1
    device.temperature += (random.random() - 0.5) * 0.4

    device_time = datetime.now(timezone.utc)
    if chaos and random.random() < 0.08:
        device_time += timedelta(days=30 if random.random() < 0.5 else -30)

    return {
        "deviceId": device.device_id,
        "bootId": device.boot_id,
        "sequence": device.sequence,
        "deviceTime": device_time.isoformat(),
        "metric": "temperature",
        "value": round(device.temperature, 2),
    }


def run(args: argparse.Namespace) -> None:
    base_url = args.base_url.rstrip("/")
    devices = [
        Device(
            device_id=f"device-{index + 1:02d}",
            boot_id=str(uuid.uuid4()),
            sequence=0,
            temperature=20 + random.random() * 4,
        )
        for index in range(args.devices)
    ]

    for device in devices:
        register_boot(base_url, device)

    print(
        f"Simulator started with {args.devices} device(s), "
        f"interval {args.interval} ms, chaos={args.chaos}.",
        flush=True,
    )

    while True:
        started = time.monotonic()
        for device in devices:
            if args.chaos and random.random() < 0.04:
                device.boot_id = str(uuid.uuid4())
                device.sequence = 0
                register_boot(base_url, device)
                print(
                    f"{device.device_id} restarted with boot {device.boot_id[:8]}",
                    flush=True,
                )

            event = make_event(device, args.chaos)
            if args.chaos and random.random() < 0.12:
                delay = random.uniform(0.5, 3.5)
                timer = threading.Timer(
                    delay, send_telemetry, args=(base_url, event.copy(), "delayed")
                )
                timer.daemon = True
                timer.start()
            else:
                send_telemetry(base_url, event, "normal")

            if args.chaos and random.random() < 0.12:
                send_telemetry(base_url, event.copy(), "duplicate")

        elapsed = time.monotonic() - started
        time.sleep(max(0, args.interval / 1000 - elapsed))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Local telemetry device simulator")
    parser.add_argument("--base-url", default="http://127.0.0.1:3000")
    parser.add_argument("--devices", type=int, default=3)
    parser.add_argument("--interval", type=int, default=1000, help="Milliseconds")
    parser.add_argument("--chaos", action="store_true")
    args = parser.parse_args()
    if args.devices <= 0:
        parser.error("--devices must be positive")
    if args.interval <= 0:
        parser.error("--interval must be positive")
    return args


def main() -> None:
    try:
        run(parse_args())
    except KeyboardInterrupt:
        print("Simulator stopped.")


if __name__ == "__main__":
    main()
