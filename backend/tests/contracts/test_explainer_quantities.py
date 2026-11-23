from typing import Any

import pytest
from pydantic import TypeAdapter, ValidationError

from app.research.blocks_insight import QuantitiesBlock
from app.research.coverage_answers import FIGURE_KINDS
from app.research.explainer import BLOCK_PHASES, BUILT_BLOCK_KINDS, Block
from app.services.claim_ledger import ClaimLedger, admission_batches
from app.services.quantities_builder import amounts_stated_in, quantities_block

from ..place.season_supply_fixtures import claims_of
from .blocks_golden import QUANTITIES, BlocksFixture
from .explainer_golden import citations_in, golden_json, seed_citations, seed_claims
from .golden import reproduces

BLOCK_ID = "s1.b1"
SAID_ID = "s2.b2"
BLOCK = TypeAdapter(Block)


def golden_block() -> dict[str, Any]:
    (block,) = golden_json(QUANTITIES)["sections"][0]["blocks"]
    return block


def said_blocks() -> list[dict[str, Any]]:
    prose, table = golden_json(QUANTITIES)["sections"][1]["blocks"]
    return [prose, table]


def test_the_quantities_fixture_is_reproduced_byte_for_byte() -> None:
    assert reproduces(BlocksFixture, QUANTITIES)


def test_the_quantities_table_is_a_built_phase_d_figure() -> None:
    assert "quantities" in BUILT_BLOCK_KINDS and BLOCK_PHASES["quantities"] == "D"
    assert "quantities" in FIGURE_KINDS


def test_every_citation_resolves_to_a_seeded_claim_source_and_every_sentence_is_its_claim() -> None:
    seeded = seed_citations()
    found = list(citations_in(golden_json(QUANTITIES)))
    assert len(found) == 2 * (1 + 1 + 1 + 1 + 3) + 1
    for cite in found:
        row = seeded[cite["id"]]
        assert (cite["claimId"], cite["sourceId"], cite["quote"]) == (
            row["claimId"],
            row["sourceId"],
            row["quote"],
        )
    for row in golden_block()["rows"]:
        claim = seed_claims()[row["sentence"]["citations"][0]["claimId"]]
        assert (row["sentence"]["text"], row["sentence"]["level"]) == (claim["text"], claim["evidenceLevel"])


def test_the_section_s_facts_give_the_fixture_s_table_each_quantity_with_its_own_words() -> None:
    golden = golden_block()
    facts = claims_of([row["sentence"] for row in golden["rows"]])
    block = quantities_block(amounts_stated_in(facts), block_id=BLOCK_ID)
    assert block is not None
    assert block.model_dump(mode="json", by_alias=True) == golden
    assert [(row.stated, row.measures) for row in block.rows] == [
        ("3 kg", "MASS"),
        ("15 litres", "VOLUME"),
        ("80–100 g", "MASS"),
        ("15–20 days", "TIME"),
        ("10 minutes", "TIME"),
    ]
    assert len(list(block.shown_sentences())) == 4


def test_a_section_stating_fewer_than_three_quantities_has_no_table() -> None:
    facts = claims_of([row["sentence"] for row in golden_block()["rows"][:2]])
    assert len(amounts_stated_in(facts)) == 2
    assert quantities_block(amounts_stated_in(facts), block_id=BLOCK_ID) is None


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"stated": "4 kg"}, "is what its sentence or quotes state"),
        ({"measures": "TIME"}, "measures what its unit"),
        ({"low": 2.0}, "carries the numbers it states"),
    ],
)
def test_a_row_shows_only_the_quantity_its_sentence_states(change: dict[str, Any], message: str) -> None:
    golden = golden_block()
    rows = [{**golden["rows"][0], **change}, *golden["rows"][1:]]
    with pytest.raises(ValidationError, match=message):
        QuantitiesBlock.model_validate({**golden, "rows": rows})


def test_a_quantity_is_listed_once_for_its_sentence() -> None:
    golden = golden_block()
    again = {**golden["rows"][0], "sentence": {**golden["rows"][0]["sentence"], "id": "s1.b1.9"}}
    with pytest.raises(ValidationError, match="each stated quantity of a sentence once"):
        QuantitiesBlock.model_validate({**golden, "rows": [*golden["rows"], again]})


def test_a_table_under_a_sentence_already_said_keeps_its_rows_and_names_where_it_is_said() -> None:
    prose, table = said_blocks()
    facts = claims_of([row["sentence"] for row in golden_block()["rows"]])
    built = quantities_block(amounts_stated_in(facts), block_id=SAID_ID)
    assert built is not None
    sources = {ref["id"]: ref for ref in golden_json(QUANTITIES)["sources"]}
    ledger = ClaimLedger()
    batches = admission_batches([BLOCK.validate_python(prose), built])
    shown = [block for batch in batches for block in ledger.admit("s2", batch, sources)]
    assert [block.model_dump(mode="json", by_alias=True) for block in shown] == [prose, table]
    said = QuantitiesBlock.model_validate(table)
    assert [row.shown_in for row in said.rows] == ["s2.b1.1", "s2.b1.1", None, None, None]
    assert [sentence.id for sentence in said.shown_sentences()] == ["s2.b2.3", "s2.b2.4", "s2.b2.5"]
    assert said.shown_labels() == ["3 kg", "15 litres", "80–100 g", "15–20 days", "10 minutes"]


def test_the_rows_of_one_sentence_say_together_where_it_is_said() -> None:
    _, table = said_blocks()
    first = {name: value for name, value in table["rows"][0].items() if name != "shownIn"}
    with pytest.raises(ValidationError, match="say where a sentence is shown for every row it backs"):
        QuantitiesBlock.model_validate({**table, "rows": [first, *table["rows"][1:]]})
