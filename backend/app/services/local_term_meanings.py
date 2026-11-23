from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from functools import lru_cache
from typing import Literal

from pydantic import Field

from app.core.errors import InvalidInput
from app.curation.dossier import parse_dossier
from app.curation.files import CURATION_DIR
from app.data.craft_master_loader import DATA_DIR
from app.research.base import ContractModel

from .glossary_plan import SeedConcept, StatedMeaning

__all__ = [
    "LOCAL_TERM_MEANINGS_FILE",
    "LocalTermMeanings",
    "checked_meanings",
    "dossier_quotes",
    "load_local_term_meanings",
    "meaning_problems",
]

LOCAL_TERM_MEANINGS_FILE = DATA_DIR / "local_term_meanings.json"
DOSSIER_CLAIM_SEPARATOR = ":"

QuotesOf = Callable[[str], Sequence[str]]


class MeaningRow(ContractModel):
    concept: str = Field(min_length=1)
    term: str = Field(min_length=1, max_length=120)
    meaning: str = Field(min_length=1, max_length=200)
    stated: str = Field(min_length=1, max_length=300)
    dossier_claim: str | None = Field(default=None, pattern=r"^[A-Za-z0-9-]+:C\d{3}$")


class LocalTermMeanings(ContractModel):
    schema_version: Literal[1]
    about: str = Field(min_length=40)
    meanings: list[MeaningRow] = Field(min_length=1)


@lru_cache(maxsize=1)
def load_local_term_meanings() -> LocalTermMeanings:
    return LocalTermMeanings.model_validate_json(LOCAL_TERM_MEANINGS_FILE.read_bytes())


def meaning_problems(
    rows: Sequence[MeaningRow], concepts: Mapping[str, SeedConcept], quotes_of: QuotesOf
) -> list[str]:
    problems: list[str] = []
    for row in rows:
        concept = concepts.get(row.concept)
        if concept is None:
            problems.append(f"{row.term}: no seed concept {row.concept}")
            continue
        stated = row.stated.casefold()
        if row.term.casefold() not in {term.casefold() for term in concept.local_terms}:
            problems.append(f"{row.term}: not a local word of {row.concept}")
        if row.term.casefold() not in stated or row.meaning.casefold() not in stated:
            problems.append(f"{row.term}: the stated words name the word or its meaning only")
        texts = quotes_of(row.dossier_claim) if row.dossier_claim else concept.claim_texts
        if not any(stated in text.casefold() for text in texts):
            problems.append(f"{row.term}: {row.stated!r} is not in {row.dossier_claim or row.concept}")
    return problems


def checked_meanings(concepts: Sequence[SeedConcept], quotes_of: QuotesOf) -> list[StatedMeaning]:
    rows = load_local_term_meanings().meanings
    problems = meaning_problems(rows, {concept.key: concept for concept in concepts}, quotes_of)
    if problems:
        raise InvalidInput(f"{LOCAL_TERM_MEANINGS_FILE.name}: {'; '.join(problems)}")
    return [StatedMeaning(concept_key=row.concept, term=row.term, meaning=row.meaning) for row in rows]


def dossier_quotes(dossier_claim: str) -> list[str]:
    slug, claim_id = dossier_claim.split(DOSSIER_CLAIM_SEPARATOR, 1)
    path = CURATION_DIR / f"{slug}.json"
    if not path.is_file():
        raise InvalidInput(f"No curated dossier {slug} holds the claim {claim_id}")
    dossier = parse_dossier(path.read_text(encoding="utf-8"))
    claim = next((claim for claim in dossier.claims if claim.id == claim_id), None)
    if claim is None:
        raise InvalidInput(f"The curated dossier {slug} holds no claim {claim_id}")
    return [claim.text, *(quote.quote for quote in claim.quotes)]
