from collections.abc import AsyncIterator
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.models import AlertDigestSend, ReviewEvent, SavedItem
from app.services.alert_digest import send_alert_digests, week_of
from app.services.mailer import Mail
from app.services.notifications import mark_all_read, mark_read, notification_list
from app.services.saved_recheck import recheck_saved

from .alerts_seed import NOW, Seeded, claim_of, craft_row, first_answer, reader, saved_row, seeded

pytestmark = pytest.mark.db

WEB = "https://kalavigyan.example.org"
EARLIER = NOW - timedelta(days=2)
CHECKED = NOW - timedelta(days=1)
WATER = "ENVIRONMENTAL_CONDITION"
PAST = "HISTORICAL_CONTEXT"


@pytest.fixture
async def db() -> AsyncIterator[Seeded]:
    async with seeded() as found:
        yield found


class Outbox:
    def __init__(self, *, accepts: bool = True) -> None:
        self.sent: list[Mail] = []
        self.accepts = accepts

    async def __call__(self, mail: Mail) -> bool:
        self.sent.append(mail)
        return self.accepts


async def saved_reader(db: Seeded, *, digest: bool = False, cited: int = 0):
    user, craft = await reader(db.session, digest=digest), await craft_row(db.session)
    shown = [await claim_of(db.session, craft, WATER, created_at=NOW) for _ in range(cited)]
    first = await first_answer(db.session, user, craft, claim_ids=tuple(shown))
    await saved_row(db.session, user, first.answer_id, checked_at=CHECKED)
    return user, craft, first


async def test_a_re_check_with_no_new_claims_makes_no_note(db: Seeded) -> None:
    user, craft, first = await saved_reader(db)
    await claim_of(db.session, craft, WATER, created_at=EARLIER)
    report = await recheck_saved(db.sessions, now=NOW)
    assert report.as_dict() == {"checked": 1, "notified": 0, "ok": True}
    assert (await notification_list(db.session, user.id)).items == []
    checked = await db.session.scalar(
        select(SavedItem.checkedAt).where(SavedItem.answerId == first.answer_id)
    )
    assert checked == NOW


async def test_a_new_claim_on_another_field_makes_no_note(db: Seeded) -> None:
    user, craft, _ = await saved_reader(db)
    await claim_of(db.session, craft, PAST, created_at=NOW)
    await claim_of(db.session, craft, "TRADITION", created_at=NOW)
    assert (await recheck_saved(db.sessions, now=NOW)).notified == 0
    assert (await notification_list(db.session, user.id)).unread == 0


async def test_a_claim_is_news_in_every_saved_field_it_is_filed_under(db: Seeded) -> None:
    user, craft, _ = await saved_reader(db)
    await claim_of(db.session, craft, "MECHANISM", created_at=NOW, filed=("PHYSICS", "CHEMISTRY"))
    await claim_of(db.session, craft, PAST, created_at=NOW, filed=("HISTORY", "GEOGRAPHY"))
    assert (await recheck_saved(db.sessions, now=NOW)).notified == 1
    (note,) = (await notification_list(db.session, user.id)).items
    assert [(entry.facet, entry.new_claims) for entry in note.payload.news] == [
        ("GEOGRAPHY", 1),
        ("CHEMISTRY", 1),
    ]


async def test_a_claim_filed_under_no_field_is_not_news(db: Seeded) -> None:
    user, craft, _ = await saved_reader(db)
    await claim_of(db.session, craft, WATER, created_at=NOW, filed=())
    assert (await recheck_saved(db.sessions, now=NOW)).notified == 0
    assert (await notification_list(db.session, user.id)).unread == 0


async def test_a_new_claim_on_a_saved_field_makes_one_note_once(db: Seeded) -> None:
    user, craft, first = await saved_reader(db, cited=1)
    await claim_of(db.session, craft, WATER, created_at=NOW)
    assert (await recheck_saved(db.sessions, now=NOW)).notified == 1
    assert (await recheck_saved(db.sessions, now=NOW + timedelta(days=1))).notified == 0
    notes = await notification_list(db.session, user.id)
    (note,) = notes.items
    assert notes.unread == 1
    assert (note.payload.explainer_id, note.payload.version) == (first.answer_id, 1)
    assert [(entry.facet, entry.new_claims) for entry in note.payload.news] == [("GEOGRAPHY", 1)]


async def test_a_claim_raised_to_a_fact_since_the_last_check_is_news(db: Seeded) -> None:
    user, craft, _ = await saved_reader(db)
    raised = await claim_of(db.session, craft, WATER, created_at=EARLIER)
    db.session.add(
        ReviewEvent(
            claimId=raised, actorKind="SYSTEM", fromLevel="HYPOTHESIS", toLevel="PROVISIONAL", createdAt=NOW
        )
    )
    await db.session.commit()
    assert (await recheck_saved(db.sessions, now=NOW)).notified == 1
    (note,) = (await notification_list(db.session, user.id)).items
    assert [(entry.facet, entry.new_claims) for entry in note.payload.news] == [("GEOGRAPHY", 1)]


async def test_notes_are_private_to_their_reader(db: Seeded) -> None:
    user, craft, _ = await saved_reader(db)
    stranger = await reader(db.session)
    await claim_of(db.session, craft, WATER, created_at=NOW)
    await recheck_saved(db.sessions, now=NOW)
    (note,) = (await notification_list(db.session, user.id)).items
    assert (await notification_list(db.session, stranger.id)).items == []
    assert not await mark_read(db.session, stranger.id, note.id)
    await mark_all_read(db.session, stranger.id)
    assert (await notification_list(db.session, user.id)).unread == 1
    assert await mark_read(db.session, user.id, note.id)
    await db.session.commit()
    assert (await notification_list(db.session, user.id)).unread == 0


async def test_the_digest_mails_opted_in_readers_once_a_week(db: Seeded) -> None:
    user, craft, _ = await saved_reader(db, digest=True)
    quiet, quiet_craft, _ = await saved_reader(db)
    await claim_of(db.session, craft, WATER, created_at=NOW)
    await claim_of(db.session, quiet_craft, WATER, created_at=NOW)
    await recheck_saved(db.sessions, now=NOW)
    outbox = Outbox()
    report = await send_alert_digests(db.sessions, now=NOW, enabled=True, web_url=WEB, send=outbox)
    assert [mail.to for mail in outbox.sent] == [user.email]
    assert (report.sent, report.failed) == (1, 0)
    again = await send_alert_digests(db.sessions, now=NOW, enabled=True, web_url=WEB, send=outbox)
    assert (again.sent, len(outbox.sent)) == (0, 1)
    weeks = await db.session.scalars(select(AlertDigestSend.weekOf).where(AlertDigestSend.userId == user.id))
    assert list(weeks) == [week_of(NOW)]
    assert quiet.email not in [mail.to for mail in outbox.sent]


async def test_a_digest_that_could_not_be_sent_is_tried_again(db: Seeded) -> None:
    user, craft, _ = await saved_reader(db, digest=True)
    await claim_of(db.session, craft, WATER, created_at=NOW)
    await recheck_saved(db.sessions, now=NOW)
    failed = await send_alert_digests(
        db.sessions, now=NOW, enabled=True, web_url=WEB, send=Outbox(accepts=False)
    )
    assert failed.failed == 1
    outbox = Outbox()
    await send_alert_digests(db.sessions, now=NOW, enabled=True, web_url=WEB, send=outbox)
    assert [mail.to for mail in outbox.sent] == [user.email]


async def test_no_digest_while_the_setting_is_off(db: Seeded) -> None:
    user, craft, _ = await saved_reader(db, digest=True)
    await claim_of(db.session, craft, WATER, created_at=NOW)
    await recheck_saved(db.sessions, now=NOW)
    outbox = Outbox()
    report = await send_alert_digests(db.sessions, now=NOW, enabled=False, web_url=WEB, send=outbox)
    assert (report.enabled, outbox.sent) == (False, [])
    assert (
        await db.session.scalar(select(AlertDigestSend.id).where(AlertDigestSend.userId == user.id)) is None
    )
