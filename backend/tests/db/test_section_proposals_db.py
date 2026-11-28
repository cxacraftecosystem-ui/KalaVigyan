import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ArticleSection, Claim, ClaimSource, Concept, SectionProposal, TaskReservation, User
from app.research.article_sections import SectionSentence
from app.research.page_proposals import PageBundle
from app.research.page_report_read import node_text
from app.research.review_queue import QueueApproval, QueueRejection, SectionQueueItem
from app.services.monograph_generated_sections import SectionOwner, publish_section
from app.services.page_preview import preview_page
from app.services.page_preview_links import preview_document
from app.services.page_proposals import PageTools, propose_page
from app.services.review_queue import QueueAdapters, open_review_item
from app.services.review_queue_decisions import ItemRef, approve_item, reject_item
from app.services.review_queue_refresh import decision_owners
from app.services.review_queue_select import QueueScope, queue_count

from ..knowledge_writes.fakes import FakeJudge
from .page_documents_seed import (
    ADMIN,
    ALUM,
    BARE,
    CATEGORY_CLAIM,
    CRAFT,
    CRAFT_CLAIM,
    CRAFT_SLUG,
    CRAFT_TEXT,
    FAMILY_CLAIM,
    PAPER,
    seed,
)
from .testimony_seed import rolled_back_session

pytestmark = pytest.mark.db

NOW = datetime(2026, 11, 28, 10, 0, tzinfo=UTC)
SITE = "https://kalavigyan.example"
RESEARCHER = uuid.UUID("5ec7d000-0000-4000-8000-000000000001")
PROFESSOR = uuid.UUID("5ec7d000-0000-4000-8000-000000000002")
GUM = uuid.UUID("5ec7d000-0000-4000-8000-000000000003")
GUM_CLAIM = uuid.UUID("5ec7d000-0000-4000-8000-0000000000c1")
HISTORY_CLAIM = uuid.UUID("5ec7d000-0000-4000-8000-0000000000c2")
SUBJECT = {"kind": "craft", "slug": CRAFT_SLUG}
TASK = f"SECTION:craft:{CRAFT_SLUG}:CHEMISTRY"
FAMILY_TEXT = "Printers across India print with carved wooden blocks."
CATEGORY_TEXT = "Textile crafts dye, print and weave cloth."
RETOLD = "Alum fixes the red of the madder on the cotton."
RESTATED = [(CRAFT_TEXT, CRAFT_CLAIM), (FAMILY_TEXT, FAMILY_CLAIM), (CATEGORY_TEXT, CATEGORY_CLAIM)]


async def no_turns(_: Any) -> Any:
    raise AssertionError("a section has no transcript")


ADAPTERS = QueueAdapters(objects=None, turns_of=no_turns)


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async for opened in rolled_back_session():
        await seed(opened)
        for user_id, role in ((RESEARCHER, "RESEARCHER"), (PROFESSOR, "PROFESSOR")):
            opened.add(User(id=user_id, name="Section writer", email=f"{user_id.hex}@example.org", role=role))
        opened.add(Concept(id=GUM, craftId=BARE, type="MATERIAL", name="Gum"))
        await opened.flush()
        opened.add_all(
            [
                _claim(GUM_CLAIM, GUM, "Gum thickens the printing paste.", "CHEMISTRY"),
                _claim(
                    HISTORY_CLAIM,
                    None,
                    "Printers in the town have dyed with alum for a long time.",
                    "HISTORY",
                ),
            ]
        )
        await opened.flush()
        for n, claim_id in enumerate((GUM_CLAIM, HISTORY_CLAIM), 7):
            opened.add(
                ClaimSource(
                    claimId=claim_id,
                    sourceId=PAPER,
                    quote=f"alum quote {n}",
                    locator=f"p. {n}",
                    quoteCheck="PASS",
                )
            )
        await opened.flush()
        yield opened


def _claim(claim_id: uuid.UUID, concept: uuid.UUID | None, text: str, field: str) -> Claim:
    return Claim(
        id=claim_id,
        subjectType="CONCEPT",
        subjectId=concept or ALUM,
        predicate="states",
        text=text,
        evidenceLevel="PROVISIONAL",
        origin="IMPORT",
        field=field,
    )


def bundle(sentences: list[tuple[str, uuid.UUID]]) -> PageBundle:
    written = [{"text": text, "claim_ids": [str(claim)]} for text, claim in sentences]
    return PageBundle.model_validate(
        {"subject": SUBJECT, "sections": [{"field": "CHEMISTRY", "sentences": written}]}
    )


def tools(*judges: Any) -> PageTools:
    nothing: Any = None
    return PageTools(
        gates=nothing,
        fetcher=nothing,
        start_picture=nothing,
        spend=spent_nothing,
        origin="AGENT",
        site=SITE,
        judges=judges,
    )


async def spent_nothing(kind: str) -> None:
    return None


async def person(session: AsyncSession, user_id: uuid.UUID) -> User:
    found = await session.get(User, user_id)
    assert found is not None
    return found


async def chemistry(session: AsyncSession) -> list[ArticleSection]:
    rows = await session.scalars(
        select(ArticleSection)
        .where(ArticleSection.craftId == CRAFT, ArticleSection.field == "CHEMISTRY")
        .order_by(ArticleSection.version)
    )
    return list(rows.all())


async def proposed(
    session: AsyncSession, user_id: uuid.UUID, sentences: list[tuple[str, uuid.UUID]], *judges: Any
) -> Any:
    result = await propose_page(
        session, await person(session, user_id), bundle(sentences), tools=tools(*judges), now=NOW
    )
    assert [(part.part, part.index) for part in result.parts] == [("section", 0)]
    return result.parts[0]


async def approved(session: AsyncSession) -> Any:
    report = await proposed(session, RESEARCHER, RESTATED)
    reviewer = await person(session, ADMIN)
    return await approve_item(
        session, ItemRef("SECTIONS", uuid.UUID(str(report.id))), reviewer, QueueApproval(), now=NOW
    )


async def test_a_contributor_s_section_waits_beside_the_published_one_and_changes_nothing_yet(
    session: AsyncSession,
) -> None:
    report = await proposed(session, RESEARCHER, RESTATED)
    assert (report.outcome, report.status) == ("ACCEPTED", "PENDING")
    assert "Stored for review" in report.message and "3 sentences" in report.message
    row = await session.get(SectionProposal, uuid.UUID(str(report.id)))
    assert row is not None and (row.taskKey, row.origin, row.field) == (TASK, "AGENT", "CHEMISTRY")
    assert [check["check"] for check in row.checks] == ["HELD", "FIELD", "SENTENCES", "STATED", "FAITHFUL"]
    assert [(section.version, section.status) for section in await chemistry(session)] == [(1, "PUBLISHED")]
    assert await queue_count(session, "SECTIONS", QueueScope(viewer_id=ADMIN)) == 1
    assert await queue_count(session, "SECTIONS", QueueScope(viewer_id=RESEARCHER)) == 0
    item = await open_review_item(
        session, await person(session, ADMIN), ItemRef("SECTIONS", row.id), adapters=ADAPTERS, now=NOW
    )
    assert isinstance(item, SectionQueueItem)
    review = item.section
    assert [sentence.text for sentence in review.proposed] == [text for text, _ in RESTATED]
    assert [fact.id for sentence in review.proposed for fact in sentence.facts] == [
        claim for _, claim in RESTATED
    ]
    assert [sentence.text for sentence in review.published] == [CRAFT_TEXT]
    assert (review.published_version, review.stale, review.task_key) == (1, None, TASK)
    assert item.proposer is not None and item.proposer.role == "RESEARCHER"


async def test_approval_puts_it_in_place_of_the_published_section_keeps_the_old_one_and_completes_the_task(
    session: AsyncSession,
) -> None:
    session.add(
        TaskReservation(
            taskKey=TASK,
            userId=RESEARCHER,
            reservedAt=NOW - timedelta(hours=1),
            expiresAt=NOW + timedelta(hours=1),
        )
    )
    await session.flush()
    decided = await approved(session)
    assert (decided.kind, decided.status) == ("SECTIONS", "APPROVED")
    old, new = await chemistry(session)
    assert (old.version, old.status, old.sentences) == (
        1,
        "SUPERSEDED",
        [{"text": CRAFT_TEXT, "claimIds": [str(CRAFT_CLAIM)]}],
    )
    assert (new.version, new.status, new.writtenByKind, new.writtenById, new.reviewedById) == (
        2,
        "PUBLISHED",
        "USER",
        RESEARCHER,
        ADMIN,
    )
    assert [sentence["text"] for sentence in new.sentences] == [text for text, _ in RESTATED]
    row = await session.get(SectionProposal, decided.id)
    assert row is not None and row.sectionId == new.id and row.reviewedById == ADMIN
    reservation = await session.scalar(select(TaskReservation).where(TaskReservation.taskKey == TASK))
    assert reservation is not None and reservation.ending == "COMPLETED"


async def test_an_approved_section_is_refreshed_on_its_page_and_kept_by_the_dossier_rebuild(
    session: AsyncSession,
) -> None:
    decided = await approved(session)
    assert CRAFT_SLUG in (await decision_owners(session, decided)).crafts
    rebuilt = [SectionSentence(text=CRAFT_TEXT, claim_ids=[CRAFT_CLAIM])]
    assert await publish_section(session, SectionOwner.craft(CRAFT), "CHEMISTRY", rebuilt) is False
    assert [(section.version, section.status) for section in await chemistry(session)] == [
        (1, "SUPERSEDED"),
        (2, "PUBLISHED"),
    ]


async def test_a_rejection_keeps_the_published_section_and_the_reason(session: AsyncSession) -> None:
    report = await proposed(session, RESEARCHER, RESTATED)
    rejection = QueueRejection(reason="It retells the list without joining the facts.")
    decided = await reject_item(
        session,
        ItemRef("SECTIONS", uuid.UUID(str(report.id))),
        await person(session, ADMIN),
        rejection,
        now=NOW,
    )
    assert decided.status == "REJECTED"
    row = await session.get(SectionProposal, decided.id)
    assert row is not None and row.reviewNote == rejection.reason and row.sectionId is None
    assert [(section.version, section.status) for section in await chemistry(session)] == [(1, "PUBLISHED")]


@pytest.mark.parametrize(
    ("sentences", "check", "said"),
    [
        (
            [
                (CRAFT_TEXT, CRAFT_CLAIM),
                ("Gum thickens the printing paste.", GUM_CLAIM),
                (CATEGORY_TEXT, CATEGORY_CLAIM),
            ],
            "HELD",
            "sentence 2 cites",
        ),
        (
            [
                (CRAFT_TEXT, CRAFT_CLAIM),
                (FAMILY_TEXT, FAMILY_CLAIM),
                ("Printers in the town have dyed with alum for a long time.", HISTORY_CLAIM),
            ],
            "FIELD",
            "a fact of HISTORY, not of CHEMISTRY",
        ),
        (
            [(CRAFT_TEXT, CRAFT_CLAIM), (FAMILY_TEXT, FAMILY_CLAIM)],
            "SENTENCES",
            "the section holds 2 sentences",
        ),
    ],
)
async def test_a_refused_section_is_kept_refused_and_changes_nothing(
    session: AsyncSession, sentences: list[tuple[str, uuid.UUID]], check: str, said: str
) -> None:
    report = await proposed(session, RESEARCHER, sentences)
    assert (report.outcome, report.status) == ("REFUSED", "REFUSED")
    assert f"the {check} check refused the whole section" in report.message and said in report.message
    assert [(section.version, section.status) for section in await chemistry(session)] == [(1, "PUBLISHED")]
    assert await queue_count(session, "SECTIONS", QueueScope(viewer_id=ADMIN)) == 0


async def test_an_unfaithful_sentence_refuses_the_section_with_what_the_judge_found(
    session: AsyncSession,
) -> None:
    reply = {
        "verdicts": [
            {
                "candidate": "sentence-1",
                "newDetails": ["the red of the madder"],
                "specific": True,
                "coveredBy": [],
                "reason": "New.",
            }
        ]
    }
    sentences = [(RETOLD, CRAFT_CLAIM), (FAMILY_TEXT, FAMILY_CLAIM), (CATEGORY_TEXT, CATEGORY_CLAIM)]
    report = await proposed(session, RESEARCHER, sentences, FakeJudge(reply))
    assert report.outcome == "REFUSED"
    assert "the FAITHFUL check refused the whole section" in report.message
    assert "sentence 1 says what its facts do not: the red of the madder" in report.message
    assert [(section.version, section.status) for section in await chemistry(session)] == [(1, "PUBLISHED")]


async def test_a_professor_s_section_is_written_at_once(session: AsyncSession) -> None:
    report = await proposed(session, PROFESSOR, RESTATED)
    assert (report.outcome, report.status) == ("ACCEPTED", "APPROVED")
    assert report.message.startswith("Written at once")
    assert [(section.version, section.status) for section in await chemistry(session)] == [
        (1, "SUPERSEDED"),
        (2, "PUBLISHED"),
    ]
    assert await queue_count(session, "SECTIONS", QueueScope(viewer_id=ADMIN)) == 0


async def test_the_preview_draws_a_bundle_s_section_in_place_of_the_published_one_and_stores_nothing(
    session: AsyncSession,
) -> None:
    sentences = [(RETOLD, CRAFT_CLAIM), (FAMILY_TEXT, FAMILY_CLAIM), (CATEGORY_TEXT, CATEGORY_CLAIM)]
    user = await person(session, RESEARCHER)
    previewed = await preview_page(session, user, bundle(sentences), site=SITE, now=NOW)
    assert [(part.part, part.outcome) for part in previewed.parts] == [("section", "SHOWN")]
    assert "Drawn in place of the chemistry section" in previewed.parts[0].message
    token = previewed.preview_url.rsplit("/", 1)[1]
    document = await preview_document(session, user, token, now=NOW)
    drawn = [node_text(unit["nodes"]) for unit in document["content"]["units"].values()]
    assert any(RETOLD.rstrip(".") in text for text in drawn), drawn
    assert await session.scalar(select(SectionProposal.id)) is None
    assert [(section.version, section.status) for section in await chemistry(session)] == [(1, "PUBLISHED")]
    refused = await preview_page(session, user, bundle(sentences[:2]), site=SITE, now=NOW)
    assert [(part.part, part.outcome) for part in refused.parts] == [("section", "REFUSED")]
    assert refused.parts[0].message.startswith(
        "Not stored for review: the SENTENCES check refused the whole section, as one unit."
    )
