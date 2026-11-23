from __future__ import annotations

from collections.abc import Collection, Iterable
from typing import Any

from app.research.named_groups import names_a_listed_group
from app.research.retrieval import HIDDEN_CLAIM_STATUSES, VISIBLE_SENSITIVITY
from app.research.vocabulary import LEVEL_ORDER
from app.schemas.media import MEDIA_MAX_CLAIMS, MEDIA_MIN_CLAIMS, names_a_group

from .records import ClaimFacts

__all__ = [
    "PASSING_QUOTE",
    "QUOTED_LEVELS",
    "REVIEWED_LEVELS",
    "claim_set",
    "enough_claims",
]

REVIEWED_LEVELS = frozenset({"VERIFIED", "REVIEWED"})
QUOTED_LEVELS = frozenset({"PROVISIONAL"})
PASSING_QUOTE = "PASS"


def claim_set(
    claims: Iterable[ClaimFacts], *, acls: Collection[str], named: Collection[str] = ()
) -> tuple[ClaimFacts, ...]:
    chosen: dict[Any, ClaimFacts] = {}
    for claim in claims:
        if not _usable(claim, acls) or names_a_listed_group(claim.text, named):
            continue
        known = chosen.get(claim.id)
        if known is None or (claim.own and not known.own):
            chosen[claim.id] = claim
    ranked = sorted(chosen.values(), key=lambda c: (LEVEL_ORDER[c.level], not c.own, str(c.id)))
    return tuple(ranked[:MEDIA_MAX_CLAIMS])


def enough_claims(claims: Collection[ClaimFacts]) -> bool:
    return len(claims) >= MEDIA_MIN_CLAIMS


def _usable(claim: ClaimFacts, acls: Collection[str]) -> bool:
    if claim.status in HIDDEN_CLAIM_STATUSES or claim.sensitivity != VISIBLE_SENSITIVITY:
        return False
    if claim.level not in LEVEL_ORDER or names_a_group(claim.text):
        return False
    if any(citation.restricted for citation in claim.citations):
        return False
    visible = [c for c in claim.citations if c.chunk_acl is not None and c.chunk_acl in acls]
    if claim.level in REVIEWED_LEVELS:
        return bool(visible)
    return claim.level in QUOTED_LEVELS and any(c.quote_check == PASSING_QUOTE for c in visible)
