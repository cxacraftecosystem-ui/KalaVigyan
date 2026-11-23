from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit

from app.data.craft_text import fold
from app.research.images import without_tracking

__all__ = ["SOURCE_ID_KEY", "TITLE_KEY_WORDS_MIN", "SourceMerge", "reconciled_source", "source_keys"]

SOURCE_ID_KEY = "sourceId"
TITLE_KEY_WORDS_MIN = 5
TITLE_PREFIX = "title:"
DOI_HOSTS = frozenset({"doi.org", "dx.doi.org"})
DOI_PREFIXES = ("https://doi.org/", "http://doi.org/", "https://dx.doi.org/", "http://dx.doi.org/", "doi:")
ASIDE = re.compile(r"\([^()]*\)|\[[^\[\]]*\]")
FILLED_FIELDS = ("authors", "doi", "url", "publisher", "licence", "attribution", "reliability")

SourceRef = Mapping[str, Any]


def source_keys(ref: SourceRef) -> list[str]:
    keys = []
    doi = _doi(ref.get("doi")) or _doi_of_url(ref.get("url"))
    if doi:
        keys.append(f"doi:{doi}")
    url = _url_key(ref.get("url"))
    if url:
        keys.append(f"url:{url}")
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
        self._owners: dict[str, str] = {}
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
            self._owners.setdefault(key, owner)
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
        matched = next((key for key in keys if key in self._owners), None)
        if matched is None:
            return None
        owner = self._owners[matched]
        return owner if _same_work(self._refs[owner], ref, matched) else None


def _same_work(kept: SourceRef, other: SourceRef, matched_key: str) -> bool:
    mine, theirs = _doi(kept.get("doi")), _doi(other.get("doi"))
    if mine and theirs and mine != theirs:
        return False
    return not matched_key.startswith(TITLE_PREFIX) or not _different_years(kept, other)


def _different_years(kept: SourceRef, other: SourceRef) -> bool:
    years = {kept.get("year"), other.get("year")}
    return None not in years and len(years) > 1


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
