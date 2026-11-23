import copy
import json
import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError
from pydantic.alias_generators import to_camel

from app.data.craft_master_loader import seed_uuid
from app.geo.layers import LAYERS_BY_ID
from app.research.datasets import BOUNDARY_CAPTION
from app.research.expert_panel import EXPERT_PANEL
from app.research.explainer import BUILT_BLOCK_KINDS, BlockEvent, payload_sentences, with_payload_sentences
from app.research.knowledge_pieces import PieceSlot, knowledge_piece, piece_slot
from app.research.piece_topics import TopicSubjects, facet_topic
from app.services.claim_seed import load_seed_claims, seed_id
from app.services.compound_lookup import record_source_id
from app.services.glossary_plan import compounds_of, concepts_of, glossary_plan
from app.services.piece_store import storable
from app.services.science_seed import load_science_seed, science_seed_plan
from app.sources.reference.pubchem import PUBCHEM_LICENCE, PUBCHEM_PUBLISHER

from .explainer_golden import (
    citations_in,
    golden_json,
    seed_citations,
    seed_claims,
    seed_sources,
    sentences_in,
)
from .golden import REPO, reproduces
from .phase_b_golden import PHASE_B, PhaseBFixture, catalog_dataset, phase_b, phase_b_blocks

PUBCHEM_RECORDED = REPO / "backend" / "tests" / "sources" / "fixtures" / "pubchem_compound.json"
AT = datetime(2026, 11, 17, 10, 30, tzinfo=UTC)
KACHCHH_BASIN = "river.kachchh.golden.json"
KHARI_HEADWATER, KHARI_OUTLET = 41054582, 41063203


def fixture() -> PhaseBFixture:
    return PhaseBFixture.model_validate(phase_b())


def blocks() -> dict[str, Any]:
    return {block.id: block for section in fixture().sections for block in section.blocks}


def subject_of(claim_id: str) -> str:
    return seed_claims()[claim_id]["subjectName"]


def test_the_phase_b_fixture_is_reproduced_byte_for_byte() -> None:
    assert reproduces(PhaseBFixture, PHASE_B)


def test_every_citation_resolves_to_a_seeded_claim_source() -> None:
    seeded = seed_citations()
    found = list(citations_in(phase_b()))
    assert len(found) == 55
    for cite in found:
        row = seeded[cite["id"]]
        assert (cite["claimId"], cite["sourceId"], cite["quote"], cite["locator"], cite["level"]) == (
            row["claimId"],
            row["sourceId"],
            row["quote"],
            row["locator"],
            row["level"],
        )


def test_every_sentence_is_its_seeded_claim_word_for_word() -> None:
    claims = seed_claims()
    for sentence in sentences_in(phase_b()):
        claim_ids = {cite["claimId"] for cite in sentence["citations"]}
        assert len(claim_ids) == 1
        claim = claims[claim_ids.pop()]
        assert (sentence["text"], sentence["level"]) == (claim["text"], claim["evidenceLevel"])


def test_sources_are_every_cited_source_once_in_order_of_first_citation() -> None:
    body = fixture()
    ordered = dict.fromkeys(sid for block in blocks().values() for sid in block.cited_source_ids())
    assert [source.id for source in body.sources] == list(ordered)
    seeded = seed_sources()
    record = str(record_source_id(6293))
    for source in body.sources:
        if source.id == record:
            continue
        row = seeded[source.id]
        assert (source.kind, source.title, source.url, source.reliability) == (
            row["kind"],
            row["title"],
            row["url"],
            row["reliability"],
        )


def test_the_molecule_cites_the_pubchem_record_link_compounds_stores() -> None:
    recorded = json.loads(PUBCHEM_RECORDED.read_text(encoding="utf-8"))["PropertyTable"]["Properties"][0]
    molecule = blocks()["s4.b3"]
    compound = next(c for c in load_science_seed()["compounds"] if c["key"] == "alizarin")
    assert str(molecule.compound_id) == str(seed_id("compound", "alizarin"))
    assert (molecule.name, molecule.formula) == (compound["name"], compound["formula"])
    assert (molecule.pubchem_cid, molecule.formula) == (recorded["CID"], recorded["MolecularFormula"])
    source = next(s for s in fixture().sources if s.id == molecule.source_id)
    assert molecule.source_id == str(record_source_id(recorded["CID"]))
    assert (source.kind, source.title, source.url, source.publisher, source.licence, source.attribution) == (
        "COMPOUND_RECORD",
        f"{recorded['Title']} (PubChem CID {recorded['CID']})",
        f"https://pubchem.ncbi.nlm.nih.gov/compound/{recorded['CID']}",
        PUBCHEM_PUBLISHER,
        PUBCHEM_LICENCE,
        f"PubChem, {PUBCHEM_PUBLISHER}, CID {recorded['CID']}",
    )


def test_the_region_story_draws_registered_districts_and_real_dataset_rows() -> None:
    story = blocks()["s1.b1"]
    register = json.loads(
        (REPO / "backend" / "app" / "data" / "lgd_register.json").read_text(encoding="utf-8")
    )
    district = next(d for d in register["districts"] if d["lgd"] == 449)
    state = next(s for s in register["states"] if s["lgd"] == district["stateLgd"])
    others = json.loads(
        (REPO / "backend" / "app" / "data" / "district_other_names.json").read_text(encoding="utf-8")
    )
    other = next(row["otherNames"] for row in others["districts"] if row["lgd"] == 449)
    assert [d.model_dump(by_alias=True) for d in story.districts] == [
        {"districtLgd": 449, "name": district["name"], "stateName": state["name"], "otherNames": other}
    ]
    layer = golden_json("region.layer.golden.json")
    assert [d.model_dump(mode="json", by_alias=True) for d in story.datasets][:2] == [
        layer["boundary"]["dataset"],
        catalog_dataset("HYDRORIVERS_1_0"),
    ]
    assert [d.code for d in story.datasets][2:] == ["OSM_RIVER_NAMES"]
    assert story.boundary_caption == BOUNDARY_CAPTION == layer["boundary"]["caption"]
    assert set(story.layers) <= set(LAYERS_BY_ID)
    assert story.river.district_lgds == [449] and story.river.name == "Khari"


def test_the_story_s_river_is_the_loaded_khari_traced_from_its_headwater_to_its_outlet() -> None:
    story = blocks()["s1.b1"]
    basin = golden_json(KACHCHH_BASIN)["objects"]["reaches"]["geometries"]
    next_down = {reach["id"]: reach["properties"]["nextDown"] for reach in basin}
    path = [KHARI_HEADWATER]
    while next_down[path[-1]] != 0:
        path.append(next_down[path[-1]])
    assert (story.river.main_riv, story.river.reach_ids) == (path[-1], path)
    assert not any(down == KHARI_HEADWATER for down in next_down.values())
    names = json.loads(
        (REPO / "backend" / "app" / "data" / "rivers" / "river_names.osm.json").read_text("utf-8")
    )
    khari = next(
        river for river in names["rivers"] if river["name"] == "Khari" and path[-1] in river["reachIds"]
    )
    assert set(khari["reachIds"]) <= set(path) and khari["mainRiv"] == path[-1]
    assert all(reach["properties"]["districts"] == [[449, 0.0]] for reach in basin)


def test_the_map_layer_is_the_layer_route_s_layer() -> None:
    layer = golden_json("region.layer.golden.json")
    block = blocks()["s2.b1"]
    assert (block.layer, block.layer_version, block.title) == (
        layer["layer"]["id"],
        layer["version"],
        layer["layer"]["title"],
    )
    assert [d.model_dump(mode="json", by_alias=True) for d in block.datasets] == [
        layer["dataset"],
        layer["boundary"]["dataset"],
    ]
    assert block.highlighted == [449] and str(449) in layer["values"]


def test_the_reaction_player_plays_the_seeded_reactions_of_the_process() -> None:
    plan = science_seed_plan(load_science_seed(), load_seed_claims())
    steps = blocks()["s4.b1"].steps
    rows = {row["id"]: row for row in plan.rows["reactions"]}
    kut, vat, red = (
        seed_id("stage", f"ie:ajrakh.process_stage.{key}") for key in ("kut", "indigo-dyeing", "red-dyeing")
    )
    assert [(step.stage_id, step.label) for step in steps] == [
        (kut, "Scrap iron dissolving into iron acetate"),
        (vat, "Indigo reduced to soluble leucoindigo in the vat"),
        (vat, "Leucoindigo oxidised back to blue indigo in air"),
        (red, "Alizarin binding to the alum mordant"),
    ]
    assert [step.equation for step in steps] == [
        "Fe + 2 CH3COOH -> Fe(CH3COO)2 + H2",
        "C16H10N2O2 + 2 H^+ + 2 e^- -> C16H12N2O2",
        "2 C16H12N2O2 + O2 -> 2 C16H10N2O2 + 2 H2O",
        None,
    ]
    for step in steps:
        row = rows[step.reaction_id]
        assert (step.stage_id, step.kind, step.balanced) == (row["stageId"], row["kind"], row["balanced"])
        assert [
            s.model_dump(mode="json", by_alias=True, exclude={"coefficient"}) for s in step.species
        ] == row["species"]
        assert [s.coefficient for s in step.species] == (row["coefficients"] or [None] * len(row["species"]))
        cites = [
            str(c["claimSourceId"]) for c in plan.rows["reactionCitations"] if c["reactionId"] == row["id"]
        ]
        assert [c.id for c in step.citations] == cites
        assert step.level == "PROVISIONAL"


REACTION_NOTES = (
    ("iron-acetate", ("seed-e1a28b32e2c7416ebed3", "seed-ca39189df4e04dcb5a7a", "seed-b22aaa6d6607a5019194")),
    (
        "indigo-reduction",
        ("seed-d9b4aea0626d66ccdb60", "seed-a16a0906bd1fa81c6de0", "seed-3965c8f733d2c1a997d5"),
    ),
    ("indigo-oxidation", ("seed-86fcd25c654d7a0e0079", "seed-bdce98b16440ad986190")),
    (
        "alizarin-lake",
        (
            "seed-b14a93745f3a652197c0",
            "seed-bd5ef6022d643b22c6dd",
            "seed-5bbd031c8cc0abd3b6b9",
            "seed-0484b9bf06c14eb12785",
        ),
    ),
)


def test_each_reaction_step_names_its_stage_stated_conditions_and_colours() -> None:
    steps = blocks()["s4.b1"].steps
    assert [step.stage for step in steps] == [
        "Kut (iron-black printing)",
        "Indigo dyeing (kun me burana)",
        "Indigo dyeing (kun me burana)",
        "Red dyeing (rang) with madder or alizarin",
    ]
    assert [[(c.label, c.stated) for c in step.conditions] for step in steps] == [
        [("Fermenting the iron paste", "ten to fifteen days")],
        [],
        [],
        [("Red dye bath", "up to four hours")],
    ]
    assert [[(c.side, c.colour, c.stated) for c in step.colours] for step in steps] == [
        [],
        [],
        [
            ("BEFORE", "GREEN", "At first bright green, the cloth rapidly becomes blue"),
            ("AFTER", "BLUE", "At first bright green, the cloth rapidly becomes blue"),
        ],
        [("AFTER", "RED", "develops red")],
    ]


def test_the_reaction_notes_are_each_reaction_s_seeded_claims_once_each() -> None:
    block = blocks()["s4.b1"]
    steps = [step.reaction_id for step in block.steps]
    expected = [
        (reaction, seed_id("claim", claim))
        for reaction, (_, claims) in zip(steps, REACTION_NOTES, strict=True)
        for claim in claims
    ]
    found = [(note.reaction_id, uuid.UUID(note.sentence.citations[0].claim_id)) for note in block.notes]
    assert found == expected
    texts = {seed_id("claim", row["id"]): row["text"] for row in load_seed_claims()["claims"]}
    assert all(
        note.sentence.text == texts[claim] for note, (_, claim) in zip(block.notes, expected, strict=True)
    )


def test_the_material_card_is_the_seeded_material_its_compound_and_its_term() -> None:
    card = blocks()["s4.b2"]
    plan = science_seed_plan(load_science_seed(), load_seed_claims())
    material = next(
        m for m in plan.rows["materials"] if m["id"] == seed_id("material", "ie:ajrakh.material.alum")
    )
    assert (card.material_id, card.name, card.material_kind) == (material["id"], "Alum (fatakdi)", "MORDANT")
    assert card.role == load_science_seed()["materials"]["ie:ajrakh.material.alum"]["role"] == "MORDANT"
    compound = next(c for c in load_science_seed()["compounds"] if c["key"] == "potassium-alum")
    assert card.compound_id == material["compoundId"] == seed_id("compound", "potassium-alum")
    assert card.formula == compound["formula"]
    plan = glossary_plan([], {}, concepts_of(load_seed_claims()), compounds_of(load_science_seed()))
    term = next(t for t in plan if t.key == card.term_key)
    assert (card.local_names, card.wikidata_id, card.pubchem_cid) == (
        term.local_names,
        term.wikidata_id,
        None,
    )


def test_season_rows_name_the_season_their_claim_names_and_carry_its_subject() -> None:
    seasons = blocks()["s3.b1"]
    for row in seasons.rows:
        assert row.label == subject_of(row.sentence.citations[0].claim_id)
        assert (row.months, row.season) == ([], "MONSOON")
    assert seasons.rainfall is not None and [dataset.code for dataset in seasons.datasets] == ["CHIRPS_3_0"]


def test_supply_links_name_seeded_materials_and_the_origins_their_sentence_states() -> None:
    links = blocks()["s6.b1"].links
    indigo = str(seed_id("material", "ie:ajrakh.material.indigo"))
    assert [
        (link.material, str(link.material_id) if link.material_id else None, link.origin) for link in links
    ] == [
        ("Indigo", indigo, "Shikarpur"),
        ("Indigo", indigo, "Dhamadka"),
        ("Blocks", None, "Pethapur"),
    ]
    assert all(link.latitude is None and link.wikidata_id is None for link in links)


def test_the_experts_differ_pair_is_stated_by_both_seats_from_different_sources() -> None:
    historian, anthropologist = blocks()["s5.b1"], blocks()["s5.b2"]
    assert {historian.seat, anthropologist.seat} == {"HISTORIAN", "ANTHROPOLOGIST"}
    assert all("HISTORY" in EXPERT_PANEL[view.seat].fields for view in (historian, anthropologist))
    mine, theirs = historian.differs[0], anthropologist.differs[0]
    assert (mine.seat, theirs.seat) == ("ANTHROPOLOGIST", "HISTORIAN")
    assert mine.this_view.text == theirs.other_view.text and mine.other_view.text == theirs.this_view.text
    assert {c.source_id for c in mine.this_view.citations} == {str(seed_id("source", "ie:ajrakh:S1"))}
    assert {c.source_id for c in mine.other_view.citations} == {str(seed_id("source", "ie:ajrakh:S7"))}


def test_each_block_is_stored_as_the_fixture_says() -> None:
    craft_id = seed_uuid("c", "Kutch-Ajrakh")
    subjects = TopicSubjects(craft_slug="Kutch-Ajrakh", districts=(449,))
    expected = []
    for section in fixture().sections:
        for block in section.blocks:
            if not storable(block):
                continue
            slot = PieceSlot(
                craft_id, section.discipline, facet_topic(section.discipline, subjects), "EXPERT"
            )
            stored = piece_slot(block, slot)
            expected.append(
                {
                    "blockId": block.id,
                    "craftId": str(stored.craft_id) if stored.craft_id else None,
                    "facet": stored.facet,
                    "topicKey": stored.topic_key,
                }
            )
    assert phase_b()["pieces"] == expected
    assert {block.kind for block in blocks().values() if not storable(block)} == {"map_layer", "molecule_3d"}


@pytest.mark.parametrize("block_id", sorted(phase_b_blocks()))
def test_phase_b_blocks_are_refused_until_their_lane_builds_them(block_id: str) -> None:
    block = phase_b_blocks()[block_id]
    event = {"sectionId": block_id.split(".")[0], "block": block}
    if block["kind"] in BUILT_BLOCK_KINDS:
        assert BlockEvent.model_validate(event).block.id == block_id
        return
    with pytest.raises(ValidationError, match="not built yet"):
        BlockEvent.model_validate(event)


def test_a_phase_b_piece_is_refused_until_built() -> None:
    slot = PieceSlot(None, "GEOGRAPHY", f"water:basin-{KHARI_OUTLET}", "EXPERT")
    waiting = [
        block for block in blocks().values() if block.kind not in BUILT_BLOCK_KINDS and storable(block)
    ]
    for block in waiting:
        with pytest.raises(ValidationError, match="not built yet"):
            knowledge_piece(block, slot, piece_id=seed_id("piece", "x"), answer_id=None, created_at=AT)


def test_a_built_region_story_is_stored_as_a_cross_craft_basin_piece() -> None:
    story = blocks()["s1.b1"]
    section = PieceSlot(seed_uuid("c", "Kutch-Ajrakh"), "GEOGRAPHY", "water:lgd-449", "EXPERT")
    piece = knowledge_piece(
        story, piece_slot(story, section), piece_id=seed_id("piece", "x"), answer_id=None, created_at=AT
    )
    assert (piece.craft_id, piece.facet, piece.topic_key, piece.kind) == (
        None,
        "GEOGRAPHY",
        f"water:basin-{KHARI_OUTLET}",
        "region_story",
    )


@pytest.mark.parametrize("block_id", sorted(phase_b_blocks()))
def test_the_payload_walk_finds_the_sentences_the_model_cites(block_id: str) -> None:
    payload = phase_b_blocks()[block_id]
    model = blocks()[block_id]
    expected = [s.model_dump(mode="json", by_alias=True) for s in model.cited_sentences()]
    assert [dict(s) for s in payload_sentences(payload)] == expected
    renamed = with_payload_sentences(copy.deepcopy(payload), lambda s: {**s, "id": f"x.{s['id']}"})
    assert [s["id"] for s in payload_sentences(renamed)] == [f"x.{s['id']}" for s in expected]
    walked = {to_camel(name) for name, _ in model.SENTENCES}
    assert {k: v for k, v in renamed.items() if k not in walked} == {
        k: v for k, v in payload.items() if k not in walked
    }
