from __future__ import annotations

import hashlib
import html
import re
from html.parser import HTMLParser

from .models import NormalizedJob
from .taxonomy import Taxonomy

_BLOCK = {"p", "div", "br", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "section"}
_SKIP = {"script", "style", "noscript", "iframe"}


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIP:
            self._skip += 1
        elif tag == "li":
            self.parts.append("\n- ")
        elif tag in _BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP:
            self._skip = max(0, self._skip - 1)
        elif tag in _BLOCK and tag != "br":
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self.parts.append(data)


def html_to_text(value: str | None) -> str:
    """HTML (possibly entity-escaped, as Greenhouse returns it) -> readable plain text."""
    if not value:
        return ""
    if "&lt;" in value and "<" not in value:
        value = html.unescape(value)
    parser = _TextExtractor()
    parser.feed(value)
    parser.close()
    text = "".join(parser.parts).replace("\xa0", " ")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    # "<li><p>text</p></li>" must read "- text", and a list is one tight block
    text = re.sub(r"\n- *\n+", "\n- ", text)
    text = re.sub(r"\n{2,}- ", "\n- ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def clean_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


_LEGAL = re.compile(
    r"\b(pvt|private|ltd|limited|inc|llc|llp|corp|corporation|co|company|gmbh|plc|india)\b\.?"
)


def _slug(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", value.lower())).strip()


def norm_company(company: str) -> str:
    return _slug(_LEGAL.sub(" ", company.lower())) or _slug(company)


def content_hash(title: str, company: str, description: str) -> str:
    joined = "\x1f".join(clean_text(p) for p in (title, company, description))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def dedupe_key(title: str, company: str, location_raw: str, taxonomy: Taxonomy) -> str:
    city = taxonomy.match_city(location_raw) or _slug(location_raw) or "unknown"
    return f"{_slug(title)}|{norm_company(company)}|{city.lower()}"


def finalize(job: NormalizedJob, taxonomy: Taxonomy) -> NormalizedJob:
    job.title = clean_text(job.title)
    job.company = clean_text(job.company)
    job.location_raw = clean_text(job.location_raw)
    job.content_hash = content_hash(job.title, job.company, job.description_text)
    job.dedupe_key = dedupe_key(job.title, job.company, job.location_raw, taxonomy)
    return job
