"""Step 1 of the accuracy check: export 50 random active jobs for a person to label.

    cd worker && uv run python ../eval/sample.py            # writes eval/out/

Writes two files:
  eval/out/labels.csv       the job text plus BLANK label columns. Fill this in.
  eval/out/model_tags.csv   what the model said. Do NOT open it until labels.csv
                            is finished: the labels must be made blind.

The sample is reproducible: jobs are ordered by id and picked with a fixed seed.
"""
from __future__ import annotations

import argparse
import csv
import random
from pathlib import Path

from jobsworker import db
from jobsworker.config import Settings
from jobsworker.taxonomy import load_taxonomy

OUT = Path(__file__).parent / "out"
FIELDS = ["role_category", "city", "work_mode", "job_type", "is_fresher"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=50)
    parser.add_argument("--seed", type=int, default=20261116)
    parser.add_argument("--include-heuristic", action="store_true",
                        help="also sample jobs tagged by the rule-based fallback (not the LLM)")
    args = parser.parse_args()

    settings = Settings.from_env()
    taxonomy = load_taxonomy(settings.taxonomy_path)
    with db.connect(settings.database_url) as conn:
        rows = conn.execute(
            """
            select j.id, j.title, j.company, j.location_raw, j.description_text, j.apply_url,
                   t.role_category, t.city, t.work_mode, t.job_type, t.is_fresher,
                   t.model, t.prompt_version
              from jobs j join job_tags t on t.job_id = j.id
             where j.is_active and j.canonical_job_id is null
               and (%s or t.model <> 'heuristic-v1')
             order by j.id
            """,
            (args.include_heuristic,),
        ).fetchall()
    if len(rows) < args.n:
        print(f"only {len(rows)} LLM-tagged active jobs; need {args.n}. Run the tagger first.")
        return 1
    sample = random.Random(args.seed).sample(rows, args.n)

    OUT.mkdir(exist_ok=True)
    with (OUT / "labels.csv").open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh)
        writer.writerow(["job_id", "title", "company", "location", "description", "apply_url", *FIELDS])
        for r in sample:
            writer.writerow([r["id"], r["title"], r["company"], r["location_raw"],
                             r["description_text"][:6000], r["apply_url"], "", "", "", "", ""])
    with (OUT / "model_tags.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["job_id", *FIELDS, "model", "prompt_version"])
        for r in sample:
            writer.writerow([r["id"], *(r[f] for f in FIELDS), r["model"], r["prompt_version"]])

    print(f"wrote {args.n} jobs to {OUT / 'labels.csv'}")
    print("allowed values:")
    print("  role_category:", ", ".join(taxonomy.role_categories))
    print("  city:", ", ".join(taxonomy.cities))
    print("  work_mode:", ", ".join(taxonomy.work_modes))
    print("  job_type:", ", ".join(taxonomy.job_types))
    print("  is_fresher: true / false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
