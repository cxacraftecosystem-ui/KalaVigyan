import uuid
from collections.abc import Collection
from typing import Any

import pytest

from app.core.errors import ExternalFailure
from app.research.blocks_play import WhatIfBlock
from app.research.crafts import CraftRef
from app.research.explainer import BUILT_BLOCK_KINDS
from app.services import craft_matter as craft_matter_module, what_if_builder
from app.services.block_builders import BLOCK_BUILDERS
from app.services.builder_interface import Built
from app.services.craft_matter import CraftMatter
from app.services.what_if_builder import WhatIfBuilder
from app.services.what_if_evidence import WhatIfEvidence

from ..planner.fakes import FakeModel
from ..science.golden_process import claim_id, stage_id
from .fixtures import (
    AL_ROOT_ID,
    ALIZARIN_LAKE,
    CONTRAST,
    FIXTURE_REPLY,
    LAKE_MECHANISM,
    MADDER_WITH_INDIGO,
    RED,
    SYNTHESISED,
    TAPANO,
    WASHING_HYPOTHESIS,
    evidence,
    golden_what_if,
    red_ask,
    red_matter,
    two_stage_matter,
    what_if_model,
    what_if_tools,
)

MORDANT_PAPER = "9187df8b-62e3-510a-ba5d-827ec098c84c"


@pytest.fixture
def stored(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    found: dict[str, Any] = {"matter": red_matter(), "evidence": evidence(), "asked": []}

    async def matter(sessions: object, craft: CraftRef) -> CraftMatter:
        return found["matter"]

    async def loaded(sessions: object, concept_ids: Collection[uuid.UUID]) -> WhatIfEvidence:
        found["asked"].append(set(concept_ids))
        return found["evidence"]

    monkeypatch.setattr(craft_matter_module, "craft_matter", matter)
    monkeypatch.setattr(what_if_builder, "what_if_evidence", loaded)
    return found


async def built(*replies: dict[str, Any] | str, **ask: Any) -> tuple[Built, FakeModel]:
    model = what_if_model(*replies)
    return await WhatIfBuilder(what_if_tools(model)).build(red_ask(**ask)), model


def reply(*options: tuple[str, list[str]], changed: str = "Red dye", chosen: str = "i1") -> dict[str, Any]:
    return {
        "input": chosen,
        "changed": changed,
        "options": [{"option": option, "outcomes": outcomes} for option, outcomes in options],
    }


def shown(block: WhatIfBlock) -> list[tuple[Any, ...]]:
    return [
        (
            option.label,
            option.material_id,
            [
                (o.sentence.text, o.sentence.level, {c.id for c in o.sentence.citations}, o.reaction_id)
                for o in option.outcomes
            ],
        )
        for option in block.options
    ]


def outcome_claims(block: WhatIfBlock) -> list[list[uuid.UUID]]:
    return [
        [uuid.UUID(o.sentence.citations[0].claim_id) for o in option.outcomes] for option in block.options
    ]


async def test_the_red_dye_what_if_of_the_fixture_is_built_from_stored_rows_and_a_recorded_reply(
    stored: dict[str, Any],
) -> None:
    result, model = await built(FIXTURE_REPLY)
    (block,) = result.blocks
    golden = WhatIfBlock.model_validate(golden_what_if())
    assert (block.id, block.changed, block.stage_id) == ("s2.whatif", golden.changed, stage_id(RED))
    assert golden.stage_id == stage_id(RED)
    assert shown(block)[:2] == shown(golden)[:2]
    assert [o.reaction_id for o in block.options[1].outcomes] == [None, ALIZARIN_LAKE]
    assert (block.options[2].label, block.options[2].material_id, block.options[2].outcomes) == (
        "Al root",
        AL_ROOT_ID,
        [],
    )
    assert (golden.options[2].label, golden.options[2].outcomes) == ("Al root", [])
    assert [s.id for s in block.cited_sentences()] == [f"s2.whatif.{n}" for n in range(1, 5)]
    assert len(model.calls) == 1


async def test_it_returns_only_the_sources_its_outcomes_cite_beyond_the_section(
    stored: dict[str, Any],
) -> None:
    result, _ = await built(FIXTURE_REPLY)
    assert set(result.sources) == {MORDANT_PAPER}
    assert result.sources[MORDANT_PAPER]["id"] == MORDANT_PAPER


async def test_an_outcome_without_a_stored_claim_of_its_option_is_dropped(stored: dict[str, Any]) -> None:
    result, _ = await built(reply(("i1.o1", ["i1.o1.e9", "i1.o1.e2", "i1.o2.e6"]), ("i1.o2", ["i1.o2.e3"])))
    (block,) = result.blocks
    assert outcome_claims(block) == [[claim_id(TAPANO)], [claim_id(SYNTHESISED)], []]


async def test_an_option_with_no_evidence_is_unknown_whatever_the_reply_gives_it(
    stored: dict[str, Any],
) -> None:
    result, _ = await built(reply(("i1.o1", ["i1.o1.e1"]), ("i1.o3", ["i1.o1.e2", "i1.o2.e3"])))
    (block,) = result.blocks
    assert [(option.label, len(option.outcomes)) for option in block.options] == [
        ("Indian madder (majith/majeeta, Rubia cordifolia)", 1),
        ("Al root", 0),
    ]


async def test_a_reply_naming_options_of_two_inputs_is_refused(stored: dict[str, Any]) -> None:
    stored["matter"] = two_stage_matter()
    result, model = await built(reply(("i1.o1", ["i1.o1.e1"]), ("i2.o2", ["i2.o2.e3"])))
    assert result == Built()
    assert "Input i2: the dye of that stage." in model.calls[0]["user"]
    again, _ = await built(reply(("i2.o1", ["i2.o1.e1"]), ("i2.o2", ["i2.o2.e3"]), chosen="i2"))
    assert [block.stage_id for block in again.blocks] == [stored["matter"].records.stages[1].id]


async def test_a_relationship_that_is_a_hypothesis_is_shown_labelled_as_one(stored: dict[str, Any]) -> None:
    stored["evidence"] = evidence(hypothesis=True)
    result, model = await built(reply(("i1.o1", ["i1.o1.e1"]), ("i1.o2", ["i1.o2.e2", "i1.o2.e1"])))
    (block,) = result.blocks
    washing, contrast = block.options[1].outcomes
    assert uuid.UUID(washing.sentence.citations[0].claim_id) == claim_id(WASHING_HYPOTHESIS)
    assert washing.sentence.level == "HYPOTHESIS"
    assert {c.level for c in washing.sentence.citations} == {"HYPOTHESIS"}
    assert uuid.UUID(contrast.sentence.citations[0].claim_id) == claim_id(CONTRAST)
    assert contrast.sentence.level == "PROVISIONAL"
    assert "i1.o2.e2: a hypothesis, a stored relation (causes)" in model.calls[0]["user"]


@pytest.mark.parametrize("changed", ["Toxic dye", "", "Red dye at 60 degrees", "x" * 81])
async def test_the_input_is_named_only_with_words_its_own_texts_use(
    stored: dict[str, Any], changed: str
) -> None:
    result, _ = await built(reply(("i1.o1", ["i1.o1.e1"]), ("i1.o2", ["i1.o2.e3"]), changed=changed))
    assert result == Built()


async def test_a_reply_choosing_no_input_or_too_few_options_adds_nothing(stored: dict[str, Any]) -> None:
    for chosen in (reply(chosen=""), reply(chosen="i7"), reply(("i1.o1", ["i1.o1.e9"]))):
        result, _ = await built(chosen)
        assert result == Built()


async def test_a_section_naming_no_option_reads_no_evidence_and_asks_no_model(stored: dict[str, Any]) -> None:
    result, model = await built(keys=(MADDER_WITH_INDIGO,))
    assert (result, model.calls, stored["asked"]) == (Built(), [], [])


async def test_a_reply_off_its_schema_fails_the_build(stored: dict[str, Any]) -> None:
    with pytest.raises(ExternalFailure, match="off its schema"):
        await built({"input": "i1", "options": []})


async def test_a_built_what_if_rests_on_the_reaction_s_own_passages(stored: dict[str, Any]) -> None:
    result, _ = await built(FIXTURE_REPLY)
    (block,) = result.blocks
    lake = block.options[1].outcomes[1]
    assert uuid.UUID(lake.sentence.citations[0].claim_id) == claim_id(LAKE_MECHANISM)
    linked = {citation for _, citation in stored["matter"].records.reactions[0].citations}
    assert {c.id for c in lake.sentence.citations} & linked


def test_the_registry_adds_what_ifs_to_process_chemistry_and_water_sections() -> None:
    (entry,) = [entry for entry in BLOCK_BUILDERS if entry.kind == "what_if"]
    assert (entry.disciplines, entry.wait_seconds, entry.rebuilt_on_reuse, entry.places_pieces) == (
        {"PROCESS", "CHEMISTRY", "GEOGRAPHY"},
        20.0,
        False,
        False,
    )
    assert entry.make(what_if_tools()).__class__ is WhatIfBuilder
    assert "what_if" in BUILT_BLOCK_KINDS
