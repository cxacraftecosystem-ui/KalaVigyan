import asyncio
from collections.abc import Iterator, Mapping
from typing import Any

from app.research.datasets import DatasetRef
from app.research.simulation_draft import SIMULATION_HTML_MAX_CHARS, RowValue
from app.research.structured import StructuredReply
from app.research.untrusted import untrusted_block
from app.services.builder_interface import BuildAsk, BuilderTools
from app.services.knowledge_view import ClaimView
from app.services.simulation_builder import (
    NO_QUANTITY,
    NO_TIME_TO_REDRAFT,
    OUT_OF_TIME,
    SimulationBudget,
    SimulationBuilder,
)

from .fixtures import (
    BUILT_AT,
    WATER_CLAIM,
    WATER_TEXT,
    DraftModel,
    PictureSearches,
    StoredPieces,
    accepted_html,
    build_ask,
    draft,
    no_matter,
    value_choices,
    water_citation,
)

RAIN = DatasetRef(
    code="CHIRPS_RAIN",
    title="CHIRPS daily rainfall",
    publisher="Climate Hazards Center",
    edition="v2.0",
    period="1991-2020",
    native_resolution="0.05 degree",
    licence="CC BY 4.0",
    licence_url=None,
    attribution=None,
    citation=None,
    url=None,
)
RAIN_STATED = "annual rainfall (mean, 1991-2020) in Kachchh"


class SilentModel(DraftModel):
    async def __call__(self, *, system: str, user: str, schema: Mapping[str, Any]) -> StructuredReply:
        self.calls.append({"system": system, "user": user, "schema": schema})
        await asyncio.Event().wait()
        raise AssertionError("never answers")


def ticking(*seconds: float) -> Iterator[float]:
    yield from seconds


def budgeted(
    model: DraftModel, budget: SimulationBudget, rows: list[RowValue] | None = None
) -> SimulationBuilder:
    async def datasets(ask: BuildAsk) -> list[RowValue]:
        return list(rows or [])

    tools = BuilderTools(sessions=None, live=None, plan_model=None, compose_model=model)
    return SimulationBuilder(
        tools,
        stored=StoredPieces(),
        clock=lambda: BUILT_AT,
        matter=no_matter,
        pictures=PictureSearches(),
        datasets=datasets,
        budget=budget,
    )


async def test_a_draft_that_runs_past_the_budget_adds_nothing_and_says_why() -> None:
    model = SilentModel([])
    built = await budgeted(model, SimulationBudget(seconds=0.01)).build(build_ask())
    assert (built.blocks, built.note) == ((), OUT_OF_TIME)
    assert len(model.calls) == 1


async def test_a_failed_draft_is_not_redrafted_when_less_time_is_left_than_it_took() -> None:
    oversized = draft(accepted_html() + "x" * SIMULATION_HTML_MAX_CHARS)
    model = DraftModel([oversized, draft(accepted_html())])
    times = ticking(0.0, 45.0)
    built = await budgeted(model, SimulationBudget(seconds=60.0, timer=lambda: next(times))).build(
        build_ask()
    )
    assert (built.blocks, built.note) == ((), NO_TIME_TO_REDRAFT)
    assert len(model.calls) == 1


async def test_a_failed_draft_is_redrafted_when_the_budget_leaves_room() -> None:
    oversized = draft(accepted_html() + "x" * SIMULATION_HTML_MAX_CHARS)
    model = DraftModel([oversized, draft(accepted_html())])
    times = ticking(0.0, 20.0)
    built = await budgeted(model, SimulationBudget(seconds=60.0, timer=lambda: next(times))).build(
        build_ask()
    )
    assert [block.kind for block in built.blocks] == ["simulation"] and built.note is None
    assert len(model.calls) == 2


async def test_a_section_stating_no_quantity_asks_no_model_and_says_why() -> None:
    plain = water_citation() | {"quote": "Water is the lifeline of printing and dyeing."}
    view = ClaimView(WATER_CLAIM, WATER_TEXT, "PROVISIONAL", "CONCEPT", None, citations=[plain])
    model = DraftModel([draft(accepted_html())])
    built = await budgeted(model, SimulationBudget()).build(build_ask(views=[view]))
    assert (built.blocks, built.note) == ((), NO_QUANTITY)
    assert model.calls == []


async def test_a_dataset_row_is_offered_apart_from_the_quoted_values_and_cited_by_its_dataset() -> None:
    rows = [RowValue(450.0, "mm", RAIN_STATED, RAIN)]
    chosen = [*value_choices(), {"ref": "d1", "key": "rainMm", "label": "Yearly rain", "unit": "mm"}]
    model = DraftModel([draft(accepted_html(), values=chosen)])
    built = await budgeted(model, SimulationBudget(), rows).build(build_ask())
    assert untrusted_block("d1", "value", f"450 mm, stated as: {RAIN_STATED}") in model.calls[0]["user"]
    (block,) = built.blocks
    rain = next(value for value in block.values if value.key == "rainMm")
    assert (rain.value, rain.unit, rain.dataset_code, rain.citations, rain.stated) == (
        450.0,
        "mm",
        RAIN.code,
        [],
        None,
    )
    assert block.datasets == [RAIN]


async def test_an_explainer_resting_on_dataset_rows_alone_is_refused() -> None:
    plain = water_citation() | {"quote": "Water is the lifeline of printing and dyeing."}
    view = ClaimView(WATER_CLAIM, WATER_TEXT, "PROVISIONAL", "CONCEPT", None, citations=[plain])
    rows = [RowValue(450.0, "mm", RAIN_STATED, RAIN)]
    only_rows = [{"ref": "d1", "key": "rainMm", "label": "Yearly rain", "unit": "mm"}]
    model = DraftModel([draft(accepted_html(), values=only_rows)])
    built = await budgeted(model, SimulationBudget(), rows).build(build_ask(views=[view]))
    assert built.blocks == ()
    assert "dataset rows alone are no explainer" in model.calls[1]["user"]
