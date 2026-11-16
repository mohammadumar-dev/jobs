from __future__ import annotations

import json
import tempfile
from pathlib import Path

import psycopg
import pytest
from psycopg.rows import dict_row

from jobsworker.config import ROOT, Settings
from jobsworker.taxonomy import load_taxonomy

FIXTURES = Path(__file__).parent / "fixtures"
MIGRATIONS = ROOT.parent / "jobs" / "src" / "main" / "resources" / "db" / "migration"


def fixture(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def settings() -> Settings:
    return Settings(
        adzuna_app_id="test-id", adzuna_app_key="test-key", llm_provider="none",
        min_interval_s=0.0,
    )


@pytest.fixture(scope="session")
def taxonomy(settings):
    return load_taxonomy(settings.taxonomy_path)


@pytest.fixture(scope="session")
def pg_uri():
    """A throwaway Postgres with the real Flyway V1 schema applied."""
    import pgserver

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        server = pgserver.get_server(Path(tmp) / "pg", cleanup_mode="stop")
        uri = server.get_uri()
        with psycopg.connect(uri, autocommit=True) as conn:
            conn.execute((MIGRATIONS / "V1__init.sql").read_text(encoding="utf-8"))
        yield uri
        server.cleanup()


@pytest.fixture()
def conn(pg_uri):
    with psycopg.connect(pg_uri, row_factory=dict_row, autocommit=True) as c:
        c.execute(
            "truncate job_tags, apply_clicks, saved_jobs, jobs, sources, ingest_runs, users "
            "restart identity cascade"
        )
        yield c
