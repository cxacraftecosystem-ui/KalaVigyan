from collections.abc import AsyncIterator

import pytest
from sqlalchemy import update

from app.models import UserPreference
from app.services.alert_digest import DIGEST_SUBJECT, send_alert_digests
from app.services.answer_translation import AnswerTranslation
from app.services.mailer import Mail
from app.services.notifications import note_improvement

from ..alerts.digest_words import HINDI, KnownTranslator, NoCache
from ..contracts.learning_golden import ALERTS, AlertsFixture, learning
from .alerts_seed import NOW, Seeded, first_answer, reader, seeded

pytestmark = pytest.mark.db

WEB = "https://kalavigyan.example.org"


@pytest.fixture
async def db() -> AsyncIterator[Seeded]:
    async with seeded() as found:
        yield found


class Outbox:
    def __init__(self) -> None:
        self.sent: list[Mail] = []

    async def __call__(self, mail: Mail) -> bool:
        self.sent.append(mail)
        return True


async def noted_reader(db: Seeded, language: str) -> str:
    user = await reader(db.session, digest=True)
    await db.session.execute(
        update(UserPreference).where(UserPreference.userId == user.id).values(answerLanguage=language)
    )
    first = await first_answer(db.session, user)
    golden = AlertsFixture.model_validate(learning(ALERTS)).notifications.items[0].payload
    news = golden.model_copy(update={"explainer_id": first.answer_id, "checked_at": NOW})
    await note_improvement(db.session, user.id, news)
    await db.session.commit()
    return user.email


async def test_each_reader_s_digest_is_written_in_their_answer_language(db: Seeded) -> None:
    hindi_reader = await noted_reader(db, "hi")
    english_reader = await noted_reader(db, "auto")
    translator = KnownTranslator(HINDI)
    outbox = Outbox()
    await send_alert_digests(
        db.sessions,
        now=NOW,
        enabled=True,
        web_url=WEB,
        send=outbox,
        translation=AnswerTranslation(translator=translator, cache=NoCache()),
    )
    subjects = {mail.to: mail.subject for mail in outbox.sent}
    assert subjects == {hindi_reader: HINDI[DIGEST_SUBJECT], english_reader: DIGEST_SUBJECT}
    assert len(translator.asked) == 1
