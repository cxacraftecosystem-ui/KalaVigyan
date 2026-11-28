import base64
import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ComponentProposal, LayoutProposal, PageProposal, User
from app.research.monograph_document import MonographDocument
from app.research.page_proposal_review import PageDecisionBody
from app.research.page_proposals import PageBundle
from app.research.page_render import RenderedImage, RenderRequest, RenderResult, RenderUnmade
from app.services.contribution_queue_tasks import my_tasks
from app.services.page_preview import preview_page
from app.services.page_proposal_decisions import decide_page
from app.services.page_proposal_drawings import draw_side
from app.services.page_proposal_pictures import drawn_picture, keep_drawn_pictures
from app.services.page_proposal_records import page_snapshot, record_page_proposal
from app.services.page_proposal_reviews import open_page_proposals, page_proposal, proposal_document
from app.services.page_proposals import propose_page
from app.services.review_queue_errors import NotYourQueue, OwnItem

from .page_documents_seed import seed
from .test_page_bundles_db import NOW, SITE, SUBJECT, component, tools
from .testimony_seed import rolled_back_session

pytestmark = pytest.mark.db

MAKER = uuid.UUID("9e3a0000-0000-4000-8000-000000000001")
ADMIN = uuid.UUID("9e3a0000-0000-4000-8000-000000000002")
LABEL = "page-docs-test-craft/chemistry/alum-print-table"
JPEG = base64.b64encode(b"\xff\xd8\xff\xe0 a drawn page").decode("ascii")
NOTE = "The layout leaves the chemistry chapter without its table."


def shot(name: str) -> RenderedImage:
    return RenderedImage(name=name, caption=f"{name} as drawn", width=390, height=844, data=JPEG)


class Renderer:
    def __init__(self, outcome: RenderResult | RenderUnmade) -> None:
        self.outcome = outcome
        self.asked: list[RenderRequest] = []

    async def render(self, request: RenderRequest) -> RenderResult | RenderUnmade:
        self.asked.append(request)
        return self.outcome


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async for opened in rolled_back_session():
        await seed(opened)
        opened.add(User(id=MAKER, name="Page maker", email=f"{MAKER.hex}@example.org", role="RESEARCHER"))
        opened.add(User(id=ADMIN, name="Page reviewer", email=f"{ADMIN.hex}@example.org", role="ADMIN"))
        await opened.flush()
        yield opened


async def person(session: AsyncSession, user_id: uuid.UUID) -> User:
    found = await session.get(User, user_id)
    assert found is not None
    return found


def bundle() -> PageBundle:
    return PageBundle.model_validate(
        {
            "subject": SUBJECT,
            "components": [{**component(LABEL), "cites": {}}],
            "layout": {"baseVersion": 0, "entries": []},
        }
    )


async def proposed(session: AsyncSession, *, drawn: bool) -> PageProposal:
    maker = await person(session, MAKER)
    previewed = await preview_page(session, maker, bundle(), site=SITE, now=NOW)
    if drawn:
        await keep_drawn_pictures(session, maker, previewed.preview_url, [shot("first-screen-390")], now=NOW)
    snapshot = await page_snapshot(session, maker, bundle(), now=NOW)
    result = await propose_page(session, maker, bundle(), tools=tools(), now=NOW)
    row = await record_page_proposal(session, maker, (bundle(), result, snapshot), origin="AGENT", now=NOW)
    assert row is not None
    return row


async def test_a_proposed_page_is_kept_as_it_stands_and_as_it_will_be_with_its_preview_s_pictures(
    session: AsyncSession,
) -> None:
    row = await proposed(session, drawn=True)
    admin = await person(session, ADMIN)
    view = await page_proposal(session, admin, row.id, site=SITE)
    after = MonographDocument.model_validate(await proposal_document(session, admin, row.id, "AFTER"))
    chapter = next(entry.chapter for entry in after.content.components if entry.label == LABEL)
    assert [(part.part, part.chapter, part.label, part.state) for part in view.parts] == [
        ("component", chapter, LABEL, "WAITING"),
        ("layout", None, None, "WAITING"),
    ]
    changed = [(each.kind, each.change, each.ref) for found in view.chapters for each in found.changes]
    assert ("COMPONENT", "ADDED", LABEL) in changed
    assert [(shown.side, shown.name) for shown in view.pictures] == [("AFTER", "first-screen-390")]
    assert view.drawable == ["BEFORE", "AFTER"] and view.waiting == 2
    stored = await drawn_picture(session, row.id, "AFTER", "first-screen-390")
    assert stored is not None and stored.data == base64.b64decode(JPEG)
    listed = await open_page_proposals(session, admin, site=SITE, now=NOW)
    assert [(each.id, each.chapters[0].changes) for each in listed.proposals] == [(row.id, [])]
    with pytest.raises(NotYourQueue):
        await open_page_proposals(session, await person(session, MAKER), site=SITE, now=NOW)


async def test_a_proposal_without_stored_pictures_opens_and_is_drawn_on_request(
    session: AsyncSession,
) -> None:
    row = await proposed(session, drawn=False)
    admin = await person(session, ADMIN)
    view = await page_proposal(session, admin, row.id, site=SITE)
    assert (view.pictures, view.drawable) == ([], ["BEFORE", "AFTER"])
    renderer = Renderer(RenderResult(problems=[], images=[shot("first-screen-390")], seconds=1.0))
    drawing = await draw_side(session, admin, row.id, "BEFORE", renderer=renderer, site=SITE, now=NOW)
    (asked,) = renderer.asked
    assert asked.preview_url.startswith(f"{SITE}/preview/") and drawing.drawn is True
    assert [(shown.side, shown.name) for shown in drawing.pictures] == [("BEFORE", "first-screen-390")]
    unmade = Renderer(RenderUnmade(reason="UNREACHABLE", message="the renderer is not running."))
    refused = await draw_side(session, admin, row.id, "AFTER", renderer=unmade, site=SITE, now=NOW)
    assert refused.drawn is False and refused.pictures == []
    with pytest.raises(NotYourQueue):
        await page_proposal(session, await person(session, MAKER), row.id, site=SITE)
    row.userId = ADMIN
    await session.flush()
    with pytest.raises(OwnItem):
        await page_proposal(session, admin, row.id, site=SITE)


async def test_one_chapter_s_approval_applies_that_chapter_alone_and_a_rejection_s_note_reaches_open_work(
    session: AsyncSession,
) -> None:
    row = await proposed(session, drawn=False)
    admin = await person(session, ADMIN)
    chapter = next(part["chapter"] for part in row.parts if part["part"] == "component")
    approval = PageDecisionBody.model_validate({"scope": "CHAPTER", "chapter": chapter, "action": "approve"})
    approved = await decide_page(session, admin, row.id, approval, now=NOW)
    assert [(each.part, each.outcome) for each in approved.decision.outcomes] == [("component", "APPLIED")]
    assert approved.open is True
    table = await session.scalar(select(ComponentProposal.status).where(ComponentProposal.label == LABEL))
    layout_status = await session.scalar(
        select(LayoutProposal.status).where(LayoutProposal.proposerId == MAKER)
    )
    assert (table, layout_status) == ("APPROVED", "PENDING")
    rejection = PageDecisionBody.model_validate({"action": "reject", "note": NOTE})
    rejected = await decide_page(session, admin, row.id, rejection, now=NOW)
    assert [(each.part, each.outcome) for each in rejected.decision.outcomes] == [
        ("component", "SKIPPED"),
        ("layout", "APPLIED"),
    ]
    assert rejected.open is False and row.closedAt == NOW
    layout = await session.scalar(select(LayoutProposal).where(LayoutProposal.proposerId == MAKER))
    assert layout is not None and (layout.status, layout.reviewNote) == ("REJECTED", NOTE)
    mine = await my_tasks(session, await person(session, MAKER), site=SITE, now=NOW)
    noted = sorted((note.action, note.scope, note.note or "") for note in mine.reviews)
    assert noted == [("approve", "CHAPTER", ""), ("reject", "PAGE", NOTE)]
    assert all(note.proposal_id == row.id for note in mine.reviews)
    assert (await open_page_proposals(session, admin, site=SITE, now=NOW)).proposals == []
