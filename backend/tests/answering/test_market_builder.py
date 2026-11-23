import uuid
from collections.abc import Sequence
from dataclasses import replace
from typing import Any

import pytest

from app.research.blocks_insight import MarketGiBlock
from app.research.citations import SourceRef
from app.research.crafts import CraftRef
from app.research.explainer import BUILT_BLOCK_KINDS
from app.science.records import KnownClaim
from app.services.block_builders import BLOCK_BUILDERS, BlockBuilders
from app.services.builder_interface import BuilderTools
from app.services.curation_keys import curated_id
from app.services.market_builder import MarketGiBuilder, market_block
from app.services.market_store import MarketOffers, PriceOffer
from app.services.piece_lookup import PieceLookup
from app.services.piece_store import kept_for

from ..contracts.phase_d_golden import phase_d, phase_d_blocks
from ..place.season_supply_fixtures import claims_of
from .insight_fixtures import claim_view, curated_offers, insight_ask, source, written

TOOLS = BuilderTools(sessions=None, live=None, plan_model=None, compose_model=None)
BLOCK = "s5.market1"
DOSSIER_CLAIMS = tuple(f"C{n:03d}" for n in range(1, 200))
GI = "s-gi"
PAPER = "s-paper"
SOURCES = {GI: source(GI), PAPER: source(PAPER, "PAPER")}
BARMER_PRICE = written(
    "barmer-price", "In Barmer an ajrakh piece was valued at Rs. 7 in 1975.", source_id=PAPER
)


def golden_market(block_id: str) -> dict[str, Any]:
    return phase_d_blocks()[block_id]


def golden_claims(block_id: str) -> list[KnownClaim]:
    block = golden_market(block_id)
    return claims_of([*block["gi"]["sentences"], *block["imitation"]])


def golden_sources(kind: str | None = None) -> dict[str, SourceRef]:
    rows = phase_d()["sources"]
    return {row["id"]: SourceRef.model_validate(row | ({"kind": kind} if kind else {})) for row in rows}


def offers_of(
    craft: CraftRef,
    claims: Sequence[KnownClaim],
    sources: dict[str, SourceRef],
    prices: Sequence[PriceOffer] = (),
) -> MarketOffers:
    priced = {price.claim_id for price in prices}
    return MarketOffers(
        craft=craft,
        prices=tuple(prices),
        candidates=tuple(claim.id for claim in claims if claim.id not in priced),
        views={claim.id: claim_view(claim) for claim in claims},
        sources=sources,
    )


def golden_offers(block_id: str, kind: str | None = None) -> MarketOffers:
    craft = CraftRef.model_validate(golden_market(block_id)["craft"])
    return offers_of(craft, golden_claims(block_id), golden_sources(kind))


def shown(block: MarketGiBlock | None) -> dict[str, Any]:
    assert block is not None
    found = block.model_dump(mode="json", by_alias=True)
    gi = found["gi"] and {**found["gi"], "sentences": [s["text"] for s in found["gi"]["sentences"]]}
    return {**found, "gi": gi, "imitation": [s["text"] for s in found["imitation"]]}


@pytest.mark.parametrize("block_id", ["s5.b1", "s5.b2"])
def test_the_stored_registry_claims_give_the_fixture_s_market_blocks(block_id: str) -> None:
    golden = golden_market(block_id)
    built = shown(market_block(golden_offers(block_id), block_id=BLOCK))
    gi = {**golden["gi"], "sentences": [s["text"] for s in golden["gi"]["sentences"]]}
    assert built["gi"] == gi
    assert built["imitation"] == [s["text"] for s in golden["imitation"]]
    assert (built["craft"], built["prices"]) == (golden["craft"], [])


def test_signs_of_imitation_come_only_from_gi_journal_text() -> None:
    offers = golden_offers("s5.b2")
    (sign,) = golden_market("s5.b2")["imitation"]
    paper = {c["sourceId"] for c in sign["citations"]}
    sources = {
        sid: ref.model_copy(update={"kind": "PAPER"}) if sid in paper else ref
        for sid, ref in offers.sources.items()
    }
    built = shown(market_block(replace(offers, sources=sources), block_id=BLOCK))
    assert built["gi"]["status"] == "REGISTERED" and built["imitation"] == []
    assert market_block(golden_offers("s5.b2", kind="PAPER"), block_id=BLOCK) is None


def test_the_curated_gi_record_of_kutch_ajrakh_is_shown_with_its_dated_barmer_price() -> None:
    built = shown(market_block(curated_offers("Kutch-Ajrakh", candidates=DOSSIER_CLAIMS), block_id=BLOCK))
    gi = built["gi"]
    assert gi["status"] == "REGISTERED"
    assert (gi["applicationNumber"], gi["certificateNumber"], gi["journalIssue"]) == ("1050", None, "188")
    assert (gi["filedOn"], gi["registeredOn"]) == ("2023-01-31", "2024-04-22")
    assert gi["proprietors"] == ["Ajarakhpur Hastkala Vikas Sangathan"]
    assert len(gi["sentences"]) == 3 and built["imitation"] == []
    (price,) = built["prices"]
    assert (price["stated"], price["low"], price["high"], price["currency"]) == ("Rs. 7", 7.0, None, "INR")
    assert (price["pricedOn"], price["place"], price["districtLgd"], price["per"]) == (
        "1975",
        "Barmer",
        90,
        None,
    )
    assert price["sentence"]["citations"][0]["claimId"] == str(curated_id("Kutch-Ajrakh", "C049"))


def gi_claim_ids(block: MarketGiBlock) -> set[str]:
    sentences = block.gi.sentences if block.gi is not None else []
    return {citation.claim_id for sentence in sentences for citation in sentence.citations}


def test_a_claim_priced_in_the_market_is_kept_out_of_its_gi_record() -> None:
    offers = curated_offers("Kutch-Ajrakh", candidates=DOSSIER_CLAIMS)
    certificate = curated_id("Kutch-Ajrakh", "C134")
    said = market_block(offers, block_id=BLOCK)
    assert said is not None and str(certificate) in gi_claim_ids(said)
    priced = replace(offers, prices=(*offers.prices, PriceOffer(certificate, "2024", "Bhuj", None)))
    block = market_block(priced, block_id=BLOCK)
    assert block is not None and str(certificate) not in gi_claim_ids(block)
    assert [price.stated for price in block.prices] == ["Rs. 7"]


def test_the_curated_gi_record_of_bastar_dhokra_counts_its_authorised_users() -> None:
    built = shown(market_block(curated_offers("Bastar-Dhokra", candidates=DOSSIER_CLAIMS), block_id=BLOCK))
    gi = built["gi"]
    assert (gi["status"], gi["applicationNumber"], gi["certificateNumber"]) == ("REGISTERED", "83", "62")
    assert (gi["filedOn"], gi["registeredOn"], gi["journalIssue"]) == ("2007-03-12", "2008-04-22", "24")
    assert (gi["authorisedUserCount"], gi["proprietors"]) == (110, ["Chhattisgarh Hastshilp Vikas Board"])
    (price,) = built["prices"]
    assert (price["stated"], price["per"], price["place"], price["pricedOn"]) == (
        "₹550",
        "kilogram",
        "Kondagaon",
        "2025",
    )


@pytest.mark.parametrize(
    ("priced_on", "place", "kept"),
    [
        ("1975", "Barmer", True),
        (None, "Barmer", False),
        ("1975", None, False),
        ("1980", "Barmer", False),
        ("1975", "Bhuj", False),
    ],
)
def test_a_price_without_its_stated_date_or_place_is_dropped(
    priced_on: str | None, place: str | None, kept: bool
) -> None:
    craft = CraftRef.model_validate(golden_market("s5.b1")["craft"])
    price = PriceOffer(BARMER_PRICE.id, priced_on, place, 90)
    block = market_block(offers_of(craft, [BARMER_PRICE], SOURCES, [price]), block_id=BLOCK)
    assert (block is not None) is kept
    if block is not None:
        assert [p.stated for p in block.prices] == ["Rs. 7"] and block.gi is None


@pytest.mark.parametrize(
    "text",
    [
        "Kutch Ajrakh is a registered GI.",
        "Kutch Ajrakh is printed with natural dyes in Ajrakhpur.",
        "Kutch Ajrakh is a registered GI, application 1050.",
    ],
)
def test_a_craft_without_a_stated_registry_record_shows_no_gi_status(text: str) -> None:
    craft = CraftRef.model_validate(golden_market("s5.b1")["craft"])
    claim = written(f"no-gi-{text}", text)
    price = PriceOffer(BARMER_PRICE.id, "1975", "Barmer", 90)
    block = market_block(offers_of(craft, [claim, BARMER_PRICE], SOURCES, [price]), block_id=BLOCK)
    assert block is not None and block.gi is None and [p.stated for p in block.prices] == ["Rs. 7"]
    assert market_block(offers_of(craft, [claim], SOURCES), block_id=BLOCK) is None


def test_a_registry_number_cited_to_a_paper_is_no_gi_status() -> None:
    craft = CraftRef.model_validate(golden_market("s5.b1")["craft"])
    claim = written(
        "paper-gi", "Kutch Ajrakh was filed as GI application 1050 on 31-01-2023.", source_id=PAPER
    )
    assert market_block(offers_of(craft, [claim], SOURCES), block_id=BLOCK) is None


class Markets:
    def __init__(self, *found: MarketOffers) -> None:
        self.found = found
        self.calls: list[list[str]] = []

    async def __call__(self, crafts: Sequence[CraftRef]) -> Sequence[MarketOffers]:
        self.calls.append([craft.slug for craft in crafts])
        return [offers for offers in self.found if offers.craft in crafts]


def comparison() -> tuple[CraftRef, CraftRef, Markets]:
    ajrakh, bagru = (CraftRef.model_validate(golden_market(b)["craft"]) for b in ("s5.b1", "s5.b2"))
    return ajrakh, bagru, Markets(golden_offers("s5.b1"), golden_offers("s5.b2"))


async def test_a_comparison_shows_each_craft_and_keeps_only_the_answer_craft_s_block() -> None:
    ajrakh, bagru, markets = comparison()
    ask = insight_ask([], SOURCES, discipline="ECONOMICS", compared=(bagru,))
    built = await MarketGiBuilder(TOOLS, offers=markets).build(ask)
    assert markets.calls == [["Kutch-Ajrakh", bagru.slug]]
    assert [block.craft for block in built.blocks] == [ajrakh, bagru]
    lookup = PieceLookup(craft_id=uuid.uuid4(), craft_slug=ajrakh.slug)
    assert [kept_for(block, lookup) for block in built.blocks] == [True, False]
    assert set(built.sources) == {s for block in built.blocks for s in block.cited_source_ids()}


async def test_a_reused_section_rebuilds_only_the_crafts_its_pieces_do_not_show() -> None:
    _, bagru, markets = comparison()
    stored = MarketGiBlock.model_validate(golden_market("s5.b1"))
    ask = insight_ask([], SOURCES, discipline="ECONOMICS", compared=(bagru,), shown=(stored,))
    built = await MarketGiBuilder(TOOLS, offers=markets).build(ask)
    assert [block.craft for block in built.blocks] == [bagru]


async def test_market_blocks_join_economics_and_policy_and_pass_the_registry_s_checks() -> None:
    entry = next(entry for entry in BLOCK_BUILDERS if entry.kind == "market_gi")
    assert entry.disciplines == {"ECONOMICS", "POLICY"} and entry.rebuilt_on_reuse
    assert "market_gi" in BUILT_BLOCK_KINDS
    _, bagru, markets = comparison()
    builders = BlockBuilders([(entry, MarketGiBuilder(TOOLS, offers=markets))])
    added = await builders.added(
        insight_ask([BARMER_PRICE], SOURCES, discipline="ECONOMICS", compared=(bagru,))
    )
    assert [block.kind for block in added.blocks] == ["market_gi", "market_gi"]
    assert PAPER not in added.sources and len(added.sources) == len(
        {s for block in added.blocks for s in block.cited_source_ids()}
    )
    assert (await builders.added(insight_ask([BARMER_PRICE], SOURCES, discipline="HISTORY"))).blocks == ()


@pytest.mark.parametrize(
    ("registered_on", "shown_on"),
    [("2024-04-22", "2024-04-22"), ("2024-04-02", "2024-04"), ("2024-02-22", "2024")],
)
def test_a_curated_registry_date_is_shown_only_as_precisely_as_its_quotes_state_it(
    registered_on: str, shown_on: str
) -> None:
    offers = curated_offers("Kutch-Ajrakh", candidates=DOSSIER_CLAIMS)
    assert offers.record is not None
    record = replace(offers.record, fields=replace(offers.record.fields, registered_on=registered_on))
    built = shown(market_block(replace(offers, record=record), block_id=BLOCK))
    assert built["gi"]["registeredOn"] == shown_on


def test_a_curated_price_dated_past_its_sentence_is_shown_by_the_year_it_states() -> None:
    craft = CraftRef.model_validate(golden_market("s5.b1")["craft"])
    price = PriceOffer(BARMER_PRICE.id, "1975-03-14", "Barmer", 90)
    block = market_block(offers_of(craft, [BARMER_PRICE], SOURCES, [price]), block_id=BLOCK)
    assert block is not None and [p.priced_on for p in block.prices] == ["1975"]
