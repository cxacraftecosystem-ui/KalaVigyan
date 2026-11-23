from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from .craft_text import core_key, key_phrases

__all__ = [
    "HISTORICAL_SITES_SCHEMA_VERSION",
    "SITE_NAME_MIN_CHARS",
    "HistoricalSites",
    "parse_historical_sites",
]

HISTORICAL_SITES_SCHEMA_VERSION = 1
SITE_NAME_MIN_CHARS = 4


def _no_sites() -> Mapping[str, frozenset[str]]:
    return MappingProxyType({})


@dataclass(frozen=True)
class HistoricalSites:
    countries: Mapping[str, frozenset[str]] = field(default_factory=_no_sites)
    longest: int = 0

    def countries_kept(self, key: str) -> frozenset[str]:
        if not self.countries:
            return frozenset()
        return frozenset(
            name for phrase in key_phrases(key, self.longest) for name in self.countries.get(phrase, ())
        )


def parse_historical_sites(
    raw: Mapping[str, Any], country_keys: Mapping[str, frozenset[str]]
) -> HistoricalSites:
    if raw.get("schemaVersion") != HISTORICAL_SITES_SCHEMA_VERSION:
        raise ValueError(f"historical sites need schemaVersion {HISTORICAL_SITES_SCHEMA_VERSION}")
    source = raw.get("source") or {}
    if not all(source.get(part) for part in ("name", "licence", "retrieved", "query")):
        raise ValueError("historical sites name their source, its licence, the date read and the query")
    entries = [
        *((_names(culture), list(culture["countries"])) for culture in raw.get("cultures", [])),
        *((_names(site), [site["country"]]) for site in raw.get("sites", [])),
    ]
    kept: dict[str, frozenset[str]] = {}
    for names, countries in entries:
        unknown = sorted(country for country in countries if country not in country_keys)
        if unknown:
            raise ValueError(f"a historical site lies in a country not listed abroad: {', '.join(unknown)}")
        abroad = frozenset(key for country in countries for key in country_keys[country])
        for name in names:
            kept[_site_key(name, kept)] = abroad
    return HistoricalSites(MappingProxyType(kept), max((len(key.split()) for key in kept), default=0))


def _names(entry: Mapping[str, Any]) -> list[str]:
    return [entry["name"], *entry.get("otherNames", [])]


def _site_key(name: str, kept: Mapping[str, frozenset[str]]) -> str:
    key = core_key(name)
    if len(key) < SITE_NAME_MIN_CHARS:
        raise ValueError(f"{name!r} is too short to name a historical site")
    if key in kept:
        raise ValueError(f"{name!r} is listed twice")
    return key
