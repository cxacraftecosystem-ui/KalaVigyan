from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ExternalFailure, InvalidInput, Refused
from app.research.component_proposals import ComponentProposalDraft, proposal_crafts
from app.research.knowledge_writes import FactProposal
from app.research.page_proposals import (
    ACCEPTED,
    REFUSED,
    PageBundle,
    PageComponent,
    PagePicture,
    PageSubject,
    PartReport,
    fact_index,
)
from app.research.structure_proposals import StructureProposal

from .open_work_subjects import WorkSubject

__all__ = [
    "CHECKS_UNAVAILABLE",
    "BundleFacts",
    "accepted",
    "checked_part",
    "fact_subject_problem",
    "keyed_problem",
    "known_texts",
    "picture_claims",
    "refuse_on",
    "refused",
    "resolved_claims",
    "resolved_component",
    "structure_subject_problem",
]

CHECKS_UNAVAILABLE = (
    "The checks could not run just now and nothing was stored for this part; send it again later."
)
OTHER_PAGE = "{part} {index} names {named}, not this bundle's page {page}: a bundle builds one page."
NOT_A_CRAFT = (
    "Structure belongs to a craft's curated page; a category's bundle carries facts, components and layout."
)
NOT_KEYED = (
    "Component {index} is keyed to another craft: key it to {slug} with craft_slug or a CRAFT subject."
)
REFUSED_FACT = (
    "{ref} was refused, so what cites it cannot rest on it; fix that fact and send the bundle again."
)
CATEGORY = "category"

Work = Callable[[], Awaitable[PartReport]]


class BundleFacts:
    def __init__(self) -> None:
        self.ids: dict[int, uuid.UUID] = {}
        self.texts: dict[uuid.UUID, list[str]] = {}
        self.refused: set[int] = set()

    def keep(self, index: int, claim_id: uuid.UUID, proposal: FactProposal) -> None:
        self.ids[index] = claim_id
        self.texts[claim_id] = [proposal.statement, *(q.text for s in proposal.sources for q in s.quotes)]

    def refuse(self, index: int) -> None:
        self.refused.add(index)


async def checked_part(session: AsyncSession, part: str, index: int, work: Work) -> PartReport:
    try:
        async with session.begin_nested():
            return await work()
    except (InvalidInput, Refused) as problem:
        message = problem.message if isinstance(problem, Refused) else str(problem)
        return PartReport(part=part, index=index, outcome=REFUSED, message=message)
    except ExternalFailure:
        return PartReport(part=part, index=index, outcome=REFUSED, message=CHECKS_UNAVAILABLE)


def accepted(part: str, index: int, *, status: str | None, ident: Any, message: str) -> PartReport:
    return PartReport(part=part, index=index, outcome=ACCEPTED, status=status, id=str(ident), message=message)


def refused(part: str, index: int, *, status: str | None, ident: Any, message: str) -> PartReport:
    shown = None if ident is None else str(ident)
    return PartReport(part=part, index=index, outcome=REFUSED, status=status, id=shown, message=message)


def fact_subject_problem(
    bundle: PageBundle, subject: WorkSubject, index: int, fact: FactProposal
) -> str | None:
    wanted = CATEGORY if bundle.subject.kind == CATEGORY else "craft"
    if fact.subject.kind == wanted and _same_slug(fact.subject.slug, bundle.subject, subject):
        return None
    return OTHER_PAGE.format(part="Fact", index=index, named=fact.subject.slug, page=subject.slug)


def structure_subject_problem(
    bundle: PageBundle, subject: WorkSubject, index: int, item: StructureProposal
) -> str | None:
    if bundle.subject.kind == CATEGORY:
        return NOT_A_CRAFT
    if _same_slug(item.subject.slug, bundle.subject, subject):
        return None
    return OTHER_PAGE.format(part="Structure item", index=index, named=item.subject.slug, page=subject.slug)


def keyed_problem(
    bundle: PageBundle, subject: WorkSubject, index: int, draft: ComponentProposalDraft
) -> str | None:
    if bundle.subject.kind == CATEGORY:
        return None
    if any(_same_slug(slug, bundle.subject, subject) for slug in proposal_crafts(draft)):
        return None
    return NOT_KEYED.format(index=index, slug=subject.slug)


def resolved_component(component: PageComponent, facts: BundleFacts) -> ComponentProposalDraft:
    units: dict[str, Any] = {}
    for ref, unit in component.proposal.units.items():
        extra = resolved_claims(component.cites.get(ref, []), facts)
        units[ref] = {"text": unit.text, "claimIds": [*unit.claim_ids, *extra]}
    values = component.proposal.model_dump(mode="json", by_alias=False, exclude={"units"})
    return ComponentProposalDraft.model_validate({**values, "units": units})


def resolved_claims(refs: Sequence[uuid.UUID | str], facts: BundleFacts) -> list[uuid.UUID]:
    found: list[uuid.UUID] = []
    for ref in refs:
        if isinstance(ref, uuid.UUID):
            found.append(ref)
            continue
        index = fact_index(ref)
        if index is None or index in facts.refused or index not in facts.ids:
            raise InvalidInput(REFUSED_FACT.format(ref=ref))
        found.append(facts.ids[index])
    return list(dict.fromkeys(found))


def picture_claims(picture: PagePicture, facts: BundleFacts) -> list[uuid.UUID]:
    return resolved_claims(picture.claim_ids, facts)


def known_texts(facts: BundleFacts, draft: ComponentProposalDraft) -> Mapping[uuid.UUID, list[str]]:
    cited = {claim for unit in draft.units.values() for claim in unit.claim_ids}
    return {claim: texts for claim, texts in facts.texts.items() if claim in cited}


def refuse_on(problem: str | None) -> None:
    if problem is not None:
        raise InvalidInput(problem)


def _same_slug(slug: str, page: PageSubject, subject: WorkSubject) -> bool:
    return slug.casefold() in {page.slug.casefold(), subject.slug.casefold()}
