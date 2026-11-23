import copy
import json
import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError
from pydantic.alias_generators import to_camel

from app.data.craft_master_loader import seed_uuid
from app.research import knowledge_pieces
from app.research.explainer import BUILT_BLOCK_KINDS, BlockEvent, payload_sentences, with_payload_sentences
from app.research.knowledge_pieces import UNSTORED_BLOCK_KINDS, PieceSlot, knowledge_piece
from app.research.measures import DEFINED_UNITS, UNIT_DEFINITIONS
from app.research.piece_topics import TopicSubjects, facet_topic
from app.services.claim_seed import load_seed_claims, seed_id
from app.services.glossary_plan import compounds_of, concepts_of, glossary_plan
from app.services.piece_store import storable
from app.services.science_seed import load_science_seed

from .explainer_golden import PIECE, citations_in, golden_json, seed_citations, seed_claims, seed_sources
from .golden import REPO, reproduces
from .phase_b_golden import catalog_dataset
from .phase_d_golden import PHASE_D, PhaseDFixture, phase_d, phase_d_blocks

AT = datetime(2026, 11, 18, 10, 30, tzinfo=UTC)
AJRAKH = "Kutch-Ajrakh"
BAGRU = "Bagru-Hand-Block-Print"
GI_JOURNAL = "GI_JOURNAL"


def fixture() -> PhaseDFixture:
    return PhaseDFixture.model_validate(phase_d())


def blocks() -> dict[str, Any]:
    return {block.id: block for section in fixture().sections for block in section.blocks}


def claim_of(sentence: Any) -> dict[str, Any]:
    claim_ids = {citation.claim_id for citation in sentence.citations}
    assert len(claim_ids) == 1
    return seed_claims()[claim_ids.pop()]


def source_kinds(sentence: Any) -> set[str]:
    return {seed_sources()[citation.source_id]["kind"] for citation in sentence.citations}


def test_the_phase_d_fixture_is_reproduced_byte_for_byte() -> None:
    assert reproduces(PhaseDFixture, PHASE_D)


def test_every_citation_resolves_to_a_seeded_claim_source() -> None:
    seeded = seed_citations()
    found = list(citations_in(phase_d()))
    assert len(found) == 64
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
    for block in blocks().values():
        for sentence in block.cited_sentences():
            claim = claim_of(sentence)
            assert (sentence.text, sentence.level) == (claim["text"], claim["evidenceLevel"])


def test_sources_are_every_cited_source_once_in_order_of_first_citation() -> None:
    body = fixture()
    ordered = dict.fromkeys(sid for block in blocks().values() for sid in block.cited_source_ids())
    assert [source.id for source in body.sources] == list(ordered)
    for source in body.sources:
        row = seed_sources()[source.id]
        assert (source.kind, source.title, source.reliability) == (
            row["kind"],
            row["title"],
            row["reliability"],
        )
        assert source.url == (row["url"] if row["url"] and row["url"].startswith("https://") else None)


def test_quiz_questions_blank_a_cited_claim_and_offer_terms_of_other_claims() -> None:
    quiz = blocks()["s1.b1"]
    assert [q.prompt for q in quiz.questions] == [
        "_____ is used as a mordant to fasten the colours.",
        "Printed on harde-treated cloth, _____ develops a deep fast chocolate-black as iron reacts with the "
        "tannic acid.",
        "Natural _____ is fermented in an underground vat; a vat need only be made once and can be kept "
        "active, sometimes for decades.",
    ]
    assert [[o.term_key for o in q.options] for q in quiz.questions] == [
        ["alum", "kut", "indigo"],
        ["kut", "gach", "tapano"],
        ["indigo", "alizarin", "alum"],
    ]
    glossary = {term.key: set(term.craft_slugs) for term in seed_glossary()}
    for question in quiz.questions:
        assert question.answer == 0
        keyed = claim_of(question.options[0].sentence)
        for option in question.options:
            assert AJRAKH in glossary[option.term_key]
            assert claim_of(option.sentence)["craftSlug"] == AJRAKH
        assert all(claim_of(o.sentence) is not keyed for o in question.options[1:])


def test_the_concept_graph_links_the_crafts_the_glossary_says_share_each_concept() -> None:
    graph = blocks()["s2.b1"]
    assert graph.focus.slug == AJRAKH
    terms = {term.key: term for term in seed_glossary()}
    concepts = {row["key"]: row for row in load_seed_claims()["concepts"]}
    assert [node.term_key for node in graph.nodes] == ["alum", "indigo"]
    for node in graph.nodes:
        term = terms[node.term_key]
        assert node.label == term.label
        assert {entry.craft.slug for entry in node.crafts} == set(term.craft_slugs)
        for entry in node.crafts:
            own = [key for key in term.concept_keys if concepts[key]["craftSlug"] == entry.craft.slug]
            assert [str(c) for c in entry.concept_ids] == [str(seed_id("concept", key)) for key in own]
            assert claim_of(entry.sentence)["subjectKey"] in own


def test_compare_sets_each_craft_s_own_claims_side_by_side() -> None:
    compare = blocks()["s3.b1"]
    assert [craft.slug for craft in compare.crafts] == [AJRAKH, BAGRU]
    assert [(row.facet, row.term.key if row.term else None) for row in compare.rows] == [
        ("MATERIALS", "alum"),
        ("MATERIALS", "indigo"),
        ("GEOGRAPHY", None),
        ("HISTORY", None),
        ("ECONOMICS", None),
    ]
    for row in compare.rows:
        assert [claim_of(cell.sentence)["craftSlug"] for cell in row.cells] == [AJRAKH, BAGRU]


def test_a_compare_cell_read_from_a_stored_piece_is_that_piece_s_sentence() -> None:
    piece = golden_json(PIECE)
    cell = blocks()["s3.b1"].rows[2].cells[0]
    assert str(cell.piece_id) == piece["id"]
    stored = next(s for s in piece["payload"]["sentences"] if s["text"] == cell.sentence.text)
    shown = cell.sentence.model_dump(mode="json", by_alias=True)
    assert (shown["text"], shown["citations"]) == (stored["text"], stored["citations"])


def test_the_measure_converts_the_stated_feet_by_the_exact_definition() -> None:
    row = blocks()["s4.b1"].rows[0]
    assert (row.stated, row.low, row.high, row.unit_label) == ("10-15 feet", 10.0, 15.0, "feet")
    assert (row.metric.low, row.metric.high, row.metric.unit) == (3.05, 4.57, "m")
    conversion = row.conversion
    assert (conversion.unit, conversion.basis, conversion.factor) == ("foot", "DEFINED", 0.3048)
    assert str(DEFINED_UNITS["foot"].factor) == "0.3048"
    assert conversion.dataset == UNIT_DEFINITIONS and conversion.region is None


def test_the_gi_records_are_what_the_registry_claims_state() -> None:
    ajrakh, bagru = blocks()["s5.b1"].gi, blocks()["s5.b2"].gi
    assert (ajrakh.application_number, ajrakh.filed_on, ajrakh.registered_on, ajrakh.journal_issue) == (
        "1050",
        "2023-01-31",
        "2024-04-22",
        "188",
    )
    assert "filed as GI application 1050 on 31-01-2023" in ajrakh.sentences[0].text
    assert (bagru.application_number, bagru.certificate_number, bagru.journal_issue) == ("183", "150", "37")
    assert (bagru.filed_on, bagru.registered_on) == ("2009-08-10", "2011-05-11")
    for gi in (ajrakh, bagru):
        assert gi.status == "REGISTERED"
        assert all(source_kinds(sentence) == {GI_JOURNAL} for sentence in gi.sentences)


def test_signs_of_imitation_come_from_gi_journal_text() -> None:
    market = blocks()["s5.b2"]
    assert market.craft.slug == BAGRU and len(market.imitation) == 1
    assert source_kinds(market.imitation[0]) == {GI_JOURNAL}
    assert "Fake screen-printed Bagru textiles" in market.imitation[0].text


def test_the_climate_trend_reads_the_chirps_row_of_kachchh_over_its_period() -> None:
    climate = blocks()["s6.b1"]
    register = json.loads(
        (REPO / "backend" / "app" / "data" / "lgd_register.json").read_text(encoding="utf-8")
    )
    district = next(d for d in register["districts"] if d["lgd"] == 449)
    trend = climate.trends[0]
    assert (trend.district.district_lgd, trend.district.name) == (449, district["name"])
    assert [d.model_dump(mode="json", by_alias=True) for d in climate.datasets] == [
        catalog_dataset("CHIRPS_3_0") | {"period": "1981-2025"}
    ]
    assert (trend.period, trend.resolution) == ("1981-2025", "0.05 degree")
    assert (trend.mean, trend.slope_per_decade, trend.p_value, trend.significant) == (
        449.356389,
        70.760167,
        0.004992,
        True,
    )


def test_each_block_is_stored_as_the_contract_says() -> None:
    crafts = {craft.slug: craft for craft in fixture().crafts}
    expected = []
    for section in fixture().sections:
        for block in section.blocks:
            if not storable(block) or block.kind in UNSTORED_BLOCK_KINDS:
                continue
            if block.kind == "market_gi" and block.craft.slug != AJRAKH:
                continue
            subjects = TopicSubjects(craft_slug=AJRAKH, districts=(449,))
            expected.append(
                {
                    "blockId": block.id,
                    "craftId": str(seed_uuid("c", AJRAKH)),
                    "facet": section.discipline,
                    "topicKey": facet_topic(section.discipline, subjects),
                }
            )
    assert phase_d()["pieces"] == expected
    assert set(crafts) == {AJRAKH, BAGRU}


@pytest.mark.parametrize("block_id", sorted(phase_d_blocks()))
def test_phase_d_blocks_are_refused_until_their_lane_builds_them(block_id: str) -> None:
    block = phase_d_blocks()[block_id]
    event = {"sectionId": block_id.split(".")[0], "block": block}
    if block["kind"] in BUILT_BLOCK_KINDS:
        assert BlockEvent.model_validate(event).block.kind == block["kind"]
        return
    with pytest.raises(ValidationError, match="not built yet"):
        BlockEvent.model_validate(event)


def test_compare_and_the_concept_graph_are_built_and_the_quiz_never_streams() -> None:
    assert {"compare", "concept_graph"} <= set(BUILT_BLOCK_KINDS)
    assert "quiz" not in BUILT_BLOCK_KINDS


@pytest.mark.parametrize("block_id", ["s1.b1", "s2.b1", "s3.b1", "s6.b1"])
def test_a_rebuilt_kind_is_never_a_stored_piece(block_id: str, monkeypatch: pytest.MonkeyPatch) -> None:
    block = blocks()[block_id]
    slot = PieceSlot(seed_uuid("c", AJRAKH), "MATERIALS", "material:kutch-ajrakh", "EXPERT")
    if block.kind not in BUILT_BLOCK_KINDS:
        with pytest.raises(ValidationError, match="not built yet"):
            knowledge_piece(block, slot, piece_id=uuid.uuid4(), answer_id=None, created_at=AT)
    assert not storable(block)
    monkeypatch.setattr(knowledge_pieces, "BUILT_BLOCK_KINDS", (*BUILT_BLOCK_KINDS, block.kind))
    with pytest.raises(ValidationError, match="rebuilt each time"):
        knowledge_piece(block, slot, piece_id=uuid.uuid4(), answer_id=None, created_at=AT)
    assert block.kind in UNSTORED_BLOCK_KINDS


@pytest.mark.parametrize("block_id", sorted(phase_d_blocks()))
def test_the_payload_walk_finds_the_sentences_the_model_cites(block_id: str) -> None:
    payload = phase_d_blocks()[block_id]
    model = blocks()[block_id]
    expected = [s.model_dump(mode="json", by_alias=True) for s in model.cited_sentences()]
    assert [dict(s) for s in payload_sentences(payload)] == expected
    renamed = with_payload_sentences(copy.deepcopy(payload), lambda s: {**s, "id": f"x.{s['id']}"})
    assert [s["id"] for s in payload_sentences(renamed)] == [f"x.{s['id']}" for s in expected]
    walked = {to_camel(name) for name, _ in model.SENTENCES}
    assert {k: v for k, v in renamed.items() if k not in walked} == {
        k: v for k, v in payload.items() if k not in walked
    }


def seed_glossary() -> list[Any]:
    return glossary_plan([], {}, concepts_of(load_seed_claims()), compounds_of(load_science_seed()))
