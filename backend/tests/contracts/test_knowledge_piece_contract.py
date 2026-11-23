import copy
import hashlib
import json
import uuid
from typing import Any

import pytest
from pydantic import ValidationError

from app.core.errors import InvalidInput
from app.data.craft_master_loader import seed_uuid
from app.research.explainer import Explainer
from app.research.knowledge_pieces import KnowledgePiece, ReuseAsk, rests_on, reuse_refusal
from app.research.subject_keys import term_key, topic_key
from app.research.terms import Term

from .explainer_golden import DOCUMENT, PIECE, TERM, citations_in, golden_json, seed_citations
from .golden import reproduces

AT = "2026-11-17T10:30:00Z"


def piece_body() -> dict[str, Any]:
    return copy.deepcopy(golden_json(PIECE))


def piece() -> KnowledgePiece:
    return KnowledgePiece.model_validate(golden_json(PIECE))


def ask(**changes: Any) -> ReuseAsk:
    body = {
        "craftId": golden_json(PIECE)["craftId"],
        "facet": "GEOGRAPHY",
        "topicKey": "water:lgd-449",
        "depth": "EXPERT",
    }
    return ReuseAsk.model_validate(body | changes)


def test_the_golden_piece_and_term_are_reproduced_byte_for_byte() -> None:
    assert reproduces(KnowledgePiece, PIECE)
    assert reproduces(Term, TERM)


def test_the_piece_belongs_to_the_seeded_craft_and_hashes_its_content() -> None:
    body = golden_json(PIECE)
    assert body["craftId"] == seed_uuid("c", "Kutch-Ajrakh")
    content = {k: v for k, v in body["payload"].items() if k not in ("id", "reuse")}
    canonical = json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    assert body["contentHash"] == hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def test_the_reused_block_is_the_piece_placed_in_this_explainer() -> None:
    stored = golden_json(PIECE)
    document = golden_json(DOCUMENT)
    reused = next(b for s in document["sections"] for b in s["blocks"] if b["reuse"])
    assert reused["reuse"] == {"pieceId": stored["id"], "storedAt": stored["createdAt"]}
    assert {k: v for k, v in reused.items() if k not in ("id", "reuse")} == {
        k: v for k, v in stored["payload"].items() if k not in ("id", "reuse")
    }
    explainer = Explainer.model_validate(document)
    block = next(b for s in explainer.sections for b in s.blocks if b.reuse)
    assert block.model_copy(update={"id": "s1.b1", "reuse": None}) == piece().payload


def test_the_piece_lists_what_it_rests_on() -> None:
    body = golden_json(PIECE)
    cites = list(citations_in(body["payload"]))
    seeded = seed_citations()
    assert all(seeded[c["id"]]["claimId"] == c["claimId"] for c in cites)
    assert body["claimIds"] == sorted({c["claimId"] for c in cites})
    assert body["sourceIds"] == [
        "907e2c52-14e7-5e41-9b27-9c10f70906a9",
        "d0f53ee9-4b97-5df7-a367-686957bdb7c8",
    ]


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda b: b["claimIds"].reverse(), "claims its block cites"),
        (lambda b: b["sourceIds"].pop(), "sources its block cites"),
        (lambda b: b.update(contentHash="0" * 64), "content hash"),
        (lambda b: b["payload"].update(reuse={"pieceId": b["id"], "storedAt": AT}), "no reuse mark"),
        (lambda b: b.update(kind="images"), "no reuse mark"),
        (lambda b: b.update(language="hi"), "translations are cached apart"),
        (lambda b: b.update(supersededById=b["id"]), "cannot supersede itself"),
        (lambda b: b.update(topicKey="water:Kachchh"), "known namespace"),
    ],
)
def test_a_piece_that_disagrees_with_its_block_is_refused(change: Any, message: str) -> None:
    body = piece_body()
    change(body)
    with pytest.raises(ValidationError, match=message):
        KnowledgePiece.model_validate(body)


def test_a_matching_piece_is_reused_when_every_claim_is_still_visible() -> None:
    stored = piece()
    visible = set(stored.claim_ids)
    assert reuse_refusal(stored, ask(), visible) is None
    assert reuse_refusal(stored, ask(depth="BASIC"), visible) is None
    assert reuse_refusal(stored, ask(), visible | {uuid.uuid4()}) is None


@pytest.mark.parametrize(
    ("change", "piece_change", "visible_drop", "reason"),
    [
        ({"craftId": None}, {}, False, "CRAFT"),
        ({"facet": "CHEMISTRY"}, {}, False, "FACET"),
        ({"topicKey": "water:bhuj"}, {}, False, "TOPIC"),
        ({}, {"depth": "DETAILED"}, False, "DEPTH"),
        ({}, {"staleSince": AT}, False, "STALE"),
        ({}, {"supersededById": "9a8b7c6d-5e4f-4a3b-8c2d-1e0f9a8b7c6d"}, False, "SUPERSEDED"),
        ({}, {"hiddenAt": AT}, False, "HIDDEN"),
        ({}, {"hiddenAt": AT}, True, "HIDDEN"),
        ({}, {"hiddenAt": AT, "supersededById": "9a8b7c6d-5e4f-4a3b-8c2d-1e0f9a8b7c6d"}, False, "SUPERSEDED"),
        ({}, {}, True, "CLAIM_NOT_VISIBLE"),
    ],
)
def test_reuse_is_refused_for_the_first_rule_that_fails(
    change: dict[str, Any], piece_change: dict[str, Any], visible_drop: bool, reason: str
) -> None:
    stored = KnowledgePiece.model_validate(piece_body() | piece_change)
    visible = set(stored.claim_ids[1:] if visible_drop else stored.claim_ids)
    assert reuse_refusal(stored, ask(**change), visible) == reason


def test_a_changed_claim_marks_the_pieces_resting_on_it() -> None:
    stored = piece()
    assert rests_on(stored, [stored.claim_ids[0], uuid.uuid4()])
    assert not rests_on(stored, [uuid.uuid4()])


def test_topic_and_term_keys_are_normalised_one_way() -> None:
    assert topic_key("water", "Kachchh") == "water:kachchh"
    assert topic_key("reaction", "Alum", "Alizarin") == "reaction:alizarin+alum"
    assert topic_key("reaction", "alizarin", "Alum", "ALUM") == "reaction:alizarin+alum"
    assert topic_key("region", "Bhūj  (Kutch)") == "region:bhuj-kutch"
    assert term_key("Iron acetate") == "iron-acetate"
    for bad in (
        lambda: topic_key("hydrology", "Kachchh"),
        lambda: topic_key("water"),
        lambda: topic_key("water", "कच्छ"),
    ):
        with pytest.raises(InvalidInput):
            bad()


@pytest.mark.parametrize(
    "key", ["reaction:alum+alizarin", "reaction:alum+alum", "hydrology:kachchh", "water:", "water:kachchh-"]
)
def test_a_topic_key_off_the_rules_is_refused(key: str) -> None:
    with pytest.raises(ValidationError):
        ask(topicKey=key)


def test_a_term_summarises_cited_facts() -> None:
    body = copy.deepcopy(golden_json(TERM))
    assert [c["id"] for c in citations_in(body)] == [
        "bbda0126-cff0-5edb-b58b-1b9ee4f8bc1a",
        "cc110cce-fba5-54c5-aa96-14f4fae15347",
    ]
    with pytest.raises(ValidationError, match="order of first citation"):
        Term.model_validate(body | {"sources": []})
    body["summary"][0]["level"] = "HYPOTHESIS"
    with pytest.raises(ValidationError, match="never a hypothesis"):
        Term.model_validate(body)
