import hashlib
import importlib.util
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from pydantic import TypeAdapter

from app.models.enums import BLOCK_KINDS, DISCIPLINES, EXPLAINER_DEPTHS
from app.research.explainer import Block
from app.research.knowledge_pieces import (
    KnowledgePiece,
    PieceSlot,
    ReuseAsk,
    knowledge_piece,
    piece_text,
    placed_block,
    region_topic,
)
from app.research.piece_reuse import ClaimState, reusable_groups, visible_as_cited
from app.research.piece_topics import (
    FACET_NAMESPACES,
    TopicSubjects,
    district_topic,
    facet_topic,
    facet_topics,
)
from app.research.retrieval import HIDDEN_CLAIM_STATUSES
from app.research.subject_keys import TOPIC_NAMESPACES
from app.services.curation_overview import piece_id_topic, piece_topic
from app.services.piece_store import piece_id, storable

from ..contracts.explainer_golden import DOCUMENT, PIECE, golden_json
from ..migration_scripts import migration

BLOCKS = TypeAdapter(Block)
CRAFT_ID = uuid.UUID("54081f83-8396-5a46-a3bc-a467984eebc2")
FIRST_ANSWER = uuid.UUID("3b9f1e2d-6c7a-4d8b-9e0f-1a2b3c4d5e6f")
SECOND_ANSWER = uuid.UUID("4c0a2f3e-7d8b-4e9c-8f10-2b3c4d5e6f70")
KEPT_AT = datetime(2026, 11, 12, 8, 15, tzinfo=UTC)
LATER = datetime(2026, 11, 14, 9, 30, tzinfo=UTC)
MIGRATION = Path(__file__).resolve().parents[2] / "migrations" / "versions" / "0015_knowledge_pieces.py"
CURATED_MIGRATION = MIGRATION.with_name("0017_curated_dossiers.py")
LEARNING_MIGRATION = MIGRATION.with_name("0018_learning_block_kinds.py")
SIGNATURE_MIGRATION = MIGRATION.with_name("0025_signature_block_kinds.py")
FIELDS_MIGRATION = MIGRATION.with_name("0032_knowledge_fields.py")


def golden_block(block_id: str) -> Any:
    document = golden_json(DOCUMENT)
    found = next(b for s in document["sections"] for b in s["blocks"] if b["id"] == block_id)
    return BLOCKS.validate_python(found | {"reuse": None})


def piece(block_id: str, *, facet: str, answer: uuid.UUID = FIRST_ANSWER, **changes: Any) -> KnowledgePiece:
    slot = PieceSlot(
        CRAFT_ID, facet, changes.pop("topic", f"{FACET_NAMESPACES[facet]}:kutch-ajrakh"), "EXPERT"
    )
    built = knowledge_piece(
        golden_block(block_id),
        slot,
        piece_id=piece_id(answer, block_id),
        answer_id=answer,
        created_at=changes.pop("at", KEPT_AT),
    )
    return built.model_copy(update=changes) if changes else built


def states(*pieces: KnowledgePiece) -> dict[uuid.UUID, ClaimState]:
    found: dict[uuid.UUID, tuple[str, set[str]]] = {}
    for stored in pieces:
        for citation in stored.payload.citations():
            found.setdefault(uuid.UUID(citation.claim_id), (citation.level, set()))[1].add(citation.id)
    return {claim: ClaimState(level, frozenset(ids)) for claim, (level, ids) in found.items()}


def ask(facet: str = "PROCESS", depth: str = "EXPERT", topic: str = "process:kutch-ajrakh") -> ReuseAsk:
    return ReuseAsk(craft_id=CRAFT_ID, facet=facet, topic_key=topic, depth=depth)


def test_every_facet_has_one_known_topic_namespace() -> None:
    assert set(FACET_NAMESPACES) == set(DISCIPLINES)
    assert set(FACET_NAMESPACES.values()) <= set(TOPIC_NAMESPACES)


@pytest.mark.parametrize(
    ("facet", "subjects", "expected"),
    [
        ("CHEMISTRY", TopicSubjects("Kutch-Ajrakh"), "reaction:kutch-ajrakh"),
        ("CHEMISTRY", TopicSubjects("Kutch-Ajrakh", ("alum", "alizarin")), "reaction:alizarin+alum"),
        ("GEOGRAPHY", TopicSubjects("Kutch-Ajrakh", districts=(449,)), "water:lgd-449"),
        ("GEOGRAPHY", TopicSubjects("Kutch-Ajrakh", ("alum",), (449,)), "water:alum"),
        ("PROCESS", TopicSubjects("Kutch-Ajrakh", districts=(449,)), "process:kutch-ajrakh"),
        ("CLIMATE", TopicSubjects("Kutch-Ajrakh", districts=(449, 90)), "climate:lgd-449+lgd-90"),
    ],
)
def test_a_facet_topic_is_the_question_terms_else_the_place_else_the_craft(
    facet: str, subjects: TopicSubjects, expected: str
) -> None:
    assert facet_topic(facet, subjects) == expected


def test_a_place_topic_keys_districts_by_lgd_code_and_a_long_set_by_its_digest() -> None:
    many = tuple(range(30, 0, -1))
    digest = hashlib.sha256(",".join(str(n) for n in range(1, 31)).encode("ascii")).hexdigest()[:16]
    assert (
        facet_topic("CLIMATE", TopicSubjects("Kutch-Ajrakh", districts=many)) == f"climate:lgd-set-{digest}"
    )
    assert district_topic("water", (3, 1, 2)) == "water:lgd-1+lgd-2+lgd-3"
    assert region_topic("GEOGRAPHY", main_riv=None, district_lgds=many) == f"water:lgd-set-{digest}"
    assert region_topic("GEOGRAPHY", main_riv=41063203, district_lgds=many) == "water:basin-41063203"


def test_the_migration_rekeys_a_place_piece_named_by_districts_to_the_key_the_store_now_writes() -> None:
    rekeyed = migration("0083_piece_districts_and_places").rekeyed
    kachchh = [{"lgd": 449, "name": "Kachchh"}]
    both = [
        {"lgd": 449, "name": "Kachchh"},
        {"lgd": 467, "name": "Bilaspur"},
        {"lgd": 320, "name": "Bilaspur"},
    ]
    assert rekeyed("water:kachchh", kachchh) == facet_topic("GEOGRAPHY", TopicSubjects("x", districts=(449,)))
    assert rekeyed("soil:bilaspur+kachchh", both) == "soil:lgd-320+lgd-449+lgd-467"
    assert rekeyed("water:alum", kachchh) is None
    assert rekeyed("water:kachchh", []) is None
    named = [{"lgd": n, "name": f"District {n}"} for n in range(1, 31)]
    subjects = "+".join(sorted(f"district-{n}" for n in range(1, 31)))
    assert rekeyed(f"climate:{subjects}", named) == facet_topic(
        "CLIMATE", TopicSubjects("x", districts=tuple(range(1, 31)))
    )


def test_a_curated_place_piece_keeps_the_id_its_district_name_gave_it_while_its_key_moves_to_codes() -> None:
    assert piece_topic("GEOGRAPHY", "Kutch-Ajrakh", [449]) == "water:lgd-449"
    assert piece_id_topic("GEOGRAPHY", "Kutch-Ajrakh", [449]) == "water:kachchh"
    assert piece_id_topic("CLIMATE", "Kutch-Ajrakh", []) == "climate:kutch-ajrakh"
    assert piece_id_topic("PROCESS", "Kutch-Ajrakh", [449]) == "process:kutch-ajrakh"


def test_a_topic_longer_than_a_key_is_not_kept() -> None:
    terms = tuple(f"term-number-{n:02d}" for n in range(20))
    assert facet_topic("HISTORY", TopicSubjects("Kutch-Ajrakh", terms)) is None
    assert facet_topics(["HISTORY", "PROCESS"], TopicSubjects("Kutch-Ajrakh", terms)) == {}


def test_a_built_block_is_stored_as_a_piece_with_its_own_sentence_ids_and_hash() -> None:
    stored = piece("s3.b1", facet="CHEMISTRY")
    prefix = f"p{piece_id(FIRST_ANSWER, 's3.b1').hex[:12]}"
    original = golden_block("s3.b1")
    assert [s.id for s in stored.payload.sentences] == [
        f"{prefix}.{n}" for n in range(1, len(original.sentences) + 1)
    ]
    assert [s.text for s in stored.payload.sentences] == [s.text for s in original.sentences]
    assert stored.claim_ids == sorted({uuid.UUID(c.claim_id) for c in original.citations()})
    body = stored.payload.model_dump(mode="json", by_alias=True, exclude={"id", "reuse"})
    canonical = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    assert stored.content_hash == hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    assert (stored.payload.reuse, stored.language, stored.created_from_answer_id) == (
        None,
        "en",
        FIRST_ANSWER,
    )


def test_ladder_stage_sentences_are_numbered_through_the_piece() -> None:
    stored = piece("s1.b1", facet="PROCESS")
    ids = [s.id for stage in stored.payload.stages for s in stage.sentences]
    prefix = f"p{piece_id(FIRST_ANSWER, 's1.b1').hex[:12]}"
    assert ids == [f"{prefix}.{n}" for n in range(1, len(ids) + 1)]


def test_an_image_block_rests_on_no_citation_so_it_is_not_a_piece() -> None:
    assert not storable(golden_block("s1.b2"))
    assert storable(golden_block("s1.b1")) and storable(golden_block("s3.b1"))


def test_placing_a_piece_changes_only_its_id_and_reuse_mark() -> None:
    stored = piece("s3.b1", facet="CHEMISTRY")
    placed = placed_block(stored, "s2.b1")
    assert (placed.id, placed.reuse.piece_id, placed.reuse.stored_at) == ("s2.b1", stored.id, KEPT_AT)
    assert placed.model_dump(exclude={"id", "reuse"}) == stored.payload.model_dump(exclude={"id", "reuse"})


def test_the_golden_piece_placement_is_the_golden_reused_block() -> None:
    stored = KnowledgePiece.model_validate(golden_json(PIECE))
    document = golden_json(DOCUMENT)
    reused = next(b for s in document["sections"] for b in s["blocks"] if b["reuse"])
    assert placed_block(stored, reused["id"]).model_dump(mode="json", by_alias=True) == reused


def test_piece_text_is_the_sentences_read_in_order() -> None:
    block = golden_block("s3.b1")
    assert piece_text(block) == " ".join(s.text for s in block.sentences)


def test_a_claim_counts_as_visible_only_with_its_citations_and_level_unchanged() -> None:
    stored = piece("s3.b1", facet="CHEMISTRY")
    current = states(stored)
    claim, state = next(iter(current.items()))
    assert visible_as_cited(stored, current) == set(stored.claim_ids)
    fewer = current | {claim: ClaimState(state.level, frozenset())}
    other_level = "VERIFIED" if state.level != "VERIFIED" else "REVIEWED"
    raised = current | {claim: ClaimState(other_level, state.citation_ids)}
    gone = {key: value for key, value in current.items() if key != claim}
    for changed in (fewer, raised, gone):
        assert visible_as_cited(stored, changed) == set(stored.claim_ids) - {claim}


def test_a_section_is_reused_whole_ladder_first() -> None:
    prose = piece("s3.b1", facet="PROCESS")
    ladder = piece("s1.b1", facet="PROCESS")
    (group,) = reusable_groups([prose, ladder], ask(), states(prose, ladder))
    assert [p.kind for p in group] == ["process_ladder", "prose"]


def test_one_stale_piece_refuses_its_whole_section() -> None:
    prose = piece("s3.b1", facet="PROCESS", stale_since=LATER)
    ladder = piece("s1.b1", facet="PROCESS")
    assert reusable_groups([prose, ladder], ask(), states(prose, ladder)) == []


def test_a_basic_piece_is_not_reused_for_an_expert_ask_but_an_expert_one_serves_a_basic_ask() -> None:
    basic = piece("s3.b1", facet="CHEMISTRY", depth="BASIC")
    topic = "reaction:kutch-ajrakh"
    assert reusable_groups([basic], ask("CHEMISTRY", "EXPERT", topic), states(basic)) == []
    assert reusable_groups([basic], ask("CHEMISTRY", "BASIC", topic), states(basic)) == [(basic,)]
    expert = piece("s3.b1", facet="CHEMISTRY", answer=SECOND_ANSWER)
    assert reusable_groups([expert], ask("CHEMISTRY", "BASIC", topic), states(expert)) == [(expert,)]


def test_groups_keep_the_order_they_were_found_in_and_skip_other_facets_and_topics() -> None:
    newer = piece("s3.b1", facet="CHEMISTRY", answer=SECOND_ANSWER, at=LATER)
    older = piece("s3.b1", facet="CHEMISTRY")
    elsewhere = piece("s3.b1", facet="CHEMISTRY", answer=uuid.uuid4(), topic="reaction:alum")
    history = piece("s3.b1", facet="HISTORY", answer=uuid.uuid4())
    current = states(newer)
    groups = reusable_groups(
        [newer, older, elsewhere, history], ask("CHEMISTRY", topic="reaction:kutch-ajrakh"), current
    )
    assert groups == [(newer,), (older,)]


def load_migration(path: Path = MIGRATION) -> Any:
    spec = importlib.util.spec_from_file_location(f"migration_{path.stem}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_migration_checks_the_same_vocabulary_as_the_models() -> None:
    migration = load_migration()
    learning = load_migration(LEARNING_MIGRATION)
    signature = load_migration(SIGNATURE_MIGRATION)
    assert migration.BLOCK_KINDS == learning.BLOCK_KINDS_BEFORE
    assert learning.BLOCK_KINDS == signature.BLOCK_KINDS_BEFORE
    assert BLOCK_KINDS[: len(signature.BLOCK_KINDS)] == signature.BLOCK_KINDS
    fields = load_migration(FIELDS_MIGRATION)
    assert migration.DISCIPLINES == fields.DISCIPLINES_BEFORE
    assert fields.DISCIPLINES == DISCIPLINES
    assert migration.DEPTHS == EXPLAINER_DEPTHS
    assert HIDDEN_CLAIM_STATUSES[: len(migration.HIDDEN_CLAIM_STATUSES)] == migration.HIDDEN_CLAIM_STATUSES
    for column in ('"status"', '"evidenceLevel"', '"text"', '"sensitivity"'):
        assert f"NEW.{column} IS DISTINCT FROM OLD.{column}" in migration.STALE_ON_CHANGE


def test_the_latest_stale_trigger_hides_every_hidden_status() -> None:
    curated = load_migration(CURATED_MIGRATION)
    assert curated.HIDDEN_CLAIM_STATUSES == HIDDEN_CLAIM_STATUSES
    assert curated.HIDDEN_BEFORE == load_migration().HIDDEN_CLAIM_STATUSES
    trigger = curated._stale_on_change(curated.HIDDEN_CLAIM_STATUSES)
    for status in HIDDEN_CLAIM_STATUSES:
        assert f"'{status}'" in trigger
    for column in ('"status"', '"evidenceLevel"', '"text"', '"sensitivity"'):
        assert f"NEW.{column} IS DISTINCT FROM OLD.{column}" in trigger
