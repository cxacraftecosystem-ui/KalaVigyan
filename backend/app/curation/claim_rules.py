from __future__ import annotations

import re
from itertools import combinations

from app.models.knowledge import QUOTE_MAX_CHARS
from app.research.hedges import dropped_hedges, unsourced_hedges

from .dossier import Dossier
from .duplicates import near_duplicates
from .figures import figure_gaps
from .limits import CLAIM_WORDS_MAX, CLAIM_WORDS_MIN, CURATED_QUOTE_MIN_CHARS
from .matching import quote_chars
from .parts import Claim
from .problems import Problem
from .references import references
from .sentences import relationship_sentence, single_sentence, word_count

__all__ = [
    "PRICE_PATTERN",
    "claim_problems",
    "duplicate_problems",
    "hypothesis_problems",
    "reliability_problems",
]

PRICE_PATTERN = re.compile(r"₹|\bRs\b\.?|\bINR\b|\brupees?\b|\$|\bUSD\b|€|£", re.IGNORECASE)
WEAKEST_RELIABILITY = "D"


def claim_problems(dossier: Dossier) -> list[Problem]:
    found: list[Problem] = []
    for claim in dossier.claims:
        found += [Problem(claim.id, message) for message in _text_messages(claim)]
        found += _quote_problems(claim)
    return [
        *found,
        *reliability_problems(dossier),
        *duplicate_problems(dossier),
        *hypothesis_problems(dossier),
    ]


def reliability_problems(dossier: Dossier) -> list[Problem]:
    found = []
    for claim in dossier.claims:
        tiers = {dossier.source(quote.source_id).reliability for quote in claim.quotes}
        if tiers == {WEAKEST_RELIABILITY} and not _price_claim(claim):
            found.append(
                Problem(
                    claim.id,
                    "rests only on D sources; a D source supports a fact only beside an A to C source, "
                    "except a dated price",
                )
            )
    return found


def duplicate_problems(dossier: Dossier) -> list[Problem]:
    linked = {
        frozenset(pair) for conflict in dossier.conflicts for pair in combinations(conflict.claim_ids, 2)
    }
    pairs = near_duplicates([(claim.id, claim.text) for claim in dossier.claims], linked=linked)
    return [
        Problem(
            pair.second,
            f"near-identical to {pair.first} (similarity {pair.score}); keep one claim with both quotes, "
            "or link the two in conflicts when their facts differ",
        )
        for pair in pairs
    ]


def hypothesis_problems(dossier: Dossier) -> list[Problem]:
    hypotheses = {claim.id for claim in dossier.claims if claim.hypothesis}
    asked = {claim_id for question in dossier.open_questions for claim_id in question.claim_ids}
    found = [
        Problem(
            claim_id,
            "is a hypothesis, which shows only under an open question, and no open question cites it",
        )
        for claim_id in sorted(hypotheses - asked)
    ]
    found += [
        Problem(reference.where, f"cites hypothesis {reference.ref} as a fact")
        for reference in references(dossier)
        if reference.kind == "claim" and reference.as_fact and reference.ref in hypotheses
    ]
    return found


def _text_messages(claim: Claim) -> list[str]:
    quotes = [quote.quote for quote in claim.quotes]
    messages = []
    words = word_count(claim.text)
    if not CLAIM_WORDS_MIN <= words <= CLAIM_WORDS_MAX:
        messages.append(f"the text has {words} words; a claim has {CLAIM_WORDS_MIN} to {CLAIM_WORDS_MAX}")
    if not single_sentence(claim.text):
        messages.append("the text is not one sentence ending in a full stop")
    if relationship_sentence(claim.text):
        messages.append(
            "the text is a relationship sentence (X uses Y, X precedes Y); keep that as structure "
            "and state what a reader learns"
        )
    gaps = figure_gaps(claim.text, quotes)
    if gaps:
        messages.append(f"{', '.join(gaps)} in the text appears in none of its quotes")
    messages += [
        f"hedging word {hedge!r} appears in none of its quotes"
        for hedge in unsourced_hedges(claim.text, quotes)
    ]
    dropped = dropped_hedges(claim.text, quotes)
    if dropped:
        messages.append(
            f"every quote hedges ({', '.join(dropped)}) and the text does not; keep the hedge "
            "(probably, believed, about, ...) or cite words that state it plainly"
        )
    return messages


def _quote_problems(claim: Claim) -> list[Problem]:
    found = []
    seen: set[tuple[str, str]] = set()
    for index, quote in enumerate(claim.quotes):
        where = f"{claim.id}.quotes.{index}"
        chars = quote_chars(quote.quote)
        if chars < CURATED_QUOTE_MIN_CHARS:
            found.append(
                Problem(
                    where,
                    f"the quote has {chars} characters; a quote has {CURATED_QUOTE_MIN_CHARS} to {QUOTE_MAX_CHARS}",
                )
            )
        if (quote.source_id, quote.quote) in seen:
            found.append(Problem(where, f"repeats an earlier quote from {quote.source_id}"))
        seen.add((quote.source_id, quote.quote))
    return found


def _price_claim(claim: Claim) -> bool:
    return (
        claim.discipline == "ECONOMICS"
        and bool(PRICE_PATTERN.search(claim.text))
        and any(char.isdigit() for char in claim.text)
    )
