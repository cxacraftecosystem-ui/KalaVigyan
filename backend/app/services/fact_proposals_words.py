from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from app.core.roles import ROLE_LABELS
from app.research.knowledge_writes import ReaderPlace
from app.research.sections import DISCIPLINE_TITLES
from app.research.trust_tiers import DRAWN, NEWCOMER, REVIEW_SAMPLE_PERCENT, ROLE, TRUSTED, TierPlacement

from .candidate_gates import GateRun
from .reader_facts import HELD, HIDDEN_CONCEPT, NO_SHOWN_SOURCE, RESTRICTED_FACT, UNEXPLAINED

__all__ = ["HIDDEN_WORDS", "placement_message", "placement_note", "reader_sentence"]

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
HIDDEN_WORDS: Mapping[str, str] = MappingProxyType(
    {
        HELD: "every quote it cites failed its check, so it is held until a quote is found again",
        RESTRICTED_FACT: "it is marked restricted, so only researchers read it",
        HIDDEN_CONCEPT: "it is filed under a concept that is hidden from readers",
        NO_SHOWN_SOURCE: "none of its sources may be shown to readers",
        UNEXPLAINED: "the pages left it out for a reason no rule names, which the nightly check reports",
    }
)


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


def placement_message(tiered: TierPlacement, run: GateRun, readers: ReaderPlace | None = None) -> str:
    refused = run.refused_at
    if refused is not None:
        return f"Not added: the {refused.gate} gate refused it. {refused.reasons[0]}"
    placed = MESSAGES.get(tiered.why) or (PUBLISHED_UNREVIEWED if tiered.placed.live else WAITING_MESSAGE)
    where = reader_sentence(readers) if readers is not None and tiered.placed.live else None
    return placed if where is None else f"{placed} {where}"


def reader_sentence(readers: ReaderPlace) -> str:
    if not readers.shown:
        why = HIDDEN_WORDS.get(readers.reason or "", HIDDEN_WORDS[UNEXPLAINED])
        return f"Readers cannot see it yet: {why}."
    field = DISCIPLINE_TITLES.get(readers.field or "", "its field's")
    page = readers.page_url or "its page"
    if readers.in_prose:
        return f"Readers see it now in the {field} section of {page}."
    task = f" (open task {readers.write_task})" if readers.write_task else ""
    return (
        f"Readers see it now at {page} among the page's cited {field} facts, once the page is refreshed; it "
        f"reads as prose when a written {field} section cites it{task}."
    )
