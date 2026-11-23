import copy
import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import TypeAdapter, ValidationError

from app.models.enums import DISCIPLINES, SOURCE_KINDS
from app.research.blocks_people import EXPERT_SEATS, expert_pairing_problems
from app.research.calendar import months_named, seasons_named
from app.research.expert_panel import EXPERT_PANEL, seats_for
from app.research.explainer import Block
from app.research.knowledge_pieces import PieceSlot, ReuseAsk, knowledge_piece
from app.research.piece_reuse import PIECE_BLOCK_ORDER, ClaimState, reusable_groups
from app.research.piece_topics import FACET_NAMESPACES
from app.services.piece_store import piece_id

from ..contracts.phase_b_golden import phase_b_blocks

BLOCK = TypeAdapter(Block)


def fixture_block(block_id: str) -> dict[str, Any]:
    return copy.deepcopy(phase_b_blocks()[block_id])


def refused(body: dict[str, Any], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        BLOCK.validate_python(body)


def test_every_fixture_block_validates() -> None:
    for body in phase_b_blocks().values():
        assert BLOCK.validate_python(body).id == body["id"]


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda b: b.update(boundaryCaption="District boundaries are indicative."), "word for word"),
        (lambda b: b.update(datasets=b["datasets"][:1]), "HYDRORIVERS_1_0 missing"),
        (
            lambda b: b.update(datasets=[b["datasets"][0], b["datasets"][0], b["datasets"][1]]),
            "each dataset once",
        ),
        (lambda b: b["steps"][0].update(districtLgd=90), "only districts it lists"),
        (lambda b: b["river"].update(districtLgds=[90]), "river's districts first"),
        (
            lambda b: (b["river"].update(name="Indus Delta"), b.update(datasets=b["datasets"][:2])),
            "names the river only as a cited step or a river names dataset row states it",
        ),
        (lambda b: b["river"].update(reachIds=b["river"]["reachIds"][::-1]), "source to its outlet"),
        (lambda b: b.update(layers=["river-density", "river-density"]), "each district and layer once"),
        (
            lambda b: b["steps"][0]["sentence"].update(id=b["steps"][1]["sentence"]["id"]),
            "each sentence once",
        ),
    ],
)
def test_a_region_story_fails_closed(change: Any, message: str) -> None:
    body = fixture_block("s1.b1")
    change(body)
    refused(body, message)


def test_a_river_name_no_step_states_stands_on_its_river_names_dataset_row() -> None:
    body = fixture_block("s1.b1")
    body["river"]["name"] = "Indus Delta"
    body["datasets"] = body["datasets"][:2]
    names = {
        "code": "WIKIDATA_RIVER_NAMES",
        "title": "Wikidata river items: English names, mouths and sources",
        "publisher": "Wikidata, Wikimedia Foundation",
        "edition": "2026-11-23",
        "period": "2026-11-23",
        "nativeResolution": "item coordinates (river mouth and river source)",
        "licence": "CC0 1.0",
        "licenceUrl": "https://creativecommons.org/publicdomain/zero/1.0/",
        "attribution": "River names from Wikidata",
        "citation": None,
        "url": "https://query.wikidata.org/sparql",
    }
    body["datasets"].append(names)
    assert BLOCK.validate_python(body).river.name == "Indus Delta"


def test_a_region_story_without_a_river_needs_only_the_boundary_dataset() -> None:
    body = fixture_block("s1.b1")
    body.update(river=None, datasets=body["datasets"][:1])
    assert BLOCK.validate_python(body).river is None


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda b: b.update(datasets=b["datasets"][::-1]), "then DR_DISTRICT_SHAPES"),
        (lambda b: b.update(datasets=b["datasets"][:1]), "at least 2"),
        (lambda b: b.update(highlighted=[449, 449]), "each district once"),
        (lambda b: b.update(layerVersion="v1"), "string_pattern_mismatch|should match pattern"),
        (lambda b: b.update(boundaryCaption=""), "word for word"),
    ],
)
def test_a_map_layer_fails_closed(change: Any, message: str) -> None:
    body = fixture_block("s2.b1")
    change(body)
    refused(body, message)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda r: r.update(months=[6]), "months its sentence and quotes do not name"),
        (lambda r: r.update(season="WINTER"), "a season its sentence and quotes do not name"),
        (lambda r: r.update(months=[], season=None), "placed by months or a season"),
        (lambda r: r.update(months=[12, 1]), "once each, in order"),
    ],
)
def test_a_season_row_shows_only_what_its_claim_names(change: Any, message: str) -> None:
    body = fixture_block("s3.b1")
    change(body["rows"][0])
    refused(body, message)


def test_rainfall_comes_with_its_dataset_row_and_only_then() -> None:
    body = fixture_block("s3.b1")
    assert BLOCK.validate_python(body).rainfall is not None
    body["datasets"] = []
    refused(body, "rainfall's dataset row, and only it")
    body["rainfall"] = None
    body["datasets"] = [fixture_block("s2.b1")["datasets"][1]]
    refused(body, "rainfall's dataset row, and only it")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Printing stops from June to September.", {6, 7, 8, 9}),
        ("The season runs October-March.", {10, 11, 12, 1, 2, 3}),
        ("Dyeing is done in Nov. and Feb.", {11, 2}),
        ("Sept is the wettest month.", {9}),
        ("May is too hot for printing.", set()),
        ("Warm afternoon water may dissolve some of the alum.", set()),
        ("Printers rest in May.", {5}),
        ("Barmer and Marwar share designs; markets peak in March.", {3}),
        ("between June and September", {6, 7, 8, 9}),
    ],
)
def test_months_are_read_only_where_named(text: str, expected: set[int]) -> None:
    assert months_named([text]) == expected


def test_seasons_are_read_from_their_words() -> None:
    assert seasons_named(["Blocks do not expand in the rainy season."]) == {"MONSOON"}
    assert seasons_named(["Monsoon humidity slows production."]) == {"MONSOON"}
    assert seasons_named(["Washing in the cold season and the hot season."]) == {"WINTER", "SUMMER"}
    assert seasons_named(["The rainstorm passed."]) == set()


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda link: link.update(origin="Bhuj"), "not what its sentence states"),
        (lambda link: link.update(latitude=23.2, longitude=69.8), "by Wikidata or by its register district"),
        (
            lambda link: link.update(materialId=None, termKey=None, material="Madder"),
            "neither stored nor stated",
        ),
    ],
)
def test_a_supply_link_fails_closed(change: Any, message: str) -> None:
    body = fixture_block("s6.b1")
    change(body["links"][0])
    refused(body, message)


def test_a_supply_origin_is_placed_with_wikidata_coordinates() -> None:
    body = fixture_block("s6.b1")
    body["links"][0].update(wikidataId="Q1", latitude=27.95, longitude=68.64)
    assert BLOCK.validate_python(body).links[0].latitude == 27.95
    body["links"].append(
        copy.deepcopy(body["links"][0]) | {"sentence": body["links"][1]["sentence"] | {"id": "s6.b1.9"}}
    )
    refused(body, "each origin of a material once")


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda s: s.update(equation="Fe + CH3COOH -> Fe(CH3COO)2 + H2"), "not built from its species"),
        (lambda s: s.update(level="VERIFIED"), "is PROVISIONAL, not VERIFIED"),
        (
            lambda s: s.update(species=[x for x in s["species"] if x["role"] == "REACTANT"]),
            "reactant and one product",
        ),
    ],
)
def test_a_reaction_step_is_the_science_engine_s(change: Any, message: str) -> None:
    body = fixture_block("s4.b1")
    change(body["steps"][0])
    refused(body, message)


def test_an_unbalanced_reaction_with_every_formula_is_shown_as_a_hypothesis() -> None:
    body = fixture_block("s4.b1")
    step = body["steps"][0]
    for species in step["species"]:
        species["coefficient"] = None
    step.update(balanced=False, equation="Fe + CH3COOH -> Fe(CH3COO)2 + H2")
    refused(body, "is HYPOTHESIS, not PROVISIONAL")
    step["level"] = "HYPOTHESIS"
    assert BLOCK.validate_python(body).steps[0].level == "HYPOTHESIS"
    body["steps"].append(copy.deepcopy(step))
    refused(body, "plays each reaction once")


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda b: b.update(materialId=None), "kind or role only from its stored material"),
        (lambda b: b.update(compoundId=None), "formula or PubChem id only from its compound"),
        (lambda b: b.update(termKey=None), "local names or Wikidata only from its glossary term"),
        (lambda b: b.update(localNames=["fatakdi", "Fatakdi"]), "each local name once"),
        (lambda b: b["facts"][0].update(level="HYPOTHESIS"), "states facts only"),
    ],
)
def test_a_material_card_shows_only_stored_values(change: Any, message: str) -> None:
    body = fixture_block("s4.b2")
    change(body)
    if body["facts"][0]["level"] == "HYPOTHESIS":
        for cite in body["facts"][0]["citations"]:
            cite["level"] = "HYPOTHESIS"
    refused(body, message)


def test_a_molecule_names_its_stored_compound_and_record() -> None:
    body = fixture_block("s4.b3")
    refused({k: v for k, v in body.items() if k != "compoundId"}, "compoundId")
    refused(body | {"pubchemCid": 0}, "greater than or equal to 1")


def views() -> list[Any]:
    return [BLOCK.validate_python(fixture_block(block_id)) for block_id in ("s5.b1", "s5.b2")]


def test_the_fixture_pair_is_mutual() -> None:
    assert expert_pairing_problems(views()) == []


def test_a_one_sided_difference_or_agreement_is_refused() -> None:
    historian, anthropologist = views()
    alone = anthropologist.model_copy(update={"differs": []})
    assert expert_pairing_problems([historian, alone]) == [
        "HISTORIAN and ANTHROPOLOGIST differ only when both views state it"
    ]
    assert expert_pairing_problems([historian]) == [
        "HISTORIAN and ANTHROPOLOGIST differ only when both views state it"
    ]
    agreeing = historian.model_copy(update={"agrees_with": ["CHEMIST"]})
    assert "HISTORIAN and CHEMIST agree only when both views say so" in expert_pairing_problems(
        [agreeing, anthropologist]
    )
    assert "each seat gives one view per section" in expert_pairing_problems(
        [historian, historian, anthropologist]
    )


def test_a_mirrored_difference_must_swap_the_same_claims() -> None:
    historian, anthropologist = views()
    theirs = anthropologist.differs[0]
    swapped = theirs.model_copy(update={"other_view": anthropologist.take[0]})
    changed = anthropologist.model_copy(update={"differs": [swapped]})
    assert expert_pairing_problems([historian, changed]) == [
        "HISTORIAN and ANTHROPOLOGIST differ only when both views state it",
        "ANTHROPOLOGIST and HISTORIAN differ only when both views state it",
    ]


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda b: b.update(agreesWith=["HISTORIAN"]), "never its own"),
        (lambda b: b.update(agreesWith=["ANTHROPOLOGIST"]), "each other seat once"),
        (
            lambda b: b["differs"][0].update(otherView=copy.deepcopy(b["differs"][0]["thisView"])),
            "its own claims and sources",
        ),
    ],
)
def test_an_expert_view_fails_closed(change: Any, message: str) -> None:
    body = fixture_block("s5.b1")
    change(body)
    refused(body, message)


def test_the_panel_briefs_every_seat_once_in_seat_order() -> None:
    assert tuple(EXPERT_PANEL) == EXPERT_SEATS
    assert len(EXPERT_PANEL) == 18
    for seat, brief in EXPERT_PANEL.items():
        assert brief.seat == seat and set(brief.source_kinds) <= set(SOURCE_KINDS)
    spoken = {field for brief in EXPERT_PANEL.values() for field in brief.fields}
    assert spoken == set(DISCIPLINES)


def test_seated_experts_speak_in_the_sections_of_their_fields() -> None:
    seated = ("CHEMIST", "HISTORIAN", "HYDROLOGIST", "ANTHROPOLOGIST", "HISTORIAN")
    assert seats_for("HISTORY", seated) == ("HISTORIAN", "ANTHROPOLOGIST")
    assert seats_for("GEOGRAPHY", seated) == ("HYDROLOGIST",)
    assert seats_for("CHEMISTRY", seated) == ("CHEMIST",)
    assert seats_for("ECOLOGY", seated) == ()


def stored(block_id: str, facet: str) -> Any:
    answer = uuid.UUID("3b9f1e2d-6c7a-4d8b-9e0f-1a2b3c4d5e6f")
    block = BLOCK.validate_python(fixture_block(block_id))
    slot = PieceSlot(None, facet, f"{FACET_NAMESPACES[facet]}:kutch-ajrakh", "EXPERT")
    created = datetime(2026, 11, 17, tzinfo=UTC)
    return knowledge_piece(
        block, slot, piece_id=piece_id(answer, block_id), answer_id=answer, created_at=created
    )


def test_a_stored_view_numbers_every_sentence_in_reading_order() -> None:
    piece = stored("s5.b1", "HISTORY")
    prefix = f"p{piece.id.hex[:12]}"
    view = piece.payload
    ids = [view.take[0].id, view.differs[0].this_view.id, view.differs[0].other_view.id]
    assert ids == [f"{prefix}.1", f"{prefix}.2", f"{prefix}.3"]


def test_a_reused_set_reads_by_kind_then_in_the_order_it_was_shown() -> None:
    views = [stored("s5.b2", "HISTORY"), stored("s5.b1", "HISTORY")]
    (group,) = reusable_groups(views, reuse_ask("HISTORY"), claim_states(views))
    assert [piece.payload.seat for piece in group] == ["HISTORIAN", "ANTHROPOLOGIST"]
    chemistry = [stored("s4.b2", "CHEMISTRY"), stored("s4.b1", "CHEMISTRY")]
    (group,) = reusable_groups(chemistry, reuse_ask("CHEMISTRY"), claim_states(chemistry))
    assert [piece.kind for piece in group] == ["reaction_player", "material_card"]
    assert (
        PIECE_BLOCK_ORDER.index("process_ladder")
        < PIECE_BLOCK_ORDER.index("prose")
        < PIECE_BLOCK_ORDER.index("region_story")
    )


def reuse_ask(facet: str) -> ReuseAsk:
    return ReuseAsk(
        craft_id=None, facet=facet, topic_key=f"{FACET_NAMESPACES[facet]}:kutch-ajrakh", depth="EXPERT"
    )


def claim_states(pieces: list[Any]) -> dict[uuid.UUID, ClaimState]:
    citations = [c for piece in pieces for c in piece.payload.citations()]
    return {
        uuid.UUID(claim): ClaimState(
            next(c.level for c in citations if c.claim_id == claim),
            frozenset(c.id for c in citations if c.claim_id == claim),
        )
        for claim in {c.claim_id for c in citations}
    }
