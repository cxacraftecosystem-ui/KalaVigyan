import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.curation.checks import default_context
from app.curation.files import CURATION_DIR
from app.data.craft_master_loader import ID_NAMESPACE
from app.models import StructureProposal as ProposalRow, User
from app.research.review_queue import STRUCTURE, QueueApproval
from app.research.structure_proposals import StructureProposal
from app.services import review_queue_decisions as decisions
from app.services.curation_import import IMPORTED, import_path
from app.services.dossier_export import export_dossier
from app.services.structure_proposals import propose_structure

from ..curation.import_support import AJRAKH
from ..knowledge_writes.fakes import FakeFetcher
from ..structure.pages import NAME_QUOTE, PAGE_URL, source
from .structure_seed import NOW, SITE, fetched
from .testimony_seed import rolled_back_session

pytestmark = pytest.mark.db

STATEMENT = "Printers in the delta call the cloth ajrak, after their word for blue."
NEXT_CLAIM = "C161"
NEXT_SOURCE = "S25"


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
    body = StructureProposal.model_validate(
        {
            "subject": {"kind": "craft", "slug": AJRAKH},
            "item": {"kind": "NATIVE_NAME", "text": "Ajrak", "language": "gu"},
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
    row = await session.get(ProposalRow, result.proposal_id)
    assert row is not None and row.claimId == uuid.uuid5(ID_NAMESPACE, f"curation:{AJRAKH}:{NEXT_CLAIM}")
