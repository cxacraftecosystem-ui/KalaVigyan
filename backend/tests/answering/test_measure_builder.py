from collections.abc import Collection
from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from app.models.enums import DISCIPLINES
from app.research.blocks_insight import MeasureRegion, UnitConversion
from app.research.citations import SourceRef
from app.research.crafts import CraftRef
from app.research.explainer import BUILT_BLOCK_KINDS
from app.science.records import KnownClaim
from app.services import block_builders
from app.services.block_builders import BLOCK_BUILDERS, BlockBuilders
from app.services.builder_interface import BuilderTools
from app.services.measure_builder import MeasureBuilder
from app.services.measure_regions import (
    CraftPlaces,
    RegionalFactor,
    RegionalFactors,
    chosen_factors,
    claim_factors,
    stated_region,
)
from app.services.piece_lookup import PieceLookup
from app.services.piece_store import kept_for

from ..contracts.phase_d_golden import phase_d, phase_d_blocks
from ..place.season_supply_fixtures import claims_of
from .insight_fixtures import insight_ask, source, written

TOOLS = BuilderTools(sessions=None, live=None, plan_model=None, compose_model=None)
KACHCHH = MeasureRegion(state_lgd=24, state_name="Gujarat", district_lgd=449, district_name="Kachchh")
GUJARAT = MeasureRegion(state_lgd=24, state_name="Gujarat", district_lgd=None, district_name=None)
BARMER = MeasureRegion(state_lgd=8, state_name="Rajasthan", district_lgd=90, district_name="Barmer")
AJRAKH_PLACES = CraftPlaces(states=frozenset({24, 8}), districts=frozenset({449, 90}))
GI = "s-gi"
GAZETTEER = "s-gazetteer"
SOURCES = {GI: source(GI), GAZETTEER: source(GAZETTEER, "GOVERNMENT_REPORT")}
ALUM = written("alum", "Add 5 seers of alum to the dye bath.")
SEER_TABLE = written("seer-table", "In Kachchh a seer weighed 0.933 kg.", source_id=GAZETTEER)


class Factors:
    def __init__(self, found: RegionalFactors | None = None) -> None:
        self.found = found or RegionalFactors()
        self.calls: list[tuple[str, frozenset[str]]] = []

    async def __call__(self, craft: CraftRef, units: Collection[str]) -> RegionalFactors:
        self.calls.append((craft.slug, frozenset(units)))
        return self.found


def golden_sources() -> dict[str, SourceRef]:
    return {row["id"]: SourceRef.model_validate(row) for row in phase_d()["sources"]}


def feet() -> tuple[dict[str, Any], KnownClaim]:
    row = phase_d_blocks()["s4.b1"]["rows"][0]
    return row, claims_of([row["sentence"]])[0]


def seer_factor(
    claim: KnownClaim = SEER_TABLE, region: MeasureRegion = KACHCHH, factor: str = "0.933"
) -> Any:
    return RegionalFactor("seer", "kg", Decimal(factor), region, claim.citations[0])


async def test_the_fixture_s_feet_become_the_fixture_s_measure() -> None:
    row, claim = feet()
    factors = Factors()
    built = await MeasureBuilder(TOOLS, factors=factors).build(insight_ask([claim], golden_sources()))
    (block,) = built.blocks
    shown = block.rows[0].model_dump(mode="json", by_alias=True)
    assert shown == {**row, "sentence": {**row["sentence"], "id": "s4.measure.1"}}
    assert (block.id, factors.calls, built.sources) == ("s4.measure", [], {})


async def test_a_local_unit_with_no_value_stated_for_its_region_stays_as_written() -> None:
    factors = Factors()
    built = await MeasureBuilder(TOOLS, factors=factors).build(insight_ask([ALUM], SOURCES))
    assert built.blocks == ()
    assert factors.calls == [("Kutch-Ajrakh", frozenset({"seer"}))]


async def test_a_value_stated_for_the_craft_s_region_converts_with_its_region_and_source() -> None:
    found = RegionalFactors({"seer": seer_factor()}, {GAZETTEER: SOURCES[GAZETTEER]})
    built = await MeasureBuilder(TOOLS, factors=Factors(found)).build(insight_ask([ALUM], SOURCES))
    (block,) = built.blocks
    (row,) = block.rows
    assert (row.stated, row.low, row.unit_label) == ("5 seers", 5.0, "seers")
    assert (row.metric.low, row.metric.high, row.metric.unit) == (4.67, None, "kg")
    conversion = row.conversion
    assert (conversion.basis, conversion.factor, conversion.region) == ("REGIONAL", 0.933, KACHCHH)
    assert conversion.citation == SEER_TABLE.citations[0] and conversion.dataset is None
    assert block.cited_source_ids() == [GI, GAZETTEER]
    assert set(built.sources) == {GAZETTEER}


async def test_a_regional_value_its_quote_does_not_state_converts_nothing() -> None:
    found = RegionalFactors({"seer": seer_factor(factor="0.93")}, {GAZETTEER: SOURCES[GAZETTEER]})
    built = await MeasureBuilder(TOOLS, factors=Factors(found)).build(insight_ask([ALUM], SOURCES))
    assert built.blocks == ()


@pytest.mark.parametrize(
    ("region", "cited", "message"),
    [
        (KACHCHH, False, "named region"),
        (None, True, "named region"),
        (KACHCHH, True, None),
    ],
)
def test_a_regional_conversion_needs_its_region_and_its_source(
    region: MeasureRegion | None, cited: bool, message: str | None
) -> None:
    fields = {"unit": "seer", "metric_unit": "kg", "factor": 0.933, "basis": "REGIONAL", "dataset": None}
    citation = SEER_TABLE.citations[0] if cited else None
    if message is None:
        assert UnitConversion(**fields, region=region, citation=citation).region == region
        return
    with pytest.raises(ValidationError, match=message):
        UnitConversion(**fields, region=region, citation=citation)


@pytest.mark.parametrize(
    ("text", "region"),
    [
        ("A seer of Kachchh weighs 0.933 kg.", KACHCHH),
        ("In Kachchh, Gujarat a seer weighed 0.933 kg.", KACHCHH),
        ("In Gujarat a seer weighed 0.933 kg.", GUJARAT),
        ("A seer of Kutch weighs 0.933 kg.", KACHCHH),
        ("In Kutch, Gujarat a seer weighed 0.933 kg.", KACHCHH),
        ("In Kutch and Kachchh a seer weighed 0.933 kg.", KACHCHH),
        ("In Kachchh and Barmer a seer weighed 0.933 kg.", None),
        ("In Kachchh, Rajasthan a seer weighed 0.933 kg.", None),
        ("In Gujarat and Rajasthan a seer weighed 0.933 kg.", None),
    ],
)
def test_a_conversion_holds_only_in_the_one_region_its_source_names(
    text: str, region: MeasureRegion | None
) -> None:
    assert stated_region([text]) == region


def test_a_stated_value_is_read_with_the_region_its_claim_names() -> None:
    claim = written("kachchh-seer", "Kachchh weights were local.", quote="Here a seer weighs 0.933 kg.")
    (factor,) = claim_factors(claim, {"seer"})
    assert (factor.unit, factor.factor, factor.metric_unit, factor.region) == (
        "seer",
        Decimal("0.933"),
        "kg",
        KACHCHH,
    )
    assert claim_factors(claim, {"maund"}) == []
    unnamed = written("anywhere-seer", "Weights were local.", quote="Here a seer weighs 0.933 kg.")
    assert claim_factors(unnamed, {"seer"}) == []
    derived = written("tola-seer", "In Kachchh a seer was 80 tolas.")
    assert claim_factors(derived, {"seer"}) == []


def test_the_narrowest_region_holding_the_craft_gives_the_one_value() -> None:
    district, state = seer_factor(), seer_factor(region=GUJARAT, factor="0.9")
    assert chosen_factors([state, district], AJRAKH_PLACES) == {"seer": district}
    assert chosen_factors([state], AJRAKH_PLACES) == {"seer": state}
    elsewhere = seer_factor(region=KACHCHH)
    assert chosen_factors([elsewhere], CraftPlaces(states=frozenset({8}), districts=frozenset({90}))) == {}
    differing = [district, seer_factor(region=BARMER, factor="0.9")]
    assert chosen_factors(differing, AJRAKH_PLACES) == {}
    agreeing = [district, seer_factor(region=BARMER)]
    assert chosen_factors(agreeing, AJRAKH_PLACES) == {"seer": district}


async def test_a_measure_joins_every_field_and_is_kept_in_its_section_s_slot() -> None:
    entry = next(entry for entry in BLOCK_BUILDERS if entry.kind == "measure")
    assert entry.disciplines == set(DISCIPLINES) and not entry.rebuilt_on_reuse
    assert "measure" in BUILT_BLOCK_KINDS
    _, claim = feet()
    built = await MeasureBuilder(TOOLS, factors=Factors()).build(insight_ask([claim], golden_sources()))
    assert kept_for(built.blocks[0], PieceLookup(craft_slug="Kutch-Ajrakh"))


async def test_a_built_measure_passes_the_registry_s_checks(monkeypatch: pytest.MonkeyPatch) -> None:
    entry = next(entry for entry in BLOCK_BUILDERS if entry.kind == "measure")
    found = RegionalFactors({"seer": seer_factor()}, {GAZETTEER: SOURCES[GAZETTEER]})
    builders = BlockBuilders([(entry, MeasureBuilder(TOOLS, factors=Factors(found)))])
    added = await builders.added(insight_ask([ALUM], SOURCES, discipline="PROCESS"))
    assert [block.kind for block in added.blocks] == ["measure"]
    assert set(added.sources) == {GI, GAZETTEER}
    monkeypatch.setattr(block_builders, "BUILT_BLOCK_KINDS", ("prose",))
    assert (await builders.added(insight_ask([ALUM], SOURCES))).blocks == ()
