from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from difflib import get_close_matches

from app.data.district_register import DistrictRegister
from app.research.licences import open_licence
from app.research.quotes import quote_occurs
from app.research.stated_dates import states_date

from .dossier import Dossier
from .entities import Place, Reaction
from .figures import figure_gaps
from .matching import stated_in
from .problems import Problem
from .records import GiRecord
from .vocabulary import GI_RECORD_SOURCE_KINDS, INDIA, INDIAN_DISTRICT_PLACE_KINDS

__all__ = [
    "claim_quotes",
    "community_problems",
    "market_problems",
    "picture_problems",
    "place_problems",
    "reaction_problems",
    "stage_problems",
]

SUGGESTIONS = 3
SUGGESTION_CUTOFF = 0.6


def claim_quotes(dossier: Dossier, claim_ids: Iterable[str]) -> list[str]:
    return [quote.quote for claim_id in claim_ids for quote in dossier.claim(claim_id).quotes]


def place_problems(dossier: Dossier, register: DistrictRegister) -> list[Problem]:
    found = []
    for place in dossier.places:
        if place.country == INDIA:
            found += [Problem(place.id, message) for message in _indian_place_messages(place, register)]
    return found


def community_problems(dossier: Dossier) -> list[Problem]:
    return [
        Problem(community.id, "a named person carries the place a published source gives (placeId)")
        for community in dossier.communities
        if community.kind == "PERSON" and community.place_id is None
    ]


def stage_problems(dossier: Dossier) -> list[Problem]:
    orders = Counter(stage.order for stage in dossier.stages if stage.order is not None)
    found = [
        Problem("stages", f"order {order} is given to more than one stage")
        for order, n in orders.items()
        if n > 1
    ]
    for stage in dossier.stages:
        for label, timing in (("duration", stage.duration), ("season", stage.season)):
            if timing is None:
                continue
            claim = dossier.claim(timing.claim_id)
            if not stated_in(timing.text, [claim.text, *(quote.quote for quote in claim.quotes)]):
                found.append(
                    Problem(
                        stage.id, f"the {label} {timing.text!r} is not stated by {claim.id} or its quotes"
                    )
                )
    return found


def reaction_problems(dossier: Dossier) -> list[Problem]:
    found = []
    for reaction in dossier.reactions:
        found += [Problem(reaction.id, message) for message in _formula_messages(dossier, reaction)]
    return found


def market_problems(dossier: Dossier) -> list[Problem]:
    gi = dossier.market.gi
    found = [] if gi is None else [Problem("market.gi", message) for message in _gi_messages(dossier, gi)]
    for index, price in enumerate(dossier.market.prices):
        if not states_date(price.date, claim_quotes(dossier, [price.claim_id])):
            found.append(
                Problem(f"market.prices.{index}", _unstated_date("date", price.date, price.claim_id))
            )
    for index, workforce in enumerate(dossier.market.workforce):
        if figure_gaps(str(workforce.year), claim_quotes(dossier, [workforce.claim_id])):
            found.append(
                Problem(
                    f"market.workforce.{index}",
                    f"the year {workforce.year} is in none of {workforce.claim_id}'s quotes",
                )
            )
    return found


def picture_problems(dossier: Dossier) -> list[Problem]:
    return [
        Problem(picture.id, f"licence {picture.licence!r} is not on the open licence allow-list")
        for picture in dossier.pictures
        if not (open_licence(picture.licence) or open_licence(picture.licence_url))
    ]


def _indian_place_messages(place: Place, register: DistrictRegister) -> list[str]:
    messages = []
    if place.kind in INDIAN_DISTRICT_PLACE_KINDS and (place.district is None or place.state is None):
        messages.append(f"a {place.kind} in India names its district and state as the LGD register does")
    if place.district is not None and place.state is None:
        messages.append("names a district without its state")
    if place.state is not None and not register.has_state(place.state):
        messages.append(_unknown("state", place.state, register.states, "the LGD register"))
    elif (
        place.state is not None
        and place.district is not None
        and not register.has_district(place.state, place.district)
    ):
        messages.append(
            _unknown(
                "district",
                place.district,
                register.district_names(place.state),
                f"{place.state} in the LGD register",
            )
        )
    return messages


def _unknown(label: str, name: str, names: Iterable[str], where: str) -> str:
    close = get_close_matches(name, sorted(names), n=SUGGESTIONS, cutoff=SUGGESTION_CUTOFF)
    hint = f"; did you mean {', '.join(close)}?" if close else ""
    return f"{label} {name!r} is not in {where}{hint}"


def _formula_messages(dossier: Dossier, reaction: Reaction) -> list[str]:
    quotes = claim_quotes(dossier, reaction.claim_ids)
    formulas = [species.formula for species in (*reaction.reactants, *reaction.products) if species.formula]
    return [
        f"formula {formula} appears in none of its claims' quotes"
        for formula in dict.fromkeys(formulas)
        if not any(quote_occurs(formula, quote) for quote in quotes)
    ]


def _gi_messages(dossier: Dossier, gi: GiRecord) -> list[str]:
    cited = {
        dossier.source(quote.source_id).kind
        for claim_id in gi.claim_ids
        for quote in dossier.claim(claim_id).quotes
    }
    messages = (
        []
        if cited & set(GI_RECORD_SOURCE_KINDS)
        else ["the GI record cites no GI journal or registry source"]
    )
    count = None if gi.authorised_user_count is None else str(gi.authorised_user_count)
    figures = [gi.application_number, gi.certificate_number, gi.journal_issue, count]
    quotes = claim_quotes(dossier, gi.claim_ids)
    gaps = [gap for figure in figures if figure is not None for gap in figure_gaps(figure, quotes)]
    dates = [
        _unstated_date(label, day, "its claims")
        for label, day in (("filedOn", gi.filed_on), ("registeredOn", gi.registered_on))
        if day is not None and not states_date(day, quotes)
    ]
    return messages + [f"{gap} appears in none of its claims' quotes" for gap in dict.fromkeys(gaps)] + dates


def _unstated_date(label: str, day: str, cited: str) -> str:
    return f"the {label} {day} is not stated to that precision by any quote of {cited}"
