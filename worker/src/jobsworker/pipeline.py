from __future__ import annotations

import logging
from typing import Any

import psycopg
import yaml

from . import db
from .adapters import ADAPTERS
from .config import Settings
from .filters import passes
from .http import PoliteClient
from .models import NormalizedJob, Source
from .normalize import finalize
from .tagger import Tagger, cost_usd, load_pricing, make_tagger
from .taxonomy import Taxonomy, load_taxonomy

log = logging.getLogger(__name__)


def load_sources_file(settings: Settings) -> list[Source]:
    data = yaml.safe_load(settings.sources_path.read_text(encoding="utf-8")) or []
    return [Source(**row) for row in data]


def collect(
    source: Source, http: PoliteClient, settings: Settings, taxonomy: Taxonomy
) -> tuple[int, list[NormalizedJob]]:
    """Steps 1-3 for one source: fetch, pre-filter, normalize. Returns (fetched, kept)."""
    adapter = ADAPTERS[source.type](http, settings)
    raws = adapter.fetch(source)
    kept: dict[str, NormalizedJob] = {}
    for raw in raws:
        job = adapter.normalize(source, raw)
        if job is None:
            continue
        job = finalize(job, taxonomy)
        if passes(job, taxonomy):
            kept[job.external_id] = job
    return len(raws), list(kept.values())


def tag_pending(
    conn: psycopg.Connection, tagger: Tagger, settings: Settings, limit: int | None = None
) -> tuple[int, float, list[dict[str, Any]]]:
    """Step 6: tag active, canonical jobs that have no tags (new, or content changed)."""
    jobs = db.jobs_needing_tags(conn, limit)
    if not jobs:
        return 0, 0.0, []
    log.info("tagging %d jobs with %s", len(jobs), tagger.model)
    outcome = tagger.tag_many(jobs)
    with conn.transaction():
        for t in outcome.tagged:
            db.save_tag(
                conn,
                t.job_id,
                {
                    **t.tag.model_dump(),
                    "model": tagger.model,
                    "prompt_version": _prompt_version(),
                    "input_tokens": t.input_tokens,
                    "output_tokens": t.output_tokens,
                },
            )
    cost = cost_usd(load_pricing(settings.pricing_path), tagger.model, outcome.tagged)
    return len(outcome.tagged), cost, outcome.errors


def _prompt_version() -> str:
    from .tagger import PROMPT_VERSION

    return PROMPT_VERSION


def run(
    settings: Settings,
    conn: psycopg.Connection,
    http: PoliteClient | None = None,
    tagger: Tagger | None = None,
    do_tag: bool = True,
    only: set[str] | None = None,
) -> dict[str, Any]:
    taxonomy = load_taxonomy(settings.taxonomy_path)
    own_http = http is None
    http = http or PoliteClient(settings.user_agent, settings.min_interval_s)
    counts: dict[str, Any] = {
        "fetched": 0, "new": 0, "updated": 0, "deactivated": 0, "tagged": 0,
        "llm_cost_usd": 0.0, "errors": [],
    }
    run_id, _started = db.start_run(conn)
    ok_ids: list[int] = []
    ok_keys: set[str] = set()
    try:
        sources = db.enabled_sources(conn)
        if only:
            sources = [s for s in sources if s.key in only]
        for source in sources:
            # 1-4. one failing source must not stop the run
            try:
                fetched, jobs = collect(source, http, settings, taxonomy)
                result = db.upsert_jobs(conn, source.id, jobs)
            except Exception as exc:  # noqa: BLE001
                log.error("source %s failed: %s", source.key, exc)
                counts["errors"].append(
                    {"source": source.key, "error": f"{type(exc).__name__}: {exc}"[:300]}
                )
                continue
            counts["fetched"] += fetched
            counts["new"] += result.new
            counts["updated"] += result.updated
            ok_ids.append(source.id)
            ok_keys.add(source.key)
            log.info(
                "%s: fetched=%d kept=%d new=%d updated=%d",
                source.key, fetched, len(jobs), result.new, result.updated,
            )

        # 7. deactivate jobs missed by two consecutive runs. A job is only counted as
        # "missed" by a run in which its source was fetched successfully.
        prev = db.previous_run(conn, run_id)
        if prev and not only:
            failed_prev = {e.get("source") for e in prev["errors_json"] if e.get("source")}
            both = [s.id for s in sources if s.key in ok_keys and s.key not in failed_prev]
            counts["deactivated"] = db.deactivate_stale(conn, both, prev["started_at"])

        # 5. cross-source dedupe (after deactivation so a dead row is never canonical)
        db.recompute_duplicates(conn)

        # 6. tag new / changed rows only
        if do_tag:
            try:
                tagger = tagger or make_tagger(settings, taxonomy)
                tagged, cost, errors = tag_pending(conn, tagger, settings)
                counts["tagged"] = tagged
                counts["llm_cost_usd"] = cost
                counts["errors"].extend(errors[:50])
            except Exception as exc:  # noqa: BLE001
                log.error("tagging failed: %s", exc)
                counts["errors"].append(
                    {"stage": "tag", "error": f"{type(exc).__name__}: {exc}"[:300]}
                )
    finally:
        # 8. always record the run, even a broken one
        db.finish_run(conn, run_id, counts)
        if own_http:
            http.close()
    return {"run_id": run_id, **counts, **db.stats(conn)}
