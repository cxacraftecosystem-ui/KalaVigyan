from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any, Literal, Self

from pydantic import Field, model_validator
from pydantic.json_schema import DEFAULT_REF_TEMPLATE, GenerateJsonSchema, JsonSchemaMode

from app.research.component_proposals import SUBJECT_LINK
from app.research.knowledge_writes import FactProposal
from app.research.monograph_document import SUBJECT_KINDS
from app.research.page_drafts import DRAFT_PARTS, SUPPLIED_PER_DRAFT_MAX, DraftAddition, PageLists
from app.research.page_proposals import (
    COMPONENTS_MAX,
    FACTS_MAX,
    NOTE_MAX_CHARS,
    PICTURES_MAX,
    STRUCTURE_MAX,
    PageBundle,
    PageComponent,
    PageLayoutPart,
    PagePicture,
    PageSubject,
)
from app.research.structure_proposals import StructureProposal

from .mcp_studio_arguments import StudioArguments
from .mcp_tool_base import Arguments

__all__ = [
    "NEEDS_SPEC",
    "ONE_PAGE",
    "ONE_WORK",
    "DraftAdd",
    "DraftRemoval",
    "EditDraft",
    "PageWork",
    "bundle_parts",
    "bundle_schema",
    "undelivered",
]

FACT = "fact"
BUNDLE = (
    "One page's parts: subject {kind, slug} and any of facts, structure, components ({proposal, cites}), "
    "layout {base_version, entries}, pictures and a note, each part exactly as edit_draft's add takes it "
    "(its input schema holds every part's fields), and translation; one part alone works"
)
NEEDS_SPEC = (
    "a component is delivered finished: give its spec (the kind's spec data) and the units it places, each "
    "unit's text with the ids of the facts it rests on; only a SUBJECT_LINK carries none"
)
ONE_PAGE = "name the draft by its page's subject or by its draft_id, one of them"
ONE_WORK = "give a bundle or a draft_id, one of them"
REMOVALS_MAX = 20


def undelivered(components: Sequence[PageComponent]) -> str | None:
    for index, component in enumerate(components):
        proposal = component.proposal
        if proposal.spec is None and proposal.extension != SUBJECT_LINK:
            return f"component {index}: {NEEDS_SPEC}"
    return None


def bundle_parts(bundle: PageBundle) -> int:
    held = (bundle.facts, bundle.structure, bundle.components, bundle.pictures)
    translated = 0 if bundle.translation is None else len(bundle.translation.passages)
    return sum(len(part) for part in held) + int(bundle.layout is not None) + translated


class DraftAdd(Arguments):
    facts: list[FactProposal] = Field(
        default_factory=list,
        max_length=FACTS_MAX,
        description="Facts, each {subject {kind, slug}, field, statement, sources, task_key}",
    )
    structure: list[StructureProposal] = Field(
        default_factory=list,
        max_length=STRUCTURE_MAX,
        description="Structure items as propose_structure takes them",
    )
    components: list[PageComponent] = Field(
        default_factory=list,
        max_length=COMPONENTS_MAX,
        description="Finished components and figures, each {proposal, cites}; cites names facts as fact:0 and on",
    )
    layout: PageLayoutPart | None = Field(default=None, description="The page's layout; replaces the draft's")
    pictures: list[PagePicture] = Field(
        default_factory=list,
        max_length=PICTURES_MAX,
        description="{contribution_id} for one given with give_pictures, or a new {claim_ids, declaration}",
    )
    supplied_sources: list[uuid.UUID] = Field(
        default_factory=list, max_length=SUPPLIED_PER_DRAFT_MAX, description="Ids from supply_source"
    )
    note: str | None = Field(default=None, min_length=1, max_length=NOTE_MAX_CHARS)

    @model_validator(mode="after")
    def _delivered(self) -> Self:
        problem = undelivered(self.components)
        if problem is not None:
            raise ValueError(problem)
        return self

    def holds(self) -> bool:
        listed = (self.facts, self.structure, self.components, self.pictures, self.supplied_sources)
        return any(listed) or self.layout is not None or self.note is not None


class DraftRemoval(Arguments):
    part: Literal[*DRAFT_PARTS] = Field(description=f"One of {', '.join(DRAFT_PARTS)}")
    index: int = Field(ge=0, description="The part's index, as the draft lists it")


class EditDraft(StudioArguments):
    subject: PageSubject | None = Field(
        default=None,
        description="The page {kind craft, family or category, slug}; its open draft, or a new one",
    )
    draft_id: uuid.UUID | None = Field(default=None, description="Or a draft's id, a submitted one too")
    add: DraftAdd | None = Field(default=None, description="Parts to add")
    remove: list[DraftRemoval] = Field(
        default_factory=list, max_length=REMOVALS_MAX, description="Parts to remove, by kind and index"
    )
    lists: PageLists | None = Field(
        default=None,
        description=(
            "The page's own lists, derived first: mechanisms, ambiguous_terms and the signature fact "
            "(fact:N of this draft, or a stored fact's id); replaces the draft's"
        ),
    )

    @model_validator(mode="after")
    def _one_page(self) -> Self:
        if (self.subject is None) == (self.draft_id is None):
            raise ValueError(ONE_PAGE)
        return self

    def changes(self) -> bool:
        return bool(self.remove) or self.lists is not None or (self.add is not None and self.add.holds())

    def removals(self) -> list[tuple[str, int]]:
        ordered = sorted(self.remove, key=lambda item: (item.part == FACT, -item.index))
        return [(item.part, item.index) for item in ordered]

    def addition(self) -> DraftAddition | None:
        given = self.add.model_dump(exclude_none=True) if self.add is not None and self.add.holds() else {}
        if not given and self.lists is None:
            return None
        return DraftAddition.model_validate({**given, "lists": self.lists})


def _parts(most: int) -> dict[str, Any]:
    return {"type": "array", "items": {"type": "object"}, "maxItems": most}


def bundle_schema() -> dict[str, Any]:
    subject = {
        "type": "object",
        "properties": {"kind": {"type": "string", "enum": list(SUBJECT_KINDS)}, "slug": {"type": "string"}},
        "required": ["kind", "slug"],
    }
    parts = {
        "facts": _parts(FACTS_MAX),
        "structure": _parts(STRUCTURE_MAX),
        "components": _parts(COMPONENTS_MAX),
        "layout": {"type": "object"},
        "pictures": _parts(PICTURES_MAX),
        "translation": {"type": "object"},
        "note": {"type": "string", "maxLength": NOTE_MAX_CHARS},
    }
    return {
        "type": ["object", "null"],
        "description": BUNDLE,
        "properties": {"subject": subject, **parts},
        "required": ["subject"],
        "additionalProperties": False,
    }


class PageWork(StudioArguments):
    bundle: PageBundle | None = Field(default=None, description=BUNDLE)
    draft_id: uuid.UUID | None = Field(default=None, description="Or an open draft's id, from edit_draft")

    @model_validator(mode="after")
    def _one_work(self) -> Self:
        if (self.bundle is None) == (self.draft_id is None):
            raise ValueError(ONE_WORK)
        problem = None if self.bundle is None else undelivered(self.bundle.components)
        if problem is not None:
            raise ValueError(problem)
        return self

    @classmethod
    def model_json_schema(
        cls,
        by_alias: bool | None = None,
        ref_template: str = DEFAULT_REF_TEMPLATE,
        schema_generator: type[GenerateJsonSchema] = GenerateJsonSchema,
        mode: JsonSchemaMode = "validation",
        *,
        union_format: Literal["any_of", "primitive_type_array"] = "any_of",
    ) -> dict[str, Any]:
        schema = super().model_json_schema(
            by_alias, ref_template, schema_generator, mode, union_format=union_format
        )
        schema.pop("$defs", None)
        return {**schema, "properties": {**schema["properties"], "bundle": bundle_schema()}}
