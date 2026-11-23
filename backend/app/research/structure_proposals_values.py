from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from .colours import states_colour
from .quotes import quote_occurs
from .structure_proposals import (
    BOTANICAL_NAME,
    GI_RECORD,
    GLOSSARY_TERM,
    GROUP_NAME,
    NATIVE_NAME,
    REACTION,
    STAGE_AFTER,
    GiRecordItem,
    ReactionItem,
    StageAfterItem,
    StructureCheck,
)

__all__ = ["STATED_CHECK", "StatedValue", "stated_check", "stated_values"]

STATED_CHECK = "STATED"
NOTHING_NAMED = "The statement is the whole of it: the proposal names nothing else a quote must hold."
EVERY_VALUE_QUOTED = "Every name and number it gives is in one of its quotes: {names}."
NOT_QUOTED = "{label} ({value}) appears in none of the quotes."
YEAR_CHARS = 4


@dataclass(frozen=True)
class StatedValue:
    label: str
    values: tuple[str, ...]
    colour: bool = False

    @property
    def shown(self) -> str:
        return " or ".join(self.values)


def stated_values(item: Any) -> list[StatedValue]:
    found = _VALUES.get(item.kind)
    return [] if found is None else found(item)


def stated_check(item: Any, quotes: Sequence[str]) -> StructureCheck:
    values = stated_values(item)
    missing = [value for value in values if not _quoted(value, quotes)]
    if missing:
        reasons = [NOT_QUOTED.format(label=_opening(value.label), value=value.shown) for value in missing]
        return StructureCheck(check=STATED_CHECK, passed=False, reasons=reasons)
    if not values:
        return StructureCheck(check=STATED_CHECK, passed=True, reasons=[NOTHING_NAMED])
    names = ", ".join(value.label for value in values)
    return StructureCheck(check=STATED_CHECK, passed=True, reasons=[EVERY_VALUE_QUOTED.format(names=names)])


def _opening(label: str) -> str:
    return label[:1].upper() + label[1:]


def _quoted(value: StatedValue, quotes: Sequence[str]) -> bool:
    if value.colour:
        return any(states_colour(quote, colour) for quote in quotes for colour in value.values)
    return any(
        quote_occurs(stated.casefold(), quote.casefold()) for quote in quotes for stated in value.values
    )


def _after(item: StageAfterItem) -> list[StatedValue]:
    return [StatedValue(f"the colour {colour.lower()}", (colour,), colour=True) for colour in item.colours]


def _named(label: str, attribute: str) -> Callable[[Any], list[StatedValue]]:
    def values(item: Any) -> list[StatedValue]:
        return [StatedValue(label, (str(getattr(item, attribute)),))]

    return values


def _reaction(item: ReactionItem) -> list[StatedValue]:
    sides = (("reactant", item.reactants), ("product", item.products))
    return [
        StatedValue(
            f"the {side} {species.name}", (species.name, *((species.formula,) if species.formula else ()))
        )
        for side, listed in sides
        for species in listed
    ]


def _gi(item: GiRecordItem) -> list[StatedValue]:
    given = [
        ("the application number", item.application_number),
        ("the certificate number", item.certificate_number),
        ("the journal issue", item.journal_issue),
        ("the year it was filed", item.filed_on[:YEAR_CHARS] if item.filed_on else None),
        ("the year it was registered", item.registered_on[:YEAR_CHARS] if item.registered_on else None),
        (
            "the number of authorised users",
            None if item.authorised_user_count is None else str(item.authorised_user_count),
        ),
    ]
    values = [StatedValue(label, (value,)) for label, value in given if value is not None]
    return values + [StatedValue(f"the proprietor {name}", (name,)) for name in item.proprietors]


_VALUES: Mapping[str, Callable[[Any], list[StatedValue]]] = MappingProxyType(
    {
        STAGE_AFTER: _after,
        NATIVE_NAME: _named("the native name", "text"),
        REACTION: _reaction,
        BOTANICAL_NAME: _named("the botanical name", "botanical_name"),
        GLOSSARY_TERM: _named("the term", "term"),
        GI_RECORD: _gi,
        GROUP_NAME: _named("the name", "name"),
    }
)
