from __future__ import annotations

import pytest

from jobsworker import db, pipeline
from jobsworker.adapters import ADAPTERS, SourceAdapter
from jobsworker.models import NormalizedJob, RawJob, Source
from jobsworker.tagger import HeuristicTagger

BOARDS: dict[str, list[dict] | Exception] = {}


class FakeAdapter(SourceAdapter):
    def fetch(self, source: Source) -> list[RawJob]:
        board = BOARDS[source.key]
        if isinstance(board, Exception):
            raise board
        return [RawJob(source_key=source.key, external_id=j["id"], payload=j) for j in board]

    def normalize(self, source: Source, raw: RawJob) -> NormalizedJob | None:
        p = raw.payload
        return NormalizedJob(
            external_id=raw.external_id, title=p["title"], company=p.get("company", "Acme"),
            location_raw=p.get("location", "Bengaluru, India"),
            description_text=p.get("desc", "Open to freshers."),
            apply_url=f"https://example.com/{raw.external_id}",
        )


class CountingTagger(HeuristicTagger):
    def __init__(self, taxonomy):
        super().__init__(taxonomy)
        self.calls = 0

    def tag_many(self, jobs):
        self.calls += len(jobs)
        return super().tag_many(jobs)


@pytest.fixture()
def world(conn, settings, taxonomy, monkeypatch):
    monkeypatch.setitem(ADAPTERS, "fake", FakeAdapter)
    BOARDS.clear()
    BOARDS["a"] = [
        {"id": "1", "title": "Software Engineer Intern"},
        {"id": "2", "title": "Graduate Analyst", "location": "Pune"},
        {"id": "3", "title": "Senior Staff Engineer"},  # filtered: senior
        {"id": "4", "title": "Marketing Intern", "location": "Berlin"},  # filtered: not India
    ]
    BOARDS["b"] = [{"id": "x", "title": "Data Intern", "location": "Mumbai"}]
    db.seed_sources(conn, [Source(key="a", type="fake"), Source(key="b", type="fake")])
    tagger = CountingTagger(taxonomy)

    def run(**kw):
        return pipeline.run(settings, conn, http=object(), tagger=tagger, **kw)

    return conn, run, tagger


def count(conn, where="true"):
    return conn.execute(f"select count(*) as n from jobs where {where}").fetchone()["n"]


def test_first_run_stores_only_india_fresher_jobs(world):
    conn, run, tagger = world
    result = run()
    assert result["fetched"] == 5
    assert result["new"] == 3
    assert result["tagged"] == 3
    assert count(conn) == 3
    run_row = conn.execute("select * from ingest_runs").fetchone()
    assert run_row["finished_at"] is not None and run_row["new"] == 3


def test_rerun_creates_no_duplicates_and_tags_nothing(world):
    conn, run, tagger = world
    run()
    calls = tagger.calls
    result = run()
    assert result["new"] == 0 and result["updated"] == 0 and result["tagged"] == 0
    assert count(conn) == 3
    assert tagger.calls == calls  # hash skip: no LLM work on unchanged content


def test_changed_content_is_retagged_once(world):
    conn, run, tagger = world
    run()
    BOARDS["a"][0]["desc"] = "Open to freshers. Stipend revised."
    result = run()
    assert result["updated"] == 1 and result["tagged"] == 1 and result["new"] == 0
    assert count(conn) == 3


def test_cross_source_duplicate_points_at_the_older_row(world):
    conn, run, tagger = world
    run()
    BOARDS["b"].append({"id": "dup", "title": "software engineer - intern", "location": "Bangalore"})
    result = run()
    assert result["new"] == 1
    original = conn.execute("select id from jobs where external_id = '1'").fetchone()["id"]
    dup = conn.execute("select canonical_job_id from jobs where external_id = 'dup'").fetchone()
    assert dup["canonical_job_id"] == original
    assert result["tagged"] == 0  # duplicates are never sent to the tagger
    assert result["active_unique"] == 3 and result["duplicates"] == 1


def test_deactivates_after_two_consecutive_misses_and_reactivates(world):
    conn, run, tagger = world
    run()
    gone = BOARDS["b"].pop()
    assert run()["deactivated"] == 0  # missed once
    assert count(conn, "is_active") == 3
    assert run()["deactivated"] == 1  # missed twice
    assert count(conn, "is_active") == 2
    BOARDS["b"].append(gone)
    run()
    assert count(conn, "is_active") == 3  # back on the board -> active again, no new row
    assert count(conn) == 3


def test_failing_source_does_not_stop_the_run_or_deactivate_its_jobs(world):
    conn, run, tagger = world
    run()
    BOARDS["b"] = RuntimeError("boom")
    for _ in range(3):
        result = run()
    assert result["errors"] == [{"source": "b", "error": "RuntimeError: boom"}]
    assert count(conn, "is_active") == 3  # an outage is not two misses
    assert result["fetched"] == 4  # source a still ran


class FakeLlmTagger(HeuristicTagger):
    """Behaves like an LLM tagger: a non-heuristic model name."""

    model = "gemini/test-model"


def test_llm_tagger_upgrades_rule_based_tags(world, settings, taxonomy):
    conn, run, _ = world
    run()  # everything tagged by the rule-based tagger
    llm = FakeLlmTagger(taxonomy)
    tagged, cost, errors = pipeline.tag_pending(conn, llm, settings)
    assert tagged == 3 and errors == []
    models = {r["model"] for r in conn.execute("select model from job_tags").fetchall()}
    assert models == {"gemini/test-model"}
    # nothing left to do on the next pass
    assert pipeline.tag_pending(conn, llm, settings)[0] == 0
