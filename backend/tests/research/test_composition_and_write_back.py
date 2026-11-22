import hashlib
import uuid
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.core.errors import InvalidInput
from app.research.composition import (
    ComposeCandidate,
    ComposedAnswer,
    ComposedSentence,
    ComposeRequest,
    QuotedSpan,
    sentence_level,
    sentence_violations,
)
from app.research.evidence import Quote
from app.research.research_summary import ResearchSummary, SearchedQuery, not_enough_evidence_message
from app.research.write_back import ClaimWriteBack

from .fixtures import AJRAKH, ALUM_QUOTE, BAGRU, evidence_item

CLAIM_ID = uuid.UUID("9f1d2c3b-4a5e-4f60-8b71-2c3d4e5f6a70")
CLAIM = ComposeCandidate(
    id=str(CLAIM_ID),
    kind="CLAIM",
    text="Alum binds alizarin to cotton as a red lake.",
    quotes=["alum forms a red lake with alizarin at about 60 °C"],
    sourceLabel="Author 2019",
    level="PROVISIONAL",
)
LIVE = ComposeCandidate(
    id="openalex:W77",
    kind="EVIDENCE",
    text="indigo is reduced to leuco-indigo at pH 11",
    sourceLabel="Author 2021",
    level="HYPOTHESIS",
)
ALLOWED = {CLAIM.id: CLAIM, LIVE.id: LIVE}
SEARCHED = ResearchSummary(
    craft=AJRAKH,
    mode="VERIFIED",
    storedClaims=0,
    storedPassages=0,
    evidenceFound=0,
    documentsRead=0,
    failures=0,
)


def kinds(sentence: ComposedSentence) -> list[tuple[str, str]]:
    return [(v.kind, v.detail) for v in sentence_violations(sentence, ALLOWED)]


def test_a_cited_sentence_with_quoted_figures_passes() -> None:
    sentence = ComposedSentence(
        text="Alum fixes alizarin as a red lake at about 60 °C, and indigo is reduced at pH 11.",
        claimIds=[CLAIM_ID],
        evidenceIds=[LIVE.id],
        spans=[
            QuotedSpan(ref=str(CLAIM_ID), text="a red lake with alizarin at about 60 °C"),
            QuotedSpan(ref=LIVE.id, text="reduced to leuco-indigo at pH 11"),
        ],
    )
    assert kinds(sentence) == []
    assert sentence_level(sentence, ALLOWED) == "HYPOTHESIS"


def test_each_post_check_names_what_failed() -> None:
    quoted = QuotedSpan(ref=str(CLAIM_ID), text="a red lake with alizarin")
    assert kinds(ComposedSentence(text="Alum fixes the dye.")) == [("UNCITED", "the sentence cites nothing")]
    assert kinds(ComposedSentence(text="Alum works.", claimIds=[CLAIM_ID])) == [
        ("UNQUOTED", "the sentence quotes no source")
    ]
    hot = "A red lake forms with alizarin at 70 °C."
    assert kinds(ComposedSentence(text=hot, claimIds=[CLAIM_ID], spans=[quoted])) == [
        ("UNSUPPORTED_FIGURE", "70")
    ]
    lake = "Alizarin makes a red lake."
    assert kinds(
        ComposedSentence(text=lake, claimIds=[CLAIM_ID], evidenceIds=["openalex:W1"], spans=[quoted])
    ) == [("UNKNOWN_ID", "openalex:W1")]
    outside = QuotedSpan(ref=LIVE.id, text="indigo is reduced to leuco-indigo")
    assert kinds(ComposedSentence(text=lake, claimIds=[CLAIM_ID], spans=[quoted, outside])) == [
        ("SPAN_NOT_CITED", LIVE.id)
    ]
    invented = QuotedSpan(ref=str(CLAIM_ID), text="alum is a red dye of cotton")
    assert kinds(ComposedSentence(text="Alum works.", claimIds=[CLAIM_ID], spans=[invented])) == [
        ("SPAN_NOT_IN_SOURCE", str(CLAIM_ID))
    ]


def test_a_quote_of_a_word_or_two_is_refused() -> None:
    for trivial in ("a", "the", "alum"):
        with pytest.raises(ValidationError):
            QuotedSpan(ref=str(CLAIM_ID), text=trivial)
    padded = QuotedSpan(ref=str(CLAIM_ID), text="a" + chr(0x00AD) * 30)
    sentence = ComposedSentence(text="Arsenic is the mordant.", claimIds=[CLAIM_ID], spans=[padded])
    assert kinds(sentence) == [("TRIVIAL_QUOTE", str(CLAIM_ID))]


def test_a_real_quote_that_does_not_carry_the_sentence_is_refused() -> None:
    lake = QuotedSpan(ref=str(CLAIM_ID), text="alum forms a red lake with alizarin")
    sentence = ComposedSentence(text="Arsenic is the mordant.", claimIds=[CLAIM_ID], spans=[lake])
    assert kinds(sentence) == [("UNRELATED_QUOTE", "the quotes do not carry its wording")]


def test_a_quote_ending_inside_a_larger_number_supports_no_figure() -> None:
    kiln = ComposeCandidate(
        id="openalex:W88",
        kind="EVIDENCE",
        text="The kiln reaches 1500 degrees during the firing.",
        sourceLabel="Author 2022",
        level="HYPOTHESIS",
    )
    clipped = QuotedSpan(ref=kiln.id, text="The kiln reaches 150")
    sentence = ComposedSentence(text="The kiln reaches 150 degrees.", evidenceIds=[kiln.id], spans=[clipped])
    found = [(v.kind, v.detail) for v in sentence_violations(sentence, {kiln.id: kiln})]
    assert found == [("UNSUPPORTED_FIGURE", "150"), ("SPAN_NOT_IN_SOURCE", kiln.id)]


def test_a_figure_must_be_in_a_quoted_span_not_only_somewhere_in_the_source() -> None:
    elsewhere = QuotedSpan(ref=str(CLAIM_ID), text="Alum binds alizarin to cotton")
    sentence = ComposedSentence(text="Alum binds alizarin at 60 °C.", claimIds=[CLAIM_ID], spans=[elsewhere])
    assert kinds(sentence) == [("UNSUPPORTED_FIGURE", "60")]


def test_a_failed_span_supports_no_figure() -> None:
    invented = QuotedSpan(ref=str(CLAIM_ID), text="it is heated to 60 °C")
    sentence = ComposedSentence(text="Alum is heated to 60 °C.", claimIds=[CLAIM_ID], spans=[invented])
    assert kinds(sentence) == [("UNSUPPORTED_FIGURE", "60"), ("SPAN_NOT_IN_SOURCE", str(CLAIM_ID))]


def test_a_sentence_level_needs_known_ids() -> None:
    with pytest.raises(InvalidInput):
        sentence_level(ComposedSentence(text="Alum works.", evidenceIds=["openalex:W1"]), ALLOWED)


def test_compose_candidates_are_claims_or_quoted_evidence() -> None:
    with pytest.raises(ValidationError):
        ComposeCandidate(id="claim-1", kind="CLAIM", text="x", sourceLabel="s", level="PROVISIONAL")
    with pytest.raises(ValidationError):
        ComposeCandidate(id="W1", kind="EVIDENCE", text="q", sourceLabel="s", level="PROVISIONAL")
    several = ComposeCandidate(
        id="openalex:W1",
        kind="EVIDENCE",
        text="q one",
        quotes=["q two"],
        sourceLabel="s",
        level="PROVISIONAL",
    )
    assert several.cited_texts == ["q one", "q two"]
    with pytest.raises(ValidationError):
        ComposeRequest(question="Why alum?", craft=AJRAKH, candidates=[CLAIM, CLAIM], searched=SEARCHED)
    with pytest.raises(ValidationError):
        ComposeRequest(question="Why alum?", craft=BAGRU, candidates=[CLAIM], searched=SEARCHED)
    request = ComposeRequest(question="Why alum?", craft=AJRAKH, candidates=[CLAIM, LIVE], searched=SEARCHED)
    assert set(request.allowed) == {str(CLAIM_ID), "openalex:W77"}
    assert ComposeRequest(question="Why alum?", craft=AJRAKH, searched=SEARCHED).candidates == []


def test_an_answer_has_sentences_or_says_what_was_searched() -> None:
    sentence = ComposedSentence(
        text="Alum works.",
        claimIds=[CLAIM_ID],
        spans=[QuotedSpan(ref=str(CLAIM_ID), text="Alum binds alizarin to cotton")],
    )
    with pytest.raises(ValidationError):
        ComposedAnswer()
    with pytest.raises(ValidationError):
        ComposedAnswer(openQuestions=[sentence], notEnoughEvidence=SEARCHED)
    assert ComposedAnswer(notEnoughEvidence=SEARCHED).model_dump()["notEnoughEvidence"]["storedClaims"] == 0


def test_the_not_enough_evidence_message_lists_what_was_searched() -> None:
    searched = SEARCHED.model_copy(
        update={
            "stored_claims": 1,
            "queries": (
                SearchedQuery(tier="T3", text="Kutch Ajrakh alum mordant"),
                SearchedQuery(tier="T4", text="Kutch Ajrakh alizarin lake"),
            ),
            "services": ("crossref", "openalex", "web"),
            "evidence_found": 4,
            "documents_read": 1,
            "failures": 1,
        }
    )
    assert not_enough_evidence_message(searched) == (
        "There is not enough cited evidence to answer this about Kutch Ajrakh yet. "
        "Searched 1 stored claim and 0 stored source passages. "
        'Live research ran 2 queries: T3 "Kutch Ajrakh alum mordant"; T4 "Kutch Ajrakh alizarin lake". '
        "Sources searched: crossref, openalex, web. "
        "Found 4 items, read 1 document and recorded 1 failed request."
    )
    assert not_enough_evidence_message(SEARCHED) == (
        "There is not enough cited evidence to answer this about Kutch Ajrakh yet. "
        "Searched 0 stored claims and 0 stored source passages. "
        "No live research ran. "
        "Found 0 items, read 0 documents and recorded 0 failed requests."
    )


def write_back(**changes: object) -> ClaimWriteBack:
    fields: dict[str, object] = {
        "craftSlug": "Kutch-Ajrakh",
        "subject": {"conceptType": "MECHANISM", "conceptName": "Alum  Mordanting"},
        "predicate": "explains",
        "text": "Alum binds alizarin at about 60 °C.",
        "label": "QUOTED",
        "levelReason": "quote matched the abstract",
        "citations": [
            {"evidence": evidence_item(), "quote": ALUM_QUOTE, "quoteCheck": "PASS", "relation": "DIRECT"}
        ],
        "foundBy": "ANSWER",
        "answerId": uuid.UUID("0a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d"),
    }
    fields.update(changes)
    return ClaimWriteBack.model_validate(fields)


def test_a_quoted_write_back_is_stored_provisional() -> None:
    claim = write_back()
    assert claim.evidence_level == "PROVISIONAL"
    dumped = claim.model_dump(mode="json")
    assert dumped["schemaVersion"] == 1
    assert {"craftSlug", "foundBy", "answerId", "levelReason", "valueNum"} <= set(dumped)
    assert dumped["citations"][0]["quoteCheck"] == "PASS"


def test_a_write_back_has_one_owner_and_a_held_one_names_its_craft() -> None:
    family = write_back(craftSlug=None, categorySlug="Textiles-Based-Craft-Category")
    parts = [
        "claim-write-back/v2",
        "category:Textiles-Based-Craft-Category",
        "CHEMISTRY",
        "alum binds alizarin at about 60 °c",
    ]
    assert family.dedupe_key == hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()
    assert family.dedupe_key != write_back(craftSlug=None).dedupe_key
    with pytest.raises(ValidationError, match="not both"):
        write_back(categorySlug="Textiles-Based-Craft-Category")
    with pytest.raises(ValidationError, match="names the craft"):
        write_back(craftSlug=None, heldBecause="names no craft")
    assert write_back(heldBecause="names no craft").dedupe_key == write_back().dedupe_key


def test_an_inferred_write_back_is_a_hypothesis_without_unquoted_figures() -> None:
    unquoted = [{"evidence": evidence_item(), "quote": None, "quoteCheck": "NA", "relation": "ANALOGOUS"}]
    claim = write_back(label="INFERRED", text="Alum may also brighten the red.", citations=unquoted)
    assert claim.evidence_level == "HYPOTHESIS"
    with pytest.raises(ValidationError):
        write_back(label="INFERRED", text="Alum works best at 60 °C.", citations=unquoted)


def test_write_backs_refuse_broken_evidence() -> None:
    other_quote = Quote(text="iron darkens the black", locator="p. 3")
    for changes in [
        {
            "citations": [
                {"evidence": evidence_item(), "quote": ALUM_QUOTE, "quoteCheck": "FAIL", "relation": "DIRECT"}
            ]
        },
        {
            "citations": [
                {"evidence": evidence_item(), "quote": None, "quoteCheck": "PASS", "relation": "DIRECT"}
            ]
        },
        {
            "citations": [
                {
                    "evidence": evidence_item(),
                    "quote": other_quote,
                    "quoteCheck": "PASS",
                    "relation": "DIRECT",
                }
            ]
        },
        {"citations": []},
        {"text": "Alum binds alizarin at about 70 °C."},
        {"foundBy": "BACKGROUND"},
        {"answerId": None},
        {"valueNum": Decimal("65")},
        {"valueUnit": "degC"},
    ]:
        with pytest.raises(ValidationError):
            write_back(**changes)
    assert write_back(valueNum=Decimal("60.0"), valueUnit="degC").value_num == Decimal("60.0")
    assert write_back(foundBy="BACKGROUND", answerId=None).answer_id is None


def test_the_dedupe_key_ignores_case_spacing_and_the_final_stop() -> None:
    canonical = "\x1f".join(
        ["claim-write-back/v2", "Kutch-Ajrakh", "CHEMISTRY", "alum binds alizarin at about 60 °c"]
    )
    expected = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    assert write_back().dedupe_key == expected
    assert write_back(text="ALUM binds  alizarin at about 60 °C").dedupe_key == expected
    assert write_back(craftSlug="Bagru-Print").dedupe_key != expected


def test_the_dedupe_key_is_the_craft_field_and_text_never_the_model_s_target() -> None:
    rejected = "Ajrakh is washed in camel dung"
    first = write_back(
        text=rejected,
        subject={"conceptType": "PROCESS_STAGE", "conceptName": "Ajrakh washing"},
        label="INFERRED",
    )
    again = write_back(
        text=f"{rejected}.",
        subject={"conceptType": "SENSORY_CUE", "conceptName": "washing"},
        label="INFERRED",
    )
    canonical = "\x1f".join(
        ["claim-write-back/v2", "Kutch-Ajrakh", "PROCESS", "ajrakh is washed in camel dung"]
    )
    assert first.dedupe_key == again.dedupe_key == hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    assert write_back(text=rejected, field="HISTORY", label="INFERRED").dedupe_key != first.dedupe_key


def test_a_section_s_field_outranks_the_concept_type_s_field() -> None:
    assert write_back().stored_field == "CHEMISTRY"
    assert write_back(field="MATERIALS").stored_field == "MATERIALS"
    assert write_back(subject={"conceptType": "OUTCOME", "conceptName": "red"}).stored_field is None


@pytest.mark.parametrize(
    "text",
    ["Write to dyer@example.org for alum at about 60 °C.", "Call 98765 43210 for alum at about 60 °C."],
)
def test_a_write_back_never_carries_personal_data(text: str) -> None:
    with pytest.raises(ValidationError, match="personal data"):
        write_back(text=text)
