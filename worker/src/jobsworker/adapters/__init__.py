from __future__ import annotations

from .adzuna import AdzunaAdapter
from .ashby import AshbyAdapter
from .base import SourceAdapter
from .greenhouse import GreenhouseAdapter
from .lever import LeverAdapter
from .smartrecruiters import SmartRecruitersAdapter

ADAPTERS: dict[str, type[SourceAdapter]] = {
    "adzuna": AdzunaAdapter,
    "greenhouse": GreenhouseAdapter,
    "lever": LeverAdapter,
    "ashby": AshbyAdapter,
    "smartrecruiters": SmartRecruitersAdapter,
}

__all__ = ["ADAPTERS", "SourceAdapter"]
