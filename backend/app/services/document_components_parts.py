from __future__ import annotations

import hashlib
import re
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from app.research.citations import Citation
from app.research.craft_page import PageClaim
from app.research.craft_parts import (
    CommunitiesPart,
    KeyFactsPart,
    OpenQuestionsPart,
    PagePart,
    PlacesPart,
    RecordPart,
    SourcesDifferPart,
)

__all__ = ["HEADING_TAG", "HYPOTHESIS", "StructureText", "hypothesis_texts", "part_texts", "sentence_case"]

HYPOTHESIS = "HYPOTHESIS"
HEADING_TAG = "h3"
TERM_TAG = "dt"
VALUE_TAG = "dd"
ITEM_TAG = "li"
UNIT_PREFIX = "s"
DIGEST_CHARS = 10
SLUG_WORD = re.compile(r"[^a-z0-9]+")
RECORD_HEADING = "In the record"
ENVIRONMENT_HEADING = "The place and its resources"
PLACES_HEADING = "Places"
COMMUNITIES_HEADING = "Communities"
DIFFER_HEADING = "Where the sources differ"
QUESTIONS_HEADING = "Open questions"
HYPOTHESES_HEADING = "Hypotheses"

Cited = tuple[str, Sequence[Citation]]
Row = tuple[str, list[Cited]]


@dataclass(frozen=True)
class StructureText:
    unit_id: str
    tag: str
    field: str | None
    text: str
    claim_ids: tuple[uuid.UUID, ...] = ()


def part_texts(
    chapter: str, part: PagePart, fields: Mapping[uuid.UUID, str], taken: set[str]
) -> list[StructureText]:
    found = _rows(part)
    if found is None:
        return []
    heading, rows = found
    texts: list[StructureText] = []
    last: str | None = None
    for label, sentences in rows:
        cited = [
            _cited(chapter, text, citations, fields, taken) for text, citations in sentences if text.strip()
        ]
        if not cited:
            continue
        if label != last:
            texts.append(StructureText(_unit_id(chapter, TERM_TAG, label, (), taken), TERM_TAG, None, label))
            last = label
        texts.extend(cited)
    if not texts or heading is None:
        return texts
    return [*_heading(chapter, heading, taken), *texts]


def hypothesis_texts(claims: Sequence[PageClaim], taken: set[str]) -> list[StructureText]:
    if not claims:
        return []
    chapter = "sources"
    texts = _heading(chapter, HYPOTHESES_HEADING, taken)
    for claim in claims:
        unit_id = _unit_id(chapter, ITEM_TAG, claim.text, (claim.id,), taken)
        texts.append(StructureText(unit_id, ITEM_TAG, claim.discipline, claim.text, (claim.id,)))
    return texts


def _rows(part: PagePart) -> tuple[str | None, list[Row]] | None:
    if isinstance(part, KeyFactsPart):
        return None, [(fact.label, [(fact.value, fact.citations)]) for fact in part.facts]
    if isinstance(part, RecordPart):
        factors = any(entry.factor is not None for entry in part.entries)
        rows = [(entry.label, [(s.text, s.citations) for s in entry.sentences]) for entry in part.entries]
        return (ENVIRONMENT_HEADING if factors else RECORD_HEADING), rows
    if isinstance(part, PlacesPart):
        return PLACES_HEADING, [(p.name, [(s.text, s.citations) for s in p.sentences]) for p in part.places]
    if isinstance(part, CommunitiesPart):
        rows = [(c.name, [(s.text, s.citations) for s in c.sentences]) for c in part.communities]
        return COMMUNITIES_HEADING, rows
    if isinstance(part, SourcesDifferPart):
        reading = part.reading
        return DIFFER_HEADING, [
            (sentence_case(reading.about), [(s.text, s.citations) for s in reading.sentences()])
        ]
    if isinstance(part, OpenQuestionsPart):
        rows = [(q.question, [(s.text, s.citations) for s in q.sentences]) for q in part.questions]
        return QUESTIONS_HEADING, rows
    return None


def sentence_case(text: str) -> str:
    shown = text.strip()
    return shown[:1].upper() + shown[1:]


def _heading(chapter: str, heading: str, taken: set[str]) -> list[StructureText]:
    unit_id = f"{UNIT_PREFIX}-{chapter}-{SLUG_WORD.sub('-', heading.lower()).strip('-')}"
    if unit_id in taken:
        return []
    taken.add(unit_id)
    return [StructureText(unit_id, HEADING_TAG, None, heading)]


def _cited(
    chapter: str,
    text: str,
    citations: Sequence[Citation],
    fields: Mapping[uuid.UUID, str],
    taken: set[str],
) -> StructureText:
    claims = tuple(dict.fromkeys(uuid.UUID(citation.claim_id) for citation in citations))
    field = next((fields[claim] for claim in claims if claim in fields), None)
    return StructureText(
        _unit_id(chapter, VALUE_TAG, text, claims, taken), VALUE_TAG, field, text.strip(), claims
    )


def _unit_id(chapter: str, tag: str, text: str, claims: Sequence[uuid.UUID], taken: set[str]) -> str:
    seed = "|".join((chapter, tag, text, *sorted(str(claim) for claim in claims)))
    stem = f"{UNIT_PREFIX}-{chapter}-{hashlib.sha256(seed.encode('utf-8')).hexdigest()[:DIGEST_CHARS]}"
    unit_id, n = stem, 1
    while unit_id in taken:
        n += 1
        unit_id = f"{stem}-{n}"
    taken.add(unit_id)
    return unit_id
