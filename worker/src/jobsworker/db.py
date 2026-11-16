"""All SQL the worker runs. The worker is the only writer to the job tables."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .models import NormalizedJob, Source


def connect(database_url: str) -> psycopg.Connection:
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set")
    # autocommit: every write below is either a single statement or an explicit
    # `conn.transaction()` block, so one source failing can never roll back another.
    return psycopg.connect(database_url, row_factory=dict_row, autocommit=True)


# ---- sources -------------------------------------------------------------

def seed_sources(conn: psycopg.Connection, sources: list[Source]) -> int:
    """Insert or update sources by key. Rows not in the list are left alone."""
    with conn.transaction(), conn.cursor() as cur:
        for s in sources:
            cur.execute(
                """
                insert into sources (key, type, config_json, enabled)
                values (%s, %s, %s, %s)
                on conflict (key) do update
                   set type = excluded.type,
                       config_json = excluded.config_json,
                       enabled = excluded.enabled
                """,
                (s.key, s.type, Jsonb(s.config), s.enabled),
            )
    return len(sources)


def enabled_sources(conn: psycopg.Connection) -> list[Source]:
    rows = conn.execute(
        "select id, key, type, config_json, enabled from sources where enabled order by id"
    ).fetchall()
    return [
        Source(id=r["id"], key=r["key"], type=r["type"], config=r["config_json"], enabled=True)
        for r in rows
    ]


# ---- runs ----------------------------------------------------------------

def start_run(conn: psycopg.Connection) -> tuple[int, datetime]:
    row = conn.execute(
        "insert into ingest_runs default values returning id, started_at"
    ).fetchone()
    return row["id"], row["started_at"]


def previous_run(conn: psycopg.Connection, run_id: int) -> dict[str, Any] | None:
    return conn.execute(
        """
        select id, started_at, errors_json from ingest_runs
         where id < %s and finished_at is not null
         order by id desc limit 1
        """,
        (run_id,),
    ).fetchone()


def finish_run(conn: psycopg.Connection, run_id: int, counts: dict[str, Any]) -> None:
    conn.execute(
        """
        update ingest_runs
           set finished_at = now(), fetched = %s, new = %s, updated = %s,
               deactivated = %s, tagged = %s, llm_cost_usd = %s, errors_json = %s
         where id = %s
        """,
        (
            counts["fetched"], counts["new"], counts["updated"], counts["deactivated"],
            counts["tagged"], counts["llm_cost_usd"], Jsonb(counts["errors"]), run_id,
        ),
    )


# ---- jobs ----------------------------------------------------------------

@dataclass
class UpsertCounts:
    new: int = 0
    updated: int = 0
    unchanged: int = 0


def upsert_jobs(conn: psycopg.Connection, source_id: int, jobs: list[NormalizedJob]) -> UpsertCounts:
    """Upsert one source's jobs in a single transaction.

    A changed content_hash drops the job's tags so step 6 re-tags it; an
    unchanged job only gets last_seen_at bumped (and is reactivated).
    """
    counts = UpsertCounts()
    with conn.transaction(), conn.cursor() as cur:
        cur.execute(
            "select external_id, id, content_hash from jobs where source_id = %s", (source_id,)
        )
        existing = {r["external_id"]: r for r in cur.fetchall()}
        for job in jobs:
            old = existing.get(job.external_id)
            cur.execute(
                """
                insert into jobs (source_id, external_id, title, company, location_raw,
                                  description_text, apply_url, posted_at, content_hash, dedupe_key)
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                on conflict (source_id, external_id) do update
                   set title = excluded.title,
                       company = excluded.company,
                       location_raw = excluded.location_raw,
                       description_text = excluded.description_text,
                       apply_url = excluded.apply_url,
                       posted_at = coalesce(excluded.posted_at, jobs.posted_at),
                       content_hash = excluded.content_hash,
                       dedupe_key = excluded.dedupe_key,
                       last_seen_at = now(),
                       is_active = true
                """,
                (
                    source_id, job.external_id, job.title, job.company, job.location_raw,
                    job.description_text, job.apply_url, job.posted_at, job.content_hash,
                    job.dedupe_key,
                ),
            )
            if old is None:
                counts.new += 1
            elif old["content_hash"] != job.content_hash:
                counts.updated += 1
                cur.execute("delete from job_tags where job_id = %s", (old["id"],))
            else:
                counts.unchanged += 1
    return counts


def recompute_duplicates(conn: psycopg.Connection) -> int:
    """Cross-source dedupe: per dedupe_key keep the oldest active row, point the rest at it."""
    with conn.transaction():
        cur = conn.execute(
            """
            with ranked as (
                select id,
                       first_value(id) over (
                           partition by dedupe_key order by first_seen_at, id
                       ) as keep
                  from jobs where is_active
            )
            update jobs j
               set canonical_job_id = nullif(r.keep, j.id)
              from ranked r
             where r.id = j.id
               and j.canonical_job_id is distinct from nullif(r.keep, j.id)
            """
        )
        conn.execute(
            "update jobs set canonical_job_id = null where not is_active and canonical_job_id is not null"
        )
        return cur.rowcount


def deactivate_stale(
    conn: psycopg.Connection, source_ids: list[int], cutoff: datetime
) -> int:
    """Deactivate jobs of the given sources that were last seen before `cutoff`."""
    with conn.transaction():
        cur = conn.execute(
            """
            update jobs set is_active = false
             where is_active and source_id = any(%s) and last_seen_at < %s
            """,
            (source_ids, cutoff),
        )
        n = cur.rowcount
        cur = conn.execute(
            """
            update jobs set is_active = false
             where is_active and source_id in (select id from sources where not enabled)
            """
        )
        return n + cur.rowcount


def jobs_needing_tags(conn: psycopg.Connection, limit: int | None = None) -> list[dict[str, Any]]:
    sql = """
        select j.id, j.title, j.company, j.location_raw, j.description_text
          from jobs j left join job_tags t on t.job_id = j.id
         where j.is_active and j.canonical_job_id is null and t.job_id is null
         order by j.first_seen_at, j.id
    """
    if limit:
        sql += f" limit {int(limit)}"
    return conn.execute(sql).fetchall()


def save_tag(conn: psycopg.Connection, job_id: Any, tag: dict[str, Any]) -> None:
    conn.execute(
        """
        insert into job_tags (job_id, role_category, role_title_clean, city, state, work_mode,
                              job_type, experience_min, experience_max, is_fresher, model,
                              prompt_version, input_tokens, output_tokens, tagged_at)
        values (%(job_id)s, %(role_category)s, %(role_title_clean)s, %(city)s, %(state)s,
                %(work_mode)s, %(job_type)s, %(experience_min)s, %(experience_max)s,
                %(is_fresher)s, %(model)s, %(prompt_version)s, %(input_tokens)s,
                %(output_tokens)s, now())
        on conflict (job_id) do update
           set role_category = excluded.role_category,
               role_title_clean = excluded.role_title_clean,
               city = excluded.city, state = excluded.state,
               work_mode = excluded.work_mode, job_type = excluded.job_type,
               experience_min = excluded.experience_min,
               experience_max = excluded.experience_max,
               is_fresher = excluded.is_fresher, model = excluded.model,
               prompt_version = excluded.prompt_version,
               input_tokens = excluded.input_tokens,
               output_tokens = excluded.output_tokens, tagged_at = now()
        """,
        {"job_id": job_id, **tag},
    )


def stats(conn: psycopg.Connection) -> dict[str, Any]:
    return conn.execute(
        """
        select count(*) filter (where is_active) as active,
               count(*) filter (where is_active and canonical_job_id is null) as active_unique,
               count(*) filter (where is_active and canonical_job_id is not null) as duplicates,
               (select count(*) from job_tags t join jobs j2 on j2.id = t.job_id
                 where j2.is_active and j2.canonical_job_id is null) as tagged_total,
               (select count(*) from job_tags t join jobs j2 on j2.id = t.job_id
                 where j2.is_active and j2.canonical_job_id is null and t.is_fresher) as fresher_total
          from jobs
        """
    ).fetchone()
