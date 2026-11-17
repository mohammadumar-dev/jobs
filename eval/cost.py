"""LLM cost per 1,000 posts, from the token counts logged in job_tags.

    cd worker && uv run python ../eval/cost.py

Prices come from worker/pricing.yaml (copied from the provider's pricing page;
re-check them and the USD->INR rate before publishing). Also reports what the
content-hash skip saved: jobs seen again in later runs that were NOT re-tagged.
"""
from __future__ import annotations

import json
from pathlib import Path

from jobsworker import db
from jobsworker.config import Settings
from jobsworker.tagger import load_pricing

OUT = Path(__file__).parent / "out"


def main() -> int:
    settings = Settings.from_env()
    pricing = load_pricing(settings.pricing_path)
    with db.connect(settings.database_url) as conn:
        by_model = conn.execute(
            """
            select model, count(*) as n, avg(input_tokens) as avg_in, avg(output_tokens) as avg_out
              from job_tags where model <> 'heuristic-v1' group by model order by n desc
            """
        ).fetchall()
        runs = conn.execute(
            """
            select count(*) as runs, coalesce(sum(tagged), 0) as tagged,
                   coalesce(sum(llm_cost_usd), 0) as spent
              from ingest_runs where finished_at is not null
            """
        ).fetchone()
        active = conn.execute(
            "select count(*) as n from jobs where is_active and canonical_job_id is null"
        ).fetchone()["n"]

    if not by_model:
        print("No LLM-tagged jobs yet (only the rule-based fallback has run). Nothing to cost.")
        return 1

    inr = pricing["usd_to_inr"]
    report = {"usd_to_inr": inr, "models": []}
    for row in by_model:
        free = row["model"].startswith(tuple(pricing.get("free_tier_prefixes") or ()))
        price = {"input": 0, "output": 0} if free else pricing["models"].get(row["model"])
        if price is None:
            print(f"{row['model']}: no price in pricing.yaml, skipped")
            continue
        per_post = (float(row["avg_in"]) * price["input"] + float(row["avg_out"]) * price["output"]) / 1e6
        per_1000 = per_post * 1000
        batch = per_1000 * pricing["batch_discount"]
        extra = {}
        if free:
            # What the same token volume would cost on the paid reference model.
            ref = pricing.get("reference_model", "claude-haiku-5-5")
            rp = pricing["models"][ref]
            eq = (float(row["avg_in"]) * rp["input"] + float(row["avg_out"]) * rp["output"]) / 1e3
            extra = {"free_tier": True, "paid_equivalent_model": ref,
                     "paid_equivalent_usd_per_1000": round(eq, 4)}
            print(f"{row['model']}: free tier ($0); same tokens on {ref}: ${eq:.4f} per 1,000 posts")
        report["models"].append({
            **extra,
            "model": row["model"], "posts": row["n"],
            "avg_input_tokens": round(float(row["avg_in"])),
            "avg_output_tokens": round(float(row["avg_out"])),
            "usd_per_1000": round(per_1000, 4), "inr_per_1000": round(per_1000 * inr, 2),
            "usd_per_1000_batch": round(batch, 4), "inr_per_1000_batch": round(batch * inr, 2),
        })
        print(f"{row['model']}: {row['n']} posts, avg {float(row['avg_in']):.0f} in / "
              f"{float(row['avg_out']):.0f} out tokens")
        print(f"  standard: ${per_1000:.4f} (Rs {per_1000 * inr:.2f}) per 1,000 posts")
        print(f"  batch   : ${batch:.4f} (Rs {batch * inr:.2f}) per 1,000 posts")

    # Without the hash skip, every run would tag every active job again.
    naive_calls = runs["runs"] * active
    saved_calls = max(0, naive_calls - runs["tagged"])
    if report["models"]:
        per_post = report["models"][0]["usd_per_1000"] / 1000
        report["hash_skip"] = {
            "runs": runs["runs"], "tag_calls_made": runs["tagged"],
            "tag_calls_without_skip": naive_calls, "calls_saved": saved_calls,
            "usd_saved_estimate": round(saved_calls * per_post, 4),
            "usd_actually_spent": float(runs["spent"]),
        }
        print(f"\nhash skip: {runs['tagged']} tag calls over {runs['runs']} runs instead of "
              f"~{naive_calls}; about ${saved_calls * per_post:.4f} saved at standard price")
    OUT.mkdir(exist_ok=True)
    (OUT / "cost.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
