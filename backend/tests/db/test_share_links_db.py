import json
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ExternalFailure, InvalidInput
from app.models import (
    Answer,
    AuditLog,
    Chunk,
    Claim,
    ClaimSource,
    Concept,
    Craft,
    SharedExportFile,
    Source,
    User,
)
from app.research.explainer import Explainer, explainer_blocks
from app.research.lessons import LessonRequest
from app.research.share_links import ShareLink
from app.services.access_roster import access_row
from app.services.explainer_history import UnknownExplainer
from app.services.explainer_payload import FIRST_VERSION, stored_payload
from app.services.lesson_packs import build_lesson
from app.services.reader_profiles import apply_role_change
from app.services.share_links import (
    NothingPublic,
    answer_share,
    lesson_share,
    share_answer,
    share_lesson,
    shared_answer,
    shared_lesson,
    unshare_answer,
    unshare_lesson,
)
from app.services.share_owners import SHARES_WITHDRAWN, WithdrawnShares, withdraw_shares
from app.services.shared_files import DroppedFiles, drop_stopped_share_files, record_shared_files

from ..contracts.explainer_golden import DOCUMENT, citations_in, golden_json
from ..contracts.golden import golden_text
from ..learning.lesson_fixtures import golden_request
from .alerts_seed import NOW, Seeded, reader, seeded

pytestmark = pytest.mark.db

FIRST = 1
CLOSED_TEXT = "Closed-licence full text that only a researcher may quote."


@pytest.fixture
async def db() -> AsyncIterator[Seeded]:
    async with seeded() as found:
        yield found


def fresh_document() -> dict[str, Any]:
    cited = {cite[key] for cite in citations_in(golden_json(DOCUMENT)) for key in ("claimId", "sourceId")}
    text = golden_text(DOCUMENT)
    for stored in sorted(cited):
        text = text.replace(stored, str(uuid.uuid4()))
    return json.loads(text) | {"answerId": str(uuid.uuid4())}


async def first_answer(session: AsyncSession, user: User) -> Explainer:
    explainer = Explainer.model_validate(fresh_document())
    session.add(
        Answer(
            id=explainer.answer_id,
            userId=user.id,
            question=explainer.question,
            mode="DEEP",
            payload=stored_payload(explainer, None),
            claimIds=[],
            explainerId=explainer.answer_id,
            explainerVersion=FIRST_VERSION,
        )
    )
    await session.commit()
    return explainer


def cited_pairs(explainer: Explainer) -> set[tuple[str, str]]:
    return {(c.claim_id, c.source_id) for block in explainer_blocks(explainer) for c in block.citations()}


def cited_quotes(explainer: Explainer) -> set[tuple[str, str, str | None]]:
    return {
        (c.claim_id, c.source_id, c.quote) for block in explainer_blocks(explainer) for c in block.citations()
    }


def token_of(link: ShareLink | None) -> str:
    assert link is not None and link.path is not None
    return link.path.rsplit("/", 1)[1]


def lesson_request_for(explainer: Explainer) -> LessonRequest:
    return LessonRequest.model_validate(
        golden_request().model_dump(mode="json", by_alias=True) | {"explainerId": str(explainer.answer_id)}
    )


def closed_pair(explainer: Explainer) -> tuple[str, str]:
    prose = next(block for section in explainer.sections for block in section.blocks if block.kind == "prose")
    citation = prose.sentences[0].citations[0]
    return citation.claim_id, citation.source_id


async def stored_citations(session: AsyncSession, explainer: Explainer, closed: tuple[str, str]) -> None:
    craft = Craft(id=uuid.uuid4(), slug=f"Share-Test-{uuid.uuid4().hex[:8]}", name="Share Test Print")
    session.add(craft)
    await session.flush()
    concept = Concept(id=uuid.uuid4(), craftId=craft.id, type="MATERIAL", name="A shared material")
    pairs = cited_pairs(explainer)
    sources = {source for _claim, source in pairs}
    claims = {claim for claim, _source in pairs}
    session.add(concept)
    session.add_all(
        Source(id=uuid.UUID(source), kind="PAPER", title=f"Source {source}") for source in sources
    )
    session.add_all(
        Claim(
            id=uuid.UUID(claim),
            subjectType="CONCEPT",
            subjectId=concept.id,
            predicate="states",
            text=f"Stored claim {claim}.",
            evidenceLevel="PROVISIONAL",
            origin="IMPORT",
        )
        for claim in claims
    )
    await session.flush()
    chunk = Chunk(
        id=uuid.uuid4(), sourceId=uuid.UUID(closed[1]), ordinal=0, text=CLOSED_TEXT, acl="RESEARCHER"
    )
    session.add(chunk)
    await session.flush()
    session.add_all(
        ClaimSource(
            claimId=uuid.UUID(claim),
            sourceId=uuid.UUID(source),
            quote=quote,
            chunkId=chunk.id if (claim, source) == closed else None,
        )
        for claim, source, quote in sorted(cited_quotes(explainer), key=str)
    )
    await session.commit()


async def test_a_shared_version_is_read_by_its_link_without_closed_quotes_until_its_asker_unshares(
    db: Seeded,
) -> None:
    asker = await reader(db.session)
    explainer = await first_answer(db.session, asker)
    closed = closed_pair(explainer)
    await stored_citations(db.session, explainer, closed)
    assert (await answer_share(db.session, asker.id, explainer.answer_id, FIRST)).shared is False
    link = await share_answer(db.session, asker.id, explainer.answer_id, FIRST, now=NOW)
    assert link.shared and link.path is not None and link.path.startswith("/shared/answers/")
    assert await share_answer(db.session, asker.id, explainer.answer_id, FIRST, now=NOW) == link
    token = link.path.rsplit("/", 1)[1]
    shown = await shared_answer(db.session, token)
    assert shown is not None and shown.mark.explainer_id == explainer.answer_id
    assert closed not in cited_pairs(shown.explainer)
    assert cited_pairs(shown.explainer) and cited_pairs(shown.explainer) < cited_pairs(explainer)
    assert str(asker.id) not in shown.model_dump_json() and asker.email not in shown.model_dump_json()
    stranger = await reader(db.session)
    with pytest.raises(UnknownExplainer):
        await share_answer(db.session, stranger.id, explainer.answer_id, FIRST, now=NOW)
    assert not await unshare_answer(db.session, stranger.id, explainer.answer_id, FIRST, objects=None)
    assert await unshare_answer(db.session, asker.id, explainer.answer_id, FIRST, objects=None)
    assert await shared_answer(db.session, token) is None
    assert (await answer_share(db.session, asker.id, explainer.answer_id, FIRST)).shared is False


async def test_an_answer_nobody_signed_out_may_quote_is_never_shared(db: Seeded) -> None:
    asker = await reader(db.session)
    explainer = await first_answer(db.session, asker)
    with pytest.raises(NothingPublic):
        await share_answer(db.session, asker.id, explainer.answer_id, FIRST, now=NOW)
    assert (await answer_share(db.session, asker.id, explainer.answer_id, FIRST)).shared is False


async def test_a_shared_lesson_is_rebuilt_from_the_public_reading_of_its_explainer(db: Seeded) -> None:
    professor = await reader(db.session)
    explainer = await first_answer(db.session, professor)
    closed = closed_pair(explainer)
    await stored_citations(db.session, explainer, closed)
    pack = await build_lesson(db.session, professor.id, lesson_request_for(explainer), now=NOW)
    link = await share_lesson(db.session, professor.id, pack.id, now=NOW)
    assert link is not None and link.path is not None and link.path.startswith("/shared/lessons/")
    assert await share_lesson(db.session, uuid.uuid4(), pack.id, now=NOW) is None
    shown = await shared_lesson(db.session, link.path.rsplit("/", 1)[1])
    assert shown is not None and (shown.id, shown.title, shown.created_at) == (
        pack.id,
        pack.title,
        pack.created_at,
    )
    cited = {
        (citation.claim_id, citation.source_id)
        for slide in shown.slides
        for sentence in slide.bullets
        for citation in sentence.citations
    }
    assert cited and closed not in cited
    assert await unshare_lesson(db.session, professor.id, pack.id, objects=None)
    assert await shared_lesson(db.session, link.path.rsplit("/", 1)[1]) is None
    shared = await lesson_share(db.session, professor.id, pack.id)
    assert shared is not None and shared.shared is False


async def shared_version(db: Seeded) -> tuple[User, Explainer, str]:
    asker = await reader(db.session)
    explainer = await first_answer(db.session, asker)
    await stored_citations(db.session, explainer, closed_pair(explainer))
    link = await share_answer(db.session, asker.id, explainer.answer_id, FIRST, now=NOW)
    return asker, explainer, token_of(link)


async def test_a_link_stops_opening_while_its_owner_is_barred_and_once_the_owner_is_deleted(
    db: Seeded,
) -> None:
    asker, _explainer, token = await shared_version(db)
    roster = await access_row(db.session, asker.email)
    assert roster is not None
    for standing, opens in (("SUSPENDED", False), ("REJECTED", False), ("ACTIVE", True)):
        roster.status = standing
        await db.session.commit()
        assert (await shared_answer(db.session, token) is not None) is opens, standing
    asker.deletedAt = NOW
    await db.session.commit()
    assert await shared_answer(db.session, token) is None


async def test_withdrawing_an_owner_s_links_ends_answers_and_lessons_and_is_audited(db: Seeded) -> None:
    asker, explainer, token = await shared_version(db)
    pack = await build_lesson(db.session, asker.id, lesson_request_for(explainer), now=NOW)
    lesson = token_of(await share_lesson(db.session, asker.id, pack.id, now=NOW))
    withdrawn = await withdraw_shares(db.session, asker.id, actor=None, cause="users.deleted", objects=None)
    await db.session.commit()
    assert withdrawn == WithdrawnShares(answers=1, lessons=1)
    assert await shared_answer(db.session, token) is None
    assert await shared_lesson(db.session, lesson) is None
    assert (await answer_share(db.session, asker.id, explainer.answer_id, FIRST)).shared is False
    detail = (
        await db.session.execute(
            select(AuditLog.detail).where(
                AuditLog.action == SHARES_WITHDRAWN, AuditLog.targetId == str(asker.id)
            )
        )
    ).scalar_one()
    assert detail == {"cause": "users.deleted", "answers": 1, "lessons": 1}


async def test_a_builder_who_may_no_longer_build_lessons_stops_sharing_them_and_keeps_answers(
    db: Seeded,
) -> None:
    professor, explainer, token = await shared_version(db)
    professor.role = "PROFESSOR"
    await db.session.commit()
    pack = await build_lesson(db.session, professor.id, lesson_request_for(explainer), now=NOW)
    lesson = token_of(await share_lesson(db.session, professor.id, pack.id, now=NOW))
    await apply_role_change(db.session, professor, "RESEARCHER", objects=None)
    professor.role = "RESEARCHER"
    await db.session.commit()
    assert await shared_lesson(db.session, lesson) is None
    assert await shared_answer(db.session, token) is not None


SHARED_FILES = "exports/00000000-0000-0000-0000-000000000000"


@dataclass
class Bucket:
    deleted: list[str] = field(default_factory=list)
    refusing: bool = False

    async def delete(self, key: str) -> None:
        if self.refusing:
            raise ExternalFailure("Could not delete the media object (AccessDenied)", kind="auth", status=403)
        self.deleted.append(key)


def shared_key(name: str) -> str:
    return f"{SHARED_FILES}/{uuid.uuid4().hex}{uuid.uuid4().hex}/{name}"


async def recorded_keys(db: Seeded, keys: list[str]) -> set[str]:
    found = await db.session.execute(select(SharedExportFile.key).where(SharedExportFile.key.in_(keys)))
    return set(found.scalars().all())


async def test_stopping_a_share_deletes_the_files_its_readers_were_given(db: Seeded) -> None:
    asker, explainer, token = await shared_version(db)
    report, handout = shared_key("Report_v1.pdf"), shared_key("Handout.pdf")
    bucket = Bucket()
    kept = await record_shared_files(db.session, token, [report, handout, report], objects=bucket)
    assert (kept, bucket.deleted) == (DroppedFiles(dropped=0, kept=0), [])
    assert await recorded_keys(db, [report, handout]) == {report, handout}
    assert await unshare_answer(db.session, asker.id, explainer.answer_id, FIRST, objects=bucket)
    assert sorted(bucket.deleted) == sorted([report, handout])
    assert await recorded_keys(db, [report, handout]) == set()


async def test_a_file_recorded_after_its_share_stopped_is_deleted_at_once(db: Seeded) -> None:
    asker, explainer, token = await shared_version(db)
    assert await unshare_answer(db.session, asker.id, explainer.answer_id, FIRST, objects=None)
    late = shared_key("Report_v1.pdf")
    bucket = Bucket()
    dropped = await record_shared_files(db.session, token, [late], objects=bucket)
    assert (dropped, bucket.deleted) == (DroppedFiles(dropped=1, kept=0), [late])
    assert await recorded_keys(db, [late]) == set()


async def test_a_file_the_bucket_will_not_delete_is_kept_for_the_next_sweep(db: Seeded) -> None:
    asker, _explainer, token = await shared_version(db)
    report = shared_key("Report_v1.pdf")
    await record_shared_files(db.session, token, [report], objects=Bucket())
    refusing = Bucket(refusing=True)
    await withdraw_shares(db.session, asker.id, actor=None, cause="users.suspended", objects=refusing)
    await db.session.commit()
    assert await recorded_keys(db, [report]) == {report}
    bucket = Bucket()
    swept = await drop_stopped_share_files(db.session, bucket)
    await db.session.commit()
    assert report in bucket.deleted and swept.kept == 0
    assert await recorded_keys(db, [report]) == set()


async def test_a_reshared_file_follows_the_new_link_and_a_key_outside_the_shared_files_is_refused(
    db: Seeded,
) -> None:
    asker, explainer, token = await shared_version(db)
    report = shared_key("Report_v1.pdf")
    await record_shared_files(db.session, token, [report], objects=Bucket())
    assert await unshare_answer(db.session, asker.id, explainer.answer_id, FIRST, objects=None)
    again = token_of(await share_answer(db.session, asker.id, explainer.answer_id, FIRST, now=NOW))
    bucket = Bucket()
    await record_shared_files(db.session, again, [report], objects=bucket)
    assert bucket.deleted == []
    owner = await db.session.get(SharedExportFile, report)
    assert owner is not None and owner.shareToken == again
    with pytest.raises(InvalidInput):
        await record_shared_files(db.session, again, [f"exports/{asker.id}/x/Report.pdf"], objects=bucket)
