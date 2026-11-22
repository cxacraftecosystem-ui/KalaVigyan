from typing import Any

from app.research.blocks import ProseBlock
from app.research.citations import SourceRef
from app.research.explainer import Explainer
from app.services.field_voices_readback import (
    WITHDRAWN_SEARCHED,
    Withdrawn,
    portal_field_source,
    without_withdrawn,
)
from app.services.public_explainer import ClosedCitations, citation_key
from tests.contracts.golden import golden_json

GI = "d0f53ee9-4b97-5df7-a367-686957bdb7c8"
MUSEUM = "f0dde764-b68a-5ea6-8d1c-05ca4a7db2b7"
SECOND_MUSEUM = "84cc8e03-ef75-55a3-9fb6-ca8b8e872a93"
INTERVIEW = "907e2c52-14e7-5e41-9b27-9c10f70906a9"
GALLERY = "4ce205e3-653f-51db-9e49-14fb3b3f2e14"


def explainer(*interviews: str) -> Explainer:
    document = golden_json("explainer.document.golden.json")
    for source in document["sources"]:
        if source["id"] in interviews:
            source.update(kind="FIELD_TESTIMONY", publisher="Field Repository", authors=["Asha Demo"])
    return Explainer.model_validate(document)


def sentence_ids(shown: Explainer, section: str) -> list[str]:
    blocks = next(s for s in shown.sections if s.id == section).blocks
    return [sentence.id for block in blocks for sentence in getattr(block, "sentences", [])]


def first_citation(shown: Explainer, sentence: str) -> tuple[str, str]:
    for section in shown.sections:
        for block in section.blocks:
            for each in getattr(block, "sentences", []):
                if each.id == sentence:
                    return each.citations[0].claim_id, each.citations[0].source_id
    raise AssertionError(sentence)


def source_ids(shown: Explainer) -> list[str]:
    return [source.id for source in shown.sources]


def test_nothing_withdrawn_leaves_the_explainer_as_stored() -> None:
    stored = explainer(INTERVIEW)
    assert without_withdrawn(stored, Withdrawn()) is stored


def test_only_portal_interviews_are_checked_against_the_portals() -> None:
    stored = explainer(INTERVIEW)
    kinds: dict[str, Any] = {source.id: portal_field_source(source) for source in stored.sources}
    assert kinds == {GI: False, MUSEUM: False, SECOND_MUSEUM: False, INTERVIEW: True, GALLERY: False}
    testimony = SourceRef.model_validate(
        stored.sources[3].model_dump(mode="json", by_alias=True) | {"publisher": "KalaVigyan"}
    )
    assert not portal_field_source(testimony)


def test_a_withdrawn_interview_takes_its_sentences_and_its_source_out() -> None:
    shown = without_withdrawn(explainer(INTERVIEW), Withdrawn(sources=frozenset({INTERVIEW})))
    assert shown is not None
    assert sentence_ids(shown, "s2") == ["s2.b1.1", "s2.b1.2"]
    assert source_ids(shown) == [GI, MUSEUM, SECOND_MUSEUM, GALLERY]
    assert "Asha Demo" not in shown.model_dump_json()


def test_a_withdrawn_quote_takes_out_only_the_sentence_that_cited_it() -> None:
    stored = explainer(GI)
    cited = first_citation(stored, "s2.b1.1")
    shown = without_withdrawn(stored, Withdrawn(citations=frozenset({cited})))
    assert shown is not None
    assert sentence_ids(shown, "s2") == ["s2.b1.2", "s2.b1.3"]
    assert sentence_ids(shown, "s3") == ["s3.b1.1", "s3.b1.2", "s3.b1.3"]


def test_a_section_left_with_nothing_says_an_interview_is_no_longer_shown() -> None:
    shown = without_withdrawn(explainer(MUSEUM), Withdrawn(sources=frozenset({MUSEUM})))
    assert shown is not None
    first = shown.sections[0]
    assert (first.state, first.blocks, first.searched) == ("EMPTY", [], WITHDRAWN_SEARCHED)
    assert source_ids(shown) == [GI, INTERVIEW, GALLERY]


def test_an_explainer_resting_only_on_withdrawn_interviews_is_not_shown() -> None:
    withdrawn = Withdrawn(sources=frozenset({GI, INTERVIEW, GALLERY}))
    assert without_withdrawn(explainer(GI, INTERVIEW, GALLERY), withdrawn) is None


def withdrawn_counts(shown: Explainer) -> dict[str, int]:
    return {section.id: section.withdrawn for section in shown.sections}


def test_a_section_keeping_other_sentences_counts_the_one_a_withdrawn_interview_took_out() -> None:
    shown = without_withdrawn(explainer(INTERVIEW), Withdrawn(sources=frozenset({INTERVIEW})))
    assert shown is not None
    assert withdrawn_counts(shown) == {"s1": 0, "s2": 1, "s3": 0}
    sections = shown.model_dump(mode="json", by_alias=True)["sections"]
    assert [section.get("withdrawn") for section in sections] == [None, 1, None]


def test_a_withdrawn_quote_counts_only_in_the_section_that_cited_it() -> None:
    stored = explainer(GI)
    shown = without_withdrawn(stored, Withdrawn(citations=frozenset({first_citation(stored, "s2.b1.1")})))
    assert shown is not None
    assert withdrawn_counts(shown) == {"s1": 0, "s2": 1, "s3": 0}


def test_a_section_emptied_by_a_withdrawal_says_so_instead_of_counting() -> None:
    shown = without_withdrawn(explainer(MUSEUM), Withdrawn(sources=frozenset({MUSEUM})))
    assert shown is not None
    assert (shown.sections[0].state, shown.sections[0].withdrawn) == ("EMPTY", 0)


def test_a_count_already_on_a_section_is_kept_when_more_is_taken_out() -> None:
    stored = explainer(INTERVIEW)
    counted = stored.model_copy(
        update={
            "sections": [
                stored.sections[0],
                stored.sections[1].model_copy(update={"withdrawn": 2}),
                stored.sections[2],
            ]
        }
    )
    shown = without_withdrawn(counted, Withdrawn(sources=frozenset({INTERVIEW})))
    assert shown is not None
    assert withdrawn_counts(shown)["s2"] == 3


def test_a_sentence_closed_to_a_public_reader_is_taken_out_without_a_withdrawn_count() -> None:
    stored = explainer(GI)
    (prose,) = stored.sections[1].blocks
    sentence = next(each for each in prose.cited_sentences() if each.id == "s2.b1.1")
    shown = without_withdrawn(
        stored, ClosedCitations(closed=frozenset({citation_key(sentence.citations[0])}))
    )
    assert shown is not None
    assert sentence_ids(shown, "s2") == ["s2.b1.2", "s2.b1.3"]
    assert withdrawn_counts(shown) == {"s1": 0, "s2": 0, "s3": 0}


def test_the_withdrawn_golden_is_the_document_with_a_withdrawn_count_and_a_named_difference() -> None:
    golden = golden_json("explainer.withdrawn.golden.json")
    third = Explainer.model_validate(golden).sections[2]
    (prose,) = third.blocks
    assert isinstance(prose, ProseBlock)
    flagged = prose.sentences[2]
    assert (third.id, third.withdrawn) == ("s3", 1)
    assert (flagged.id, flagged.sources_differ, flagged.differs_on) == (
        "s3.b1.3",
        True,
        "where the alum paste is printed",
    )
    shown = golden["sections"][2]
    assert shown.pop("withdrawn") == 1
    assert shown["blocks"][0]["sentences"][2].pop("sourcesDiffer") is True
    assert shown["blocks"][0]["sentences"][2].pop("differsOn") == "where the alum paste is printed"
    assert golden == golden_json("explainer.document.golden.json")
