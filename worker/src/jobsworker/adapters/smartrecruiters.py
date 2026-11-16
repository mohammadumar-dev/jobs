from __future__ import annotations

import logging

from ..filters import title_might_be_fresher
from ..models import NormalizedJob, RawJob, Source
from ..normalize import html_to_text
from .base import SourceAdapter, http_url, parse_iso

log = logging.getLogger(__name__)

BASE = "https://api.smartrecruiters.com/v1/companies/{company}/postings"
PAGE = 100
SENIOR_LEVELS = {"mid_senior_level", "director", "executive"}


class SmartRecruitersAdapter(SourceAdapter):
    """SmartRecruiters Posting API.

    config: {company_id: str, company: str, max_details: int}
    The list endpoint has no description, so each kept posting costs one more
    request. To stay polite we ask the API for India only (country=in), skip
    obviously senior titles/levels, and cap detail requests at `max_details`.
    """

    def fetch(self, source: Source) -> list[RawJob]:
        company = source.config["company_id"]
        max_details = int(source.config.get("max_details", 150))
        listed: list[dict] = []
        offset = 0
        while True:
            page = self.http.get_json(
                BASE.format(company=company),
                params={"country": "in", "limit": PAGE, "offset": offset},
            )
            content = page.get("content", [])
            listed.extend(content)
            offset += PAGE
            if len(content) < PAGE or offset >= int(page.get("totalFound", 0)):
                break

        candidates = [
            item
            for item in listed
            if item.get("id")
            and title_might_be_fresher(item.get("name") or "")
            and ((item.get("experienceLevel") or {}).get("id") or "") not in SENIOR_LEVELS
        ]
        if len(candidates) > max_details:
            log.warning(
                "%s: %d candidates, fetching details for the first %d",
                source.key, len(candidates), max_details,
            )
            candidates = candidates[:max_details]

        out: list[RawJob] = []
        for item in candidates:
            resp = self.http.get(f"{BASE.format(company=company)}/{item['id']}")
            if resp.status_code == 404:
                continue  # unpublished between list and detail
            resp.raise_for_status()
            out.append(
                RawJob(source_key=source.key, external_id=str(item["id"]), payload=resp.json())
            )
        return out

    def normalize(self, source: Source, raw: RawJob) -> NormalizedJob | None:
        p = raw.payload
        url = http_url(p.get("postingUrl")) or http_url(p.get("applyUrl"))
        title = (p.get("name") or "").strip()
        if not url or not title:
            return None
        loc = p.get("location") or {}
        location = loc.get("fullLocation") or ", ".join(
            x for x in (loc.get("city"), loc.get("region")) if x
        )
        if "india" not in location.lower() and (loc.get("country") or "").lower() == "in":
            location = f"{location}, India" if location else "India"
        sections = ((p.get("jobAd") or {}).get("sections")) or {}
        parts = []
        for key in ("jobDescription", "qualifications", "additionalInformation"):
            sec = sections.get(key) or {}
            text = html_to_text(sec.get("text"))
            if text:
                parts.append(f"{sec.get('title') or key}\n{text}")
        level = (p.get("experienceLevel") or {}).get("id") or ""
        employment = (p.get("typeOfEmployment") or {}).get("label")
        return NormalizedJob(
            external_id=raw.external_id,
            title=title,
            company=source.config.get("company")
            or (p.get("company") or {}).get("name")
            or source.key,
            location_raw=location,
            description_text="\n\n".join(parts),
            apply_url=url,
            posted_at=parse_iso(p.get("releasedDate")),
            country_code=(loc.get("country") or "").upper() or None,
            remote_hint=True if loc.get("remote") else None,
            employment_hint="internship" if level == "internship" else employment,
        )
