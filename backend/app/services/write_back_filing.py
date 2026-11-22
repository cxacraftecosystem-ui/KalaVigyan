from __future__ import annotations

import json
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Any

from app.research.field_voices import FIELD_SOURCE_KIND

from .write_back_crafts import CraftFiling, FilingTexts, craft_filing, researched_craft
from .write_back_names import CraftNames
from .write_back_passages import passage_around

__all__ = [
    "SHARED_PLACE",
    "UNKNOWN_PLACE",
    "FilingRow",
    "StoredCitation",
    "StoredFiling",
    "craft_place",
    "family_place",
    "filed_place",
    "filing_row",
    "held_place",
    "report_lines",
    "stored_texts",
]

PASSED_QUOTE = "PASS"
TEXT_SHOWN_CHARS = 100
CRAFT_PREFIX = "craft:"
FAMILY_PREFIX = "family:"
HELD_PREFIX = "held:"
SHARED_PLACE = "shared"
REFUSED_PLACE = "refused"
UNKNOWN_PLACE = "unknown"
UNKNOWN_REASON = "the craft its research was for is not recorded"


@dataclass(frozen=True)
class StoredCitation:
    quote: str | None
    quote_check: str
    title: str
    kind: str
    passage_text: str | None


@dataclass(frozen=True)
class StoredFiling:
    claim_id: uuid.UUID
    text: str
    status: str
    field: str | None
    place: str
    checked: bool
    citations: tuple[StoredCitation, ...]


@dataclass(frozen=True)
class FilingRow:
    claim_id: uuid.UUID
    status: str
    checked: bool
    place: str
    would: str
    why: str | None
    text: str

    @property
    def moves(self) -> bool:
        return self.would not in (self.place, UNKNOWN_PLACE)

    def as_dict(self) -> dict[str, Any]:
        return {
            "claim": str(self.claim_id),
            "status": self.status,
            "checked": self.checked,
            "is": self.place,
            "would": self.would,
            "why": self.why,
            "text": self.text[:TEXT_SHOWN_CHARS],
        }


def craft_place(slug: str) -> str:
    return CRAFT_PREFIX + slug


def family_place(slug: str) -> str:
    return FAMILY_PREFIX + slug


def held_place(slug: str | None) -> str:
    return f"{HELD_PREFIX}{slug}"


def stored_texts(text: str, citations: Sequence[StoredCitation]) -> FilingTexts:
    quoted = [c for c in citations if c.quote and c.quote_check == PASSED_QUOTE]
    read = [c for c in citations if c.kind != FIELD_SOURCE_KIND]
    passages = (
        passage_around(c.passage_text, c.quote)
        for c in quoted
        if c.quote and c.passage_text and c.kind != FIELD_SOURCE_KIND
    )
    return FilingTexts(
        text=text,
        quotes=tuple(dict.fromkeys(c.quote for c in quoted if c.quote)),
        passages=tuple(dict.fromkeys(passage for passage in passages if passage)),
        titles=tuple(dict.fromkeys(c.title for c in read)),
    )


def filing_row(claim: StoredFiling, names: CraftNames | None) -> FilingRow:
    row = FilingRow(
        claim_id=claim.claim_id,
        status=claim.status,
        checked=claim.checked,
        place=claim.place,
        would=UNKNOWN_PLACE,
        why=UNKNOWN_REASON,
        text=claim.text,
    )
    if names is None:
        return row
    field_only = bool(claim.citations) and all(c.kind == FIELD_SOURCE_KIND for c in claim.citations)
    if field_only:
        filing = researched_craft(names)
    else:
        filing = craft_filing(stored_texts(claim.text, claim.citations), field=claim.field, names=names)
    return replace(row, would=filed_place(filing), why=filing.refused or filing.held)


def filed_place(filing: CraftFiling) -> str:
    if filing.refused is not None:
        return REFUSED_PLACE
    if filing.held is not None:
        return held_place(filing.slug)
    if filing.family is not None:
        return family_place(filing.family.slug)
    return craft_place(filing.slug) if filing.slug is not None else SHARED_PLACE


def report_lines(rows: Sequence[FilingRow]) -> list[str]:
    summary = {
        "claims": len(rows),
        "moves": sum(1 for row in rows if row.moves),
        "held": sum(1 for row in rows if row.would.startswith(HELD_PREFIX)),
        "refused": sum(1 for row in rows if row.would == REFUSED_PLACE),
        "unknown": sum(1 for row in rows if row.would == UNKNOWN_PLACE),
        "unchecked": [str(row.claim_id) for row in rows if not row.checked],
    }
    return [_line(row.as_dict()) for row in rows] + [_line(summary)]


def _line(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
