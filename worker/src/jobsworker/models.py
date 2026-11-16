from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Source(BaseModel):
    id: int | None = None
    key: str
    type: str
    config: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class RawJob(BaseModel):
    """One posting exactly as the provider returned it."""

    source_key: str
    external_id: str
    payload: dict[str, Any]


class NormalizedJob(BaseModel):
    external_id: str
    title: str
    company: str
    location_raw: str = ""
    description_text: str = ""
    apply_url: str
    posted_at: datetime | None = None
    # Provider hints. Not stored; used by the pre-filter.
    country_code: str | None = None  # ISO-2 when the provider states it
    remote_hint: bool | None = None
    employment_hint: str | None = None
    # Filled by the pipeline.
    content_hash: str = ""
    dedupe_key: str = ""
