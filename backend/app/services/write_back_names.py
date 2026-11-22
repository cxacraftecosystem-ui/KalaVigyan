from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.craft_master_loader import load_master
from app.data.craft_text import STOP_TOKENS, ascii_key, core_key, key_phrases, script_of
from app.data.district_register import load_district_other_names, load_district_register
from app.data.english_words import load_english_words
from app.data.places_abroad import PlacesAbroad, load_places_abroad
from app.models import Craft, CraftCategory, CraftSubCategory
from app.research.crafts import CraftRef

from .craft_index import MAX_NGRAM_TOKENS, CraftIndex, NameEntry, keys_of
from .craft_matching import named_craft_ids
from .craft_resolver import CraftIndexStore

__all__ = [
    "ANCHOR_MIN_CHARS",
    "COMMON_NAME_USES",
    "CraftFamily",
    "CraftNames",
    "NamedCraft",
    "craft_names",
    "filing_index",
    "filing_names",
]

ANCHOR_MIN_CHARS = 4
COMMON_NAME_USES = 3
FULL_NAME = "EXACT_NAME"
LATIN_SCRIPTS = frozenset({"Latn", "Zyyy"})


@dataclass(frozen=True)
class NamedCraft:
    ref: CraftRef
    keys: frozenset[str]


@dataclass(frozen=True)
class CraftFamily:
    name: str
    slug: str


@dataclass(frozen=True)
class CraftNames:
    lead: NamedCraft | None
    compared: tuple[NamedCraft, ...]
    index: CraftIndex
    filing: CraftIndex
    places: frozenset[str]
    abroad: PlacesAbroad
    family: CraftFamily | None = None

    @property
    def lead_slug(self) -> str | None:
        return self.lead.ref.slug if self.lead is not None else None

    def researched(self, texts: Sequence[str]) -> list[CraftRef]:
        said = _said(texts)
        return [craft.ref for craft in self._crafts() if craft.keys & said]

    def catalogued(self, texts: Sequence[str]) -> list[CraftRef]:
        own = {target.craft_id for c in self._crafts() if (target := self.index.slugs.get(c.ref.slug))}
        found = {craft_id for text in texts for craft_id in named_craft_ids(self.filing, text)} - own
        return sorted((self.index.refs[i] for i in found if i in self.index.refs), key=lambda ref: ref.slug)

    def abroad_in(self, texts: Sequence[str]) -> tuple[str, ...]:
        return tuple(dict.fromkeys(name for text in texts for name in self.abroad.named_in(text)))

    def places_in(self, texts: Sequence[str]) -> list[str]:
        return sorted(self.places & _said(texts))

    def _crafts(self) -> list[NamedCraft]:
        return [craft for craft in (self.lead, *self.compared) if craft is not None]


def craft_names(
    index: CraftIndex,
    lead: CraftRef | None,
    compared: Sequence[CraftRef] = (),
    *,
    family: CraftFamily | None = None,
    abroad: PlacesAbroad | None = None,
) -> CraftNames:
    others = list({c.slug: c for c in compared if lead is None or c.slug != lead.slug}.values())
    crafts = [craft for craft in (lead, *others) if craft is not None]
    states, places = _register_places()
    local = (places | frozenset(index.places)) - states
    keys = {craft.slug: _keys(craft, crafts, index, local) for craft in crafts}
    shared = {key for key, uses in Counter(k for found in keys.values() for k in found).items() if uses > 1}
    named = {slug: found - shared for slug, found in keys.items()}
    return CraftNames(
        lead=NamedCraft(lead, frozenset(named[lead.slug])) if lead is not None else None,
        compared=tuple(NamedCraft(craft, frozenset(named[craft.slug])) for craft in others),
        index=index,
        filing=filing_index(index),
        places=places | frozenset(index.places),
        abroad=abroad or load_places_abroad(),
        family=family,
    )


async def filing_names(
    session: AsyncSession, store: CraftIndexStore, lead: CraftRef | None, compared: Sequence[CraftRef]
) -> CraftNames:
    index = await store.get(session)
    family = await _shared_family(session, [craft for craft in (lead, *compared) if craft is not None])
    return craft_names(index, lead, compared, family=family)


def filing_index(index: CraftIndex) -> CraftIndex:
    ordinary = _ordinary_words()
    entries = {
        key: kept
        for key, found in index.entries.items()
        if (kept := tuple(entry for entry in found if _names_its_craft(key, entry, ordinary)))
    }
    return CraftIndex(index.refs, index.slugs, entries, index.places, index.craft_places, index.embedded)


def _names_its_craft(key: str, entry: NameEntry, ordinary: frozenset[str]) -> bool:
    if entry.kind == FULL_NAME or len(key.split()) > 1:
        return True
    return script_of(entry.label) not in LATIN_SCRIPTS or key not in ordinary


def _keys(craft: CraftRef, crafts: Sequence[CraftRef], index: CraftIndex, local: frozenset[str]) -> set[str]:
    keys = _anchors(craft, crafts, _common_name_words())
    keys |= set(key_phrases(core_key(craft.name), MAX_NGRAM_TOKENS)) & local
    target = index.slugs.get(craft.slug)
    if target is None:
        return keys
    keys |= {
        key for key, entries in index.entries.items() if any(e.craft_id == target.craft_id for e in entries)
    }
    return keys | (index.craft_places.get(target.craft_id, frozenset()) & local)


def _anchors(craft: CraftRef, crafts: Sequence[CraftRef], common: frozenset[str]) -> set[str]:
    shared = {word for other in crafts if other.slug != craft.slug for word in _words(other.name)}
    return {
        word
        for word in _words(craft.name)
        if len(word) >= ANCHOR_MIN_CHARS and word not in STOP_TOKENS | common | shared
    }


@lru_cache(maxsize=1)
def _common_name_words() -> frozenset[str]:
    uses = Counter(word for master in load_master() for word in set(_words(master.name)))
    return frozenset(word for word, count in uses.items() if count >= COMMON_NAME_USES)


@lru_cache(maxsize=1)
def _ordinary_words() -> frozenset[str]:
    return load_english_words() | _common_name_words()


@lru_cache(maxsize=1)
def _register_places() -> tuple[frozenset[str], frozenset[str]]:
    register = load_district_register()
    states = frozenset(key for name in register.states for key in keys_of(name))
    districts = {key for names in register.districts.values() for name in names for key in keys_of(name)}
    others = {
        key for names in load_district_other_names().values() for name in names for key in keys_of(name)
    }
    return states, frozenset(states | districts | others)


def _said(texts: Sequence[str]) -> set[str]:
    return {phrase for text in texts for phrase in key_phrases(core_key(text), MAX_NGRAM_TOKENS)}


def _words(name: str) -> list[str]:
    return ascii_key(name).split()


async def _shared_family(session: AsyncSession, crafts: Sequence[CraftRef]) -> CraftFamily | None:
    if not crafts:
        return None
    rows = (
        await session.execute(
            select(Craft.slug, CraftCategory.name, CraftCategory.slug.label("category"))
            .join(CraftSubCategory, CraftSubCategory.id == Craft.subCategoryId)
            .join(CraftCategory, CraftCategory.id == CraftSubCategory.categoryId)
            .where(Craft.slug.in_([craft.slug for craft in crafts]))
        )
    ).all()
    families = {CraftFamily(name=row.name, slug=row.category) for row in rows}
    if {row.slug for row in rows} != {craft.slug for craft in crafts} or len(families) != 1:
        return None
    return families.pop()
