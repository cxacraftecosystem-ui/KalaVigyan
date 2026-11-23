import asyncio
import dataclasses
import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import TypeAdapter

from app.core.errors import InvalidInput
from app.research.blocks import ReuseMarker
from app.research.blocks_matter import MaterialCardBlock
from app.research.blocks_place import MapLayerBlock
from app.research.explainer import BLOCK_PHASES, BUILT_BLOCK_KINDS, Block
from app.research.piece_reuse import PIECE_BLOCK_ORDER
from app.research.planning import PlanRequest
from app.research.retrieval import KnowledgeHits
from app.research.sections import SectionSpec
from app.services.answer_events import CitedClaims
from app.services.block_builders import (
    BLOCK_BUILDERS,
    BUILDER_WAIT_MAX_SECONDS,
    BlockBuilders,
    BuilderEntry,
    built_by_registry,
)
from app.services.builder_interface import BuildAsk, Built
from app.services.builder_record import BuilderOutcome
from app.services.simulation_builder import SIMULATION_BUDGET_SECONDS, SIMULATION_WAIT_SECONDS

from ..composer.fixtures import pack
from ..contracts.phase_b_golden import phase_b, phase_b_blocks
from ..place.fixtures import water_prose
from ..research.fixtures import AJRAKH
from ..research.test_explainer_blocks import declared
from .fakes import (
    UNDERSTOOD_REPLY,
    FakeResearch,
    FakeStore,
    enriched,
    pipeline,
    streamed,
    understanding_model,
)
from .piece_fakes import MemoryPieces
from .test_answer_flow import REPLY, detailed, events

CARD = MaterialCardBlock.model_validate(phase_b_blocks()["s4.b2"])
SOURCES = {source["id"]: source for source in phase_b()["sources"]}
CARD_SOURCES = {sid: SOURCES[sid] for sid in CARD.cited_source_ids()}
REUSED = ReuseMarker(piece_id=uuid.uuid4(), stored_at=datetime(2026, 11, 17, tzinfo=UTC))


@dataclasses.dataclass
class FakeBuilder:
    blocks: tuple[Any, ...] = (CARD,)
    sources: dict[str, Any] = dataclasses.field(default_factory=lambda: dict(CARD_SOURCES))
    delay: float = 0.0
    failure: Exception | None = None
    asks: list[BuildAsk] = dataclasses.field(default_factory=list)

    async def build(self, ask: BuildAsk) -> Built:
        self.asks.append(ask)
        await asyncio.sleep(self.delay)
        if self.failure is not None:
            raise self.failure
        return Built(self.blocks, self.sources)


def entry(
    kind: str = "material_card", fields: tuple[str, ...] = ("CHEMISTRY",), wait: float = 1.0
) -> BuilderEntry:
    return BuilderEntry(kind, frozenset(fields), lambda tools: FakeBuilder(), wait)


def ask(discipline: str = "CHEMISTRY") -> BuildAsk:
    request = PlanRequest(question="Why is alum used in Ajrakh?", mode="HYBRID", craft=None)
    spec = SectionSpec(id="s1", discipline=discipline, title="The chemistry", order=1)
    return BuildAsk(uuid.uuid4(), spec, request, (water_prose(),), CitedClaims())


def test_every_later_built_kind_has_a_builder() -> None:
    later = {kind for kind in BUILT_BLOCK_KINDS if BLOCK_PHASES[kind] != "A"}
    assert later <= built_by_registry()


def test_the_matter_builders_add_to_chemistry_and_materials_sections() -> None:
    fields = {entry.kind: entry.disciplines for entry in BLOCK_BUILDERS}
    assert fields["reaction_player"] == {"CHEMISTRY"}
    assert fields["material_card"] == fields["molecule_3d"] == {"CHEMISTRY", "MATERIALS"}


def test_seasons_join_climate_process_and_geography_and_supply_joins_materials_process_and_economics() -> (
    None
):
    entries = {entry.kind: entry for entry in BLOCK_BUILDERS}
    assert entries["seasons"].disciplines == {"CLIMATE", "PROCESS", "GEOGRAPHY"}
    assert entries["supply_map"].disciplines == {"MATERIALS", "PROCESS", "ECONOMICS"}
    assert (entries["seasons"].wait_seconds, entries["supply_map"].wait_seconds) == (8.0, 30.0)
    assert {"seasons", "supply_map"} <= set(BUILT_BLOCK_KINDS)


def test_the_matter_kinds_are_built_with_their_builders() -> None:
    assert {"reaction_player", "material_card", "molecule_3d"} <= set(BUILT_BLOCK_KINDS)


def test_only_builders_of_built_kinds_are_started() -> None:
    made: list[str] = []
    entries = [
        BuilderEntry(
            kind, frozenset({"CHEMISTRY"}), lambda tools, kind=kind: made.append(kind) or FakeBuilder()
        )
        for kind in ("material_card", "artisan_voice")
    ]
    started = BlockBuilders.from_registry(object(), entries)
    assert made == ["material_card"]
    assert [entry.kind for entry, _ in started.for_section("CHEMISTRY")] == ["material_card"]


@pytest.mark.parametrize(
    ("kind", "fields", "wait", "message"),
    [
        ("prose", ("CHEMISTRY",), 1.0, "later phase's block kind"),
        ("not_a_kind", ("CHEMISTRY",), 1.0, "later phase's block kind"),
        ("material_card", (), 1.0, "names the fields"),
        ("material_card", ("ALCHEMY",), 1.0, "names the fields"),
        ("material_card", ("CHEMISTRY",), BUILDER_WAIT_MAX_SECONDS + 1, "at most"),
        ("material_card", ("CHEMISTRY",), 0.0, "at most"),
    ],
)
def test_a_registry_entry_fails_closed(kind: str, fields: tuple[str, ...], wait: float, message: str) -> None:
    with pytest.raises(InvalidInput, match=message):
        entry(kind, fields, wait)


async def test_builders_run_together_for_their_fields_only() -> None:
    slow, quick, elsewhere = FakeBuilder(delay=0.05), FakeBuilder(), FakeBuilder()
    builders = BlockBuilders([(entry(), slow), (entry(), quick), (entry(fields=("HISTORY",)), elsewhere)])
    started = asyncio.get_running_loop().time()
    added = await builders.added(ask())
    assert asyncio.get_running_loop().time() - started < 0.1 + 0.05
    assert [block.kind for block in added.blocks] == ["material_card", "material_card"]
    assert (len(slow.asks), len(quick.asks), elsewhere.asks) == (1, 1, [])
    assert added.sources == CARD_SOURCES


async def test_a_late_failing_or_wrong_builder_adds_nothing_and_the_others_still_count() -> None:
    builders = BlockBuilders(
        [
            (entry(wait=0.01), FakeBuilder(delay=1.0)),
            (entry(), FakeBuilder(failure=RuntimeError("gone"))),
            (entry(kind="seasons"), FakeBuilder()),
            (entry(), FakeBuilder(sources={})),
            (entry(), FakeBuilder(blocks=(CARD.model_copy(update={"reuse": REUSED}),))),
            (entry(), FakeBuilder()),
        ]
    )
    added = await builders.added(ask())
    assert [block.kind for block in added.blocks] == ["material_card"]


async def test_a_kind_that_is_not_built_yet_is_never_added() -> None:
    voice = TypeAdapter(Block).validate_python(declared("artisan_voice"))
    later = FakeBuilder(blocks=(voice,), sources={})
    added = await BlockBuilders([(entry(kind="artisan_voice"), later)]).added(ask())
    assert (added.blocks, len(later.asks)) == ((), 1)


async def test_section_builds_number_their_blocks_after_the_section_s_own() -> None:
    builders = BlockBuilders([(entry(), FakeBuilder()), (entry(), FakeBuilder())])
    async with builders.building() as builds:
        builds.start(ask())
        added = await builds.added("s1", first_ordinal=2)
    assert [block.id for block in added.blocks] == ["s1.b2", "s1.b3"]
    unchecked = dataclasses.replace(ask(), blocks=())
    async with builders.building() as builds:
        builds.start(unchecked)
        assert (await builds.added("s1", first_ordinal=1)).blocks == ()
    async with builders.building() as builds:
        assert (await builds.added("s1", first_ordinal=2)).blocks == ()


async def test_builds_still_running_when_a_section_stops_are_cancelled() -> None:
    hanging = FakeBuilder(delay=30.0)
    builders = BlockBuilders([(entry(wait=BUILDER_WAIT_MAX_SECONDS), hanging)])
    async with builders.building() as builds:
        builds.start(ask())
        await asyncio.sleep(0.01)
    assert len(hanging.asks) == 1


async def test_an_added_block_streams_after_the_prose_before_the_pictures_and_is_stored() -> None:
    store, pieces = FakeStore(), MemoryPieces()
    builder = FakeBuilder()
    answer = dataclasses.replace(
        pipeline(replies=[REPLY], store=store, pieces=pieces, enrichment=enriched()),
        builders=BlockBuilders([(entry(), builder)]),
    )
    found = events(await streamed(detailed(), answer))
    shown = [(payload["block"]["id"], payload["block"]["kind"]) for name, payload in found if name == "block"]
    assert shown == [("s1.b1", "prose"), ("s1.b2", "material_card"), ("s1.b3", "images")]
    sent = [payload["id"] for name, payload in found if name == "source"]
    assert set(CARD_SOURCES) <= set(sent)
    (built_ask,) = builder.asks
    assert [block.kind for block in built_ask.blocks] == ["prose"]
    (finished,) = store.finished
    assert [block.kind for block in finished["explainer"].sections[0].blocks] == [
        "prose",
        "material_card",
        "images",
    ]
    ((_, _, sections),) = pieces.kept
    assert [[block.kind for block in section.blocks] for section in sections] == [["prose", "material_card"]]


def test_the_registry_adds_kinds_in_the_one_order_a_reused_section_reads() -> None:
    kinds = [entry.kind for entry in BLOCK_BUILDERS]
    assert kinds == sorted(kinds, key=PIECE_BLOCK_ORDER.index)
    assert [entry.kind for entry in BLOCK_BUILDERS if entry.rebuilt_on_reuse] == [
        "region_story",
        "map_layer",
        "climate_risk",
        "market_gi",
        "reaction_player",
        "molecule_3d",
        "artisan_voice",
        "zoom_story",
        "compare",
        "concept_graph",
    ]


async def test_a_section_with_nothing_checked_starts_no_builder_and_stays_empty() -> None:
    climate = FakeBuilder(blocks=(MapLayerBlock.model_validate(phase_b_blocks()["s2.b1"]),), sources={})
    empty = pack(stored=KnowledgeHits(craft_slug=AJRAKH.slug), evidence=(), documents=())
    understand = {**UNDERSTOOD_REPLY, "disciplines": ["CLIMATE"], "seats": ["CLIMATOLOGIST"]}
    answer = dataclasses.replace(
        pipeline(research=FakeResearch(pack=empty), understand_model=understanding_model(understand)),
        builders=BlockBuilders([(entry(kind="map_layer", fields=("CLIMATE",)), climate)]),
    )
    found = events(await streamed(detailed(), answer))
    assert [name for name, _ in found if name == "block"] == []
    (done,) = [payload for name, payload in found if name == "section_done"]
    assert (done["state"], done["searched"].startswith("Searched ")) == ("EMPTY", True)
    assert climate.asks == []


SEASONS = TypeAdapter(Block).validate_python({**phase_b_blocks()["s3.b1"], "reuse": None})
SEASON_SOURCES = {sid: SOURCES[sid] for sid in SEASONS.cited_source_ids()}


@dataclasses.dataclass
class SecondTime:
    asks: list[str] = dataclasses.field(default_factory=list)

    async def build(self, ask: BuildAsk) -> Built:
        self.asks.append(ask.section.discipline)
        return Built((SEASONS,), dict(SEASON_SOURCES)) if len(self.asks) > 1 else Built()


def seasons_in(builder: Any, *fields: str) -> BlockBuilders:
    entry = BuilderEntry("seasons", frozenset(fields), lambda tools: builder, 1.0)
    return BlockBuilders([(entry, builder)])


async def test_one_answer_builds_a_craft_level_story_once_and_takes_it_back_when_none_was_built() -> None:
    builder = SecondTime()
    answer = seasons_in(builder, "PROCESS", "CLIMATE", "GEOGRAPHY").for_answer()
    assert (await answer.added(ask("PROCESS"))).blocks == ()
    assert [block.kind for block in (await answer.added(ask("CLIMATE"))).blocks] == ["seasons"]
    assert (await answer.added(ask("GEOGRAPHY"))).blocks == ()
    assert builder.asks == ["PROCESS", "CLIMATE"]


async def test_a_craft_level_story_a_reused_section_shows_is_not_built_again() -> None:
    seasons = FakeBuilder((SEASONS,), dict(SEASON_SOURCES))
    answer = seasons_in(seasons, "CLIMATE").for_answer()
    answer.without(()).note_shown(["prose", "seasons"])
    assert (await answer.added(ask("CLIMATE"))).blocks == ()
    unscoped = seasons_in(seasons, "CLIMATE")
    assert len((await unscoped.added(ask("CLIMATE"))).blocks) == 1
    assert len((await unscoped.added(ask("CLIMATE"))).blocks) == 1


def test_an_entry_replaces_a_stored_block_only_when_rebuilt_and_names_a_depth_it_is_reused_from() -> None:
    with pytest.raises(InvalidInput):
        BuilderEntry("reaction_player", frozenset({"CHEMISTRY"}), FakeBuilder, replaces_stored=True)
    with pytest.raises(InvalidInput):
        BuilderEntry("what_if", frozenset({"CHEMISTRY"}), FakeBuilder, reused_from="DEEP")
    reused = {entry.kind: entry.reused_from for entry in BLOCK_BUILDERS if entry.reused_from != "BASIC"}
    assert reused == {"expert_view": "EXPERT", "simulation": "EXPERT"}


@dataclasses.dataclass
class Says:
    note: str

    async def build(self, ask: BuildAsk) -> Built:
        return Built(note=self.note)


async def test_each_builder_s_outcome_and_time_is_recorded_for_its_section() -> None:
    recorded: list[tuple[uuid.UUID, str, list[BuilderOutcome]]] = []

    async def record(answer_id: uuid.UUID, section_id: str, outcomes: list[BuilderOutcome]) -> None:
        recorded.append((answer_id, section_id, list(outcomes)))

    pairs = [
        (entry("simulation"), Says("NO_QUANTITY")),
        (entry("material_card"), FakeBuilder()),
        (entry("what_if", wait=0.01), FakeBuilder(delay=1.0)),
        (entry("molecule_3d"), FakeBuilder(failure=RuntimeError("broken"))),
    ]
    asked = ask()
    added = await BlockBuilders(pairs, record=record).added(asked)
    assert [block.kind for block in added.blocks] == ["material_card"]
    ((answer_id, section_id, outcomes),) = recorded
    assert (answer_id, section_id) == (asked.answer_id, "s1")
    assert [(o.kind, o.outcome, o.blocks) for o in outcomes] == [
        ("simulation", "NO_QUANTITY", 0),
        ("material_card", "ADDED", 1),
        ("what_if", "TIMED_OUT", 0),
        ("molecule_3d", "FAILED", 0),
    ]
    assert all(outcome.seconds >= 0 for outcome in outcomes)


def test_the_generated_explainer_drafts_within_a_budget_well_under_its_wait() -> None:
    entries = {item.kind: item for item in BLOCK_BUILDERS}
    assert entries["simulation"].wait_seconds == SIMULATION_WAIT_SECONDS == 75.0
    assert SIMULATION_BUDGET_SECONDS == 60.0
    assert entries["expert_view"].wait_seconds > SIMULATION_WAIT_SECONDS
