"""Step 2 of the accuracy check: compare the human labels with the model's tags.

    cd worker && uv run python ../eval/score.py

Reads eval/out/labels.csv (filled in by a person) and eval/out/model_tags.csv,
prints per-field accuracy, the all-fields-correct rate and every mismatch, and
writes eval/out/score.json. Refuses to score a sheet with blank labels.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

OUT = Path(__file__).parent / "out"
FIELDS = ["role_category", "city", "work_mode", "job_type", "is_fresher"]
TRUE = {"true", "t", "yes", "y", "1"}
FALSE = {"false", "f", "no", "n", "0"}


def norm(field: str, value: str) -> str:
    value = (value or "").strip()
    if field == "is_fresher":
        low = value.lower()
        if low in TRUE:
            return "true"
        if low in FALSE:
            return "false"
        return value
    return value if field == "city" else value.lower()


def score(labels: list[dict], model: dict[str, dict]) -> dict:
    blank = [(r["job_id"], f) for r in labels for f in FIELDS if not (r.get(f) or "").strip()]
    if blank:
        raise SystemExit(f"{len(blank)} blank labels (first: {blank[0]}). Finish labelling first.")
    correct = {f: 0 for f in FIELDS}
    all_correct = 0
    mismatches = []
    for row in labels:
        tags = model[row["job_id"]]
        ok = True
        for f in FIELDS:
            human, machine = norm(f, row[f]), norm(f, tags[f])
            if human.lower() == machine.lower():
                correct[f] += 1
            else:
                ok = False
                mismatches.append({"job_id": row["job_id"], "title": row["title"], "field": f,
                                   "human": human, "model": machine})
        all_correct += ok
    n = len(labels)
    return {
        "n": n,
        "model": next(iter(model.values()))["model"],
        "prompt_version": next(iter(model.values()))["prompt_version"],
        "accuracy": {f: round(100 * correct[f] / n, 1) for f in FIELDS},
        "all_fields_correct": round(100 * all_correct / n, 1),
        "mismatches": mismatches,
    }


def main() -> int:
    with (OUT / "labels.csv").open(encoding="utf-8-sig", newline="") as fh:
        labels = list(csv.DictReader(fh))
    with (OUT / "model_tags.csv").open(encoding="utf-8", newline="") as fh:
        model = {r["job_id"]: r for r in csv.DictReader(fh)}
    result = score(labels, model)
    print(f"{result['n']} jobs, model {result['model']}, prompt {result['prompt_version']}")
    for field, pct in result["accuracy"].items():
        print(f"  {field:14} {pct:5.1f}%")
    print(f"  {'all fields':14} {result['all_fields_correct']:5.1f}%")
    print(f"\n{len(result['mismatches'])} mismatches:")
    for m in result["mismatches"]:
        print(f"  [{m['field']}] human={m['human']!r} model={m['model']!r}  {m['title'][:60]}")
    (OUT / "score.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
