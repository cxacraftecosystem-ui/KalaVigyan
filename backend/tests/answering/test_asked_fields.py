from app.research.planning import ResearchShare
from app.research.sections import SectionSpec
from app.services.answer_sections import started_order
from app.services.block_builders import BLOCK_BUILDERS
from app.services.market_builder import GI_PARTS, MARKET_PARTS, PRICE_PARTS, market_block, section_parts
from app.services.research_ledger import NOTHING, ResearchLedger, first_shares
from app.services.section_fields import SectionFields

from .fakes import FakeResearch, SectionModel, pipeline, streamed
from .piece_fakes import MemoryPieces
from .test_answer_flow import REPLY
from .test_market_builder import BLOCK, golden_offers, shown
from .test_sections import asked, two_fields

WATER_AND_CLIMATE = SectionFields(
    asked=frozenset({"GEOGRAPHY", "CLIMATE", "ECOLOGY"}),
    held=frozenset({"PROCESS", "MATERIALS", "GEOGRAPHY", "CLIMATE", "SOCIETY"}),
    shown=frozenset({"PROCESS", "MATERIALS", "GEOGRAPHY", "CLIMATE", "ECOLOGY"}),
)


def spec(number: int, discipline: str) -> SectionSpec:
    return SectionSpec(id=f"s{number}", discipline=discipline, title=discipline.title(), order=number)


def test_an_asked_field_the_craft_holds_fewer_than_three_facts_in_comes_first() -> None:
    fields = WATER_AND_CLIMATE
    found = [fields.priority(field) for field in ("ECOLOGY", "CLIMATE", "GEOGRAPHY", "PROCESS", "MATERIALS")]
    assert found == [2, 1, 1, 0, 0]
    assert (fields.is_thin("ECOLOGY"), fields.is_thin("CLIMATE"), fields.is_thin("PROCESS")) == (
        True,
        False,
        False,
    )


def test_a_field_the_question_did_not_ask_gets_half_the_section_s_sentences() -> None:
    fields = WATER_AND_CLIMATE
    assert [fields.sentences_max(field, 8) for field in ("CLIMATE", "ECOLOGY", "PROCESS")] == [8, 8, 4]
    assert fields.sentences_max("PROCESS", 1) == 1


def test_an_understanding_that_names_no_asked_field_treats_every_field_as_asked() -> None:
    fields = SectionFields(held=frozenset({"PROCESS"}))
    assert (fields.priority("PROCESS"), fields.priority("ECOLOGY")) == (1, 2)
    assert fields.sentences_max("PROCESS", 8) == 8


def test_the_budget_goes_to_the_thin_asked_fields_before_any_other() -> None:
    total = ResearchShare(queries=4, native_queries=0, fetches=10)
    shares = first_shares(total, [1, 0, 2, 1, 2])
    assert [(share.queries, share.fetches) for share in shares] == [(0, 0), (0, 0), (2, 5), (0, 0), (2, 5)]
    assert first_shares(total, [1, 0, 1])[1] == NOTHING
    assert [(share.queries, share.fetches) for share in first_shares(total, [0, 0])] == [(2, 5), (2, 5)]


def test_a_held_asked_field_takes_what_the_thin_field_left_once_it_settles() -> None:
    ledger = ResearchLedger(ResearchShare(queries=4, native_queries=0, fetches=10), (2, 1))
    thin, held = ledger.shares
    taken = ledger.take_section(thin)
    assert (taken.queries, taken.fetches) == (4, 10)
    ledger.give_back(ResearchShare(queries=2, native_queries=0, fetches=7))
    later = ledger.take_section(held)
    assert (later.queries, later.fetches) == (2, 7)


def test_sections_start_thin_asked_fields_first_and_unasked_fields_last() -> None:
    specs = [
        spec(1, "PROCESS"),
        spec(2, "GEOGRAPHY"),
        spec(3, "ECOLOGY"),
        spec(4, "MATERIALS"),
        spec(5, "CLIMATE"),
    ]

    class Context:
        fields = WATER_AND_CLIMATE

    started = started_order(specs, Context())  # type: ignore[arg-type]
    assert [one.discipline for one in started] == ["ECOLOGY", "GEOGRAPHY", "CLIMATE", "PROCESS", "MATERIALS"]


async def test_the_thin_asked_field_researches_fresh_with_the_whole_budget() -> None:
    research = FakeResearch()
    model = SectionModel(replies={"Geography and water": [REPLY], "Ecology": [REPLY]})
    held = MemoryPieces(held_fields=("GEOGRAPHY",))
    understood = two_fields("GEOGRAPHY", "ECOLOGY")
    await streamed(
        asked(), pipeline(research=research, understand_model=understood, compose_model=model, pieces=held)
    )
    ecology = next(request for request in research.requests if request.focus == "ECOLOGY")
    geography = next(request for request in research.requests if request.focus == "GEOGRAPHY")
    assert ecology.share is not None and geography.share is not None
    assert (ecology.fresh, ecology.share.queries, ecology.share.fetches) == (True, 4, 10)
    assert geography.fresh is False
    assert all(reads is research.reads[0] and reads is not None for reads in research.reads)


def test_an_answer_with_a_policy_section_files_the_gi_record_there_and_prices_under_economics() -> None:
    both = {"ECONOMICS", "POLICY", "HISTORY"}
    assert section_parts("POLICY", both) == GI_PARTS
    assert section_parts("ECONOMICS", both) == PRICE_PARTS
    assert section_parts("ECONOMICS", {"ECONOMICS", "HISTORY"}) == MARKET_PARTS
    assert section_parts("POLICY", set()) == MARKET_PARTS


def test_the_economics_part_of_a_market_block_leaves_the_gi_record_to_policy() -> None:
    offers = golden_offers("s5.b1")
    policy = shown(market_block(offers, block_id=BLOCK, parts=GI_PARTS))
    assert (policy["gi"]["status"], policy["prices"]) == ("REGISTERED", [])
    economics = shown(market_block(offers, block_id=BLOCK, parts=PRICE_PARTS))
    assert (economics["gi"], [price["stated"] for price in economics["prices"]]) == (None, ["Rs. 7"])
    assert market_block(golden_offers("s5.b2"), block_id=BLOCK, parts=PRICE_PARTS) is None


def test_the_seasons_block_is_built_by_the_climate_section_when_the_answer_has_one() -> None:
    (seasons,) = [entry for entry in BLOCK_BUILDERS if entry.kind == "seasons"]
    answer = {"PROCESS", "GEOGRAPHY", "CLIMATE"}
    assert [seasons.builds_in(field, answer) for field in ("PROCESS", "GEOGRAPHY", "CLIMATE")] == [
        False,
        False,
        True,
    ]
    assert seasons.builds_in("PROCESS", {"PROCESS", "GEOGRAPHY"})
    assert seasons.builds_in("PROCESS", set())
