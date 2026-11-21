from __future__ import annotations

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInput
from app.models import User
from app.research.monograph_document import MonographDocument
from app.research.page_proposals import (
    REFUSED,
    SHOWN,
    TRANSLATION,
    PageBundle,
    PagePreviewResult,
    PageSubject,
    PartReport,
)
from app.research.page_translation_gates import GateInput, refusal, translation_checks
from app.research.page_translation_texts import NO_PAGE, NO_PASSAGE
from app.research.page_translation_variant import ServedTranslations
from app.research.page_translations import PageTranslationPart, PassageTranslation, task_problem
from app.research.translation_passages import is_translatable, passage_leaves, unit_hash
from app.research.vocabulary import ANSWER_LANGUAGE_SPECS

from .open_work_subjects import WorkSubject, subject_by_key
from .page_english import english_page
from .page_layouts import subject_path
from .page_preview_links import preview_path, store_preview
from .page_translation_serving import variant_body
from .page_translation_store import served_translations

__all__ = ["SHOWN_PASSAGE", "only_translation", "preview_translation", "previewed_translation"]

SHOWN_PASSAGE = (
    "Drawn in place on the {language} page as it will be once accepted; the passages not yet translated show "
    "in English, marked as English."
)
REFUSED_PASSAGE = "Would be refused: the {check} check. {reason}"
NOTHING_SHOWN = "No passage of this translation passes its checks, so the preview draws the English page."
READY = "The preview draws the page in {language} as the site will once the shown passages are accepted."


def only_translation(bundle: PageBundle) -> bool:
    others = (bundle.facts, bundle.structure, bundle.components, bundle.layout, bundle.pictures)
    return bundle.translation is not None and not any(others)


async def preview_translation(
    session: AsyncSession, user: User, bundle: PageBundle, *, site: str, now: datetime
) -> PagePreviewResult:
    part = bundle.translation
    if part is None:
        raise InvalidInput(NO_PAGE)
    subject = await subject_by_key(session, bundle.subject.kind, bundle.subject.slug)
    english = await english_page(session, (subject.kind, subject.slug))
    if english is None:
        raise InvalidInput(NO_PAGE)
    document, reports = await previewed_translation(session, subject, english.document, part)
    row, token = await store_preview(session, user, document, now=now)
    shown = any(report.outcome == SHOWN for report in reports)
    return PagePreviewResult(
        subject=PageSubject(kind=subject.kind, slug=subject.slug),
        page_url=f"{site}{subject_path(subject)}",
        preview_url=f"{site}{preview_path(token)}",
        expires_at=row.expiresAt,
        chapters=list(dict.fromkeys(entry.chapter for entry in document.content.layout)),
        components=len(document.content.components),
        sources=len(document.content.sources),
        parts=reports,
        message=READY.format(language=ANSWER_LANGUAGE_SPECS[part.language].label) if shown else NOTHING_SHOWN,
    )


async def previewed_translation(
    session: AsyncSession, subject: WorkSubject, document: MonographDocument, part: PageTranslationPart
) -> tuple[MonographDocument, list[PartReport]]:
    problem = task_problem(part.task_key, (subject.kind, subject.slug), part.language)
    if problem is not None:
        return document, [_report(index, REFUSED, problem) for index in range(len(part.passages))]
    reports = [
        _checked(document, index, passage, part.language) for index, passage in enumerate(part.passages)
    ]
    passing = {
        passage.source_hash: tuple(passage.texts)
        for passage, report in zip(part.passages, reports, strict=True)
        if report.outcome == SHOWN
    }
    if not passing:
        return document, reports
    stored = await served_translations(session, (subject.kind, subject.slug), part.language)
    served = ServedTranslations(
        by_hash={**stored.by_hash, **passing}, earlier=stored.earlier, digest=stored.digest
    )
    body = document.model_dump(mode="json", by_alias=True)
    variant = variant_body(body, document.content, served, part.language)
    return (document if variant is None else MonographDocument.model_validate(variant)), reports


def _checked(
    document: MonographDocument, index: int, passage: PassageTranslation, language: str
) -> PartReport:
    unit = document.content.units.get(passage.key)
    if unit is None or not is_translatable(passage.key, unit.nodes):
        return _report(index, REFUSED, NO_PASSAGE.format(key=passage.key))
    given = GateInput(
        leaves=passage_leaves(unit.nodes),
        current_hash=unit_hash(unit.nodes, unit.claim_ids),
        given_hash=passage.source_hash,
        texts=passage.texts,
        language=language,
    )
    failed = refusal(translation_checks(given))
    if failed is not None:
        return _report(index, REFUSED, REFUSED_PASSAGE.format(check=failed.check, reason=failed.reasons[0]))
    return _report(index, SHOWN, SHOWN_PASSAGE.format(language=ANSWER_LANGUAGE_SPECS[language].label))


def _report(index: int, outcome: str, message: str) -> PartReport:
    return PartReport(part=TRANSLATION, index=index, outcome=outcome, message=message)
