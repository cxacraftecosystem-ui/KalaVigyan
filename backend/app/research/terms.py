from __future__ import annotations

import unicodedata
from collections.abc import Mapping, Sequence
from typing import Any, Literal, Self

from pydantic import AwareDatetime, Field, model_validator

from app.models.enums import TERM_BASES

from .base import ContractModel
from .citations import AnswerSentence, SourceRef, cited_source_ids
from .subject_keys import TermKey
from .vocabulary import FACT_LEVELS, AnswerLanguage

__all__ = [
    "TERM_BASES",
    "TERM_LABEL_MAX_CHARS",
    "TERM_SCHEMA_VERSION",
    "TERM_SUMMARY_MAX_SENTENCES",
    "WIKIDATA_ID_PATTERN",
    "Term",
    "TermSpan",
    "shown_as_word",
    "span_problems",
    "spans_still_shown",
]

TERM_SCHEMA_VERSION = 1
TERM_LABEL_MAX_CHARS = 120
TERM_SUMMARY_MAX_SENTENCES = 3
WIKIDATA_ID_PATTERN = r"^Q[1-9]\d*$"
WORD_CATEGORIES = frozenset({"L", "M", "N"})

TermBasis = Literal[*TERM_BASES]


class TermSpan(ContractModel):
    text: str = Field(min_length=1, max_length=TERM_LABEL_MAX_CHARS)
    term_key: TermKey


class Term(ContractModel):
    schema_version: Literal[1]
    key: TermKey
    label: str = Field(min_length=1, max_length=TERM_LABEL_MAX_CHARS)
    language: AnswerLanguage
    local_names: list[str]
    craft_slugs: list[str]
    wikidata_id: str | None = Field(pattern=WIKIDATA_ID_PATTERN)
    basis: TermBasis
    summary: list[AnswerSentence] = Field(min_length=1, max_length=TERM_SUMMARY_MAX_SENTENCES)
    sources: list[SourceRef]
    checked_at: AwareDatetime

    @model_validator(mode="after")
    def _a_cited_summary_of_facts(self) -> Self:
        if len(set(self.local_names)) != len(self.local_names) or any(
            not n.strip() for n in self.local_names
        ):
            raise ValueError(f"term {self.key} lists each local name once")
        if len(set(self.craft_slugs)) != len(self.craft_slugs):
            raise ValueError(f"term {self.key} lists each craft once")
        if any(sentence.level not in FACT_LEVELS for sentence in self.summary):
            raise ValueError(f"term {self.key} summarises facts only, never a hypothesis")
        if [source.id for source in self.sources] != cited_source_ids(self.summary):
            raise ValueError(f"term {self.key} lists every cited source once, in order of first citation")
        return self


def span_problems(text: str, spans: list[TermSpan]) -> list[str]:
    problems: list[str] = []
    keys = [span.term_key for span in spans]
    if len(set(keys)) != len(keys):
        problems.append("each term is marked once")
    taken: list[tuple[int, int]] = []
    for span in spans:
        start = text.find(span.text)
        if start < 0:
            problems.append(f"term {span.term_key} marks {span.text!r}, which is not in the sentence")
            continue
        end = start + len(span.text)
        if _overlaps(start, end, taken):
            problems.append(f"term {span.term_key} overlaps another term")
        taken.append((start, end))
    return problems


def spans_still_shown(
    text: str,
    spans: Sequence[Mapping[str, Any]],
    renderings: Mapping[str, str] | None = None,
    local_names: Mapping[str, Sequence[str]] | None = None,
) -> list[Mapping[str, Any]]:
    kept: list[Mapping[str, Any]] = []
    taken: list[tuple[int, int]] = []
    for span in spans:
        shown = _shown_span(text, span, renderings or {}, local_names or {})
        if shown is None:
            continue
        start = text.find(shown["text"])
        end = start + len(shown["text"])
        if _overlaps(start, end, taken):
            continue
        kept.append(shown)
        taken.append((start, end))
    return kept


def shown_as_word(text: str, name: str) -> bool:
    start = text.find(name)
    if start < 0:
        return False
    end = start + len(name)
    before = text[start - 1] if start > 0 else ""
    after = text[end] if end < len(text) else ""
    return not _in_word(before) and not _in_word(after)


def _shown_span(
    text: str,
    span: Mapping[str, Any],
    renderings: Mapping[str, str],
    local_names: Mapping[str, Sequence[str]],
) -> Mapping[str, Any] | None:
    if span["text"] in text:
        return span
    names = (renderings.get(span["text"], ""), *local_names.get(span["termKey"], ()))
    for name in (" ".join(name.split()) for name in names):
        if name and len(name) <= TERM_LABEL_MAX_CHARS and shown_as_word(text, name):
            return {**span, "text": name}
    return None


def _in_word(character: str) -> bool:
    return bool(character) and unicodedata.category(character)[0] in WORD_CATEGORIES


def _overlaps(start: int, end: int, taken: Sequence[tuple[int, int]]) -> bool:
    return any(start < other_end and other_start < end for other_start, other_end in taken)
