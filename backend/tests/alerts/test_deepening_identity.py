import uuid
from typing import Any

from pydantic import TypeAdapter

from app.research.block_identity import block_keys, repeats_shown
from app.research.explainer import Block
from app.research.planning import PlanRequest
from app.research.sections import SectionSpec
from app.services.answer_events import CitedClaims
from app.services.block_builders import BlockBuilders, BuilderEntry
from app.services.builder_interface import BuildAsk, Built
from app.services.section_deepening import shown_deepening

from ..contracts.phase_b_golden import phase_b_blocks
from ..place.fixtures import water_prose

BLOCKS = TypeAdapter(Block)
SOIL = "map_layer:soil-ph-0-5cm"


def golden(block_id: str) -> Any:
    return BLOCKS.validate_python(phase_b_blocks()[block_id])


class LayerBuilder:
    def __init__(self, *layers: str) -> None:
        self.layers = layers

    async def build(self, ask: BuildAsk) -> Built:
        return Built(tuple(golden("s2.b1").model_copy(update={"layer": layer}) for layer in self.layers))


def map_layers(builder: LayerBuilder) -> BlockBuilders:
    entry = BuilderEntry("map_layer", frozenset({"GEOLOGY"}), lambda tools: builder, 1.0)
    return BlockBuilders([(entry, builder)])


def geology_ask() -> BuildAsk:
    request = PlanRequest(question="How does the soil shape Ajrakh?", mode="HYBRID", craft=None)
    spec = SectionSpec(id="s2", discipline="GEOLOGY", title="The soil", order=2)
    return BuildAsk(uuid.uuid4(), spec, request, (water_prose(),), CitedClaims())


def test_each_identified_kind_is_known_by_what_it_shows() -> None:
    assert block_keys(golden("s2.b1")) == {SOIL}
    assert block_keys(golden("s1.b1")) == {"region_story:river:3"}
    assert block_keys(golden("s4.b1")) == {
        "reaction:d2e727af-a1bd-55a8-a151-f1aff8414e61",
        "reaction:c33b87a8-1dc1-5040-a4dc-07a182f52911",
        "reaction:e6df0432-d41b-5ad2-aded-4ff814786935",
        "reaction:65916ac6-7a8e-57c9-baf6-6b0ba5f684da",
    }
    assert block_keys(golden("s4.b2")) == {"material_card:id:bbcf61d3-1b84-5c95-b7fa-1811026d5606"}
    assert block_keys(golden("s4.b3")) == {"molecule_3d:20675edc-039d-5c49-85f9-aba0597c7aab"}
    assert block_keys(golden("s3.b1")) is None


def test_a_story_without_a_river_is_known_by_its_districts() -> None:
    story = golden("s1.b1").model_copy(update={"river": None})
    assert block_keys(story) == {"region_story:district:449"}


def test_a_block_repeats_a_section_only_when_everything_it_shows_is_shown_already() -> None:
    player = golden("s4.b1")
    first_two = {f"reaction:{step.reaction_id}" for step in player.steps[:2]}
    assert not repeats_shown(player, first_two)
    assert repeats_shown(player, block_keys(player) | {SOIL})
    assert not repeats_shown(golden("s3.b1"), {SOIL})


def test_a_deepened_section_shows_identified_blocks_by_key_and_the_rest_by_kind() -> None:
    claims = frozenset({uuid.UUID(int=1)})
    deepening = shown_deepening([golden("s2.b1"), golden("s3.b1")], first_block=3, claims=claims)
    assert (deepening.kinds, deepening.keys, deepening.claims) == (frozenset({"seasons"}), {SOIL}, claims)
    assert deepening.shows("seasons") and not deepening.shows("map_layer")


async def test_a_second_layer_is_built_into_a_deepened_section_and_the_shown_one_is_not() -> None:
    builders = map_layers(LayerBuilder("soil-ph-0-5cm", "rainfall-annual")).without((), shown={SOIL})
    added = await builders.added(geology_ask())
    assert [block.layer for block in added.blocks] == ["rainfall-annual"]


async def test_a_section_that_shows_the_only_layer_built_adds_nothing() -> None:
    builders = map_layers(LayerBuilder("soil-ph-0-5cm")).without((), shown={SOIL})
    assert (await builders.added(geology_ask())).blocks == ()
    unshown = map_layers(LayerBuilder("soil-ph-0-5cm")).without(())
    assert [block.layer for block in (await unshown.added(geology_ask())).blocks] == ["soil-ph-0-5cm"]
