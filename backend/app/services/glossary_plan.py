from __future__ import annotations

import re
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from rapidfuzz import fuzz

from app.core.errors import InvalidInput
from app.data.english_words import load_english_words
from app.research.subject_keys import term_key
from app.research.terms import TERM_LABEL_MAX_CHARS

from .term_scales import COMPOUND_LEVEL, stated_zoom_level

__all__ = [
    "CONCEPT_TERM_TYPES",
    "HEAD_WORDS_MAX",
    "SPELLING_SIMILARITY_MIN",
    "CraftNames",
    "SeedCompound",
    "SeedConcept",
    "StatedMeaning",
    "TermSeed",
    "WikidataLink",
    "compounds_of",
    "concepts_of",
    "glossary_plan",
    "stated_local_names",
    "wikidata_links",
]

CONCEPT_TERM_TYPES = frozenset({"MATERIAL", "TOOL", "PROCESS_STAGE"})
PLAIN_TERM_TYPES = frozenset({"MATERIAL"})
TRADITION_TYPE = "TRADITION"
HEAD_WORDS_MAX = 4
SPELLING_SIMILARITY_MIN = 80
MATCHED = "MATCHED"
ENGLISH = "en"
NUMBERING = re.compile(r"^\d+\.\s*")
GLOSSED = re.compile(r"^(?P<head>[^()]+?)\s*\((?P<gloss>[^()]+)\)\s*(?:$|[—–-]\s)")
GLOSS_ITEMS = re.compile(r"\s*[,/;]\s*")
NOT_A_HEAD = re.compile(r"[\d/:;,()]")
LOCAL_NAME_PHRASE = re.compile(
    r"\b(?:locally\s+(?:known\s+as|called(?:\s+as)?)|known\s+locally\s+as|called\s+locally)\s+",
    re.IGNORECASE,
)
QUOTED_NAME = re.compile(r"[\"'‘“](?P<name>[^\"'’”]+)[\"'’”]")
NAME_RUN = re.compile(r"[^\W\d_][\w'’-]*(?:[ \t]+[^\W\d_][\w'’-]*)*")
WORD = re.compile(r"[^\W\d_]+")
NAMED_BEFORE_WORDS = 6
NAME_WORD_MIN_CHARS = 4


@dataclass(frozen=True)
class CraftNames:
    slug: str
    name: str
    aliases: tuple[str, ...] = ()
    local_names: tuple[str, ...] = ()


@dataclass(frozen=True)
class WikidataLink:
    qid: str
    description: str | None
    labels: tuple[str, ...]


@dataclass(frozen=True)
class SeedConcept:
    key: str
    craft_slug: str | None
    type: str
    name: str
    local_terms: tuple[str, ...]
    claim_texts: tuple[str, ...] = ()


@dataclass(frozen=True)
class StatedMeaning:
    concept_key: str
    term: str
    meaning: str


@dataclass(frozen=True)
class SeedCompound:
    name: str
    material_keys: tuple[str, ...]


@dataclass
class TermSeed:
    key: str
    label: str
    meaning: str | None = None
    local_names: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)
    craft_slugs: list[str] = field(default_factory=list)
    concept_keys: list[str] = field(default_factory=list)
    wikidata_id: str | None = None
    compound: bool = False
    zoom_level: str | None = None

    def merge(self, other: TermSeed) -> None:
        self.meaning = self.meaning or other.meaning
        self.wikidata_id = self.wikidata_id or other.wikidata_id
        self.compound = self.compound or other.compound
        _extend(self.local_names, other.local_names, leave_out=self.label)
        _extend(self.aliases, other.aliases, leave_out=self.label)
        _extend(self.craft_slugs, other.craft_slugs)
        _extend(self.concept_keys, other.concept_keys)


def glossary_plan(
    crafts: Sequence[CraftNames],
    wikidata: Mapping[str, WikidataLink],
    concepts: Sequence[SeedConcept],
    compounds: Sequence[SeedCompound],
    meanings: Sequence[StatedMeaning] = (),
) -> list[TermSeed]:
    by_key: dict[str, TermSeed] = {}
    concept_crafts = {concept.key: concept.craft_slug for concept in concepts if concept.craft_slug}
    traditions: dict[str, list[str]] = {}
    for concept in concepts:
        if concept.type == TRADITION_TYPE and concept.craft_slug:
            traditions.setdefault(concept.craft_slug, []).append(concept.key)
    ordered = sorted(crafts, key=lambda craft: craft.slug)
    found = [
        *(_craft_term(craft, wikidata.get(craft.slug), traditions.get(craft.slug, [])) for craft in ordered),
        *(_concept_term(concept) for concept in concepts),
        *(_compound_term(compound, concept_crafts) for compound in compounds),
        *(_meaning_term(meaning, concept_crafts) for meaning in meanings),
    ]
    for seed in found:
        if seed is None or not seed.craft_slugs:
            continue
        kept = by_key.setdefault(seed.key, seed)
        if kept is not seed:
            kept.merge(seed)
    return [_levelled(by_key[key]) for key in sorted(by_key)]


def wikidata_links(document: Mapping[str, Any]) -> dict[str, WikidataLink]:
    links: dict[str, WikidataLink] = {}
    for row in document.get("crafts") or []:
        match = row.get("match") if row.get("status") == MATCHED else None
        if not match or not match.get("qid"):
            continue
        labels = tuple(
            label for lang, label in (match.get("labels") or {}).items() if lang != ENGLISH and label
        )
        links[row["slug"]] = WikidataLink(
            qid=match["qid"], description=match.get("description"), labels=labels
        )
    return links


def concepts_of(seed_claims: Mapping[str, Any]) -> list[SeedConcept]:
    texts: dict[str, list[str]] = {}
    for claim in seed_claims.get("claims") or []:
        if claim.get("subjectType") == "CONCEPT":
            texts.setdefault(claim["subjectKey"], []).append(claim["text"])
    return [
        SeedConcept(
            key=row["key"],
            craft_slug=row.get("craftSlug"),
            type=row["type"],
            name=row["name"],
            local_terms=tuple(term.strip() for term in row.get("localTerms") or [] if term.strip()),
            claim_texts=tuple(texts.get(row["key"], ())),
        )
        for row in seed_claims.get("concepts") or []
    ]


def stated_local_names(
    head: str, texts: Iterable[str], *, english: Collection[str] | None = None
) -> list[str]:
    ordinary = load_english_words() if english is None else english
    found: list[str] = []
    for text in texts:
        for phrase in LOCAL_NAME_PHRASE.finditer(text):
            if not _names_head(head, text[: phrase.start()]):
                continue
            name = _name_after(text[phrase.end() :], ordinary)
            if name is not None and _usable_head(name):
                found.append(name)
    return found


def compounds_of(science_seed: Mapping[str, Any]) -> list[SeedCompound]:
    using: dict[str, list[str]] = {}
    for material_key, material in (science_seed.get("materials") or {}).items():
        if material.get("compound"):
            using.setdefault(material["compound"], []).append(material_key)
    return [
        SeedCompound(name=compound["name"], material_keys=tuple(using.get(compound["key"], ())))
        for compound in science_seed.get("compounds") or []
    ]


def _craft_term(craft: CraftNames, link: WikidataLink | None, traditions: list[str]) -> TermSeed | None:
    seed = _seed(craft.name, craft_slugs=[craft.slug], concept_keys=traditions)
    if seed is None:
        return None
    _extend(seed.aliases, craft.aliases, leave_out=craft.name)
    _extend(seed.local_names, craft.local_names, leave_out=craft.name)
    if link is not None:
        seed.wikidata_id = link.qid
        seed.meaning = link.description
        _extend(seed.local_names, link.labels, leave_out=craft.name)
    return seed


def _concept_term(concept: SeedConcept) -> TermSeed | None:
    seed = _glossed_term(concept)
    if seed is not None:
        _extend(seed.local_names, stated_local_names(seed.label, concept.claim_texts), leave_out=seed.label)
    return seed


def _glossed_term(concept: SeedConcept) -> TermSeed | None:
    if concept.type not in CONCEPT_TERM_TYPES or not concept.craft_slug:
        return None
    name = NUMBERING.sub("", concept.name).strip()
    glossed = GLOSSED.match(name)
    head = glossed["head"].strip() if glossed else name
    if not _usable_head(head):
        return None
    local = {term.casefold(): term for term in concept.local_terms}
    seed = _seed(head, craft_slugs=[concept.craft_slug], concept_keys=[concept.key])
    if seed is None:
        return None
    gloss = glossed["gloss"].strip() if glossed else None
    if gloss and head.casefold() in local:
        seed.meaning = gloss
        _extend(seed.local_names, _spellings_of(head, concept.local_terms), leave_out=head)
        return seed
    items = [item for item in GLOSS_ITEMS.split(gloss or "") if item]
    named_locally = [local[item.casefold()] for item in items if item.casefold() in local]
    if named_locally:
        _extend(seed.local_names, named_locally, leave_out=head)
        rest = [item for item in items if item.casefold() not in local]
        seed.meaning = ", ".join(rest) or None
        return seed
    if concept.type not in PLAIN_TERM_TYPES:
        return None
    seed.meaning = gloss
    return seed


def _compound_term(compound: SeedCompound, concept_crafts: Mapping[str, str]) -> TermSeed | None:
    crafts = [concept_crafts[key] for key in compound.material_keys if key in concept_crafts]
    keys = [key for key in compound.material_keys if key in concept_crafts]
    seed = _seed(compound.name, craft_slugs=list(dict.fromkeys(crafts)), concept_keys=keys)
    if seed is not None:
        seed.compound = True
    return seed


def _levelled(seed: TermSeed) -> TermSeed:
    seed.zoom_level = COMPOUND_LEVEL if seed.compound else stated_zoom_level(seed.label, seed.meaning)
    return seed


def _meaning_term(meaning: StatedMeaning, concept_crafts: Mapping[str, str]) -> TermSeed | None:
    craft = concept_crafts.get(meaning.concept_key)
    seed = _seed(meaning.term, craft_slugs=[craft] if craft else [], concept_keys=[meaning.concept_key])
    if seed is not None:
        seed.meaning = meaning.meaning
    return seed


def _seed(label: str, *, craft_slugs: list[str], concept_keys: list[str] | None = None) -> TermSeed | None:
    shown = " ".join(label.split())
    if not shown or len(shown) > TERM_LABEL_MAX_CHARS:
        return None
    try:
        key = term_key(shown)
    except InvalidInput:
        return None
    return TermSeed(key=key, label=shown, craft_slugs=craft_slugs, concept_keys=list(concept_keys or []))


def _names_head(head: str, before: str) -> bool:
    named = {_stem(word) for word in WORD.findall(head) if len(word) >= NAME_WORD_MIN_CHARS}
    return any(_stem(word) in named for word in WORD.findall(before)[-NAMED_BEFORE_WORDS:])


def _name_after(rest: str, ordinary: Collection[str]) -> str | None:
    quoted = QUOTED_NAME.match(rest)
    if quoted is not None:
        return " ".join(quoted["name"].split()) or None
    run = NAME_RUN.match(rest)
    words: list[str] = []
    for word in run.group(0).split() if run else []:
        if len(word) < NAME_WORD_MIN_CHARS or word.casefold() in ordinary or len(words) == HEAD_WORDS_MAX:
            break
        words.append(word)
    return " ".join(words) or None


def _stem(word: str) -> str:
    return word.casefold().removesuffix("s")


def _usable_head(head: str) -> bool:
    return bool(head) and len(head.split()) <= HEAD_WORDS_MAX and not NOT_A_HEAD.search(head)


def _spellings_of(head: str, local_terms: Iterable[str]) -> list[str]:
    folded = head.casefold()
    return [
        term
        for term in local_terms
        if term.casefold() != folded and fuzz.ratio(term.casefold(), folded) >= SPELLING_SIMILARITY_MIN
    ]


def _extend(kept: list[str], more: Iterable[str], *, leave_out: str | None = None) -> None:
    seen = {item.casefold() for item in kept}
    if leave_out is not None:
        seen.add(leave_out.casefold())
    for item in more:
        if item and item.casefold() not in seen:
            seen.add(item.casefold())
            kept.append(item)
