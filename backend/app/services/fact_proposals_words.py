from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from app.core.roles import ROLE_LABELS
from app.research.trust_tiers import DRAWN, NEWCOMER, REVIEW_SAMPLE_PERCENT, ROLE, TRUSTED, TierPlacement

from .candidate_gates import GateRun

__all__ = ["placement_message", "placement_note"]

MESSAGES: Mapping[str, str] = MappingProxyType(
    {
        ROLE: "Published, and approved at once because your account reviews contributions.",
        TRUSTED: (
            "Published at once: this account's record makes it a proven contributor, and this fact was not "
            "drawn for review."
        ),
        DRAWN: (
            "Published at once as a proven contributor's fact; it was drawn for review, and a Professor or "
            "Admin will review it."
        ),
        NEWCOMER: "Received. It stays hidden until a Professor or Admin approves it, as a new contributor's facts do.",
    }
)
PUBLISHED_UNREVIEWED = "Published as unreviewed; a Professor or Admin will review it."
WAITING_MESSAGE = "Received. It stays hidden until a Professor or Admin approves it."


def placement_note(origin: str, tiered: TierPlacement, run: GateRun, role: str) -> str:
    refused = run.refused_at
    if refused is not None:
        return f"{origin} proposal refused at the {refused.gate} gate"
    if tiered.why == ROLE:
        return f"{origin} proposal approved at once: proposed by a {ROLE_LABELS.get(role, role)} account"
    if tiered.why == TRUSTED:
        return f"{origin} proposal approved at once: a proven contributor's fact not drawn for review"
    if tiered.why == DRAWN:
        return (
            f"{origin} proposal published unreviewed: a proven contributor's fact drawn for review "
            f"(one in {100 // REVIEW_SAMPLE_PERCENT}); it waits in the review queue"
        )
    if tiered.why == NEWCOMER:
        return (
            f"{origin} proposal waits hidden for a Professor's or Admin's approval: a new contributor's fact"
        )
    if tiered.placed.live:
        return f"{origin} proposal published unreviewed by the review switch (AUTO); it waits in the review queue"
    return f"{origin} proposal waits hidden for a Professor's or Admin's approval (review switch APPROVAL)"


def placement_message(tiered: TierPlacement, run: GateRun) -> str:
    refused = run.refused_at
    if refused is not None:
        return f"Not added: the {refused.gate} gate refused it. {refused.reasons[0]}"
    if tiered.why in MESSAGES:
        return MESSAGES[tiered.why]
    return PUBLISHED_UNREVIEWED if tiered.placed.live else WAITING_MESSAGE
