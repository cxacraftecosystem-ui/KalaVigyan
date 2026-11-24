from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit

from app.data.craft_text import fold
from app.research.evidence import shares_an_author
from app.research.images import without_tracking

__all__ = [
    "PART_KINDS",
    "SOURCE_ID_KEY",
    "TITLE_KEY_WORDS_MIN",
    "SourceMerge",
    "reconciled_source",
    "source_keys",
]

SOURCE_ID_KEY = "sourceId"
TITLE_KEY_WORDS_MIN = 5
DOI_PREFIX = "doi:"
URL_PREFIX = "url:"
TITLE_PREFIX = "title:"
PART_KINDS = frozenset({"BOOK_CHAPTER", "GI_JOURNAL"})
DOI_HOSTS = frozenset({"doi.org", "dx.doi.org"})
DOI_PREFIXES = ("https://doi.org/", "http://doi.org/", "https://dx.doi.org/", "http://dx.doi.org/", "doi:")
ASIDE = re.compile(r"\([^()]*\)|\[[^\[\]]*\]")
FILLED_FIELDS = ("authors", "doi", "url", "publisher", "licence", "attribution", "reliability")

SourceRef = Mapping[str, Any]


def source_keys(ref: SourceRef) -> list[str]:
    keys = []
    doi = _doi(ref.get("doi")) or _doi_of_url(ref.get("url"))
    if doi:
        keys.append(f"{DOI_PREFIX}{doi}")
    url = _url_key(ref.get("url"))
    if url:
        keys.append(f"{URL_PREFIX}{url}")
    title = _title_key(ref.get("title"))
    if title:
        keys.append(f"{TITLE_PREFIX}{title}")
    return keys


def reconciled_source(kept: SourceRef, other: SourceRef) -> dict[str, Any]:
    merged = dict(kept)
    for name in FILLED_FIELDS:
        if not merged.get(name) and other.get(name):
            merged[name] = other[name]
    years = [year for year in (kept.get("year"), other.get("year")) if isinstance(year, int)]
    merged["year"] = min(years) if years else None
    return merged


class SourceMerge:
    def __init__(self) -> None:
        self._canonical: dict[str, str] = {}
        self._owners: dict[str, list[str]] = {}
        self._refs: dict[str, dict[str, Any]] = {}

    def register(self, source_id: str, ref: SourceRef | None) -> str:
        known = self._canonical.get(source_id)
        if known is not None or ref is None:
            return known or source_id
        keys = source_keys(ref)
        owner = self._owner_of(ref, keys)
        if owner is None:
            owner = source_id
            self._refs[owner] = {**ref, "id": owner}
        else:
            self._refs[owner] = reconciled_source(self._refs[owner], ref)
        self._canonical[source_id] = owner
        for key in keys:
            owners = self._owners.setdefault(key, [])
            if owner not in owners:
                owners.append(owner)
        return owner

    def canonical(self, source_id: str) -> str:
        return self._canonical.get(source_id, source_id)

    def knows(self, source_id: str) -> bool:
        return self.canonical(source_id) in self._refs

    def refs(self) -> dict[str, dict[str, Any]]:
        return {source_id: dict(ref) for source_id, ref in self._refs.items()}

    def remapped(self, payload: Any) -> Any:
        if isinstance(payload, dict):
            return {
                key: self.canonical(value)
                if key == SOURCE_ID_KEY and isinstance(value, str)
                else self.remapped(value)
                for key, value in payload.items()
            }
        if isinstance(payload, list):
            return [self.remapped(item) for item in payload]
        return payload

    def _owner_of(self, ref: SourceRef, keys: list[str]) -> str | None:
        found = ((key, owner) for key in keys for owner in self._owners.get(key, ()))
        return next((owner for key, owner in found if _same_work(self._refs[owner], ref, key)), None)


def _same_work(kept: SourceRef, other: SourceRef, matched_key: str) -> bool:
    mine, theirs = _doi(kept.get("doi")), _doi(other.get("doi"))
    if mine and theirs and mine != theirs:
        return False
    if matched_key.startswith(DOI_PREFIX):
        return True
    if _different_authors(kept, other):
        return False
    if matched_key.startswith(TITLE_PREFIX):
        return not _different_years(kept, other)
    return not _different_parts(kept, other)


def _different_authors(kept: SourceRef, other: SourceRef) -> bool:
    mine, theirs = _names(kept.get("authors")), _names(other.get("authors"))
    if not mine or not theirs:
        return False
    return not (shares_an_author(mine, theirs) or shares_an_author(theirs, mine))


def _different_parts(kept: SourceRef, other: SourceRef) -> bool:
    if kept.get("kind") not in PART_KINDS or other.get("kind") != kept.get("kind"):
        return False
    mine, theirs = _title_key(kept.get("title")), _title_key(other.get("title"))
    return bool(mine and theirs and mine != theirs)


def _different_years(kept: SourceRef, other: SourceRef) -> bool:
    years = {kept.get("year"), other.get("year")}
    return None not in years and len(years) > 1


def _names(value: Any) -> list[str]:
    if not isinstance(value, list | tuple):
        return []
    return [name for name in value if isinstance(name, str) and name.strip()]


def _doi(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip().lower()
    for prefix in DOI_PREFIXES:
        text = text.removeprefix(prefix)
    return text if text.startswith("10.") and "/" in text else None


def _doi_of_url(url: Any) -> str | None:
    if not isinstance(url, str):
        return None
    parts = urlsplit(url)
    if (parts.hostname or "").lower() not in DOI_HOSTS:
        return None
    return _doi(parts.path.lstrip("/"))


def _url_key(url: Any) -> str | None:
    if not isinstance(url, str) or not url.strip():
        return None
    parts = urlsplit(without_tracking(url.strip()))
    host = (parts.hostname or "").lower().removeprefix("www.")
    if not host or host in DOI_HOSTS:
        return None
    query = f"?{parts.query}" if parts.query else ""
    return f"{host}{parts.path.rstrip('/')}{query}"


def _title_key(title: Any) -> str | None:
    if not isinstance(title, str):
        return None
    words = sorted(set(fold(ASIDE.sub(" ", title)).split()))
    return " ".join(words) if len(words) >= TITLE_KEY_WORDS_MIN else None
