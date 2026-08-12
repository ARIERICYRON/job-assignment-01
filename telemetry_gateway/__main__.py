from __future__ import annotations

import os

import uvicorn

from telemetry_gateway.api import create_app


def main() -> None:
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "3000"))
    database_path = os.environ.get("DATA_FILE", "data/telemetry.db")
    uvicorn.run(create_app(database_path), host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
