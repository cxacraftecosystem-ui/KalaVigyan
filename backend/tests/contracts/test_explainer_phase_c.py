import copy
import hashlib
import json
import re
from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic.alias_generators import to_camel

from app.data.craft_master_loader import seed_uuid
from app.research.datasets import BOUNDARY_CAPTION
from app.research.explainer import BUILT_BLOCK_KINDS, BlockEvent, payload_sentences, with_payload_sentences
from app.research.knowledge_pieces import PieceSlot, knowledge_piece, piece_slot
from app.research.piece_topics import TopicSubjects, facet_topic
from app.research.sandbox import SANDBOX_ATTRIBUTE, SANDBOX_CSP, SANDBOX_DATA_ELEMENT_ID, sandbox_problems
from app.services.claim_seed import load_seed_claims, seed_id
from app.services.compound_lookup import record_source_id
from app.services.piece_store import storable
from app.services.science_seed import load_science_seed, science_seed_plan
from app.services.supply_places import chosen_candidate
from app.sources.reference.wikidata_places import exact_candidates

from ..sources.recorded import WIKIDATA_API, WIKIDATA_SPARQL, Reply, recorded, wikidata_adapter
from .explainer_golden import (
    citations_in,
    golden_json,
    seed_citations,
    seed_claims,
    seed_sources,
    sentences_in,
)
from .golden import REPO, reproduces
from .phase_c_golden import PHASE_C, PhaseCFixture, phase_c, phase_c_blocks

PLAN = REPO / "docs" / "plans" / "answer-experience.md"
PUBCHEM_RECORDED = "pubchem_compound.json"
CAPITALISED = re.compile(r"\b[A-Z][\w-]{3,}")
AT = datetime(2026, 11, 18, 10, 30, tzinfo=UTC)


def fixture() -> PhaseCFixture:
    return PhaseCFixture.model_validate(phase_c())


def blocks() -> dict[str, Any]:
    return {block.id: block for section in fixture().sections for block in section.blocks}


def claim_key(sentence: Any) -> str:
    return seed_claims()[sentence.citations[0].claim_id]["id"]


def test_the_phase_c_fixture_is_reproduced_byte_for_byte() -> None:
    assert reproduces(PhaseCFixture, PHASE_C)


def test_every_citation_resolves_to_a_seeded_claim_source() -> None:
    seeded = seed_citations()
    found = list(citations_in(phase_c()))
    assert len(found) == 17
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
    for sentence in sentences_in(phase_c()):
        claim_ids = {cite["claimId"] for cite in sentence["citations"]}
        assert len(claim_ids) == 1
        claim = claims[claim_ids.pop()]
        assert (sentence["text"], sentence["level"]) == (claim["text"], claim["evidenceLevel"])


def test_sources_are_every_cited_source_once_in_order_of_first_citation() -> None:
    body = fixture()
    ordered = dict.fromkeys(sid for block in blocks().values() for sid in block.cited_source_ids())
    assert [source.id for source in body.sources] == list(ordered)
    record = str(record_source_id(6293))
    seeded = seed_sources()
    for source in body.sources:
        if source.id == record:
            assert (source.kind, source.url) == (
                "COMPOUND_RECORD",
                "https://pubchem.ncbi.nlm.nih.gov/compound/6293",
            )
            continue
        row = seeded[source.id]
        assert (source.kind, source.title, source.url, source.reliability) == (
            row["kind"],
            row["title"],
            row["url"],
            row["reliability"],
        )


def test_the_sandbox_frame_is_the_plan_s_frame() -> None:
    plan = PLAN.read_text(encoding="utf-8")
    frame = fixture().sandbox
    assert (frame.attribute, frame.csp, frame.data_element_id, frame.max_bytes) == (
        SANDBOX_ATTRIBUTE,
        SANDBOX_CSP,
        SANDBOX_DATA_ELEMENT_ID,
        200 * 1024,
    )
    assert f'sandbox="{frame.attribute}"' in plan
    planned = "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:"
    assert planned in " ".join(plan.split())
    assert frame.csp == f"{planned}; webrtc 'block'"


def test_the_generated_explainer_runs_on_its_cited_figures_only() -> None:
    simulation = blocks()["s1.b1"]
    assert simulation.html_sha256 == hashlib.sha256(simulation.html.encode("utf-8")).hexdigest()
    assert sandbox_problems(simulation.html, {value.key: value.value for value in simulation.values}) == []
    assert [(value.key, value.value) for value in simulation.values] == [
        ("fallLowFeet", 10.0),
        ("fallHighFeet", 15.0),
    ]
    for value in simulation.values:
        (cite,) = value.citations
        assert value.stated == "10-15 feet every year" and value.stated in cite.quote
        assert claim_key(value) == "seed-a6b2bc66dfd07b5c8033"
    assert (simulation.hidden, simulation.datasets, simulation.reuse) == (False, [], None)
    assert 'getElementById("kv-data")' in simulation.html


def test_what_if_options_are_the_red_dye_stage_s_materials_and_an_unknown() -> None:
    what_if = blocks()["s2.b1"]
    plan = science_seed_plan(load_science_seed(), load_seed_claims())
    red = seed_id("stage", "ie:ajrakh.process_stage.red-dyeing")
    used = {row["materialId"] for row in plan.rows["stageMaterials"] if row["stageId"] == red}
    names = {row["id"]: row["name"] for row in plan.rows["materials"]}
    assert what_if.stage_id == red and what_if.changed == "Red dye"
    madder, alizarin, unknown = what_if.options
    for option in (madder, alizarin):
        assert option.material_id in used and option.label == names[option.material_id]
    assert [claim_key(o) for o in (outcome.sentence for outcome in madder.outcomes)] == [
        "seed-9f1f03372efe28f1a53a",
        "seed-32e7a43af292f11fd3b8",
    ]
    assert all("madder" in outcome.sentence.text for outcome in madder.outcomes)
    assert (unknown.label, unknown.material_id, unknown.term_key, unknown.outcomes) == (
        "Al root",
        None,
        None,
        [],
    )


def test_a_what_if_reaction_outcome_rests_on_the_reaction_s_own_citations() -> None:
    plan = science_seed_plan(load_science_seed(), load_seed_claims())
    outcome = blocks()["s2.b1"].options[1].outcomes[1]
    reaction = next(row for row in plan.rows["reactions"] if row["id"] == outcome.reaction_id)
    assert reaction["label"] == "Alizarin binding to the alum mordant"
    cited = {
        str(c["claimSourceId"]) for c in plan.rows["reactionCitations"] if c["reactionId"] == reaction["id"]
    }
    assert cited & {citation.id for citation in outcome.sentence.citations}


def test_the_zoom_story_shows_real_matter_and_leaves_out_unlicensed_levels() -> None:
    zoom = blocks()["s3.b1"]
    assert [level.level for level in zoom.levels] == ["DISTRICT", "WORKSHOP", "MOLECULE"]
    district, workshop, molecule = zoom.levels
    register = json.loads(
        (REPO / "backend" / "app" / "data" / "lgd_register.json").read_text(encoding="utf-8")
    )
    row = next(d for d in register["districts"] if d["lgd"] == 449)
    state = next(s for s in register["states"] if s["lgd"] == row["stateLgd"])
    assert (district.district.name, district.district.state_name) == (row["name"], state["name"])
    pictures = golden_json("explainer.document.golden.json")["sections"][0]["blocks"][1]["items"]
    assert workshop.media.model_dump(mode="json", by_alias=True) == pictures[0]["media"]
    assert (workshop.media.licence, workshop.media.author) == ("CC BY-SA 4.0", "SMarndi")
    assert pictures[1]["media"]["display"] == "LINK_CARD"
    pubchem = json.loads(recorded(PUBCHEM_RECORDED))["PropertyTable"]["Properties"][0]
    compound = molecule.compound
    assert (compound.pubchem_cid, compound.formula) == (pubchem["CID"], pubchem["MolecularFormula"])
    assert (compound.compound_id, compound.source_id) == (
        seed_id("compound", "alizarin"),
        str(record_source_id(6293)),
    )
    layer = golden_json("region.layer.golden.json")
    assert [d.model_dump(mode="json", by_alias=True) for d in zoom.datasets] == [layer["boundary"]["dataset"]]
    assert zoom.boundary_caption == BOUNDARY_CAPTION


def test_timeline_dates_are_the_years_their_sources_state() -> None:
    timeline = blocks()["s4.b1"]
    stated = [(point.year_from, point.year_to) for point in timeline.points]
    assert stated == [(1401, 1500), (1586, 1586), (2001, 2001)]
    fustat, dhamadka, ajrakhpur = timeline.points
    assert "15th-century" in fustat.sentence.text
    assert any("in the year 1586" in (c.quote or "") for c in dhamadka.sentence.citations)
    assert "in 2001" in ajrakhpur.sentence.text
    (route,) = timeline.routes
    assert ((route.year_from, route.year_to), "(1586-1631)" in route.sentence.text) == ((1586, 1631), True)
    (quote,) = [c.quote for c in route.sentence.citations]
    assert "invited" in quote and "from Sindh" in quote and "Kutch" in quote
    names = [place.name for place in timeline.places]
    assert (names[route.start], names[route.end]) == ("Sindh", "Kutch")


async def test_timeline_places_are_placed_only_from_recorded_wikidata() -> None:
    timeline = blocks()["s4.b1"]
    searches = {
        "Fustat": "wikidata_places_fustat.json",
        "Dhamadka": "wikidata_places_dhamadka.json",
        "Ajrakhpur": "wikidata_places_ajrakhpur.json",
        "Sindh": "wikidata_places_sindh.json",
        "Kutch": "wikidata_places_kutch.json",
    }
    words = _sentence_words(timeline)
    chosen = {}
    for place in timeline.places:
        hits = json.loads(recorded(searches[place.name]))["search"]
        candidate = chosen_candidate(exact_candidates(place.name, hits), words[place.name] - {place.name})
        chosen[place.name] = candidate.item_id if candidate else None
    assert chosen == {
        "Fustat": "Q839456",
        "Dhamadka": None,
        "Ajrakhpur": None,
        "Sindh": None,
        "Kutch": "Q37488690",
    }
    replies = [Reply("wikidata_place_points_fustat.json"), Reply("wikidata_place_points_kutch.json")]
    adapter, _ = wikidata_adapter({WIKIDATA_SPARQL: replies, WIKIDATA_API: []})
    points = {**await adapter.place_points(["Q839456"]), **await adapter.place_points(["Q37488690"])}
    for place in timeline.places:
        point = points.get(chosen[place.name] or "")
        expected = (chosen[place.name], point.latitude, point.longitude) if point else (None, None, None)
        assert (place.wikidata_id, place.latitude, place.longitude) == expected


def _sentence_words(timeline: Any) -> dict[str, set[str]]:
    words: dict[str, set[str]] = {}
    uses = [(point.place, point.sentence) for point in timeline.points]
    uses += [(i, route.sentence) for route in timeline.routes for i in (route.start, route.end)]
    for index, sentence in uses:
        texts = [sentence.text, *(c.quote for c in sentence.citations if c.quote)]
        found = {word for text in texts for word in CAPITALISED.findall(text)}
        words.setdefault(timeline.places[index].name, set()).update(found)
    return words


def test_each_block_is_stored_as_the_fixture_says() -> None:
    craft_id = seed_uuid("c", "Kutch-Ajrakh")
    subjects = TopicSubjects(craft_slug="Kutch-Ajrakh", districts=(449,))
    expected = []
    for section in fixture().sections:
        for block in section.blocks:
            assert storable(block)
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
    assert phase_c()["pieces"] == expected
    assert expected[0] == {
        "blockId": "s1.b1",
        "craftId": None,
        "facet": "GEOGRAPHY",
        "topicKey": "concept:falling-water-table",
    }


@pytest.mark.parametrize("block_id", sorted(phase_c_blocks()))
def test_every_phase_c_block_is_built_and_streams_as_the_fixture_writes_it(block_id: str) -> None:
    block = phase_c_blocks()[block_id]
    assert block["kind"] in BUILT_BLOCK_KINDS
    event = BlockEvent.model_validate({"sectionId": block_id.split(".")[0], "block": block})
    assert event.block.model_dump(mode="json", by_alias=True) == block


def test_every_phase_c_block_can_be_kept_as_a_piece() -> None:
    for block in blocks().values():
        slot = piece_slot(block, PieceSlot(None, "HISTORY", "history:kutch-ajrakh", "EXPERT"))
        piece = knowledge_piece(block, slot, piece_id=seed_id("piece", "x"), answer_id=None, created_at=AT)
        assert (piece.kind, piece.payload.reuse) == (block.kind, None)


@pytest.mark.parametrize("block_id", sorted(phase_c_blocks()))
def test_the_payload_walk_finds_the_sentences_the_model_cites(block_id: str) -> None:
    payload = phase_c_blocks()[block_id]
    model = blocks()[block_id]
    expected = [s.model_dump(mode="json", by_alias=True) for s in model.cited_sentences()]
    assert [dict(s) for s in payload_sentences(payload)] == expected
    renamed = with_payload_sentences(copy.deepcopy(payload), lambda s: {**s, "id": f"x.{s['id']}"})
    assert [s["id"] for s in payload_sentences(renamed)] == [f"x.{s['id']}" for s in expected]
    walked = {to_camel(name) for name, _ in model.SENTENCES}
    assert {k: v for k, v in renamed.items() if k not in walked} == {
        k: v for k, v in payload.items() if k not in walked
    }
