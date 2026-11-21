import importlib.util
import uuid
from pathlib import Path
from typing import Any

import pytest
from pydantic import TypeAdapter, ValidationError

from app.models import block_kinds, enums
from app.models.component_kinds import COMPONENT_KINDS
from app.research.blocks_component import ComponentBlock, component_href, stood_for
from app.research.explainer import BLOCK_PHASES, BUILT_BLOCK_KINDS, Block, BlockEvent
from app.research.knowledge_pieces import UNSTORED_BLOCK_KINDS
from app.services.piece_store import storable

from ..research.fixtures import AJRAKH

VERSIONS = Path(__file__).resolve().parents[2] / "migrations" / "versions"
SOURCE = "1a2b3c4d-0000-4000-8000-000000000001"
BLOCKS: TypeAdapter[Block] = TypeAdapter(Block)


def wire(**changes: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": "s1.b2",
        "kind": "component",
        "version": 1,
        "reuse": None,
        "label": "kutch-ajrakh/chemistry/red-alum-madder-player",
        "componentKind": "reaction_player",
        "title": "Red develops only where alum was printed",
        "craft": {"slug": "Kutch-Ajrakh", "name": "Kutch Ajrakh", "path": "/crafts/Kutch-Ajrakh"},
        "href": "/crafts/Kutch-Ajrakh#rp-red",
        "sources": [{"sourceId": SOURCE}],
    }
    return payload | changes


def load(name: str) -> Any:
    path = VERSIONS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"migration_{name}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a_component_block_reads_and_writes_the_wire_shape() -> None:
    block = BLOCKS.validate_python(wire())
    assert isinstance(block, ComponentBlock)
    assert block.model_dump(mode="json") == wire()
    assert block.cited_source_ids() == [SOURCE]
    assert block.cited_claim_ids() == set()


def test_a_component_is_shown_in_a_section_and_never_kept_as_a_piece() -> None:
    block = BLOCKS.validate_python(wire())
    assert BlockEvent(section_id="s1", block=block).block == block
    assert BLOCK_PHASES["component"] == "A"
    assert BUILT_BLOCK_KINDS[-1] == "component"
    assert "component" in UNSTORED_BLOCK_KINDS
    assert storable(block) is False


@pytest.mark.parametrize(
    "changes",
    [
        {"href": "/crafts/Bagru-Print#rp-red"},
        {"href": '/crafts/Kutch-Ajrakh[class="mols"]'},
        {"href": "https://example.org/crafts/Kutch-Ajrakh"},
        {"href": "/crafts/Kutch-Ajrakh#"},
        {"componentKind": "component"},
        {"componentKind": "not_a_kind"},
        {"label": "Not A Label"},
        {"sources": []},
        {"title": ""},
    ],
)
def test_a_component_that_breaks_a_rule_is_refused(changes: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        BLOCKS.validate_python(wire(**changes))


def test_the_page_link_keeps_only_an_anchor_that_names_an_element() -> None:
    assert component_href(AJRAKH, "#fig1") == "/crafts/Kutch-Ajrakh#fig1"
    assert component_href(AJRAKH, "#b-ws-iron") == "/crafts/Kutch-Ajrakh#b-ws-iron"
    assert component_href(AJRAKH, '[class="mols mol-two"]') == "/crafts/Kutch-Ajrakh"
    assert component_href(AJRAKH, "") == "/crafts/Kutch-Ajrakh"
    assert BLOCKS.validate_python(wire(href="/crafts/Kutch-Ajrakh")).href == "/crafts/Kutch-Ajrakh"


def test_a_placed_component_stands_for_the_builder_of_the_same_purpose() -> None:
    player = BLOCKS.validate_python(wire())
    cards = BLOCKS.validate_python(wire(id="s1.b3", componentKind="material_cards"))
    plate = BLOCKS.validate_python(wire(id="s1.b4", componentKind="picture_plate"))
    assert stood_for([player, cards, plate]) == {"reaction_player", "material_card"}
    assert stood_for([plate]) == frozenset()


def test_the_block_kinds_moved_home_and_every_old_import_still_reads_them() -> None:
    assert enums.BLOCK_KINDS is block_kinds.BLOCK_KINDS
    assert block_kinds.BLOCK_KINDS[-1] == "component"
    assert len(block_kinds.BLOCK_KINDS) == len(set(block_kinds.BLOCK_KINDS)) == 30


def test_migration_0035_widens_the_piece_kinds_by_the_component_kind_only() -> None:
    before, after = load("0034_component_kinds"), load("0035_answer_components")
    assert (after.revision, after.down_revision) == ("0035_answer_components", "0034_component_kinds")
    assert after.BLOCK_KINDS_BEFORE == before.BLOCK_KINDS
    assert (
        after.COMPONENT_KINDS
        == before.COMPONENT_KINDS
        == load("0056_datasets_and_materials").COMPONENT_KINDS_BEFORE
    )
    assert set(COMPONENT_KINDS) - set(before.COMPONENT_KINDS) == {"drawing"}
    assert after.BLOCK_KINDS == enums.BLOCK_KINDS
    assert set(after.BLOCK_KINDS) - set(before.BLOCK_KINDS) == {"component"}
    assert after.CONSTRAINT == before.CONSTRAINT == "KnowledgePiece_kind_check"


def test_a_component_cites_the_sources_it_rests_on_in_their_order() -> None:
    block = BLOCKS.validate_python(wire(sources=[{"sourceId": str(uuid.UUID(int=7))}, {"sourceId": SOURCE}]))
    assert block.cited_source_ids() == [str(uuid.UUID(int=7)), SOURCE]
