from __future__ import annotations

from ..models import NormalizedJob, RawJob, Source
from ..normalize import html_to_text
from .base import SourceAdapter, http_url, parse_iso

URL = "https://api.ashbyhq.com/posting-api/job-board/{name}"


def _country(address: dict | None) -> str:
    return ((address or {}).get("postalAddress") or {}).get("addressCountry") or ""


class AshbyAdapter(SourceAdapter):
    """Ashby public job posting API. config: {name: str, company: str}."""

    def fetch(self, source: Source) -> list[RawJob]:
        data = self.http.get_json(URL.format(name=source.config["name"]))
        return [
            RawJob(source_key=source.key, external_id=str(j["id"]), payload=j)
            for j in data.get("jobs", [])
            if j.get("id") and j.get("isListed", True)
        ]

    def normalize(self, source: Source, raw: RawJob) -> NormalizedJob | None:
        p = raw.payload
        url = http_url(p.get("jobUrl")) or http_url(p.get("applyUrl"))
        title = (p.get("title") or "").strip()
        if not url or not title:
            return None
        # Location names are often bare cities; append the country so the India
        # filter can see it ("Bengaluru" -> "Bengaluru, India").
        locations: list[str] = []
        pairs = [(p.get("location") or "", _country(p.get("address")))]
        for sec in p.get("secondaryLocations") or []:
            pairs.append((sec.get("location") or "", _country(sec.get("address"))))
        for name, country in pairs:
            label = name
            if country and country.lower() not in name.lower():
                label = f"{name}, {country}" if name else country
            if label and label not in locations:
                locations.append(label)
        return NormalizedJob(
            external_id=raw.external_id,
            title=title,
            company=source.config.get("company") or source.key,
            location_raw="; ".join(locations),
            description_text=p.get("descriptionPlain") or html_to_text(p.get("descriptionHtml")),
            apply_url=url,
            posted_at=parse_iso(p.get("publishedAt")),
            remote_hint=True if p.get("isRemote") else None,
            employment_hint=p.get("employmentType"),
        )
