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
from .tagger import Tagger, cost_usd, load_pricing, make_tagger, paid_equivalent_usd
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


TAG_BATCH = 10  # jobs per LLM batch; tags are saved after each one


def tag_pending(
    conn: psycopg.Connection, tagger: Tagger, settings: Settings, limit: int | None = None
) -> tuple[int, float, list[dict[str, Any]], psycopg.Connection]:
    """Step 6: tag active, canonical jobs that have no tags (new, or content changed).

    A real LLM tagger also re-tags rows that only have a rule-based fallback tag.
    Free-tier tagging is slow (minutes per batch), so tags are saved batch by batch
    and the connection is reopened if the database closed it in the meantime.
    Returns the connection in use, which may be a new one.
    """
    upgrade = tagger.model != "heuristic-v1"
    reused = db.reuse_duplicate_tags(conn)
    if reused:
        log.info("reused tags of identical postings for %d jobs (no LLM call)", reused)
    jobs = db.jobs_needing_tags(conn, limit or (settings.llm_max_jobs if upgrade else None), upgrade)
    if not jobs:
        return 0, 0.0, [], conn
    log.info("tagging %d jobs with %s", len(jobs), tagger.model)
    pricing = load_pricing(settings.pricing_path)
    tagged, cost, paid, errors = 0, 0.0, 0.0, []
    tokens_in = tokens_out = fixed = 0
    by_model: dict[str, int] = {}
    for i in range(0, len(jobs), TAG_BATCH):
        outcome = tagger.tag_many(jobs[i : i + TAG_BATCH])
        conn = db.ensure_open(conn, settings.database_url)
        with conn.transaction():
            for t in outcome.tagged:
                db.save_tag(
                    conn,
                    t.job_id,
                    {
                        **t.tag.model_dump(),
                        "model": t.model or tagger.model,
                        "prompt_version": _prompt_version(),
                        "input_tokens": t.input_tokens,
                        "output_tokens": t.output_tokens,
                    },
                )
        tagged += len(outcome.tagged)
        cost += cost_usd(pricing, tagger.model, outcome.tagged)
        paid += paid_equivalent_usd(pricing, outcome.tagged)
        tokens_in += outcome.input_tokens
        tokens_out += outcome.output_tokens
        for t in outcome.tagged:
            by_model[t.model or tagger.model] = by_model.get(t.model or tagger.model, 0) + 1
            if t.fixes:
                fixed += 1
                log.info("guard fixed job %s: %s", t.job_id, ", ".join(t.fixes))
        errors.extend(outcome.errors)
        log.info("tagged %d/%d", tagged, len(jobs))
    log.info("tags by model: %s; %d corrected by guards", by_model, fixed)
    log.info(
        "tokens: %d in, %d out (%.0f/%.0f per job, failed attempts included); spent $%.4f; "
        "at %s list price this would be $%.4f ($%.3f per 1,000 jobs)",
        tokens_in, tokens_out, tokens_in / max(tagged, 1), tokens_out / max(tagged, 1), cost,
        pricing.get("reference_model"), paid, paid / max(tagged, 1) * 1000,
    )
    return tagged, cost, errors, conn


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
    original_conn = conn
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
                # a slow source can take minutes; Neon may have closed the idle connection
                conn = db.ensure_open(conn, settings.database_url)
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
        conn = db.ensure_open(conn, settings.database_url)
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
                tagged, cost, errors, conn = tag_pending(conn, tagger, settings)
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
        conn = db.ensure_open(conn, settings.database_url)
        db.finish_run(conn, run_id, counts)
        if own_http:
            http.close()
    result = {"run_id": run_id, **counts, **db.stats(conn)}
    if conn is not original_conn:
        conn.close()
    return result
