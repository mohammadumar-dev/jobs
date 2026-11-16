"""Cheap rule-based pre-filter: India location AND an entry-level signal.

Runs before any LLM call so we never pay to tag senior or non-India posts.
It is deliberately recall-biased; the tagger sets the final `is_fresher`.
"""
from __future__ import annotations

import re

from .models import NormalizedJob
from .taxonomy import Taxonomy

INTERN = re.compile(
    r"\b(intern|interns|internship|internships|trainee|trainees|apprentice|apprenticeship)\b",
    re.IGNORECASE,
)
_STRONG = re.compile(
    r"\b(fresher|freshers|graduate|new grad|campus|entry[- ]level|early careers?"
    r"|university hire|junior|jr)\b",
    re.IGNORECASE,
)
_WEAK = re.compile(r"\b(associate|analyst i|engineer i|developer i|level 1|l1)\b", re.IGNORECASE)
SENIOR = re.compile(
    r"\b(senior|sr|lead|staff|principal|manager|director|head|architect|vp|vice president"
    r"|chief|president|expert|ii|iii|iv|sde[- ]?[23]|l[4-9])\b",
    re.IGNORECASE,
)
_DESC_POS = re.compile(
    r"\b(0\s*(?:-|–|to)\s*[12]\s*(?:\+\s*)?(?:years?|yrs?)"
    r"|freshers?|fresh graduates?|recent(?:ly)? graduate[sd]?|entry[- ]level|new grad(?:uate)?s?"
    r"|no (?:prior |previous )?(?:work )?experience (?:is )?(?:required|needed|necessary)"
    r"|final[- ]year students?|20(?:25|26|27) (?:batch|graduates?|pass\s?outs?))",
    re.IGNORECASE,
)
_YEARS = re.compile(
    r"(?<![\d.,])(\d{1,2})\s*(?:\+|plus)?\s*(?:(?:-|–|to)\s*(\d{1,2})\s*\+?\s*)?(?:years?|yrs?)\b", re.IGNORECASE
)


def experience_range(text: str) -> tuple[int | None, int | None]:
    """Lowest experience requirement stated in the text, e.g. '0-2 years' -> (0, 2)."""
    best: tuple[int, int | None] | None = None
    for m in _YEARS.finditer(text):
        lo = int(m.group(1))
        hi = int(m.group(2)) if m.group(2) else None
        if lo > 25 or (hi is not None and hi < lo):
            continue  # "30 years of history", malformed ranges
        if best is None or lo < best[0]:
            best = (lo, hi)
    return best if best else (None, None)


def is_india(job: NormalizedJob, taxonomy: Taxonomy) -> bool:
    if job.country_code:
        return job.country_code.upper() in {"IN", "IND", "INDIA"}
    return taxonomy.mentions_india(job.location_raw)


def title_might_be_fresher(title: str) -> bool:
    """Title-only screen, for providers where the description costs an extra request."""
    return bool(INTERN.search(title)) or not SENIOR.search(title)


def has_fresher_signal(job: NormalizedJob) -> bool:
    title = job.title
    if INTERN.search(title):
        return True
    if SENIOR.search(title):
        return False
    lo, _ = experience_range(job.description_text)
    if _STRONG.search(title):
        return lo is None or lo <= 2
    if (job.employment_hint or "").lower() in {"intern", "internship"}:
        return True
    if _WEAK.search(title):
        return lo is None or lo <= 1
    return bool(_DESC_POS.search(job.description_text)) and (lo is None or lo <= 1)


def passes(job: NormalizedJob, taxonomy: Taxonomy) -> bool:
    return is_india(job, taxonomy) and has_fresher_signal(job)
