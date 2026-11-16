from __future__ import annotations

from datetime import UTC, datetime

from ..models import NormalizedJob, RawJob, Source
from ..normalize import html_to_text
from .base import SourceAdapter, http_url

HOSTS = ("https://api.lever.co", "https://api.eu.lever.co")


class LeverAdapter(SourceAdapter):
    """Lever Postings API. config: {site: str, company: str}. Falls back to the EU host."""

    def fetch(self, source: Source) -> list[RawJob]:
        site = source.config["site"]
        resp = None
        for host in HOSTS:
            resp = self.http.get(f"{host}/v0/postings/{site}", params={"mode": "json"})
            if resp.status_code != 404:
                break
        assert resp is not None
        resp.raise_for_status()
        return [
            RawJob(source_key=source.key, external_id=str(j["id"]), payload=j)
            for j in resp.json()
            if j.get("id")
        ]

    def normalize(self, source: Source, raw: RawJob) -> NormalizedJob | None:
        p = raw.payload
        url = http_url(p.get("hostedUrl")) or http_url(p.get("applyUrl"))
        title = (p.get("text") or "").strip()
        if not url or not title:
            return None
        cats = p.get("categories") or {}
        locations = [cats.get("location") or ""]
        for loc in cats.get("allLocations") or []:
            if loc and loc not in locations:
                locations.append(loc)
        parts = [p.get("descriptionPlain") or html_to_text(p.get("description"))]
        for block in p.get("lists") or []:
            parts.append(f"{block.get('text', '')}\n{html_to_text(block.get('content'))}")
        parts.append(p.get("additionalPlain") or html_to_text(p.get("additional")))
        created = p.get("createdAt")
        workplace = (p.get("workplaceType") or "").lower()
        return NormalizedJob(
            external_id=raw.external_id,
            title=title,
            company=source.config.get("company") or source.key,
            location_raw="; ".join(x for x in locations if x),
            description_text="\n\n".join(x.strip() for x in parts if x and x.strip()),
            apply_url=url,
            posted_at=(
                datetime.fromtimestamp(created / 1000, tz=UTC)
                if isinstance(created, (int, float))
                else None
            ),
            country_code=p.get("country") or None,
            remote_hint=True if workplace == "remote" else None,
            employment_hint=cats.get("commitment"),
        )
