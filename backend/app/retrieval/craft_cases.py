from __future__ import annotations

import json
import re
import unicodedata
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, ValidationError, field_validator

from app.core.errors import InvalidInput
from app.research.base import ContractModel
from app.research.crafts import QUESTION_MAX_CHARS, CraftResolution

from .eval_floors import EVAL_DIR
from .question_writing import seeded_rank

__all__ = [
    "AMBIGUOUS",
    "CASES_FILE",
    "CASES_SEED",
    "CASES_VERSION",
    "CASE_KINDS",
    "LEXICAL_KINDS",
    "PASS_FLOOR",
    "RESOLVED",
    "CaseOutcome",
    "CraftCase",
    "CraftCases",
    "CraftNames",
    "RecordedName",
    "case_report",
    "common_words",
    "craft_cases",
    "craft_cases_file",
    "folded",
    "outcome_of",
    "parse_cases",
]

CASES_FILE = EVAL_DIR / "craft_matching_cases.json"
CASES_VERSION = 1
CASES_SEED = 20261122
CASE_KINDS = ("EXACT", "FOLDED", "MISSPELLED", "PARTIAL", "COMPARISON")
LEXICAL_KINDS = frozenset({"EXACT", "FOLDED", "COMPARISON"})
RESOLVED = "RESOLVED"
AMBIGUOUS = "AMBIGUOUS"
PASS_FLOOR = 0.95
LATIN = "Latn"
ACTIVE = "ACTIVE"
TRANSLITERATED = "TRANSLITERATION"
MISSPELT_MIN_LETTERS = 5
PARTIAL_MIN_WORDS = 2
COMMON_WORD_NAMES = 4
FAILURES_SHOWN = 25
NOT_WORD = re.compile(r"[^0-9a-z]+")
PUNCTUATION = re.compile(r"[^\w\s]")
ABOUT = (
    "Craft-matching cases built by app.scripts.build_craft_cases from the craft master list and "
    "craft_aliases.json (decision 0126). A RESOLVED case passes when its craft is the first candidate; an "
    "AMBIGUOUS case passes when the resolver says AMBIGUOUS and offers every expected craft."
)

CaseKind = Literal[*CASE_KINDS]
CaseStatus = Literal["RESOLVED", "AMBIGUOUS"]


@dataclass(frozen=True)
class RecordedName:
    text: str
    script: str | None
    source: str
    status: str


@dataclass(frozen=True)
class CraftNames:
    slug: str
    name: str
    sub_category: str
    aliases: tuple[RecordedName, ...] = ()


class CraftCase(ContractModel):
    key: str = Field(min_length=1, max_length=240)
    kind: CaseKind
    text: str = Field(min_length=1, max_length=QUESTION_MAX_CHARS)
    status: CaseStatus
    expected: tuple[str, ...] = Field(min_length=1)


class CraftCases(ContractModel):
    version: Literal[1]
    seed: int
    about: str = ""
    cases: tuple[CraftCase, ...]

    @field_validator("cases")
    @classmethod
    def _keys_of_their_own(cls, cases: tuple[CraftCase, ...]) -> tuple[CraftCase, ...]:
        keys = [case.key for case in cases]
        if len(set(keys)) != len(keys):
            raise ValueError("Each craft-matching case needs a key of its own")
        return cases


@dataclass(frozen=True)
class CaseOutcome:
    case: CraftCase
    status: str
    candidates: tuple[str, ...]

    @property
    def passed(self) -> bool:
        if self.case.status == RESOLVED:
            return self.candidates[:1] == self.case.expected[:1]
        return self.status == AMBIGUOUS and set(self.case.expected) <= set(self.candidates)

    @property
    def resolved(self) -> bool:
        return self.case.status == RESOLVED and self.status == RESOLVED and self.passed


def folded(text: str) -> str:
    if any(ch.isalpha() and unicodedata.name(ch, "").split(" ")[0] != "LATIN" for ch in text):
        return " ".join(unicodedata.normalize("NFC", text).casefold().split())
    plain = "".join(ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch))
    return " ".join(NOT_WORD.sub(" ", plain.casefold().replace("&", " and ")).split())


def craft_cases(crafts: Sequence[CraftNames], *, seed: int = CASES_SEED) -> CraftCases:
    held = _holders(crafts)
    common = common_words([craft.name for craft in crafts])
    cases = [case for craft in crafts for case in _named(craft, held, seed, common)]
    cases += _comparisons(crafts, held, seed)
    return CraftCases(version=CASES_VERSION, seed=seed, about=ABOUT, cases=tuple(cases))


def common_words(names: Sequence[str]) -> frozenset[str]:
    counts: dict[str, int] = defaultdict(int)
    for name in names:
        for word in {word.casefold() for word in name.split()}:
            counts[word] += 1
    return frozenset(word for word, count in counts.items() if count >= COMMON_WORD_NAMES)


def outcome_of(case: CraftCase, resolution: CraftResolution) -> CaseOutcome:
    return CaseOutcome(case, resolution.status, tuple(found.craft.slug for found in resolution.candidates))


def case_report(outcomes: Sequence[CaseOutcome]) -> dict[str, dict[str, Any]]:
    kinds: dict[str, list[CaseOutcome]] = defaultdict(list)
    for outcome in outcomes:
        kinds[outcome.case.kind].append(outcome)
    return {kind: _kind_report(found) for kind, found in sorted(kinds.items())}


def parse_cases(data: Any) -> CraftCases:
    if not isinstance(data, dict) or data.get("version") != CASES_VERSION:
        raise InvalidInput(f"The craft-matching cases must be a version {CASES_VERSION} object")
    try:
        return CraftCases.model_validate(data)
    except ValidationError as error:
        raise InvalidInput(f"The craft-matching cases are malformed: {error}") from None


@cache
def craft_cases_file(path: Path = CASES_FILE) -> CraftCases:
    return parse_cases(json.loads(path.read_text(encoding="utf-8")))


def _kind_report(outcomes: Sequence[CaseOutcome]) -> dict[str, Any]:
    single = [outcome for outcome in outcomes if outcome.case.status == RESOLVED]
    return {
        "cases": len(outcomes),
        "passed": round(sum(outcome.passed for outcome in outcomes) / len(outcomes), 4),
        "resolved": round(sum(outcome.resolved for outcome in single) / len(single), 4) if single else None,
        "failed": [outcome.case.key for outcome in outcomes if not outcome.passed][:FAILURES_SHOWN],
    }


def _usable(alias: RecordedName) -> bool:
    return alias.status == ACTIVE and bool(alias.text.strip())


def _holders(crafts: Sequence[CraftNames]) -> Mapping[str, frozenset[str]]:
    found: dict[str, set[str]] = defaultdict(set)
    for craft in crafts:
        for text in (craft.name, *(alias.text for alias in craft.aliases if _usable(alias))):
            found[folded(text)].add(craft.slug)
    return {key: frozenset(slugs) for key, slugs in found.items()}


def _case(key: str, kind: str, text: str, owners: frozenset[str]) -> CraftCase:
    status = RESOLVED if len(owners) == 1 else AMBIGUOUS
    return CraftCase(key=key, kind=kind, text=text, status=status, expected=tuple(sorted(owners)))


def _named(
    craft: CraftNames, held: Mapping[str, frozenset[str]], seed: int, common: frozenset[str]
) -> list[CraftCase]:
    own = frozenset({craft.slug})
    owners = held.get(folded(craft.name), own)
    cases = [
        _case(f"exact-name-{craft.slug}", "EXACT", craft.name, owners),
        _case(f"folded-name-{craft.slug}", "FOLDED", _folded_variant(craft.name, seed), owners),
    ]
    for variant, alias in _chosen_aliases(craft, seed).items():
        cases.append(_case(f"exact-{variant}-{craft.slug}", "EXACT", alias, held.get(folded(alias), own)))
    accented = next(
        (a.text for a in craft.aliases if _usable(a) and a.script == LATIN and _unaccented(a.text) != a.text),
        None,
    )
    if accented is not None:
        cases.append(
            _case(f"folded-alias-{craft.slug}", "FOLDED", _unaccented(accented), held[folded(accented)])
        )
    for kind, text in (
        ("MISSPELLED", _misspelt(craft.name, seed, common)),
        ("PARTIAL", _partial(craft.name, common)),
    ):
        if text is not None and folded(text) not in held:
            cases.append(_case(f"{kind.lower()}-name-{craft.slug}", kind, text, own))
    return cases


def _chosen_aliases(craft: CraftNames, seed: int) -> dict[str, str]:
    name_key = folded(craft.name)
    usable = [a for a in craft.aliases if _usable(a) and folded(a.text) != name_key]
    latin = [a.text for a in usable if a.script == LATIN and a.source != TRANSLITERATED]
    native = [a.text for a in usable if a.script not in (LATIN, None)]
    chosen: dict[str, str] = {}
    for variant, texts in (("alias", latin), ("native", native)):
        if texts:
            chosen[variant] = min(texts, key=lambda text: seeded_rank(seed, craft.slug, variant, text))
    return chosen


def _folded_variant(name: str, seed: int) -> str:
    if PUNCTUATION.search(name):
        return " ".join(PUNCTUATION.sub(" ", name.replace("&", " and ")).split())
    return name.upper() if int(seeded_rank(seed, "case", name), 16) % 2 else name.lower()


def _unaccented(text: str) -> str:
    plain = "".join(ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch))
    return unicodedata.normalize("NFC", plain)


def _misspelt(name: str, seed: int, common: frozenset[str]) -> str | None:
    words = name.split()
    eligible = [i for i, word in enumerate(words) if word.isalpha() and word.casefold() not in common]
    if not eligible:
        return None
    at = max(eligible, key=lambda index: (len(words[index]), -index))
    word = words[at]
    if len(word) < MISSPELT_MIN_LETTERS:
        return None
    rank = int(seeded_rank(seed, "misspell", name), 16)
    place = 1 + rank % (len(word) - 2)
    edits = (
        word[:place] + word[place + 1 :],
        word[:place] + word[place + 1] + word[place] + word[place + 2 :],
        word[:place] + word[place] + word[place:],
    )
    edited = edits[(rank // len(word)) % len(edits)]
    if edited.casefold() == word.casefold():
        edited = edits[0]
    return " ".join([*words[:at], edited, *words[at + 1 :]])


def _partial(name: str, common: frozenset[str]) -> str | None:
    words = name.split()
    kept = [word for word in words if word.casefold() not in common]
    return " ".join(kept) if PARTIAL_MIN_WORDS <= len(kept) < len(words) else None


def _comparisons(
    crafts: Sequence[CraftNames], held: Mapping[str, frozenset[str]], seed: int
) -> list[CraftCase]:
    groups: dict[str, list[CraftNames]] = defaultdict(list)
    for craft in crafts:
        if held.get(folded(craft.name)) == frozenset({craft.slug}):
            groups[craft.sub_category].append(craft)
    cases: list[CraftCase] = []
    for group in groups.values():
        ordered = sorted(group, key=lambda craft: seeded_rank(seed, "pair", craft.slug))
        for first, second in zip(ordered[::2], ordered[1::2], strict=False):
            text = f"{first.name} or {second.name}"
            if len(text) <= QUESTION_MAX_CHARS:
                owners = frozenset({first.slug, second.slug})
                cases.append(_case(f"comparison-{first.slug}-{second.slug}", "COMPARISON", text, owners))
    return cases
