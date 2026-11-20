from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.curation.dossier import CATEGORY_SCOPE, Dossier, parse_dossier
from app.curation.files import CATEGORIES_DIR_NAME, CURATION_DIR, category_paths, dossier_paths
from app.models import Craft, CraftCategory
from app.research.article_sections import SectionSentence

from . import knowledge_view
from .curation_keys import HYPOTHESIS_LEVEL, curated_id
from .knowledge_view import ClaimView
from .monograph_document import has_authored_content
from .monograph_generated_sections import SectionOwner, publish_section, retire_sections

__all__ = ["SectionsReport", "dossier_sections", "publish_curated_sections", "publish_dossier_sections"]


@dataclass
class SectionsReport:
    written: dict[str, int] = field(default_factory=dict)
    unchanged: list[str] = field(default_factory=list)
    waiting: list[str] = field(default_factory=list)
    refused: dict[str, str] = field(default_factory=dict)

    def summary(self) -> dict[str, Any]:
        return {
            "written": self.written,
            "unchanged": len(self.unchanged),
            "waiting": self.waiting,
            "refused": self.refused,
        }


def dossier_sections(
    dossier: Dossier, shown: Mapping[uuid.UUID, ClaimView]
) -> dict[str, list[SectionSentence]]:
    sections: dict[str, list[SectionSentence]] = {}
    for claim in dossier.claims:
        claim_id = curated_id(dossier.slug, claim.id)
        view = shown.get(claim_id)
        if view is None or view.level == HYPOTHESIS_LEVEL or not view.citations:
            continue
        sentence = SectionSentence(text=view.text, claim_ids=[claim_id])
        sections.setdefault(claim.discipline, []).append(sentence)
    return sections


async def publish_dossier_sections(session: AsyncSession, dossier: Dossier, owner: SectionOwner) -> int:
    if has_authored_content(dossier.slug):
        return 0
    shown, _ = await knowledge_view.claims_by_id(
        session, [curated_id(dossier.slug, claim.id) for claim in dossier.claims]
    )
    sections = dossier_sections(dossier, shown)
    written = 0
    for discipline, sentences in sections.items():
        written += await publish_section(session, owner, discipline, sentences)
    retired = await retire_sections(session, owner, sections)
    if written:
        await session.flush()
    return written + len(retired)


async def publish_curated_sections(session: AsyncSession, *, directory: Path | None = None) -> SectionsReport:
    report = SectionsReport()
    folder = directory or CURATION_DIR
    for path in [*dossier_paths(folder), *category_paths(folder)]:
        name = f"{CATEGORIES_DIR_NAME}/{path.name}" if path.parent.name == CATEGORIES_DIR_NAME else path.name
        try:
            dossier = parse_dossier(path.read_bytes().decode("utf-8"))
        except (UnicodeDecodeError, ValidationError) as error:
            report.refused[name] = str(error).splitlines()[0]
            continue
        owner = await _owner(session, dossier)
        if owner is None:
            report.waiting.append(name)
            continue
        changed = await publish_dossier_sections(session, dossier, owner)
        if changed:
            report.written[name] = changed
        else:
            report.unchanged.append(name)
    return report


async def _owner(session: AsyncSession, dossier: Dossier) -> SectionOwner | None:
    if dossier.scope == CATEGORY_SCOPE:
        category = await session.scalar(select(CraftCategory.id).where(CraftCategory.slug == dossier.slug))
        return None if category is None else SectionOwner.category(category)
    craft = await session.scalar(select(Craft.id).where(Craft.slug == dossier.slug))
    return None if craft is None else SectionOwner.craft(craft)
