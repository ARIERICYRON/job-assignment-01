from __future__ import annotations

import os

import uvicorn

from telemetry_gateway.api import create_app


def main() -> None:
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "3000"))
    database_path = os.environ.get("DATA_FILE", "data/telemetry.db")
    ws_buffer_limit = int(os.environ.get("WS_BUFFER_LIMIT", "32"))
    uvicorn.run(
        create_app(database_path, ws_buffer_limit=ws_buffer_limit),
        host=host,
        port=port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
