from __future__ import annotations

import logging
import uuid
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from types import MappingProxyType
from typing import Any

from sqlalchemy import delete, exists, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.clock import INDIA_TZ
from app.models import AccessRoster, AlertDigestSend, User, UserPreference
from app.research.alerts import ALERTS_SCHEMA_VERSION, DIGEST_ITEMS_MAX, AnswerImproved, WeeklyDigest
from app.research.sections import DISCIPLINE_TITLES

from .access_roster import ACTIVE
from .answer_translation import AnswerTranslation
from .digest_language import DigestTranslations, digest_language
from .mailer import Mail
from .notifications import unread_improvements

__all__ = [
    "DIGEST_OPENING",
    "DIGEST_STOP",
    "DIGEST_SUBJECT",
    "DIGEST_WINDOW",
    "DigestReader",
    "DigestReport",
    "digest_mail",
    "digest_texts",
    "explainer_url",
    "news_line",
    "send_alert_digests",
    "week_of",
    "weekly_digest",
]

logger = logging.getLogger(__name__)

DIGEST_SUBJECT = "Your saved KalaVigyan explainers got better"
DIGEST_OPENING = "New cited findings arrived this week for explainers you saved."
DIGEST_STOP = "Stop these emails in Settings:"
DIGEST_WINDOW = timedelta(days=7)
SETTINGS_PATH = "/settings"
EXPLAINER_PATH = "/ask?explainer="
ENGLISH: Mapping[str, str] = MappingProxyType({})

Send = Callable[[Mail], Awaitable[bool]]


@dataclass(frozen=True)
class DigestWeek:
    week: date
    since: datetime
    web_url: str


@dataclass(frozen=True)
class DigestReader:
    user_id: uuid.UUID
    email: str
    language: str


@dataclass
class DigestReport:
    enabled: bool
    week_of: date | None = None
    readers: int = 0
    sent: int = 0
    failed: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "weekOf": self.week_of.isoformat() if self.week_of else None,
            "readers": self.readers,
            "sent": self.sent,
            "failed": self.failed,
            "ok": self.failed == 0,
        }


def week_of(now: datetime) -> date:
    day = now.astimezone(INDIA_TZ).date()
    return day - timedelta(days=day.weekday())


def weekly_digest(items: Sequence[AnswerImproved], *, week: date, web_url: str) -> WeeklyDigest:
    return WeeklyDigest(
        schema_version=ALERTS_SCHEMA_VERSION,
        week_of=week,
        items=list(items),
        settings_url=f"{web_url.rstrip('/')}{SETTINGS_PATH}",
    )


def digest_texts(digest: WeeklyDigest) -> list[str]:
    return [DIGEST_SUBJECT, DIGEST_OPENING, *(news_line(item) for item in digest.items), DIGEST_STOP]


def digest_mail(
    to: str, digest: WeeklyDigest, *, web_url: str, rendered: Mapping[str, str] = ENGLISH
) -> Mail:
    lines = [rendered.get(DIGEST_OPENING, DIGEST_OPENING), ""]
    for item in digest.items:
        news = news_line(item)
        lines += [
            item.question,
            f"{item.craft.name}: {rendered.get(news, news)}",
            explainer_url(web_url, item),
            "",
        ]
    lines.append(f"{rendered.get(DIGEST_STOP, DIGEST_STOP)} {digest.settings_url}")
    return Mail(to=to, subject=rendered.get(DIGEST_SUBJECT, DIGEST_SUBJECT), text="\n".join(lines))


def explainer_url(web_url: str, item: AnswerImproved) -> str:
    return f"{web_url.rstrip('/')}{EXPLAINER_PATH}{item.explainer_id}"


def news_line(item: AnswerImproved) -> str:
    parts = [f"{entry.new_claims} in {DISCIPLINE_TITLES[entry.facet]}" for entry in item.news]
    total = sum(entry.new_claims for entry in item.news)
    noun = "finding" if total == 1 else "findings"
    return f"{total} new {noun} ({', '.join(parts)})"


async def send_alert_digests(
    sessions: async_sessionmaker[AsyncSession],
    *,
    now: datetime,
    enabled: bool,
    web_url: str,
    send: Send,
    translation: AnswerTranslation | None = None,
) -> DigestReport:
    if not enabled:
        return DigestReport(enabled=False)
    digest_week = DigestWeek(week=week_of(now), since=now - DIGEST_WINDOW, web_url=web_url)
    report = DigestReport(enabled=True, week_of=digest_week.week)
    async with sessions() as session:
        readers = await _readers(session, digest_week.week)
    report.readers = len(readers)
    words = DigestTranslations(translation)
    for reader in readers:
        digest = await _claimed_digest(sessions, reader.user_id, digest_week)
        if digest is None:
            continue
        rendered = await words.rendered(reader.language, digest_texts(digest))
        if await send(digest_mail(reader.email, digest, web_url=web_url, rendered=rendered)):
            report.sent += 1
            continue
        report.failed += 1
        await _released(sessions, reader.user_id, digest_week)
    return report


async def _claimed_digest(
    sessions: async_sessionmaker[AsyncSession], user_id: uuid.UUID, digest_week: DigestWeek
) -> WeeklyDigest | None:
    async with sessions() as session:
        items = await unread_improvements(session, user_id, since=digest_week.since, limit=DIGEST_ITEMS_MAX)
        if not items:
            return None
        digest = weekly_digest(items, week=digest_week.week, web_url=digest_week.web_url)
        claimed = await session.scalar(
            insert(AlertDigestSend)
            .values(userId=user_id, weekOf=digest_week.week, items=len(items))
            .on_conflict_do_nothing(index_elements=["userId", "weekOf"])
            .returning(AlertDigestSend.id)
        )
        await session.commit()
    return digest if claimed is not None else None


async def _released(
    sessions: async_sessionmaker[AsyncSession], user_id: uuid.UUID, digest_week: DigestWeek
) -> None:
    async with sessions() as session:
        await session.execute(
            delete(AlertDigestSend).where(
                AlertDigestSend.userId == user_id, AlertDigestSend.weekOf == digest_week.week
            )
        )
        await session.commit()


async def _readers(session: AsyncSession, week: date) -> list[DigestReader]:
    sent = exists().where(AlertDigestSend.userId == User.id, AlertDigestSend.weekOf == week)
    rows = await session.execute(
        select(User.id, User.email, UserPreference.answerLanguage)
        .join(UserPreference, UserPreference.userId == User.id)
        .join(AccessRoster, AccessRoster.email == func.lower(User.email))
        .where(
            UserPreference.alertDigest.is_(True),
            User.deletedAt.is_(None),
            AccessRoster.status == ACTIVE,
            ~sent,
        )
        .order_by(User.id)
    )
    return [DigestReader(user_id, email, digest_language(language)) for user_id, email, language in rows]
