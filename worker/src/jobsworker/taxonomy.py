from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Taxonomy:
    role_categories: tuple[str, ...]
    work_modes: tuple[str, ...]
    job_types: tuple[str, ...]
    city_state: dict[str, str]
    special_cities: tuple[str, ...]
    _alias_re: re.Pattern[str]
    _alias_to_city: dict[str, str]
    _india_re: re.Pattern[str]

    def __hash__(self) -> int:  # dict fields make the default hash unusable
        return id(self)

    @property
    def cities(self) -> tuple[str, ...]:
        return tuple(self.city_state) + self.special_cities

    def match_city(self, text: str) -> str | None:
        """First canonical city mentioned in free text, or None."""
        m = self._alias_re.search(text.lower())
        return self._alias_to_city[m.group(1)] if m else None

    def mentions_india(self, text: str) -> bool:
        low = text.lower()
        return bool(self._india_re.search(low) or self._alias_re.search(low))


def _alternation(words: list[str]) -> str:
    # longest first so "navi mumbai" wins over "mumbai", "new delhi" over "delhi"
    return "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True))


@lru_cache(maxsize=4)
def load_taxonomy(path: Path) -> Taxonomy:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    alias_to_city: dict[str, str] = {}
    city_state: dict[str, str] = {}
    for city, info in data["cities"].items():
        city_state[city] = info["state"]
        for alias in info["aliases"]:
            alias_to_city[alias.lower()] = city
    alias_re = re.compile(rf"(?<![a-z])({_alternation(list(alias_to_city))})(?![a-z])")
    india_re = re.compile(rf"(?<![a-z])({_alternation(data['india_markers'])})(?![a-z])")
    return Taxonomy(
        role_categories=tuple(data["role_categories"]),
        work_modes=tuple(data["work_modes"]),
        job_types=tuple(data["job_types"]),
        city_state=city_state,
        special_cities=tuple(data["special_cities"]),
        _alias_re=alias_re,
        _alias_to_city=alias_to_city,
        _india_re=india_re,
    )
