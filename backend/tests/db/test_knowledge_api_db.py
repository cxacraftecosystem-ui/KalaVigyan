import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_engine
from app.core.errors import InvalidInput
from app.models import (
    ArticleSection,
    Claim,
    ClaimSource,
    Concept,
    Craft,
    KnowledgePiece,
    Source,
)
from app.services.craft_finder import find_crafts
from app.services.craft_resolver import CraftIndexStore
from app.services.knowledge_api import craft_facts, craft_section
from app.services.knowledge_export import craft_export, exported_slugs

pytestmark = pytest.mark.db

SITE = "https://kalavigyan.example"
SLUG = "Knowledge-Api-Test-Craft"
CRAFT = uuid.UUID("7a1e0000-0000-4000-8000-000000000001")
ALUM = uuid.UUID("7a1e0000-0000-4000-8000-000000000002")
OPEN_PAPER = uuid.UUID("7a1e0000-0000-4000-8000-000000000010")
SECRET_LETTER = uuid.UUID("7a1e0000-0000-4000-8000-000000000011")
CHEMISTRY = uuid.UUID("7a1e0000-0000-4000-8000-0000000000c1")
HISTORY = uuid.UUID("7a1e0000-0000-4000-8000-0000000000c2")
HIDDEN = uuid.UUID("7a1e0000-0000-4000-8000-0000000000c3")
ALUM_QUOTE = "alum fixes the madder red on cotton"


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async with get_engine().connect() as connection:
        transaction = await connection.begin()
        try:
            opened = AsyncSession(bind=connection, expire_on_commit=False, autoflush=False)
            await _seed(opened)
            yield opened
            await opened.close()
        finally:
            await transaction.rollback()


async def _seed(session: AsyncSession) -> None:
    session.add(Craft(id=CRAFT, name="Knowledge Api Test Craft", slug=SLUG))
    session.add(
        Source(id=OPEN_PAPER, kind="PAPER", title="Alum mordants on cotton", licence="CC-BY-4.0", year=2019)
    )
    session.add(Source(id=SECRET_LETTER, kind="PAPER", title="A restricted letter", sensitivity="RESTRICTED"))
    await session.flush()
    session.add(Concept(id=ALUM, craftId=CRAFT, type="MATERIAL", name="Alum"))
    await session.flush()
    session.add(_claim(CHEMISTRY, "Alum fixes the madder red.", field="CHEMISTRY"))
    session.add(
        _claim(HISTORY, "Printers moved here two centuries ago.", field="HISTORY", fields=["SOCIETY"])
    )
    session.add(_claim(HIDDEN, "A secret measure of alum.", field="CHEMISTRY"))
    await session.flush()
    session.add(_cite(CHEMISTRY, OPEN_PAPER, ALUM_QUOTE))
    session.add(_cite(HISTORY, OPEN_PAPER, None))
    session.add(_cite(HIDDEN, SECRET_LETTER, "weighed by the dyer's own measure"))
    await session.flush()


def _claim(claim_id: uuid.UUID, text: str, **changes: Any) -> Claim:
    return Claim(
        id=claim_id,
        subjectType="CONCEPT",
        subjectId=ALUM,
        predicate="states",
        text=text,
        evidenceLevel="PROVISIONAL",
        origin="IMPORT",
        **changes,
    )


def _cite(claim_id: uuid.UUID, source_id: uuid.UUID, quote: str | None) -> ClaimSource:
    return ClaimSource(
        claimId=claim_id,
        sourceId=source_id,
        quote=quote,
        locator="p. 4" if quote else None,
        quoteCheck="PASS" if quote else "NA",
        relation="DIRECT",
    )


async def test_facts_of_one_field_carry_their_quotes_and_licensed_sources(session: AsyncSession) -> None:
    found = await craft_facts(session, SLUG, site=SITE, field="CHEMISTRY")
    assert [fact.id for fact in found.facts] == [CHEMISTRY]
    (fact,) = found.facts
    assert (fact.field, fact.fields, fact.level) == ("CHEMISTRY", [], "PROVISIONAL")
    assert [(c.source_id, c.quote, c.locator) for c in fact.citations] == [
        (str(OPEN_PAPER), ALUM_QUOTE, "p. 4")
    ]
    assert [(s.id, s.licence, s.year) for s in found.sources] == [(str(OPEN_PAPER), "CC-BY-4.0", 2019)]
    assert found.page_url == f"{SITE}/crafts/{SLUG}"
    assert "KalaVigyan" in found.attribution


async def test_a_secondary_field_finds_a_fact_and_a_restricted_source_never_shows(
    session: AsyncSession,
) -> None:
    society = await craft_facts(session, SLUG, site=SITE, field="SOCIETY")
    assert [(fact.id, fact.field, fact.fields) for fact in society.facts] == [
        (HISTORY, "HISTORY", ["SOCIETY"])
    ]
    every = await craft_facts(session, SLUG, site=SITE)
    assert {fact.id for fact in every.facts} == {CHEMISTRY, HISTORY}
    assert str(SECRET_LETTER) not in {source.id for source in every.sources}


async def test_an_unknown_craft_is_refused_with_the_way_to_find_one(session: AsyncSession) -> None:
    with pytest.raises(InvalidInput, match="find_crafts"):
        await craft_facts(session, "No-Such-Craft-Anywhere", site=SITE)


async def test_a_section_is_null_until_one_is_published(session: AsyncSession) -> None:
    assert (await craft_section(session, SLUG, "CHEMISTRY", site=SITE)).section is None
    sentences = [{"text": "Alum fixes the madder red.", "claimIds": [str(CHEMISTRY)]}]
    session.add(
        ArticleSection(craftId=CRAFT, field="CHEMISTRY", version=1, status="PROPOSED", sentences=sentences)
    )
    await session.flush()
    assert (await craft_section(session, SLUG, "CHEMISTRY", site=SITE)).section is None
    session.add(
        ArticleSection(craftId=CRAFT, field="CHEMISTRY", version=2, status="PUBLISHED", sentences=sentences)
    )
    await session.flush()
    shown = (await craft_section(session, SLUG, "CHEMISTRY", site=SITE)).section
    assert shown is not None
    assert (shown.version, shown.subject_slug, shown.sentences[0].claim_ids) == (2, SLUG, [CHEMISTRY])


async def test_find_crafts_names_the_craft_by_its_name(session: AsyncSession) -> None:
    found = await find_crafts(session, CraftIndexStore(), "Knowledge Api Test Craft", site=SITE)
    assert found.crafts and found.crafts[0].craft.slug == SLUG
    assert found.crafts[0].page_url == f"{SITE}/crafts/{SLUG}"


def _component(label: str, claim_ids: list[uuid.UUID]) -> KnowledgePiece:
    return KnowledgePiece(
        craftId=CRAFT,
        kind="dip_player",
        facet="CHEMISTRY",
        topicKey=f"monograph:{label}",
        language="en",
        depth="EXPERT",
        payload={"monograph": SLUG, "anchor": "#fig1"},
        claimIds=claim_ids,
        sourceIds=[str(OPEN_PAPER)],
        contentHash=label.ljust(64, "0")[:64],
        label=label,
        title="Green from the vat",
        description="An animated vat dip.",
    )


async def test_the_export_holds_every_public_fact_and_only_what_rests_on_them(session: AsyncSession) -> None:
    sentences = [
        {"text": "Alum fixes the madder red.", "claimIds": [str(CHEMISTRY)]},
        {"text": "A secret measure of alum.", "claimIds": [str(HIDDEN)]},
    ]
    session.add(
        ArticleSection(craftId=CRAFT, field="CHEMISTRY", version=1, status="PUBLISHED", sentences=sentences)
    )
    session.add(_component("knowledge-api-test-craft/chemistry/vat-dip", [CHEMISTRY, HIDDEN]))
    session.add(_component("knowledge-api-test-craft/chemistry/secret-measure", [HIDDEN]))
    await session.flush()
    now = datetime(2026, 11, 19, 12, 0, tzinfo=UTC)
    exported = await craft_export(session, SLUG, site=SITE, now=now)
    assert (exported.craft.slug, exported.curation_version, exported.exported_at) == (SLUG, None, now)
    assert {fact.id for fact in exported.facts} == {CHEMISTRY, HISTORY}
    assert [source.id for source in exported.sources] == [str(OPEN_PAPER)]
    (section,) = exported.sections
    assert [(s.text, s.claim_ids) for s in section.sentences] == [("Alum fixes the madder red.", [CHEMISTRY])]
    (component,) = exported.components
    assert (component.label, component.claim_ids) == (
        "knowledge-api-test-craft/chemistry/vat-dip",
        [CHEMISTRY],
    )
    assert component.spec == {"monograph": SLUG, "anchor": "#fig1"}
    assert SLUG in await exported_slugs(session)
