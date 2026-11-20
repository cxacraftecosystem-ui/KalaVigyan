from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Annotated, Any, Literal, Self

from pydantic import Field, ValidationError, model_validator

from .base import ContractModel
from .knowledge_writes import FactProposal
from .page_proposals import (
    COMPONENTS_MAX,
    FACT_REF_PATTERN,
    FACTS_MAX,
    NOTE_MAX_CHARS,
    PICTURES_MAX,
    STRUCTURE_MAX,
    PageBundle,
    PageComponent,
    PageLayoutPart,
    PagePicture,
    PageProposalResult,
    PageSubject,
    fact_index,
)
from .structure_proposals import StructureProposal

__all__ = [
    "DRAFTS_OPEN_MAX",
    "DRAFT_BYTES_MAX",
    "DRAFT_LIFETIME",
    "DRAFT_PARTS",
    "DRAFT_SCHEMA_VERSION",
    "DRAFT_STATES",
    "LIMITS",
    "OPEN",
    "SUBMITTED",
    "SUPPLIED_PER_DRAFT_MAX",
    "DraftAddition",
    "DraftCounts",
    "DraftPart",
    "DraftParts",
    "DraftPreviewLink",
    "DraftView",
    "PageLists",
    "bundle_problem",
    "draft_bundle",
    "part_summaries",
    "parts_counts",
    "with_added",
    "without",
]

DRAFT_SCHEMA_VERSION = 1
DRAFT_LIFETIME = timedelta(days=14)
DRAFTS_OPEN_MAX = 10
DRAFT_BYTES_MAX = 600_000
SUPPLIED_PER_DRAFT_MAX = 40
LIST_ITEMS_MAX = 12
SUMMARY_CHARS = 140
OPEN, SUBMITTED = DRAFT_STATES = ("OPEN", "SUBMITTED")
FACT, STRUCTURE, COMPONENT, LAYOUT, PICTURE, SUPPLIED = DRAFT_PARTS = (
    "fact",
    "structure",
    "component",
    "layout",
    "picture",
    "supplied_source",
)
STILL_CITED = (
    "fact:{index} is still named by {by}; remove or change that part first, so no part points at a fact "
    "that is gone"
)

ListItem = Annotated[str, Field(min_length=2, max_length=120)]
SignatureRef = Annotated[str, Field(pattern=FACT_REF_PATTERN)] | uuid.UUID


class PageLists(ContractModel):
    mechanisms: list[ListItem] = Field(default_factory=list, max_length=LIST_ITEMS_MAX)
    ambiguous_terms: list[ListItem] = Field(default_factory=list, max_length=LIST_ITEMS_MAX)
    signature: SignatureRef | None = None


class DraftParts(ContractModel):
    facts: list[FactProposal] = Field(default_factory=list, max_length=FACTS_MAX)
    structure: list[StructureProposal] = Field(default_factory=list, max_length=STRUCTURE_MAX)
    components: list[PageComponent] = Field(default_factory=list, max_length=COMPONENTS_MAX)
    layout: PageLayoutPart | None = None
    pictures: list[PagePicture] = Field(default_factory=list, max_length=PICTURES_MAX)
    supplied_sources: list[uuid.UUID] = Field(default_factory=list, max_length=SUPPLIED_PER_DRAFT_MAX)
    lists: PageLists | None = None
    note: str | None = Field(default=None, min_length=1, max_length=NOTE_MAX_CHARS)


class DraftAddition(DraftParts):
    @model_validator(mode="after")
    def _adds_something(self) -> Self:
        if not any(parts_counts(self).model_dump().values()) and self.lists is None and self.note is None:
            raise ValueError(
                "add at least one fact, structure item, component, layout, picture, source or list"
            )
        return self


class DraftCounts(ContractModel):
    facts: int = Field(ge=0)
    structure: int = Field(ge=0)
    components: int = Field(ge=0)
    layout: int = Field(ge=0, le=1)
    pictures: int = Field(ge=0)
    supplied_sources: int = Field(ge=0)


LIMITS = DraftCounts(
    facts=FACTS_MAX,
    structure=STRUCTURE_MAX,
    components=COMPONENTS_MAX,
    layout=1,
    pictures=PICTURES_MAX,
    supplied_sources=SUPPLIED_PER_DRAFT_MAX,
)


class DraftPart(ContractModel):
    part: Literal[*DRAFT_PARTS]
    index: int = Field(ge=0)
    summary: str


class DraftPreviewLink(ContractModel):
    url: str
    expires_at: datetime
    passed: int = Field(ge=0)
    failed: int = Field(ge=0)
    judged: int = Field(ge=0)


class DraftView(ContractModel):
    schema_version: Literal[1] = DRAFT_SCHEMA_VERSION
    draft_id: uuid.UUID
    subject: PageSubject
    state: Literal[*DRAFT_STATES]
    version: int = Field(ge=1)
    updated_at: datetime
    expires_at: datetime
    bytes: int = Field(ge=0)
    bytes_max: int = DRAFT_BYTES_MAX
    counts: DraftCounts
    limits: DraftCounts = LIMITS
    parts: list[DraftPart]
    lists: PageLists | None
    preview: DraftPreviewLink | None
    result: PageProposalResult | None
    draft: DraftParts | None = None
    message: str
    next_step: str


def parts_counts(parts: DraftParts) -> DraftCounts:
    return DraftCounts(
        facts=len(parts.facts),
        structure=len(parts.structure),
        components=len(parts.components),
        layout=int(parts.layout is not None),
        pictures=len(parts.pictures),
        supplied_sources=len(parts.supplied_sources),
    )


def with_added(held: DraftParts, added: DraftAddition) -> DraftParts:
    merged = {
        "facts": [*held.facts, *added.facts],
        "structure": [*held.structure, *added.structure],
        "components": [*held.components, *added.components],
        "layout": added.layout if added.layout is not None else held.layout,
        "pictures": [*held.pictures, *added.pictures],
        "supplied_sources": list(dict.fromkeys([*held.supplied_sources, *added.supplied_sources])),
        "lists": added.lists if added.lists is not None else held.lists,
        "note": added.note if added.note is not None else held.note,
    }
    return _checked(merged)


def without(held: DraftParts, part: str, index: int) -> DraftParts:
    if part == LAYOUT:
        if held.layout is None or index != 0:
            raise ValueError("the draft holds no layout to remove")
        return held.model_copy(update={"layout": None})
    if part == FACT:
        return _without_fact(held, index)
    field = {
        STRUCTURE: "structure",
        COMPONENT: "components",
        PICTURE: "pictures",
        SUPPLIED: "supplied_sources",
    }
    held_list: list[Any] = list(getattr(held, field[part]))
    if not 0 <= index < len(held_list):
        raise ValueError(f"the draft holds no {part} {index}; get_draft lists its parts by index")
    del held_list[index]
    return _checked({**_dumped(held), field[part]: held_list})


def draft_bundle(subject: PageSubject, parts: DraftParts) -> PageBundle:
    return PageBundle(
        subject=subject,
        facts=list(parts.facts),
        structure=list(parts.structure),
        components=list(parts.components),
        layout=parts.layout,
        pictures=list(parts.pictures),
        note=parts.note,
    )


def part_summaries(parts: DraftParts) -> list[DraftPart]:
    listed = [
        *(_part(FACT, n, f"{fact.field}: {fact.statement}") for n, fact in enumerate(parts.facts)),
        *(_part(STRUCTURE, n, _structure_line(item)) for n, item in enumerate(parts.structure)),
        *(_part(COMPONENT, n, _component_line(c)) for n, c in enumerate(parts.components)),
        *(_part(PICTURE, n, _picture_line(picture)) for n, picture in enumerate(parts.pictures)),
        *(_part(SUPPLIED, n, f"supplied source {ident}") for n, ident in enumerate(parts.supplied_sources)),
    ]
    if parts.layout is not None:
        layout = parts.layout
        listed.append(_part(LAYOUT, 0, f"{len(layout.entries)} entries on version {layout.base_version}"))
    return listed


def _without_fact(held: DraftParts, index: int) -> DraftParts:
    if not 0 <= index < len(held.facts):
        raise ValueError(f"the draft holds no fact {index}; get_draft lists its parts by index")
    named = _naming(held, f"fact:{index}")
    if named:
        raise ValueError(STILL_CITED.format(index=index, by=", ".join(named)))
    shift = _shifted(index)
    data = _dumped(held)
    data["facts"] = [fact for n, fact in enumerate(data["facts"]) if n != index]
    for component in data["components"]:
        component["cites"] = {unit: [shift(ref) for ref in refs] for unit, refs in component["cites"].items()}
    for picture in data["pictures"]:
        picture["claim_ids"] = [shift(ref) for ref in picture["claim_ids"]]
    if data.get("lists") and isinstance(data["lists"].get("signature"), str):
        data["lists"]["signature"] = shift(data["lists"]["signature"])
    return _checked(data)


def _naming(held: DraftParts, ref: str) -> list[str]:
    named = [
        f"component {n}" for n, c in enumerate(held.components) if any(ref in r for r in c.cites.values())
    ]
    named += [f"picture {n}" for n, p in enumerate(held.pictures) if ref in [str(c) for c in p.claim_ids]]
    if held.lists is not None and str(held.lists.signature) == ref:
        named.append("the signature fact")
    return named


def _shifted(removed: int) -> Callable[[str], str]:
    def shift(ref: str) -> str:
        found = fact_index(ref)
        return ref if found is None or found < removed else f"fact:{found - 1}"

    return shift


def _dumped(parts: DraftParts) -> dict[str, Any]:
    return parts.model_dump(mode="json", by_alias=False)


def _checked(data: dict[str, Any]) -> DraftParts:
    parts = DraftParts.model_validate(data)
    beyond = sorted(
        {
            ref
            for ref in [*_component_refs(parts), *_picture_refs(parts), *_signature_refs(parts)]
            if (fact_index(ref) or 0) >= len(parts.facts)
        }
    )
    if beyond:
        raise ValueError(
            f"{', '.join(beyond)} names a fact this draft does not hold; facts count from fact:0"
        )
    return parts


def _component_refs(parts: DraftParts) -> list[str]:
    return [ref for component in parts.components for refs in component.cites.values() for ref in refs]


def _picture_refs(parts: DraftParts) -> list[str]:
    return [ref for picture in parts.pictures for ref in picture.claim_ids if isinstance(ref, str)]


def _signature_refs(parts: DraftParts) -> list[str]:
    signature = parts.lists.signature if parts.lists is not None else None
    return [signature] if isinstance(signature, str) else []


def _part(part: str, index: int, summary: str) -> DraftPart:
    short = summary if len(summary) <= SUMMARY_CHARS else summary[: SUMMARY_CHARS - 1].rstrip() + "…"
    return DraftPart(part=part, index=index, summary=short)


def _structure_line(item: StructureProposal) -> str:
    return f"{item.item.kind}: {item.statement or 'a conflict between held facts'}"


def _component_line(component: PageComponent) -> str:
    proposal = component.proposal
    return f"{proposal.kind} {proposal.label}: {proposal.title}"


def _picture_line(picture: PagePicture) -> str:
    if picture.contribution_id is not None:
        return f"picture given as contribution {picture.contribution_id}"
    return f"a new picture of {len(picture.claim_ids)} facts, uploaded when the draft is submitted"


def bundle_problem(subject: PageSubject, parts: DraftParts) -> str | None:
    try:
        draft_bundle(subject, parts)
    except ValidationError as refused:
        return "; ".join(str(problem["msg"]) for problem in refused.errors())
    return None
