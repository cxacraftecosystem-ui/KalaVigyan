from typing import Any

import pytest
from pydantic import ValidationError

from app.research.blocks_insight import QuantitiesBlock
from app.research.coverage_answers import FIGURE_KINDS
from app.research.explainer import BLOCK_PHASES, BUILT_BLOCK_KINDS
from app.services.quantities_builder import amounts_stated_in, quantities_block

from ..place.season_supply_fixtures import claims_of
from .blocks_golden import QUANTITIES, BlocksFixture
from .explainer_golden import citations_in, golden_json, seed_citations, seed_claims
from .golden import reproduces

BLOCK_ID = "s1.b1"


def golden_block() -> dict[str, Any]:
    (section,) = golden_json(QUANTITIES)["sections"]
    (block,) = section["blocks"]
    return block


def test_the_quantities_fixture_is_reproduced_byte_for_byte() -> None:
    assert reproduces(BlocksFixture, QUANTITIES)


def test_the_quantities_table_is_a_built_phase_d_figure() -> None:
    assert "quantities" in BUILT_BLOCK_KINDS and BLOCK_PHASES["quantities"] == "D"
    assert "quantities" in FIGURE_KINDS


def test_every_citation_resolves_to_a_seeded_claim_source_and_every_sentence_is_its_claim() -> None:
    seeded = seed_citations()
    found = list(citations_in(golden_json(QUANTITIES)))
    assert len(found) == 1 + 1 + 1 + 1 + 3
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
