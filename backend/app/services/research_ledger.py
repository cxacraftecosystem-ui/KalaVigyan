from __future__ import annotations

from app.research.evidence_pack import EvidencePack
from app.research.planning import MODE_POLICIES, ResearchShare, split_share
from app.research.vocabulary import CANONICAL_LANGUAGE

__all__ = ["FRESH_MIN_FETCHES", "ResearchLedger", "may_research_fresh"]

FRESH_MIN_FETCHES = 2
NOTHING = ResearchShare(queries=0, native_queries=0, fetches=0)


class ResearchLedger:
    def __init__(self, total: ResearchShare, parts: int) -> None:
        self._left = total
        self._waiting = parts
        self._reserved = total
        self.shares = split_share(total, parts)

    @property
    def left(self) -> ResearchShare:
        return self._left

    def take_section(self, share: ResearchShare) -> ResearchShare:
        spare = _above(self._left, self._reserved)
        extra = split_share(spare, self._waiting)[0] if self._waiting else NOTHING
        self._reserved = _above(self._reserved, share)
        self._waiting = max(self._waiting - 1, 0)
        return self.take(_shifted(share, extra, sign=1))

    def take(self, wanted: ResearchShare) -> ResearchShare:
        granted = wanted.capped(self._left)
        self._left = _shifted(self._left, granted, sign=-1)
        return granted

    def give_back(self, unused: ResearchShare) -> None:
        self._left = _shifted(self._left, unused, sign=1)

    def settle(self, share: ResearchShare, pack: EvidencePack) -> None:
        native = sum(1 for query in pack.plan.queries if query.query.language != CANONICAL_LANGUAGE)
        used = ResearchShare(
            queries=min(len(pack.plan.queries) - native, share.queries),
            native_queries=min(native, share.native_queries),
            fetches=min(len(pack.documents), share.fetches),
        )
        self.give_back(_shifted(share, used, sign=-1))

    def take_fresh(self, share: ResearchShare) -> ResearchShare | None:
        wanted = ResearchShare(
            queries=max(share.queries, 1),
            native_queries=share.native_queries,
            fetches=max(share.fetches, FRESH_MIN_FETCHES),
        )
        granted = self.take(wanted)
        if granted.queries:
            return granted
        self.give_back(granted)
        return None


def may_research_fresh(pack: EvidencePack) -> bool:
    return not pack.plan.queries and MODE_POLICIES[pack.plan.mode].max_queries > 0


def _above(base: ResearchShare, floor: ResearchShare) -> ResearchShare:
    return ResearchShare(
        queries=max(base.queries - floor.queries, 0),
        native_queries=max(base.native_queries - floor.native_queries, 0),
        fetches=max(base.fetches - floor.fetches, 0),
    )


def _shifted(base: ResearchShare, change: ResearchShare, *, sign: int) -> ResearchShare:
    return ResearchShare(
        queries=base.queries + sign * change.queries,
        native_queries=base.native_queries + sign * change.native_queries,
        fetches=base.fetches + sign * change.fetches,
    )
