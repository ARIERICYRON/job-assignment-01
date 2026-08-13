from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

NODE = shutil.which("node")


def test_dashboard_reconnect_behavior() -> None:
    assert NODE is not None, "Node.js is required for executable dashboard tests"
    script = Path(__file__).with_name("dashboard_reconnect.test.mjs")
    result = subprocess.run(
        [NODE, "--test", str(script)],
        capture_output=True,
        check=False,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stdout + result.stderr
