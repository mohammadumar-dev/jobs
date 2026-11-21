"""Re-tag the labelled sample with the current prompt, without touching the database.

    cd worker && uv run python ../eval/retag.py

Reads the job text from eval/out/labels_final.csv (or labels.csv), tags it with the
configured LLM chain and the current PROMPT_VERSION, and writes
eval/out/model_tags_<version>.csv in the same format as model_tags.csv.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

from jobsworker.config import Settings
from jobsworker.tagger import PROMPT_VERSION, make_tagger
from jobsworker.taxonomy import load_taxonomy

OUT = Path(__file__).parent / "out"


def main() -> int:
    src = OUT / "labels_final.csv"
    if not src.exists():
        src = OUT / "labels.csv"
    with src.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    jobs = [{"id": r["job_id"], "title": r["title"], "company": r["company"],
             "location_raw": r["location"], "description_text": r["description"]} for r in rows]
    settings = Settings.from_env()
    tagger = make_tagger(settings, load_taxonomy(settings.taxonomy_path))
    outcome = tagger.tag_many(jobs)
    if outcome.errors:
        print(f"{len(outcome.errors)} jobs failed: {outcome.errors[:3]}")
    dest = OUT / f"model_tags_{PROMPT_VERSION}.csv"
    with dest.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["job_id", "role_category", "city", "work_mode", "job_type", "is_fresher",
                    "model", "prompt_version"])
        for t in outcome.tagged:
            g = t.tag
            w.writerow([t.job_id, g.role_category, g.city, g.work_mode, g.job_type,
                        str(g.is_fresher).lower(), getattr(t, "model", None) or outcome.model,
                        PROMPT_VERSION])
    print(f"tagged {len(outcome.tagged)}/{len(jobs)} -> {dest}")
    return 0 if len(outcome.tagged) == len(jobs) else 1


if __name__ == "__main__":
    sys.exit(main())
