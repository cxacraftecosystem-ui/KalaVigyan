import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.curation.checks import default_context
from app.curation.files import CATEGORIES_DIR_NAME, CURATION_DIR
from app.data.craft_master_loader import ID_NAMESPACE
from app.models import Claim, Craft, CuratedCategory, CuratedCraft, StructureProposal as ProposalRow, User
from app.research.review_queue import STRUCTURE, QueueApproval
from app.research.structure_proposals import StructureProposal
from app.services import review_queue_decisions as decisions
from app.services.category_import import import_category_path
from app.services.curated_category_index import CuratedCategoryPage
from app.services.curated_index import CuratedPage
from app.services.curation_approvals import BEHIND_FILE
from app.services.curation_import import BEHIND, IMPORTED, import_dossier, import_path
from app.services.dossier_export import export_dossier
from app.services.structure_proposals import propose_structure

from ..curation.import_support import AJRAKH, checked
from ..knowledge_writes.fakes import FakeFetcher
from ..structure.pages import NAME_QUOTE, PAGE_URL, source
from .structure_seed import NOW, SITE, fetched
from .testimony_seed import rolled_back_session

pytestmark = pytest.mark.db

STATEMENT = "Printers in the delta call the cloth ajrak, after their word for blue."
NEXT_CLAIM = "C161"
NEXT_SOURCE = "S25"
NATIVE_NAME = {"kind": "NATIVE_NAME", "text": "Ajrak", "language": "gu"}
TERM = {"kind": "GLOSSARY_TERM", "term": "Ajrak", "meaning": "The printed cloth, named for its blue."}
ON_AJRAKH = {"kind": "craft", "slug": AJRAKH}
METAL = "Metal-Craft-Category"
APPROVED_NAME_MISSING = (
    f"{NEXT_CLAIM} (native name, approved 2026-11-20) is held by the database and not by this file"
)
APPROVED_TERM_MISSING = "(glossary term, approved 2026-11-20) is held by the database and not by this file"


@pytest.fixture
async def imported() -> AsyncIterator[tuple[AsyncSession, User, User]]:
    async for opened in rolled_back_session():
        outcome = await import_path(opened, CURATION_DIR / f"{AJRAKH}.json", default_context())
        assert outcome.status == IMPORTED, outcome.problems
        researcher = _person("RESEARCHER")
        professor = _person("PROFESSOR")
        opened.add_all([researcher, professor])
        await opened.flush()
        yield opened, researcher, professor


def _person(role: str) -> User:
    token = uuid.uuid4()
    return User(id=token, name=f"{role.title()} Exporter", email=f"{token.hex[:12]}@example.org", role=role)


async def test_an_approved_native_name_is_exported_in_the_dossier_with_its_fact_and_source(
    imported: tuple[AsyncSession, User, User],
) -> None:
    session, researcher, professor = imported
    proposal_id = await _approved(session, (researcher, professor), ON_AJRAKH, NATIVE_NAME)
    exported = (await export_dossier(session, AJRAKH)).exported.dossier
    assert ("Ajrak", "gu", NEXT_CLAIM) in [
        (name.text, name.language, name.claim_id) for name in exported.native_names
    ]
    claim = exported.claim(NEXT_CLAIM)
    assert (claim.text, claim.discipline, claim.subject.type, claim.hypothesis) == (
        STATEMENT,
        "HISTORY",
        "CRAFT",
        False,
    )
    assert [(quote.source_id, quote.locator, quote.quote) for quote in claim.quotes] == [
        (NEXT_SOURCE, "para 1", NAME_QUOTE)
    ]
    cited = exported.source(NEXT_SOURCE)
    assert (cited.url, cited.language, cited.access, cited.reliability) == (PAGE_URL, "en", "OPEN", "C")
    assert exported.claims[-1].id == NEXT_CLAIM
    row = await session.get(ProposalRow, proposal_id)
    assert row is not None and row.claimId == _ajrakh_claim(NEXT_CLAIM)


async def test_importing_the_older_dossier_keeps_the_approved_name_and_its_fact(
    imported: tuple[AsyncSession, User, User],
) -> None:
    session, researcher, professor = imported
    await _approved(session, (researcher, professor), ON_AJRAKH, NATIVE_NAME)
    outcome = await import_path(session, CURATION_DIR / f"{AJRAKH}.json", default_context())
    assert (outcome.status, outcome.changed, outcome.problems) == (
        BEHIND,
        {},
        (BEHIND_FILE, APPROVED_NAME_MISSING),
    )
    claim = await session.get(Claim, _ajrakh_claim(NEXT_CLAIM), populate_existing=True)
    assert claim is not None and (claim.status, claim.text) == ("APPROVED", STATEMENT)
    assert ("Ajrak", "gu", claim.id) in await _native_names(session)


async def test_the_export_that_holds_the_approved_name_is_imported_and_keeps_it(
    imported: tuple[AsyncSession, User, User],
) -> None:
    session, researcher, professor = imported
    await _approved(session, (researcher, professor), ON_AJRAKH, NATIVE_NAME)
    exported = (await export_dossier(session, AJRAKH)).exported.dossier
    git = checked(AJRAKH).check
    assert git is not None
    outcome = await import_dossier(session, exported, git, digest="1" * 64)
    assert (outcome.status, outcome.problems) == (IMPORTED, ())
    claim = await session.get(Claim, _ajrakh_claim(NEXT_CLAIM), populate_existing=True)
    assert claim is not None and claim.status == "APPROVED"
    assert ("Ajrak", "gu", claim.id) in await _native_names(session)


async def test_importing_the_older_category_dossier_keeps_the_approved_glossary_term(
    imported: tuple[AsyncSession, User, User],
) -> None:
    session, researcher, professor = imported
    path = CURATION_DIR / CATEGORIES_DIR_NAME / f"{METAL}.json"
    assert (await import_category_path(session, path, default_context())).status == IMPORTED
    proposal_id = await _approved(session, (researcher, professor), {"kind": "category", "slug": METAL}, TERM)
    row = await session.get(ProposalRow, proposal_id)
    assert row is not None and row.claimId is not None
    outcome = await import_category_path(session, path, default_context())
    assert (outcome.status, outcome.changed, outcome.problems[0]) == (BEHIND, {}, BEHIND_FILE)
    (missing,) = outcome.problems[1:]
    assert missing.endswith(APPROVED_TERM_MISSING)
    claim = await session.get(Claim, row.claimId, populate_existing=True)
    assert claim is not None and claim.status == "APPROVED"
    stored = await session.scalar(
        select(CuratedCategory.page).where(CuratedCategory.categoryId == row.categoryId)
    )
    page = CuratedCategoryPage.model_validate(stored)
    assert [(term.term, term.claim_ids) for term in page.glossary if term.term == "Ajrak"] == [
        ("Ajrak", [row.claimId])
    ]


async def _approved(
    session: AsyncSession, people: tuple[User, User], subject: dict[str, str], item: dict[str, Any]
) -> uuid.UUID:
    researcher, professor = people
    body = StructureProposal.model_validate(
        {
            "subject": subject,
            "item": item,
            "field": "HISTORY",
            "statement": STATEMENT,
            "sources": [source(NAME_QUOTE)],
        }
    )
    fetcher = FakeFetcher({PAGE_URL: fetched()})
    result = await propose_structure(
        session, researcher, body, context=("CONTRIBUTION", fetcher, SITE), now=NOW
    )
    assert result.status == "PENDING"
    ref = decisions.ItemRef(STRUCTURE, result.proposal_id)
    await decisions.approve_item(session, ref, professor, QueueApproval(), now=NOW)
    return result.proposal_id


def _ajrakh_claim(key: str) -> uuid.UUID:
    return uuid.uuid5(ID_NAMESPACE, f"curation:{AJRAKH}:{key}")


async def _native_names(session: AsyncSession) -> list[tuple[str, str, uuid.UUID]]:
    craft = select(Craft.id).where(Craft.slug == AJRAKH).scalar_subquery()
    page = CuratedPage.model_validate(
        await session.scalar(select(CuratedCraft.page).where(CuratedCraft.craftId == craft))
    )
    return [(name.text, name.language, name.claim_id) for name in page.native_names]
