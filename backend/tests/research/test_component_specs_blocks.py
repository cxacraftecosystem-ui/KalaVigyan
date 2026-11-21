from typing import Any

import pytest
from pydantic import ValidationError

from app.models.component_kinds import DOCUMENT_KINDS
from app.research.component_specs import checked_spec
from app.research.component_specs_blocks import ANSWER_BLOCK_KIND, AnswerBlockSpec
from app.research.why_here import WHY_HERE_KIND

from ..contracts.golden import golden_json

LADDER_ID = "made.ladder"
LADDER_STAGES = 14


def golden_ladder() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    page = golden_json("craft.page.golden.json")
    block = next(
        item["block"]
        for chapter in page["chapters"]
        for item in chapter["items"]
        if item["block"] is not None and item["block"]["id"] == LADDER_ID
    )
    cited = {found["sourceId"] for found in _citations(block)}
    refs = [
        {key: value for key, value in source.items() if key not in {"group", "from", "supports"}}
        for source in page["sources"]
        if source["id"] in cited
    ]
    return block, refs


def _citations(node: Any) -> list[dict[str, Any]]:
    if isinstance(node, dict):
        own = [node] if "sourceId" in node and "claimId" in node else []
        return own + [found for value in node.values() for found in _citations(value)]
    if isinstance(node, list):
        return [found for value in node for found in _citations(value)]
    return []


def spec(block: dict[str, Any], refs: list[dict[str, Any]], **figure: Any) -> dict[str, Any]:
    return {
        "block": block,
        "figure": figure or None,
        "sources": [{"key": f"g{n}", "ref": ref} for n, ref in enumerate(refs, 1)],
    }


def test_the_answer_block_is_a_document_kind_and_draws_a_page_block_with_its_sources() -> None:
    block, refs = golden_ladder()
    assert DOCUMENT_KINDS == (ANSWER_BLOCK_KIND, WHY_HERE_KIND)
    checked = checked_spec(
        ANSWER_BLOCK_KIND, spec(block, refs, kind="FIGURE", number=1, title="How it is made")
    )
    assert isinstance(checked, AnswerBlockSpec)
    assert checked.block.kind == "process_ladder"
    assert len(checked.block.stages) == LADDER_STAGES
    assert [source.key for source in checked.sources] == [f"g{n}" for n in range(1, len(refs) + 1)]
    assert checked.model_dump(mode="json")["block"] == block


def test_a_block_citing_a_source_it_does_not_list_is_refused() -> None:
    block, _ = golden_ladder()
    with pytest.raises(ValidationError, match="cites sources it does not list"):
        checked_spec(ANSWER_BLOCK_KIND, spec(block, []))


def test_each_source_is_listed_once_under_its_own_key() -> None:
    block, refs = golden_ladder()
    twice = spec(block, [*refs, refs[0]])
    with pytest.raises(ValidationError, match="each source once"):
        checked_spec(ANSWER_BLOCK_KIND, twice)
    keyed = spec(block, refs)
    keyed["sources"][1]["key"] = keyed["sources"][0]["key"]
    with pytest.raises(ValidationError, match="each source once"):
        checked_spec(ANSWER_BLOCK_KIND, keyed)


def test_a_figure_is_numbered_from_one() -> None:
    block, refs = golden_ladder()
    with pytest.raises(ValidationError):
        checked_spec(ANSWER_BLOCK_KIND, spec(block, refs, kind="FIGURE", number=0, title="How it is made"))
