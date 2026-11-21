from __future__ import annotations

import re
import uuid
from collections.abc import Iterable
from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from .base import ContractModel, absent, empty
from .component_proposals import ComponentMatch
from .component_specs_general_delivery import CLAIMS_PER_UNIT_MAX, UnitKey
from .crafts import SLUG_MAX_CHARS
from .knowledge_writes import FactProposal
from .layout_proposals import LAYOUT_NOTE_MAX_CHARS
from .monograph_document import SUBJECT_KINDS
from .own_proposals import ComponentProposalBody
from .page_layout import LAYOUT_ENTRIES_MAX, PageLayoutEntry, check_entries
from .page_translations import PageTranslationPart
from .structure_proposals import StructureProposal
from .upload_links import CLAIMS_MAX, SlotDeclaration, UploadStart

__all__ = [
    "ACCEPTED",
    "COMPONENT",
    "FACT",
    "FACT_REF",
    "LAYOUT",
    "LISTED",
    "PAGE_PROPOSAL_SCHEMA_VERSION",
    "PART_KINDS",
    "PART_OUTCOMES",
    "PICTURE",
    "PREVIEW_OUTCOMES",
    "PROPOSAL_OUTCOMES",
    "REFUSED",
    "SHOWN",
    "STRUCTURE",
    "TRANSLATION",
    "FactRef",
    "PageBundle",
    "PageComponent",
    "PageLayoutPart",
    "PagePicture",
    "PagePreviewResult",
    "PageProposalResult",
    "PageSubject",
    "PartReport",
    "fact_index",
]

PAGE_PROPOSAL_SCHEMA_VERSION = 1
FACTS_MAX = 20
STRUCTURE_MAX = 20
COMPONENTS_MAX = 10
PICTURES_MAX = 10
NOTE_MAX_CHARS = 500
FACT, STRUCTURE, COMPONENT, LAYOUT, PICTURE, TRANSLATION = PART_KINDS = (
    "fact",
    "structure",
    "component",
    "layout",
    "picture",
    "translation",
)
ACCEPTED, REFUSED = PROPOSAL_OUTCOMES = ("ACCEPTED", "REFUSED")
SHOWN, LISTED = "SHOWN", "LISTED"
PREVIEW_OUTCOMES = (SHOWN, LISTED, REFUSED)
PART_OUTCOMES = (ACCEPTED, REFUSED, SHOWN, LISTED)
FACT_REF_PATTERN = r"^fact:(\d{1,2})$"
FACT_REF = re.compile(FACT_REF_PATTERN)
SLUG_PATTERN = r"^[A-Za-z0-9-]+$"

FactRef = Annotated[str, Field(pattern=FACT_REF_PATTERN)]
ClaimRef = uuid.UUID | FactRef


def fact_index(ref: str) -> int | None:
    found = FACT_REF.match(ref)
    return None if found is None else int(found.group(1))


class PageSubject(ContractModel):
    kind: Literal[*SUBJECT_KINDS]
    slug: str = Field(min_length=1, max_length=SLUG_MAX_CHARS, pattern=SLUG_PATTERN)


class PageComponent(ContractModel):
    proposal: ComponentProposalBody
    cites: dict[UnitKey, list[FactRef]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _cites_its_own_units(self) -> Self:
        unknown = sorted(set(self.cites) - set(self.proposal.units))
        if unknown:
            raise ValueError(f"cites names units the component does not hold: {', '.join(unknown)}")
        if any(
            len(refs) + len(self.proposal.units[ref].claim_ids) > CLAIMS_PER_UNIT_MAX
            for ref, refs in self.cites.items()
        ):
            raise ValueError(f"a unit cites at most {CLAIMS_PER_UNIT_MAX} facts")
        return self


class PageLayoutPart(ContractModel):
    base_version: int = Field(ge=0)
    entries: list[PageLayoutEntry] = Field(max_length=LAYOUT_ENTRIES_MAX)
    note: str | None = Field(default=None, min_length=1, max_length=LAYOUT_NOTE_MAX_CHARS)

    @model_validator(mode="after")
    def _entries_follow_the_rules(self) -> Self:
        check_entries(self.entries)
        return self


class PagePicture(ContractModel):
    stage_id: uuid.UUID | None = None
    claim_ids: list[ClaimRef] = Field(default_factory=list, max_length=CLAIMS_MAX)
    declaration: SlotDeclaration | None = None
    contribution_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _new_or_given(self) -> Self:
        if self.contribution_id is None and not self.claim_ids:
            raise ValueError("a new picture names the facts it shows (claim_ids)")
        if self.contribution_id is not None and (self.claim_ids or self.declaration or self.stage_id):
            raise ValueError(
                "a picture given already (contribution_id) carries its own facts, stage and declaration"
            )
        return self


class PageBundle(ContractModel):
    schema_version: Literal[1] = PAGE_PROPOSAL_SCHEMA_VERSION
    subject: PageSubject
    facts: list[FactProposal] = Field(default_factory=list, max_length=FACTS_MAX)
    structure: list[StructureProposal] = Field(default_factory=list, max_length=STRUCTURE_MAX)
    components: list[PageComponent] = Field(default_factory=list, max_length=COMPONENTS_MAX)
    layout: PageLayoutPart | None = None
    pictures: list[PagePicture] = Field(default_factory=list, max_length=PICTURES_MAX)
    translation: PageTranslationPart | None = Field(default=None, exclude_if=absent)
    note: str | None = Field(default=None, min_length=1, max_length=NOTE_MAX_CHARS)

    @model_validator(mode="after")
    def _holds_work(self) -> Self:
        held = (self.facts, self.structure, self.components, self.layout, self.pictures, self.translation)
        if not any(held):
            raise ValueError(
                "a page bundle holds at least one fact, structure item, component, layout, picture or "
                "translation"
            )
        named = [ref for component in self.components for refs in component.cites.values() for ref in refs]
        named += _refs(picture.claim_ids for picture in self.pictures)
        beyond = sorted({ref for ref in named if (fact_index(ref) or 0) >= len(self.facts)})
        if beyond:
            raise ValueError(
                f"{', '.join(beyond)} names a fact this bundle does not hold; facts count from fact:0"
            )
        return self


class PartReport(ContractModel):
    part: Literal[*PART_KINDS]
    index: int = Field(ge=0)
    outcome: Literal[*PART_OUTCOMES]
    status: str | None = None
    id: str | None = None
    message: str
    upload: UploadStart | None = None
    matches: list[ComponentMatch] = Field(default_factory=list, exclude_if=empty)
    ways_on: list[str] = Field(default_factory=list, exclude_if=empty)


class PageProposalResult(ContractModel):
    schema_version: Literal[1] = PAGE_PROPOSAL_SCHEMA_VERSION
    subject: PageSubject
    page_url: str
    accepted: int = Field(ge=0)
    refused: int = Field(ge=0)
    parts: list[PartReport]
    message: str


class PagePreviewResult(ContractModel):
    schema_version: Literal[1] = PAGE_PROPOSAL_SCHEMA_VERSION
    subject: PageSubject
    page_url: str
    preview_url: str
    expires_at: datetime
    chapters: list[str]
    components: int = Field(ge=0)
    sources: int = Field(ge=0)
    parts: list[PartReport]
    message: str


def _refs(groups: Iterable[Iterable[uuid.UUID | str]]) -> list[str]:
    return [ref for group in groups for ref in group if isinstance(ref, str)]
