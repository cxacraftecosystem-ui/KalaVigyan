import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInput
from app.models import (
    Chunk,
    ClaimSource,
    Concept,
    Craft,
    CraftCategory,
    CraftSubCategory,
    Source,
    SuppliedSource,
    User,
)
from app.research.evidence import EvidenceItem
from app.research.knowledge_writes import FactProposal
from app.research.supplied_sources import SupplySource
from app.services import supplied_sources
from app.services.fact_proposals import ProposalAdapters, propose_fact
from app.services.review_queue_fact_views import fact_sources
from app.services.supplied_sources_identity import no_lookup

from ..craft_fixtures import unit
from ..knowledge_writes.fakes import FakeEmbedder, FakeFetcher, FakeJudge, page
from .testimony_seed import rolled_back_session

pytestmark = pytest.mark.db

NOW = datetime(2026, 11, 21, 9, tzinfo=UTC)
SLUG = "Supplied-Source-Test-Craft"
DOI = "10.1000/kv.supplied"
CITE = f"https://doi.org/{DOI}"
PASSAGE = "Printers in Dhamadka dip the cloth in the indigo vat four times before it dries in the sun."
QUOTE = "dip the cloth in the indigo vat four times"
STATEMENT = "Ajrakh printers in Dhamadka dip the cloth in the indigo vat four times."


def key(name: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"test-supplied-sources/{name}")


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async for opened in rolled_back_session():
        opened.add(
            CraftCategory(id=key("category"), slug="supplied-test-category", name="Supplied", sortOrder=996)
        )
        await opened.flush()
        opened.add(
            CraftSubCategory(
                id=key("family"),
                slug="supplied-test-family",
                name="Supplied",
                categoryId=key("category"),
                sortOrder=1,
            )
        )
        await opened.flush()
        opened.add(
            Craft(id=key("craft"), slug=SLUG, name="Supplied Source Test Craft", subCategoryId=key("family"))
        )
        await opened.flush()
        opened.add(Concept(id=key("concept"), craftId=key("craft"), type="ARTISAN_ACTION", name="Supplied"))
        await opened.flush()
        yield opened


async def person(session: AsyncSession, role: str = "RESEARCHER") -> User:
    token = uuid.uuid4()
    user = User(
        id=token, name=f"{role.title()} {token.hex[:4]}", email=f"{token.hex[:12]}@example.org", role=role
    )
    session.add(user)
    await session.flush()
    return user


def supplied_draft(**changes: Any) -> SupplySource:
    body: dict[str, Any] = {
        "identity": {"doi": DOI, "title": "Indigo dipping in Kachchh", "authors": ["Meera Shah"]},
        "access": {"how": "SUBSCRIPTION", "accessedOn": "2026-11-20"},
        "passages": [{"text": PASSAGE, "locator": "p. 14"}],
    }
    return SupplySource.model_validate(body | changes)


async def supply(session: AsyncSession, user: User, **changes: Any) -> supplied_sources.Supplied:
    return await supplied_sources.supply_source(
        session, user, supplied_draft(**changes), lookup=no_lookup, now=NOW
    )


def proposal(quote: str = QUOTE, url: str = CITE) -> FactProposal:
    source = {
        "url": url,
        "title": "Indigo dipping in Kachchh",
        "quotes": [{"text": quote, "locator": "p. 14"}],
    }
    body = {
        "subject": {"kind": "craft", "slug": SLUG},
        "field": "PROCESS",
        "statement": STATEMENT,
        "sources": [source],
    }
    return FactProposal.model_validate(body)


def adapters(fetcher: FakeFetcher) -> ProposalAdapters:
    return ProposalAdapters(fetcher=fetcher, embed=FakeEmbedder(unit(1.0)), judge=FakeJudge())


async def test_a_fact_resting_on_supplied_text_passes_its_quotes_without_a_fetch(
    session: AsyncSession,
) -> None:
    researcher = await person(session)
    supplied = await supply(session, researcher)
    fetcher = FakeFetcher({})
    reply = await propose_fact(session, proposal(), researcher, "AGENT", adapters=adapters(fetcher), now=NOW)
    assert fetcher.asked == [] and reply.outcome == "WAITING"
    quotes = reply.gates[0]
    assert quotes.gate == "QUOTES" and quotes.passed
    assert any(f"supplied source {supplied.row.id}" in reason for reason in quotes.reasons)
    assert reply.gates[1].reasons == [f"{CITE} is graded C; licence: no licence stated"]
    (cite,) = await session.scalars(select(ClaimSource).where(ClaimSource.claimId == reply.claim_id))
    assert (cite.quote, cite.locator, cite.chunkId) == (QUOTE, "p. 14", None)
    source = await session.get(Source, cite.sourceId)
    assert source is not None and (source.storage, source.reliability, source.doi) == ("LINK_ONLY", "C", DOI)
    assert list(await session.scalars(select(Chunk.id).where(Chunk.sourceId == source.id))) == []
    await session.refresh(supplied.row)
    assert supplied.row.sourceIds == [source.id]


async def test_the_review_queue_shows_the_fact_rests_on_supplied_text(session: AsyncSession) -> None:
    researcher = await person(session)
    supplied = await supply(session, researcher)
    reply = await propose_fact(
        session, proposal(), researcher, "AGENT", adapters=adapters(FakeFetcher({})), now=NOW
    )
    (shown,) = (await fact_sources(session, [reply.claim_id]))[reply.claim_id]
    assert shown.supplied is not None
    assert (shown.supplied.supplied_source_id, shown.supplied.access, shown.supplied.grade) == (
        supplied.row.id,
        "SUBSCRIPTION",
        "C",
    )
    assert shown.supplied.characters == len(PASSAGE)


async def test_a_quote_missing_from_the_supplied_text_is_refused(session: AsyncSession) -> None:
    researcher = await person(session)
    await supply(session, researcher)
    fetcher = FakeFetcher({})
    quote = "dip the cloth in the madder bath four times"
    reply = await propose_fact(
        session, proposal(quote), researcher, "AGENT", adapters=adapters(fetcher), now=NOW
    )
    assert (reply.outcome, fetcher.asked) == ("REFUSED", [])
    assert reply.gates[0].reasons == [f"quote 1 from {CITE} is not in the text supplied for it"]


async def test_another_account_s_supplied_text_is_never_read(session: AsyncSession) -> None:
    await supply(session, await person(session))
    other = await person(session)
    fetcher = FakeFetcher({CITE: page("A page about something else entirely, with no dipping at all.")})
    reply = await propose_fact(session, proposal(), other, "AGENT", adapters=adapters(fetcher), now=NOW)
    assert fetcher.asked == [CITE] and reply.outcome == "REFUSED"
    assert reply.gates[0].reasons == [f"quote 1 from {CITE} is not in the page as fetched"]


async def test_a_confirmed_work_takes_the_index_s_grade_and_doi(session: AsyncSession) -> None:
    found = EvidenceItem(
        id="openalex:W42",
        adapter="openalex",
        tier="T3",
        source_type="PAPER",
        url=CITE,
        title="Indigo dipping in Kachchh",
        authors=["Meera Shah"],
        published="2019",
        retrieved_at=NOW,
        trust="A",
        doi=DOI,
    )

    async def lookup(identity: Any) -> EvidenceItem:
        return found

    draft = supplied_draft(
        identity={"url": "https://archive.example.org/dipping", "title": "Indigo dipping in Kachchh"}
    )
    made = await supplied_sources.supply_source(session, await person(session), draft, lookup=lookup, now=NOW)
    assert (made.row.citeUrl, made.row.doi, made.row.grade) == (CITE, DOI, "A")
    assert made.row.confirmation is not None and made.row.confirmation["index"] == "openalex"


async def test_an_upload_slot_fills_once_and_closes(session: AsyncSession) -> None:
    researcher = await person(session)
    made = await supply(session, researcher, passages=[], upload="text")
    assert made.slot_token is not None and made.row.state == "AWAITING_FILE"
    filled = await supplied_sources.fill_supplied_slot(session, made.slot_token, PASSAGE.encode(), now=NOW)
    assert (filled.state, filled.characters, filled.slotHash) == ("READY", len(PASSAGE), None)
    with pytest.raises(supplied_sources.UnknownSlot):
        await supplied_sources.fill_supplied_slot(session, made.slot_token, PASSAGE.encode(), now=NOW)
    late = await supply(session, researcher, passages=[], upload="text")
    with pytest.raises(supplied_sources.SuppliedGone, match="expired"):
        await supplied_sources.fill_supplied_slot(
            session, late.slot_token or "", PASSAGE.encode(), now=NOW + timedelta(minutes=31)
        )


async def test_a_source_read_on_a_day_not_yet_come_is_refused(session: AsyncSession) -> None:
    with pytest.raises(InvalidInput, match="has not come yet"):
        await supply(session, await person(session), access={"how": "OWN_COPY", "accessedOn": "2026-11-22"})


async def test_only_its_supplier_and_reviewers_read_a_supplied_text(session: AsyncSession) -> None:
    made = await supply(session, await person(session))
    assert (
        await supplied_sources.own_supplied(session, await person(session, "ADMIN"), made.row.id)
    ).id == made.row.id
    with pytest.raises(InvalidInput, match="No supplied source of yours"):
        await supplied_sources.own_supplied(session, await person(session), made.row.id)
    stored = await session.get(SuppliedSource, made.row.id)
    assert stored is not None and stored.text == PASSAGE and stored.textSha256 is not None
