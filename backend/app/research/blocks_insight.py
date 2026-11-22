from __future__ import annotations

import re
from collections.abc import Iterator, Mapping
from decimal import Decimal
from types import MappingProxyType
from typing import Annotated, ClassVar, Literal, Self

from pydantic import Field, model_validator

from .base import ContractModel, PartialDate
from .blocks import (
    SENTENCE,
    BlockBase,
    ExplainerSentence,
    SentenceSpec,
    named_in,
    require_facts,
    stated_texts,
)
from .citations import Citation
from .crafts import CraftRef
from .datasets import DatasetRef
from .measures import (
    CONVERSION_BASES,
    DEFINED_UNITS,
    UNIT_DEFINITIONS,
    MetricUnit,
    UnitKey,
    metric_value,
    stated_numbers,
)
from .quotes import figures_in
from .stated_amounts import AMOUNT_KINDS, AMOUNT_UNITS
from .stated_dates import states_date

__all__ = [
    "CURRENCIES",
    "CURRENCY_MARKS",
    "GI_STATUSES",
    "MEASURE_ROWS_MAX",
    "PRICE_SCALES",
    "QUANTITY_ROWS_MAX",
    "QUANTITY_ROWS_MIN",
    "SCALE_WORDS",
    "GiStatus",
    "MarketGiBlock",
    "MeasureBlock",
    "MeasureRegion",
    "MeasureRow",
    "MetricAmount",
    "PriceRange",
    "QuantitiesBlock",
    "QuantityRow",
    "UnitConversion",
]

MEASURE_ROWS_MAX = 12
QUANTITY_ROWS_MIN = 3
QUANTITY_ROWS_MAX = 12
GI_STATUSES = ("APPLIED", "REGISTERED", "WITHDRAWN")
CURRENCIES = ("INR", "USD")
CURRENCY_MARKS: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {"INR": ("rs", "₹", "rupee", "rupees", "inr"), "USD": ("$", "usd", "dollar", "dollars")}
)
PRICE_SCALES = ("THOUSAND", "LAKH", "CRORE")
SCALE_WORDS: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {"THOUSAND": ("thousand",), "LAKH": ("lakh", "lakhs"), "CRORE": ("crore", "crores")}
)
ConversionBasis = Literal[*CONVERSION_BASES]
GiStatusName = Literal[*GI_STATUSES]
Currency = Literal[*CURRENCIES]
PriceScale = Literal[*PRICE_SCALES]
AmountKind = Literal[*AMOUNT_KINDS]
Lgd = Annotated[int, Field(ge=1)]


class MeasureRegion(ContractModel):
    state_lgd: Lgd
    state_name: str = Field(min_length=1, max_length=200)
    district_lgd: Lgd | None
    district_name: str | None = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def _a_district_with_its_name(self) -> Self:
        if (self.district_lgd is None) != (self.district_name is None):
            raise ValueError("a region names its district together with its code")
        return self


class UnitConversion(ContractModel):
    unit: UnitKey
    metric_unit: MetricUnit
    factor: float = Field(gt=0)
    basis: ConversionBasis
    region: MeasureRegion | None
    citation: Citation | None
    dataset: DatasetRef | None

    @model_validator(mode="after")
    def _a_defined_or_a_stated_regional_value(self) -> Self:
        defined = DEFINED_UNITS.get(self.unit)
        if self.basis == "DEFINED":
            exact = defined is not None and (defined.metric_unit, defined.factor) == (
                self.metric_unit,
                Decimal(repr(self.factor)),
            )
            if not exact or self.region or self.citation or self.dataset != UNIT_DEFINITIONS:
                raise ValueError(f"{self.unit} converts by its exact definition, cited to the definitions")
            return self
        if defined is not None or self.region is None or self.citation is None or self.dataset is not None:
            raise ValueError(f"{self.unit} converts by a value a cited source states for a named region")
        quote = self.citation.quote or ""
        if Decimal(repr(self.factor)) not in stated_numbers(quote):
            raise ValueError(f"{self.unit} converts by {self.factor}, which its cited quote does not state")
        return self


class MetricAmount(ContractModel):
    low: float = Field(ge=0)
    high: float | None
    unit: MetricUnit


class MeasureRow(ContractModel):
    stated: str = Field(min_length=1, max_length=120)
    low: float = Field(gt=0)
    high: float | None
    unit_label: str = Field(min_length=1, max_length=60)
    conversion: UnitConversion
    metric: MetricAmount
    sentence: ExplainerSentence

    @model_validator(mode="after")
    def _the_stated_quantity_converted(self) -> Self:
        if not named_in(self.stated, self.sentence):
            raise ValueError(f"measure {self.stated!r} is what its sentence or quotes state")
        if not _states_range(self.stated, self.low, self.high):
            raise ValueError(f"measure {self.stated!r} carries the numbers it states, low then high")
        if not _mentions(self.stated, self.unit_label):
            raise ValueError(f"measure {self.stated!r} names its unit {self.unit_label!r}")
        factor = self.conversion.factor
        expected = MetricAmount(
            low=metric_value(self.low, factor),
            high=None if self.high is None else metric_value(self.high, factor),
            unit=self.conversion.metric_unit,
        )
        if self.metric != expected:
            raise ValueError(f"measure {self.stated!r} is {expected.low} to {expected.high} {expected.unit}")
        return self


class MeasureBlock(BlockBase):
    SENTENCES: ClassVar[SentenceSpec] = (("rows", [(("sentence", SENTENCE),)]),)

    kind: Literal["measure"]
    version: Literal[1]
    rows: list[MeasureRow] = Field(min_length=1, max_length=MEASURE_ROWS_MAX)

    @model_validator(mode="after")
    def _each_quantity_once(self) -> Self:
        require_facts(f"measure {self.id}", [row.sentence for row in self.rows])
        stated = [(row.stated.casefold(), row.sentence.id) for row in self.rows]
        if len(set(stated)) != len(stated):
            raise ValueError(f"measure {self.id} converts each stated quantity once")
        return self

    def citations(self) -> Iterator[Citation]:
        yield from super().citations()
        for row in self.rows:
            if row.conversion.citation is not None:
                yield row.conversion.citation

    def cites_datasets(self) -> bool:
        return any(row.conversion.dataset is not None for row in self.rows)

    def shown_labels(self) -> list[str]:
        return [row.stated for row in self.rows]


class QuantityRow(ContractModel):
    stated: str = Field(min_length=1, max_length=120)
    low: float = Field(ge=0)
    high: float | None
    unit: UnitKey
    measures: AmountKind
    sentence: ExplainerSentence

    @model_validator(mode="after")
    def _a_quantity_as_its_sentence_states_it(self) -> Self:
        unit = AMOUNT_UNITS.get(self.unit)
        if unit is None or unit.measures != self.measures:
            raise ValueError(f"quantity {self.stated!r} measures what its unit {self.unit!r} measures")
        if not named_in(self.stated, self.sentence):
            raise ValueError(f"quantity {self.stated!r} is what its sentence or quotes state")
        if not _states_range(self.stated, self.low, self.high):
            raise ValueError(f"quantity {self.stated!r} carries the numbers it states, low then high")
        return self


class QuantitiesBlock(BlockBase):
    SENTENCES: ClassVar[SentenceSpec] = (("rows", [(("sentence", SENTENCE),)]),)

    kind: Literal["quantities"]
    version: Literal[1]
    rows: list[QuantityRow] = Field(min_length=QUANTITY_ROWS_MIN, max_length=QUANTITY_ROWS_MAX)

    @model_validator(mode="after")
    def _each_stated_quantity_once(self) -> Self:
        require_facts(f"quantities {self.id}", [row.sentence for row in self.rows])
        stated = [(row.stated.casefold(), row.sentence.original or row.sentence.text) for row in self.rows]
        if len(set(stated)) != len(stated):
            raise ValueError(f"quantities {self.id} list each stated quantity of a sentence once")
        return self

    def shown_labels(self) -> list[str]:
        return [row.stated for row in self.rows]


class GiStatus(ContractModel):
    status: GiStatusName
    application_number: str | None = Field(min_length=1, max_length=40)
    certificate_number: str | None = Field(min_length=1, max_length=40)
    filed_on: PartialDate | None
    registered_on: PartialDate | None
    journal_issue: str | None = Field(min_length=1, max_length=100)
    proprietors: list[str]
    authorised_user_count: int | None = Field(ge=0)
    sentences: list[ExplainerSentence] = Field(min_length=1)

    @model_validator(mode="after")
    def _a_registry_record_its_sentences_state(self) -> Self:
        problems = _gi_status_problems(self)
        stated = [text for sentence in self.sentences for text in stated_texts(sentence)]
        figures = {figure for text in stated for figure in figures_in(text)}
        missing = [figure for figure in _gi_figures(self) if figure not in figures]
        missing += [
            day for day in (self.filed_on, self.registered_on) if day and not states_date(day, stated)
        ]
        if missing:
            problems.append(f"the GI record states {', '.join(missing)}, which its sentences do not")
        if any(not any(named_in(name, s) for s in self.sentences) for name in self.proprietors):
            problems.append("the GI record names only proprietors its sentences state")
        if len(set(self.proprietors)) != len(self.proprietors):
            problems.append("the GI record names each proprietor once")
        if problems:
            raise ValueError("; ".join(problems))
        return self


class PriceRange(ContractModel):
    stated: str = Field(min_length=1, max_length=120)
    low: float = Field(ge=0)
    high: float | None
    currency: Currency
    scale: PriceScale | None
    per: str | None = Field(min_length=1, max_length=60)
    priced_on: PartialDate
    place: str = Field(min_length=1, max_length=200)
    district_lgd: Lgd | None
    sentence: ExplainerSentence

    @model_validator(mode="after")
    def _a_price_with_its_date_and_place(self) -> Self:
        problems = []
        if not named_in(self.stated, self.sentence) or not _states_range(self.stated, self.low, self.high):
            problems.append(f"price {self.stated!r} is stated by its sentence or quotes, low then high")
        if not any(_mentions(self.stated, mark) for mark in CURRENCY_MARKS[self.currency]):
            problems.append(f"price {self.stated!r} states its currency {self.currency}")
        stated_scale = [
            s for s, marks in SCALE_WORDS.items() if any(_mentions(self.stated, m) for m in marks)
        ]
        if stated_scale != ([self.scale] if self.scale else []):
            problems.append(f"price {self.stated!r} carries the scale it states")
        for name in (self.place, self.per):
            if name is not None and not named_in(name, self.sentence):
                problems.append(f"price {self.stated!r} names {name!r} only as its sentence states it")
        if not states_date(self.priced_on, stated_texts(self.sentence)):
            problems.append(
                f"price {self.stated!r} is dated only as precisely as its sentence or quotes state"
            )
        if problems:
            raise ValueError("; ".join(problems))
        return self


class MarketGiBlock(BlockBase):
    SENTENCES: ClassVar[SentenceSpec] = (
        ("gi", (("sentences", [SENTENCE]),)),
        ("imitation", [SENTENCE]),
        ("prices", [(("sentence", SENTENCE),)]),
    )

    kind: Literal["market_gi"]
    version: Literal[1]
    craft: CraftRef
    gi: GiStatus | None
    imitation: list[ExplainerSentence]
    prices: list[PriceRange]

    @model_validator(mode="after")
    def _cited_market_facts(self) -> Self:
        require_facts(f"market {self.id}", list(self.cited_sentences()))
        return self

    def shown_labels(self) -> list[str]:
        return [self.craft.name, *(price.stated for price in self.prices)]


def _states_range(stated: str, low: float, high: float | None) -> bool:
    expected = [Decimal(repr(low))] + ([] if high is None else [Decimal(repr(high))])
    return (high is None or high > low) and stated_numbers(stated) == expected


def _mentions(text: str, mark: str) -> bool:
    folded, wanted = text.casefold(), mark.casefold()
    if not wanted.isalpha():
        return wanted in folded
    return re.search(rf"(?<![^\W\d_]){re.escape(wanted)}(?![^\W\d_])", folded) is not None


def _gi_status_problems(gi: GiStatus) -> list[str]:
    registered = gi.registered_on is not None or gi.certificate_number is not None
    applied = gi.application_number is not None or gi.filed_on is not None
    rules = {
        "REGISTERED": registered,
        "APPLIED": applied and not registered,
        "WITHDRAWN": gi.application_number is not None,
    }
    problems = [] if rules[gi.status] else [f"a {gi.status} GI record carries what makes it so"]
    if gi.filed_on and gi.registered_on and gi.filed_on > gi.registered_on:
        problems.append("a GI is filed before it is registered")
    return problems


def _gi_figures(gi: GiStatus) -> list[str]:
    numbers = [gi.application_number, gi.certificate_number, gi.journal_issue]
    count = None if gi.authorised_user_count is None else str(gi.authorised_user_count)
    return [figure for value in (*numbers, count) if value for figure in figures_in(value)]
