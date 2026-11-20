from __future__ import annotations

from dataclasses import dataclass

from app.research.open_work import NO_ITEMS, Items
from app.research.open_work_texts import counted
from app.research.sections import DISCIPLINE_FIELDS

from .upkeep_links import ROTTEN_AFTER_FAILURES

__all__ = [
    "CORROBORATE_ACCEPTANCE",
    "RESOURCE_ACCEPTANCE",
    "ROTTEN_ACCEPTANCE",
    "Wording",
    "corroborate_wording",
    "resource_wording",
    "rotten_wording",
]

RESOURCE_ACCEPTANCE = (
    "For each fact, a source graded A to C that states it, quoted verbatim with its locator and given to "
    "propose_source with the fact's id; the fact returns to its page once the quote is found in the fetched "
    "source."
)
CORROBORATE_ACCEPTANCE = (
    "For each fact, a second source from a different publisher that states it, quoted verbatim with its "
    "locator and given to propose_source with the fact's id."
)
ROTTEN_ACCEPTANCE = (
    "For each fact, another source that states it, or an archived snapshot of the same page "
    "(https://web.archive.org/web/<timestamp>/<url>) in which the quote is found, quoted verbatim with its "
    "locator and given to propose_source with the fact's id."
)


@dataclass(frozen=True)
class Wording:
    needed: str
    acceptance: str
    facts: Items = NO_ITEMS
    sources: Items = NO_ITEMS


def resource_wording(name: str, discipline: str | None, facts: Items) -> Wording:
    one = facts.count == 1
    return Wording(
        needed=(
            f"{counted(facts.count, 'fact')} of {name}{_under(discipline)} {'is' if one else 'are'} held from "
            f"the page: no quote cited for {'it' if one else 'them'} is found in its source any more."
        ),
        acceptance=RESOURCE_ACCEPTANCE,
        facts=facts,
    )


def corroborate_wording(name: str, discipline: str | None, facts: Items) -> Wording:
    one = facts.count == 1
    return Wording(
        needed=(
            f"{counted(facts.count, 'fact')} of {name}{_under(discipline)} {'cites' if one else 'cite'} a quote "
            f"its source no longer holds, and {'shows' if one else 'show'} on the quotes that still hold."
        ),
        acceptance=CORROBORATE_ACCEPTANCE,
        facts=facts,
    )


def rotten_wording(name: str, facts: Items, sources: Items) -> Wording:
    one = sources.count == 1
    return Wording(
        needed=(
            f"{counted(facts.count, 'fact')} of {name} {'rests' if facts.count == 1 else 'rest'} only on "
            f"{counted(sources.count, 'source')} that failed to answer on {ROTTEN_AFTER_FAILURES} nightly checks "
            f"in a row and {'has' if one else 'have'} no archived copy."
        ),
        acceptance=ROTTEN_ACCEPTANCE,
        facts=facts,
        sources=sources,
    )


def _under(discipline: str | None) -> str:
    if discipline is None:
        return ""
    return f" under {discipline} ({DISCIPLINE_FIELDS[discipline]})"
