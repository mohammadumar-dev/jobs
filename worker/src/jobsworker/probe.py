"""Check candidate company boards and report how many India fresher posts each has.

Usage: jobsworker probe candidates.yaml
Used to build sources.yaml from *verified* slugs instead of guesses.
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

from .adapters import ADAPTERS
from .adapters.smartrecruiters import BASE as SR_BASE
from .config import Settings
from .filters import passes, title_might_be_fresher
from .http import PoliteClient
from .models import Source
from .normalize import finalize
from .taxonomy import load_taxonomy

ID_FIELD = {
    "greenhouse": "token",
    "lever": "site",
    "ashby": "name",
    "smartrecruiters": "company_id",
}


def probe(path: Path, settings: Settings) -> list[dict]:
    taxonomy = load_taxonomy(settings.taxonomy_path)
    http = PoliteClient(settings.user_agent, settings.min_interval_s, max_retries=1)
    rows: list[dict] = []
    candidates = yaml.safe_load(path.read_text(encoding="utf-8"))
    for type_, entries in candidates.items():
        for entry in entries:
            slug, company = (entry, entry) if isinstance(entry, str) else entry
            source = Source(
                key=f"{type_}:{slug}", type=type_, config={ID_FIELD[type_]: slug, "company": company}
            )
            row = {"type": type_, "slug": slug, "company": company, "total": 0, "match": 0}
            try:
                if type_ == "smartrecruiters":
                    # list-only: do not spend detail requests while probing
                    page = http.get_json(
                        SR_BASE.format(company=slug), params={"country": "in", "limit": 100}
                    )
                    row["total"] = int(page.get("totalFound", 0))
                    row["match"] = sum(
                        1
                        for i in page.get("content", [])
                        if title_might_be_fresher(i.get("name") or "")
                        and ((i.get("experienceLevel") or {}).get("id") or "")
                        in {"internship", "entry_level", "associate"}
                    )
                else:
                    adapter = ADAPTERS[type_](http, settings)
                    raws = adapter.fetch(source)
                    row["total"] = len(raws)
                    for raw in raws:
                        job = adapter.normalize(source, raw)
                        if job and passes(finalize(job, taxonomy), taxonomy):
                            row["match"] += 1
            except Exception as exc:  # noqa: BLE001 - a dead slug is an expected outcome
                row["error"] = f"{type(exc).__name__}: {str(exc)[:80]}"
            rows.append(row)
            print(
                f"{row['type']:16} {row['slug']:34} total={row['total']:5} "
                f"match={row['match']:4} {row.get('error', '')}",
                flush=True,
            )
    http.close()
    return rows


def main(argv: list[str]) -> int:
    probe(Path(argv[0]), Settings.from_env())
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
