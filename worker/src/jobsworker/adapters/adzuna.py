from __future__ import annotations

from ..models import NormalizedJob, RawJob, Source
from ..normalize import html_to_text
from .base import SourceAdapter, http_url, parse_iso

BASE = "https://api.adzuna.com/v1/api/jobs/in/search/{page}"
DEFAULT_QUERIES = ["fresher", "intern", "internship", "graduate trainee", "entry level"]


class AdzunaAdapter(SourceAdapter):
    """Adzuna India search API. config: {queries: [...], max_pages: int, max_days_old: int}."""

    def fetch(self, source: Source) -> list[RawJob]:
        if not (self.settings.adzuna_app_id and self.settings.adzuna_app_key):
            raise RuntimeError("ADZUNA_APP_ID / ADZUNA_APP_KEY are not set")
        cfg = source.config
        seen: dict[str, RawJob] = {}
        for query in cfg.get("queries", DEFAULT_QUERIES):
            for page in range(1, int(cfg.get("max_pages", 3)) + 1):
                data = self.http.get_json(
                    BASE.format(page=page),
                    params={
                        "app_id": self.settings.adzuna_app_id,
                        "app_key": self.settings.adzuna_app_key,
                        "results_per_page": 50,
                        "what": query,
                        "max_days_old": int(cfg.get("max_days_old", 30)),
                        "sort_by": "date",
                        "content-type": "application/json",
                    },
                )
                results = data.get("results", [])
                for item in results:
                    ext = str(item.get("id", ""))
                    if ext:
                        seen.setdefault(
                            ext, RawJob(source_key=source.key, external_id=ext, payload=item)
                        )
                if len(results) < 50:
                    break
        return list(seen.values())

    def normalize(self, source: Source, raw: RawJob) -> NormalizedJob | None:
        p = raw.payload
        # Adzuna terms: link out through their redirect_url.
        url = http_url(p.get("redirect_url"))
        title = html_to_text(p.get("title"))
        if not url or not title:
            return None
        contract = p.get("contract_time") or p.get("contract_type")
        return NormalizedJob(
            external_id=raw.external_id,
            title=title,
            company=(p.get("company") or {}).get("display_name") or "Unknown company",
            location_raw=(p.get("location") or {}).get("display_name") or "India",
            description_text=html_to_text(p.get("description")),
            apply_url=url,
            posted_at=parse_iso(p.get("created")),
            country_code="IN",  # the /in/ endpoint only returns India
            employment_hint=contract,
        )
