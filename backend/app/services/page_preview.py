from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from functools import partial

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInput
from app.models import User
from app.research.component_proposals import SUBJECT_LINK
from app.research.knowledge_writes import FactProposal
from app.research.monograph_document import MonographDocument
from app.research.page_layout import PageLayout
from app.research.page_proposals import (
    COMPONENT,
    FACT,
    LAYOUT,
    LISTED,
    PICTURE,
    REFUSED,
    SECTION,
    SHOWN,
    STRUCTURE,
    PageBundle,
    PageComponent,
    PageLayoutPart,
    PagePicture,
    PagePreviewResult,
    PageSubject,
    PartReport,
)
from app.research.section_proposals import SENTENCES, SectionPart
from app.research.structure_proposals import CONFLICT, StructureProposal

from .component_proposals import CheckedProposal
from .monograph_document import has_authored_content
from .monograph_generated import generated_parts
from .monograph_generated_assembly import assembled_document
from .monograph_generated_drawings import Drawings
from .open_work_subjects import WorkSubject, subject_by_key
from .page_layout_checks import published_missing
from .page_layouts import layout_of, subject_path
from .page_part_checks import PartRun, part_checked
from .page_preview_lifecycle import previewed_link, previewed_withdrawals
from .page_preview_links import preview_path, store_preview
from .page_preview_parts import PreviewDraft, previewed_component
from .page_preview_pictures import given_plates
from .page_proposals_parts import checked_part, component_report, refuse_on
from .page_translation_preview import only_translation, preview_translation, previewed_translation
from .section_proposals import CheckedSection, refusal_message
from .structure_proposals import stated_refusal

__all__ = ["PreviewedPage", "preview_page", "previewed_document"]

AUTHORED = (
    "{slug}'s page is authored and drawn from its stored document, so a bundle cannot be previewed on it: "
    "propose its parts with propose_facts and propose_page."
)
THIN = (
    "With this bundle the page still holds too few published fields to be drawn as a monograph: a craft's "
    "page needs sentences in 3 fields, a family's or category's in 1. Add facts in more fields and preview again."
)
SHOWN_FACT = (
    "Drawn as a sentence of its field's section, citing its sources; the gates read them when it is proposed."
)
SHOWN_STATEMENT = (
    "Drawn as a sentence of its field's section; approval also writes it into the page's structure."
)
LISTED_CONFLICT = "A conflict changes no sentence until a reviewer decides it, so the preview lists it only."
LISTED_NAME = (
    "A name kept out of AI pictures changes no sentence and is never shown, so the preview lists it only."
)
SHOWN_COMPONENT = "Drawn from its spec where the page will draw it once it is registered."
SHOWN_SECTION = (
    "Drawn in place of the {field} section the page publishes now, by the page checklist like the rest: "
    "{said}. The judge reads each sentence against its facts when it is proposed."
)
NO_SPEC = "A component of a page bundle carries its spec, so that it is drawn as delivered."
SHOWN_LAYOUT = "The page is ordered by this layout, as the next version would order it."
LISTED_PICTURE = (
    "A new picture is drawn once its file is given: give it with give_pictures and name it here as "
    "contribution_id to see it in place, or propose_page starts its upload."
)
SHOWN_PICTURE = (
    "Drawn in its place as the page will draw it once an Admin approves it; until then only you see it."
)
READY = (
    "The preview draws the page as the site will once every shown part is accepted. It is private to you "
    "for 24 hours."
)


@dataclass(frozen=True)
class PreviewedPage:
    subject: WorkSubject
    document: MonographDocument
    reports: list[PartReport]


async def preview_page(
    session: AsyncSession, user: User, bundle: PageBundle, *, site: str, now: datetime
) -> PagePreviewResult:
    if only_translation(bundle):
        return await preview_translation(session, user, bundle, site=site, now=now)
    previewed = await previewed_document(session, user, bundle, now=now)
    subject, document, reports = previewed.subject, previewed.document, list(previewed.reports)
    if bundle.translation is not None:
        document, translated = await previewed_translation(session, subject, document, bundle.translation)
        reports += translated
    row, token = await store_preview(session, user, document, now=now)
    return PagePreviewResult(
        subject=PageSubject(kind=subject.kind, slug=subject.slug),
        page_url=f"{site}{subject_path(subject)}",
        preview_url=f"{site}{preview_path(token)}",
        expires_at=row.expiresAt,
        chapters=list(dict.fromkeys(entry.chapter for entry in document.content.layout)),
        components=len(document.content.components),
        sources=len(document.content.sources),
        parts=reports,
        message=READY,
    )


async def previewed_document(
    session: AsyncSession, user: User, bundle: PageBundle, *, now: datetime
) -> PreviewedPage:
    subject = await subject_by_key(session, bundle.subject.kind, bundle.subject.slug)
    if has_authored_content(subject.slug):
        raise InvalidInput(AUTHORED.format(slug=subject.slug))
    draft = PreviewDraft(digest=hashlib.sha256(bundle.model_dump_json().encode("utf-8")).hexdigest())
    run = PartRun(session, user, bundle, subject, draft.facts, now)
    reports = [
        *await _reports(run, draft),
        *await _pictures(run, draft),
        *await previewed_withdrawals(run, draft),
    ]
    parts = await generated_parts(session, subject, draft.additions())
    document = None if parts is None else assembled_document(parts, Drawings())
    if document is None:
        raise InvalidInput(THIN)
    if bundle.layout is None:
        reports += await _published_layout(run, document)
    return PreviewedPage(subject, document, reports)


async def _reports(run: PartRun, draft: PreviewDraft) -> list[PartReport]:
    bundle, session = run.bundle, run.session
    reports: list[PartReport] = []
    for index, fact in enumerate(bundle.facts):
        report = await checked_part(session, FACT, index, partial(_fact, run, draft, index, fact))
        if report.outcome == REFUSED:
            draft.facts.refuse(index)
        reports.append(report)
    for index, item in enumerate(bundle.structure):
        work = partial(_structure, run, draft, index, item)
        reports.append(await checked_part(session, STRUCTURE, index, work))
    for index, component in enumerate(bundle.components):
        work = partial(_component, run, draft, index, component)
        reports.append(await checked_part(session, COMPONENT, index, work))
    if bundle.layout is not None:
        work = partial(_layout, run, draft, bundle.layout)
        reports.append(await checked_part(session, LAYOUT, 0, work))
    for index, section in enumerate(bundle.sections):
        work = partial(_section, run, draft, index, section)
        reports.append(await checked_part(session, SECTION, index, work))
    return reports


async def _pictures(run: PartRun, draft: PreviewDraft) -> list[PartReport]:
    reports: list[PartReport] = []
    for index, picture in enumerate(run.bundle.pictures):
        work = partial(_picture, run, draft, index, picture)
        reports.append(await checked_part(run.session, PICTURE, index, work))
    return reports


async def _picture(run: PartRun, draft: PreviewDraft, index: int, picture: PagePicture) -> PartReport:
    await part_checked(run, PICTURE, index, picture)
    if picture.contribution_id is None:
        return _report(PICTURE, index, LISTED, LISTED_PICTURE)
    draft.pictures += await given_plates(run.session, run.user, run.subject, [picture.contribution_id])
    return _report(PICTURE, index, SHOWN, SHOWN_PICTURE)


async def _fact(run: PartRun, draft: PreviewDraft, index: int, fact: FactProposal) -> PartReport:
    await part_checked(run, FACT, index, fact)
    claim_id = draft.drafted(f"fact:{index}", fact.field, fact.statement, fact.sources)
    draft.facts.keep(index, claim_id, fact)
    return _report(FACT, index, SHOWN, SHOWN_FACT)


async def _structure(run: PartRun, draft: PreviewDraft, index: int, item: StructureProposal) -> PartReport:
    await part_checked(run, STRUCTURE, index, item)
    refuse_on(stated_refusal(item))
    if item.item.kind == CONFLICT:
        return _report(STRUCTURE, index, LISTED, LISTED_CONFLICT)
    if item.field is None or item.statement is None:
        return _report(STRUCTURE, index, LISTED, LISTED_NAME)
    draft.drafted(f"structure:{index}", item.field, item.statement, item.sources)
    return _report(STRUCTURE, index, SHOWN, SHOWN_STATEMENT)


async def _component(run: PartRun, draft: PreviewDraft, index: int, component: PageComponent) -> PartReport:
    checked: CheckedProposal = await part_checked(run, COMPONENT, index, component)
    if checked.refused is not None:
        return component_report(index, checked.refused)
    resolved = checked.draft
    if resolved.extension == SUBJECT_LINK and resolved.extends is not None:
        report = await previewed_link(run.session, run.subject, draft, index, resolved)
    elif checked.delivery is None:
        raise InvalidInput(NO_SPEC)
    else:
        draft.components.append(previewed_component(resolved, checked.delivery))
        report = _report(COMPONENT, index, SHOWN, SHOWN_COMPONENT)
    run.made.add(resolved.label)
    return report


async def _layout(run: PartRun, draft: PreviewDraft, part: PageLayoutPart) -> PartReport:
    await part_checked(run, LAYOUT, 0, part)
    subject = run.subject
    draft.layout = PageLayout(
        subject_kind=subject.kind,
        subject_slug=subject.slug,
        version=part.base_version + 1,
        entries=list(part.entries),
    )
    return _report(LAYOUT, 0, SHOWN, SHOWN_LAYOUT)


async def _section(run: PartRun, draft: PreviewDraft, index: int, part: SectionPart) -> PartReport:
    checked: CheckedSection = await part_checked(run, SECTION, index, part)
    refuse_on(refusal_message(checked.checks))
    draft.written[part.field] = [
        sentence.model_dump(mode="json", by_alias=True) for sentence in part.sentences
    ]
    said = next(check for check in checked.checks if check.check == SENTENCES).reasons[0]
    return _report(SECTION, index, SHOWN, SHOWN_SECTION.format(field=part.field.lower(), said=said))


async def _published_layout(run: PartRun, document: MonographDocument) -> list[PartReport]:
    drawn = {component.label for component in document.content.components}
    published = await layout_of(run.session, run.subject)
    notice = await published_missing(run.session, published, {*drawn, *run.made})
    return [] if notice is None else [_report(LAYOUT, 0, LISTED, notice)]


def _report(part: str, index: int, outcome: str, message: str) -> PartReport:
    return PartReport(part=part, index=index, outcome=outcome, message=message)
