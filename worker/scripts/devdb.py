"""Local Postgres for development without Docker.

    uv run python scripts/devdb.py            # start (data in ../.pgdata), Ctrl-C to stop

Uses the Postgres binaries bundled with the `pgserver` dev dependency. Trust auth,
localhost only: never use this for anything but local development. The schema is
created by the API's Flyway migrations: start the API once before running the worker.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

import pgserver

DATA = Path(__file__).resolve().parents[2] / ".pgdata"


def main() -> int:
    DATA.mkdir(exist_ok=True)
    server = pgserver.get_server(DATA, cleanup_mode="stop")
    uri = server.get_uri()
    parts = urlsplit(uri)
    jdbc = f"jdbc:postgresql://{parts.hostname}:{parts.port}{parts.path}"
    (DATA / "url.txt").write_text(f"{uri}\n{jdbc}\n", encoding="utf-8")
    print(f"DATABASE_URL={uri}")
    print(f"SPRING_DATASOURCE_URL={jdbc}")
    print("SPRING_DATASOURCE_USERNAME=postgres")
    print("running; Ctrl-C to stop", flush=True)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass
    finally:
        server.cleanup()
    return 0


if __name__ == "__main__":
    sys.exit(main())
