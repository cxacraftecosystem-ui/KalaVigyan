import copy
from typing import Any

import pytest
from pydantic import ValidationError

from app.models.enums import BLOCK_KINDS
from app.research.blocks import ImagesBlock, ProcessLadderBlock, ProseBlock
from app.research.blocks_signature import SIGNATURE_KINDS
from app.research.explainer import (
    BLOCK_MODELS,
    BLOCK_PHASES,
    BUILT_BLOCK_KINDS,
    SIGNATURE_PHASE,
    Explainer,
    ExplainerSection,
)
from app.research.media_refs import MediaRef

from ..research.test_explainer_blocks import declared
from .explainer_golden import (
    DOCUMENT,
    citations_in,
    golden_json,
    seed_citations,
    seed_claims,
    seed_source_id,
    seed_sources,
    sentences_in,
)
from .golden import reproduces

BLOCK_VERSIONS = {"artisan_voice": (2,), "timeline_map": (1, 2)}


def document() -> dict[str, Any]:
    return copy.deepcopy(golden_json(DOCUMENT))


def section(body: dict[str, Any], section_id: str) -> dict[str, Any]:
    return next(s for s in body["sections"] if s["id"] == section_id)


def block(body: dict[str, Any], block_id: str) -> dict[str, Any]:
    return next(b for s in body["sections"] for b in s["blocks"] if b["id"] == block_id)


def test_the_golden_explainer_is_reproduced_byte_for_byte() -> None:
    assert reproduces(Explainer, DOCUMENT)


def test_every_citation_resolves_to_a_seeded_claim_source() -> None:
    seeded = seed_citations()
    found = list(citations_in(golden_json(DOCUMENT)))
    assert len(found) == 23
    for cite in found:
        row = seeded[cite["id"]]
        assert (cite["claimId"], cite["sourceId"], cite["quote"], cite["locator"]) == (
            row["claimId"],
            row["sourceId"],
            row["quote"],
            row["locator"],
        )
        assert cite["level"] == row["level"] and cite["evidence"] == "QUOTED"


def test_every_sentence_is_its_seeded_claim_word_for_word() -> None:
    claims = seed_claims()
    for sentence in sentences_in(golden_json(DOCUMENT)):
        claim_ids = {cite["claimId"] for cite in sentence["citations"]}
        assert len(claim_ids) == 1
        claim = claims[claim_ids.pop()]
        assert (sentence["text"], sentence["level"]) == (claim["text"], claim["evidenceLevel"])


def test_sources_are_the_seeded_sources_in_order_of_first_citation() -> None:
    body = golden_json(DOCUMENT)
    expected = [seed_source_id(f"ie:ajrakh:{key}") for key in ("S1", "S3", "S4", "S10", "S11")]
    assert [source["id"] for source in body["sources"]] == expected
    rows = seed_sources()
    for source in body["sources"]:
        row = rows[source["id"]]
        assert (source["title"], source["url"], source["reliability"]) == (
            row["title"],
            row["url"],
            row["reliability"],
        )


def test_the_ladder_uses_the_seeded_stages_and_the_science_rows() -> None:
    body = golden_json(DOCUMENT)
    science = golden_json("science.process.golden.json")["processes"][0]
    ladder = block(body, "s1.b1")
    assert ladder["processId"] == science["id"]
    assert [stage["ordinal"] for stage in ladder["stages"]] == [4, 5, 6, 11]
    by_ordinal = {stage["ordinal"]: stage for stage in science["stages"]}
    for stage in ladder["stages"][1:]:
        seeded = by_ordinal[stage["ordinal"]]
        assert stage["stageId"] == seeded["id"] and stage["name"] == seeded["name"]
        assert [m["materialId"] for m in stage["materials"]] == [m["id"] for m in seeded["materials"]]
        assert stage["reactionIds"] == [r["id"] for r in seeded["reactions"]]
    assert ladder["stages"][1]["conditions"][0]["stated"] == "ten to fifteen days"


def test_the_block_kinds_are_every_plan_kind_with_phase_a_built() -> None:
    assert set(BLOCK_MODELS) == set(BLOCK_KINDS) == set(BLOCK_PHASES)
    assert len(BLOCK_KINDS) == 31
    assert [kind for kind, phase in BLOCK_PHASES.items() if phase == SIGNATURE_PHASE] == list(SIGNATURE_KINDS)
    assert not set(SIGNATURE_KINDS) & set(BUILT_BLOCK_KINDS)
    assert [kind for kind, phase in BLOCK_PHASES.items() if phase == "D"] == [
        "quiz",
        "compare",
        "in_practice",
        "open_questions",
        "concept_graph",
        "measure",
        "market_gi",
        "climate_risk",
        "quantities",
    ]
    assert BUILT_BLOCK_KINDS[:3] == ("prose", "process_ladder", "images")
    assert {kind for kind, phase in BLOCK_PHASES.items() if phase == "A"} <= set(BUILT_BLOCK_KINDS)
    assert {BLOCK_PHASES[kind] for kind in BUILT_BLOCK_KINDS} <= {"A", "B", "C", "D"}
    assert BLOCK_PHASES["designs"] == "DEFERRED"
    for kind, model in BLOCK_MODELS.items():
        assert model.model_fields["kind"].annotation.__args__ == (kind,)
        assert model.model_fields["version"].annotation.__args__ == BLOCK_VERSIONS.get(kind, (1,))
        assert list(model.model_fields)[:4] == ["id", "kind", "version", "reuse"]


def test_a_block_that_is_not_built_is_never_shown() -> None:
    body = document()
    section(body, "s3")["blocks"].append(declared("artisan_voice") | {"id": "s3.b2"})
    with pytest.raises(ValidationError, match="not built yet"):
        Explainer.model_validate(body)


def test_images_only_illustrate_claims_their_section_cites() -> None:
    body = document()
    images = block(body, "s1.b2")
    images["items"][0]["claimIds"] = [
        section(body, "s3")["blocks"][0]["sentences"][0]["citations"][0]["claimId"]
    ]
    with pytest.raises(ValidationError, match="images only for claims it cites"):
        ExplainerSection.model_validate(section(body, "s1"))


def test_a_section_is_ready_with_blocks_or_empty_with_what_it_searched() -> None:
    body = document()
    empty = {**section(body, "s3"), "state": "EMPTY", "blocks": [], "searched": "Searched stored findings."}
    assert ExplainerSection.model_validate(empty).state == "EMPTY"
    with pytest.raises(ValidationError, match="exactly when it is EMPTY"):
        ExplainerSection.model_validate({**empty, "searched": None})
    with pytest.raises(ValidationError, match="READY exactly when it holds blocks"):
        ExplainerSection.model_validate({**empty, "state": "READY", "searched": None})


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda b: b["sections"].reverse(), "listed by order"),
        (lambda b: b["sources"].reverse(), "order of first citation"),
        (lambda b: b["sources"].pop(), "order of first citation"),
        (lambda b: block(b, "s3.b1").update(id="s1.b1"), "each block id is used once"),
        (lambda b: b["understood"].update(candidates=b["understood"]["crafts"]), "chosen or offered, once"),
    ],
)
def test_the_document_rules_fail_closed(change: Any, message: str) -> None:
    body = document()
    change(body)
    with pytest.raises(ValidationError, match=message):
        Explainer.model_validate(body)


def test_term_spans_mark_text_the_sentence_shows() -> None:
    prose = block(document(), "s3.b1")
    ProseBlock.model_validate(prose)
    spans = prose["sentences"][0]["terms"]
    for broken, message in (
        ([{"text": "alizarin", "termKey": "alizarin"}], "not in the sentence"),
        ([spans[0], {"text": "indigo", "termKey": "indigo-dye"}], "overlaps another term"),
        ([spans[0], {"text": "madder", "termKey": spans[0]["termKey"]}], "each term is marked once"),
        ([{"text": "madder", "termKey": "Madder"}], "not a term key"),
    ):
        prose["sentences"][0]["terms"] = broken
        with pytest.raises(ValidationError, match=message):
            ProseBlock.model_validate(prose)


def test_prose_states_facts_and_never_a_hypothesis() -> None:
    prose = block(document(), "s3.b1")
    sentence = prose["sentences"][1]
    sentence["level"] = "HYPOTHESIS"
    for cite in sentence["citations"]:
        cite["level"] = "HYPOTHESIS"
    with pytest.raises(ValidationError, match="a hypothesis is an open question"):
        ProseBlock.model_validate(prose)


def test_a_ladder_climbs_by_ordinal_and_states_conditions_as_quoted() -> None:
    ladder = block(document(), "s1.b1")
    ProcessLadderBlock.model_validate(ladder)
    swapped = copy.deepcopy(ladder)
    swapped["stages"][1], swapped["stages"][2] = swapped["stages"][2], swapped["stages"][1]
    with pytest.raises(ValidationError, match="rising ordinal"):
        ProcessLadderBlock.model_validate(swapped)
    restated = copy.deepcopy(ladder)
    restated["stages"][1]["conditions"][0]["stated"] = "two weeks"
    with pytest.raises(ValidationError, match="which no cited quote says"):
        ProcessLadderBlock.model_validate(restated)
    relevelled = copy.deepcopy(ladder)
    relevelled["stages"][0]["level"] = "VERIFIED"
    with pytest.raises(ValidationError, match="is PROVISIONAL, not VERIFIED"):
        ProcessLadderBlock.model_validate(relevelled)


def test_inline_images_need_an_open_licence_and_their_author() -> None:
    images = block(document(), "s1.b2")
    inline, card = images["items"][0]["media"], images["items"][1]["media"]
    assert MediaRef.model_validate(card).display == "LINK_CARD"
    with pytest.raises(ValidationError, match="open licence"):
        MediaRef.model_validate({**inline, "licence": "All rights reserved", "licenceUrl": None})
    with pytest.raises(ValidationError, match="with its author"):
        MediaRef.model_validate({**inline, "author": None})
    with pytest.raises(ValidationError, match="open licence"):
        MediaRef.model_validate({**card, "display": "INLINE", "author": "V&A"})
    with pytest.raises(ValidationError, match="width and height"):
        MediaRef.model_validate({**inline, "height": None})
    images["items"].append(copy.deepcopy(images["items"][0]))
    with pytest.raises(ValidationError, match="each image once"):
        ImagesBlock.model_validate(images)


def test_a_reused_block_carries_the_piece_and_its_date() -> None:
    reused = [
        b for s in Explainer.model_validate(golden_json(DOCUMENT)).sections for b in s.blocks if b.reuse
    ]
    assert [b.id for b in reused] == ["s2.b1"]
    assert str(reused[0].reuse.piece_id) == golden_json("explainer.piece.golden.json")["id"]
