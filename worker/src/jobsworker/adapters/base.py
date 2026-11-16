from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime

from ..config import Settings
from ..http import PoliteClient
from ..models import NormalizedJob, RawJob, Source


class SourceAdapter(ABC):
    """One subclass per source type. `fetch` talks to the network, `normalize` is pure."""

    def __init__(self, http: PoliteClient, settings: Settings) -> None:
        self.http = http
        self.settings = settings

    @abstractmethod
    def fetch(self, source: Source) -> list[RawJob]: ...

    @abstractmethod
    def normalize(self, source: Source, raw: RawJob) -> NormalizedJob | None:
        """Return None for postings that cannot be shown (no title or apply URL)."""


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def http_url(value: str | None) -> str | None:
    value = (value or "").strip()
    return value if value.lower().startswith(("https://", "http://")) else None
