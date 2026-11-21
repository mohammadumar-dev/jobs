"""Turn eval/out/labels.csv into a readable labelling page: eval/out/label.html.

    python eval/make_label_page.py

Open the page in a browser, label each job, then click "Download labels.csv"
and put the file back at eval/out/labels.csv. Answers are kept in the browser
while you work, so you can close the page and continue later.
The page never shows the model's tags, so the labels stay blind.
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).parent / "out"
FIELDS = ["role_category", "city", "work_mode", "job_type", "is_fresher"]


def cities() -> list[str]:
    text = (ROOT / "worker" / "taxonomy.yaml").read_text(encoding="utf-8")
    block = text.split("cities:", 1)[1].split("\n\n", 1)[0]
    return re.findall(r"^\s{2}([A-Z][^:]+):", block, re.M) + ["Remote", "Other"]


def main() -> None:
    with (OUT / "labels.csv").open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    options = {
        "role_category": ["software", "data", "design", "product", "marketing", "sales",
                          "operations", "finance", "hr", "support", "content", "other"],
        "city": cities(),
        "work_mode": ["onsite", "hybrid", "remote"],
        "job_type": ["internship", "full_time", "contract"],
        "is_fresher": ["yes", "no"],
    }
    data = json.dumps({"rows": rows, "options": options}, ensure_ascii=False).replace("</", "<\\/")
    html = (Path(__file__).parent / "label_template.html").read_text(encoding="utf-8")
    (OUT / "label.html").write_text(html.replace("__DATA__", data), encoding="utf-8")
    print(f"wrote {OUT / 'label.html'} ({len(rows)} jobs)")


if __name__ == "__main__":
    main()
