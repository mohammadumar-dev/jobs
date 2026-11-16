from __future__ import annotations

from ..models import NormalizedJob, RawJob, Source
from ..normalize import html_to_text
from .base import SourceAdapter, http_url, parse_iso

URL = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs"


class GreenhouseAdapter(SourceAdapter):
    """Greenhouse Job Board API. config: {token: str, company: str}."""

    def fetch(self, source: Source) -> list[RawJob]:
        data = self.http.get_json(
            URL.format(token=source.config["token"]), params={"content": "true"}
        )
        return [
            RawJob(source_key=source.key, external_id=str(j["id"]), payload=j)
            for j in data.get("jobs", [])
            if j.get("id") is not None
        ]

    def normalize(self, source: Source, raw: RawJob) -> NormalizedJob | None:
        p = raw.payload
        url = http_url(p.get("absolute_url"))
        title = (p.get("title") or "").strip()
        if not url or not title:
            return None
        locations = [(p.get("location") or {}).get("name") or ""]
        for office in p.get("offices") or []:
            loc = office.get("location") or office.get("name") or ""
            if loc and loc not in locations:
                locations.append(loc)
        return NormalizedJob(
            external_id=raw.external_id,
            title=title,
            company=source.config.get("company") or p.get("company_name") or source.key,
            location_raw="; ".join(x for x in locations if x),
            description_text=html_to_text(p.get("content")),
            apply_url=url,
            posted_at=parse_iso(p.get("first_published") or p.get("updated_at")),
        )
