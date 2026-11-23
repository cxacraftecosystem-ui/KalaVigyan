from __future__ import annotations

import re
import uuid
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, overload

from app.research.structure_proposals import (
    ALTERNATIVE,
    BOTANICAL_NAME,
    CONFLICT,
    GLOSSARY_TERM,
    NATIVE_NAME,
    OPEN_QUESTION,
    REACTION,
    STAGE_AFTER,
    STAGE_WHY,
    AlternativeItem,
    BotanicalNameItem,
    ConflictItem,
    GlossaryTermItem,
    NativeNameItem,
    OpenQuestionItem,
    ReactionItem,
    StageAfterItem,
    StageWhyItem,
)

from .curated_category_index import CuratedCategoryPage, IndexCategoryQuestion
from .curated_index import (
    CuratedPage,
    IndexAfter,
    IndexAlternative,
    IndexConflict,
    IndexMaterial,
    IndexNativeName,
    IndexQuestion,
    IndexReaction,
    IndexSpecies,
    IndexStage,
    IndexTerm,
)

__all__ = [
    "OwnerPage",
    "PlacedEntry",
    "current_value",
    "entry_keys",
    "entry_prefix",
    "material_of",
    "next_key",
    "placed_page",
    "stage_of",
    "subject_concept",
    "target_problem",
]

KEY_NUMBER = re.compile(r"^([A-Z])(\d+)$")
OwnerPage = CuratedPage | CuratedCategoryPage
TERM_PREFIX, QUESTION_PREFIX, REACTION_PREFIX = "W", "O", "R"
ENTRY_WIDTH = 2


@dataclass(frozen=True)
class PlacedEntry:
    claim_id: uuid.UUID | None
    key: str | None = None
    concept_id: uuid.UUID | None = None


def stage_of(page: CuratedPage, key: str | None) -> IndexStage | None:
    return next((stage for stage in page.stages if stage.key == key), None)


def material_of(page: OwnerPage, key: str) -> IndexMaterial | None:
    return next((material for material in page.materials if material.key == key), None)


def next_key(prefix: str, taken: Iterable[str], *, width: int = ENTRY_WIDTH) -> str:
    numbers = [
        int(found.group(2)) for found in map(KEY_NUMBER.match, taken) if found and found.group(1) == prefix
    ]
    return f"{prefix}{max(numbers, default=0) + 1:0{width}d}"


def entry_prefix(kind: str) -> str | None:
    return {GLOSSARY_TERM: TERM_PREFIX, OPEN_QUESTION: QUESTION_PREFIX, REACTION: REACTION_PREFIX}.get(kind)


def entry_keys(page: OwnerPage, kind: str) -> list[str]:
    if kind == GLOSSARY_TERM:
        return [term.key for term in page.glossary]
    if kind == OPEN_QUESTION:
        return [question.key for question in page.open_questions]
    return [reaction.key for reaction in page.reactions]


def target_problem(page: OwnerPage, item: Any, *, held: frozenset[uuid.UUID] | None = None) -> str | None:
    if item.kind == CONFLICT:
        return _conflict_problem(page, item, held)
    check = _TARGETS.get(item.kind)
    return None if check is None else check(page, item)


def subject_concept(page: OwnerPage, item: Any, field: str | None) -> uuid.UUID | None:
    if isinstance(page, CuratedPage) and (
        item.kind in (STAGE_AFTER, STAGE_WHY) or (item.kind == REACTION and item.stage_key is not None)
    ):
        stage = stage_of(page, item.stage_key)
        return stage.concept_id if stage is not None else None
    if item.kind in (BOTANICAL_NAME, ALTERNATIVE):
        material = material_of(page, item.material_key)
        return material.concept_id if material is not None else None
    if item.kind == GLOSSARY_TERM or field is None or not isinstance(page, CuratedPage):
        return None
    return page.craft_concepts.get(field)


def current_value(page: OwnerPage, item: Any) -> str | None:
    if item.kind == ALTERNATIVE:
        return _alternatives_now(page, item)
    if not isinstance(page, CuratedPage):
        return None
    if item.kind == STAGE_AFTER:
        stage = stage_of(page, item.stage_key)
        return stage.after.text if stage is not None and stage.after is not None else None
    if item.kind == BOTANICAL_NAME:
        material = material_of(page, item.material_key)
        return material.botanical_name if material is not None else None
    return None


@overload
def placed_page(page: CuratedPage, item: Any, entry: PlacedEntry) -> CuratedPage: ...


@overload
def placed_page(page: CuratedCategoryPage, item: Any, entry: PlacedEntry) -> CuratedCategoryPage: ...


@overload
def placed_page(page: OwnerPage, item: Any, entry: PlacedEntry) -> OwnerPage: ...


def placed_page(page: OwnerPage, item: Any, entry: PlacedEntry) -> OwnerPage:
    place = _PLACES.get(item.kind)
    changed: dict[str, Any] = {} if place is None else place(page, item, entry)
    if (
        isinstance(page, CuratedPage)
        and entry.claim_id is not None
        and entry.claim_id not in page.claim_order
    ):
        changed["claim_order"] = [*page.claim_order, entry.claim_id]
    return page.model_copy(update=changed)


def _stage_problem(page: CuratedPage, item: StageAfterItem | StageWhyItem) -> str | None:
    return None if stage_of(page, item.stage_key) else f"{item.stage_key} is not a stage of this page"


def _reaction_problem(page: CuratedPage, item: ReactionItem) -> str | None:
    if item.stage_key is None or stage_of(page, item.stage_key):
        return None
    return f"{item.stage_key} is not a stage of this page"


def _alternative_problem(page: OwnerPage, item: AlternativeItem) -> str | None:
    material = material_of(page, item.material_key)
    missing = [key for key in (item.material_key, item.alternative_key) if material_of(page, key) is None]
    if missing or material is None:
        return f"{', '.join(missing)} is not a material of this page"
    if item.alternative_key in {other.key for other in material.alternatives}:
        return f"the page already gives {item.alternative_key} as an alternative to {item.material_key}"
    return None


def _alternatives_now(page: OwnerPage, item: AlternativeItem) -> str | None:
    material = material_of(page, item.material_key)
    named = [material_of(page, other.key) for other in (material.alternatives if material else [])]
    return ", ".join(found.name for found in named if found is not None) or None


def _material_problem(page: CuratedPage, item: BotanicalNameItem) -> str | None:
    return (
        None
        if material_of(page, item.material_key)
        else f"{item.material_key} is not a material of this page"
    )


def _name_problem(page: CuratedPage, item: NativeNameItem) -> str | None:
    held = {(name.text.casefold(), name.language) for name in page.native_names}
    if (item.text.casefold(), item.language) in held:
        return f"the page already gives the native name {item.text} in {item.language}"
    return None


def _term_problem(page: CuratedPage, item: GlossaryTermItem) -> str | None:
    if item.term.casefold() in {term.term.casefold() for term in page.glossary}:
        return f"the page's glossary already explains {item.term}"
    return None


def _question_problem(page: CuratedPage, item: OpenQuestionItem) -> str | None:
    if item.question.casefold() in {question.question.casefold() for question in page.open_questions}:
        return "the page already asks this open question"
    return None


def _conflict_problem(page: OwnerPage, item: ConflictItem, held: frozenset[uuid.UUID] | None) -> str | None:
    owned = held if held is not None else frozenset(page.claim_order if isinstance(page, CuratedPage) else ())
    unknown = [str(claim_id) for claim_id in item.claim_ids if claim_id not in owned]
    if unknown:
        return f"a conflict names facts of this page's dossier; these are not: {', '.join(unknown)}"
    if set(item.claim_ids) in [set(conflict.claim_ids) for conflict in page.conflicts]:
        return "the page already shows these facts as a conflict"
    return None


def _after(page: CuratedPage, item: StageAfterItem, entry: PlacedEntry) -> dict[str, Any]:
    after = IndexAfter(text=item.text, colours=list(item.colours), claim_id=_claim(entry))
    return {"stages": _replaced_stage(page, item.stage_key, {"after": after})}


def _why(page: CuratedPage, item: StageWhyItem, entry: PlacedEntry) -> dict[str, Any]:
    return {"stages": _replaced_stage(page, item.stage_key, {"why_claim_id": _claim(entry)})}


def _native_name(page: CuratedPage, item: NativeNameItem, entry: PlacedEntry) -> dict[str, Any]:
    name = IndexNativeName(text=item.text, language=item.language, script=item.script, claim_id=_claim(entry))
    return {"native_names": [*page.native_names, name]}


def _reaction(page: CuratedPage, item: ReactionItem, entry: PlacedEntry) -> dict[str, Any]:
    reaction = IndexReaction(
        key=_key(entry),
        reaction_id=None,
        stage_key=item.stage_key,
        kind=item.reaction_kind,
        reactants=[IndexSpecies(name=s.name, formula=s.formula) for s in item.reactants],
        products=[IndexSpecies(name=s.name, formula=s.formula) for s in item.products],
        claim_ids=[_claim(entry)],
    )
    return {"reactions": [*page.reactions, reaction]}


def _alternative(page: OwnerPage, item: AlternativeItem, entry: PlacedEntry) -> dict[str, Any]:
    added = IndexAlternative(key=item.alternative_key, claim_id=_claim(entry))
    materials = [
        material.model_copy(update={"alternatives": [*material.alternatives, added]})
        if material.key == item.material_key
        else material
        for material in page.materials
    ]
    return {"materials": materials}


def _botanical(page: CuratedPage, item: BotanicalNameItem, entry: PlacedEntry) -> dict[str, Any]:
    claim_id = _claim(entry)
    materials = [
        material.model_copy(
            update={"botanical_name": item.botanical_name, "claim_ids": [*material.claim_ids, claim_id]}
        )
        if material.key == item.material_key
        else material
        for material in page.materials
    ]
    return {"materials": materials}


def _term(page: CuratedPage, item: GlossaryTermItem, entry: PlacedEntry) -> dict[str, Any]:
    if entry.concept_id is None:
        raise ValueError("a glossary term is placed with the concept written for it")
    term = IndexTerm(
        key=_key(entry),
        term_key=None,
        term=item.term,
        names=[item.term],
        meaning=item.meaning,
        language=item.language,
        script=item.script,
        concept_id=entry.concept_id,
        claim_ids=[_claim(entry)],
    )
    return {"glossary": [*page.glossary, term]}


def _conflict(page: CuratedPage, item: ConflictItem, _entry: PlacedEntry) -> dict[str, Any]:
    return {"conflicts": [*page.conflicts, IndexConflict(about=item.about, claim_ids=list(item.claim_ids))]}


def _question(page: OwnerPage, item: OpenQuestionItem, entry: PlacedEntry) -> dict[str, Any]:
    parts = {"key": _key(entry), "question": item.question, "settled_by": item.settled_by}
    if isinstance(page, CuratedCategoryPage):
        asked = IndexCategoryQuestion(**parts, claim_ids=[_claim(entry)], sub_categories=[])
        return {"open_questions": [*page.open_questions, asked]}
    question = IndexQuestion(**parts, claim_ids=[_claim(entry)])
    return {"open_questions": [*page.open_questions, question]}


def _replaced_stage(page: CuratedPage, key: str, update: Mapping[str, Any]) -> list[IndexStage]:
    return [stage.model_copy(update=dict(update)) if stage.key == key else stage for stage in page.stages]


def _claim(entry: PlacedEntry) -> uuid.UUID:
    if entry.claim_id is None:
        raise ValueError("this entry rests on the fact written for it")
    return entry.claim_id


def _key(entry: PlacedEntry) -> str:
    if entry.key is None:
        raise ValueError("a new entry is placed under the key chosen for it")
    return entry.key


_TARGETS: Mapping[str, Callable[[Any, Any], str | None]] = MappingProxyType(
    {
        STAGE_AFTER: _stage_problem,
        STAGE_WHY: _stage_problem,
        REACTION: _reaction_problem,
        BOTANICAL_NAME: _material_problem,
        NATIVE_NAME: _name_problem,
        GLOSSARY_TERM: _term_problem,
        OPEN_QUESTION: _question_problem,
        ALTERNATIVE: _alternative_problem,
    }
)
_PLACES: Mapping[str, Callable[[Any, Any, PlacedEntry], dict[str, Any]]] = MappingProxyType(
    {
        STAGE_AFTER: _after,
        STAGE_WHY: _why,
        NATIVE_NAME: _native_name,
        REACTION: _reaction,
        BOTANICAL_NAME: _botanical,
        GLOSSARY_TERM: _term,
        CONFLICT: _conflict,
        OPEN_QUESTION: _question,
        ALTERNATIVE: _alternative,
    }
)
