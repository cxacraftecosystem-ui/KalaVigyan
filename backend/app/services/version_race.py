from __future__ import annotations

import logging
import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.research.explainer import Explainer
from app.research.explainer_versions import ExplainerVersionDocument, VersionMark
from app.research.sections import AnswerPlans

from .answer_gaps import FieldReading, answer_readings
from .explainer_history import StaleVersion
from .follow_ups import AnswerLayout, StoredAnswer
from .section_context import SectionOutcome, answer_plans

__all__ = ["VERSION_ATTEMPTS", "Asker", "VersionRace", "VersionStore"]

logger = logging.getLogger(__name__)

VERSION_ATTEMPTS = 3


class VersionStore(Protocol):
    async def finish(
        self,
        answer_id: uuid.UUID,
        *,
        asked_at: datetime,
        plans: AnswerPlans,
        claim_ids: Sequence[uuid.UUID],
        explainer: Explainer | None,
        version: VersionMark | None = None,
        readings: Sequence[FieldReading] = (),
    ) -> None: ...

    async def latest(
        self, explainer_id: uuid.UUID, user_id: uuid.UUID | None
    ) -> ExplainerVersionDocument: ...


class Asker(Protocol):
    @property
    def user_id(self) -> uuid.UUID | None: ...

    @property
    def asked_at(self) -> datetime: ...


@dataclass(frozen=True)
class VersionRace:
    store: VersionStore
    answer_id: uuid.UUID
    asker: Asker
    outcomes: Sequence[SectionOutcome]

    async def kept(
        self, layout: AnswerLayout, document: Explainer | None, claim_ids: Iterable[uuid.UUID]
    ) -> StoredAnswer:
        claims = tuple(dict.fromkeys(claim_ids))
        stored = layout.stored(document, claims)
        for _ in range(VERSION_ATTEMPTS - 1):
            try:
                await self._finish(stored)
                return stored
            except StaleVersion as stale:
                stored = await self._onto_newer(
                    stored, stale, lambda newer: layout.stored_onto(newer, document, claims)
                )
        await self._finish(stored)
        return stored

    async def _onto_newer(self, stored: StoredAnswer, stale: StaleVersion, remerge: Remerge) -> StoredAnswer:
        mark = stored.version
        if mark is None:
            raise stale
        newer = await self.store.latest(mark.explainer_id, self.asker.user_id)
        moved = remerge(newer) if newer.mark.version >= mark.version else None
        if moved is None or moved.version is None:
            raise stale
        logger.info(
            "follow-up %s found version %s of explainer %s saved meanwhile and is kept as version %s",
            self.answer_id,
            newer.mark.version,
            mark.explainer_id,
            moved.version.version,
        )
        return moved

    async def _finish(self, stored: StoredAnswer) -> None:
        await self.store.finish(
            self.answer_id,
            asked_at=self.asker.asked_at,
            plans=answer_plans(self.outcomes),
            claim_ids=list(stored.claim_ids),
            explainer=stored.explainer,
            version=stored.version,
            readings=answer_readings(self.outcomes),
        )


class Remerge(Protocol):
    def __call__(self, newer: ExplainerVersionDocument) -> StoredAnswer | None: ...
