import uuid

import pytest

from app.data.places_abroad import parse_places_abroad
from app.research.composition import ComposeCandidate, ComposeRequest
from app.research.coverage_eval import answer_measures, rubric_score
from app.research.crafts import CraftRef
from app.research.explainer import Explainer
from app.research.research_summary import ResearchSummary
from app.services.craft_index import AliasRecord, CraftRecord, build_index
from app.services.off_question import off_question_sentences, off_question_topics, screened_request
from app.services.write_back_names import CraftNames, craft_names

from ..contracts.explainer_golden import DOCUMENT
from ..contracts.golden import golden_json
from ..research.fixtures import AJRAKH, BAGRU


def ref(slug: str, name: str) -> CraftRef:
    return CraftRef(slug=slug, name=name, path=f"/crafts/{slug}")


KHURJA = ref("Khurja-Pottery", "Khurja Pottery")
BLUE_POTTERY = ref("Blue-Pottery-Of-Jaipur", "Blue Pottery of Jaipur")
PLACES = {KHURJA.slug: ("Uttar Pradesh", "Bulandshahr", "Khurja"), BLUE_POTTERY.slug: ("Rajasthan", "Jaipur")}
ALIASES = {BLUE_POTTERY.slug: ("Jaipur Blue Pottery", "Blue Pottery")}
ABROAD = parse_places_abroad(
    {"schemaVersion": 1, "countries": {"Nigeria": ["Nigerian"], "Taiwan": ["Taiwanese"]}}
)
CLAIM = "d2000000-0000-4000-8000-000000000001"
KHURJA_PAGE = "searxng:https://crafts.example.org/khurja-glazes"
JAIPUR_PAGE = "searxng:https://crafts.example.org/jaipur-blue-pottery"
NIGERIA_PAPER = "openalex:W2001"
KILN_PAGE = "searxng:https://kilns.example.com/schedules"


def craft_id(slug: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"test-off-question/{slug}")


def names(lead: CraftRef, compared: tuple[CraftRef, ...] = ()) -> CraftNames:
    index = build_index(
        [
            CraftRecord(craft_id(c.slug), c.slug, c.name, "ACTIVE", places=PLACES[c.slug])
            for c in (KHURJA, BLUE_POTTERY)
        ],
        [AliasRecord(craft_id(slug), alias) for slug, aliases in ALIASES.items() for alias in aliases],
        [],
    )
    return craft_names(index, lead, compared, abroad=ABROAD)


def candidate(ref_id: str, text: str) -> ComposeCandidate:
    kind = "CLAIM" if ":" not in ref_id else "EVIDENCE"
    return ComposeCandidate(id=ref_id, kind=kind, text=text, source_label="a source", level="PROVISIONAL")


def request(*candidates: ComposeCandidate) -> ComposeRequest:
    summary = ResearchSummary(
        craft=KHURJA,
        mode="DEEP",
        stored_claims=0,
        stored_passages=0,
        evidence_found=0,
        documents_read=0,
        failures=0,
    )
    return ComposeRequest(
        question="What gives Khurja's glazes their blue and turquoise colours?",
        craft=KHURJA,
        candidates=list(candidates),
        searched=summary,
    )


KHURJA_ANSWER = request(
    candidate(CLAIM, "Blue Pottery of Jaipur uses a quartz body rather than clay."),
    candidate(KHURJA_PAGE, "Khurja potters fire their blue and turquoise glazes in coal kilns."),
    candidate(JAIPUR_PAGE, "Jaipur Blue Pottery takes its blue from cobalt oxide."),
    candidate(NIGERIA_PAPER, "Nigerian porcelain bodies were fired at 1250 degrees."),
    candidate(KILN_PAGE, "A glaze firing schedule ramps slowly through 573 degrees."),
)


def test_the_khurja_answer_s_passages_about_jaipur_and_nigeria_are_off_question() -> None:
    lead = names(KHURJA)
    assert off_question_topics(["Jaipur Blue Pottery takes its blue from cobalt oxide."], lead) == (
        "Blue Pottery of Jaipur",
    )
    assert off_question_topics(["Nigerian porcelain bodies were fired at 1250 degrees."], lead) == (
        "Nigerian",
    )
    assert off_question_topics(["Khurja potters fire their glazes in coal kilns."], lead) == ()
    assert off_question_topics(["A glaze firing schedule ramps slowly through 573 degrees."], lead) == ()


def test_an_answer_about_one_craft_is_offered_no_passage_about_another_craft_or_a_place_abroad() -> None:
    screened = screened_request(KHURJA_ANSWER, names(KHURJA), comparison=False)
    assert [c.id for c in screened.candidates] == [CLAIM, KHURJA_PAGE, KILN_PAGE]


def test_a_comparison_keeps_such_a_passage_labelled_for_comparison_only() -> None:
    screened = screened_request(KHURJA_ANSWER, names(KHURJA), comparison=True)
    labels = {c.id: c.source_label for c in screened.candidates}
    assert set(labels) == {CLAIM, KHURJA_PAGE, JAIPUR_PAGE, NIGERIA_PAPER, KILN_PAGE}
    assert labels[JAIPUR_PAGE] == (
        "about Blue Pottery of Jaipur, not the craft asked about: cite only to compare; a source"
    )
    assert labels[KHURJA_PAGE] == "a source"


def test_a_compared_craft_s_passage_is_on_question() -> None:
    screened = screened_request(KHURJA_ANSWER, names(KHURJA, (BLUE_POTTERY,)), comparison=True)
    labels = {c.id: c.source_label for c in screened.candidates}
    assert labels[JAIPUR_PAGE] == "a source"


def test_without_the_craft_names_every_candidate_is_offered() -> None:
    assert screened_request(KHURJA_ANSWER, None, comparison=False) is KHURJA_ANSWER


def ajrakh_names() -> CraftNames:
    crafts = {AJRAKH.slug: (AJRAKH, ("Gujarat", "Kachchh")), BAGRU.slug: (BAGRU, ("Rajasthan",))}
    index = build_index(
        [CraftRecord(craft_id(s), c.slug, c.name, "ACTIVE", places=p) for s, (c, p) in crafts.items()],
        [AliasRecord(craft_id(AJRAKH.slug), "Ajrakh"), AliasRecord(craft_id(BAGRU.slug), "Bagru")],
        [],
    )
    return craft_names(index, AJRAKH, (), abroad=ABROAD)


def golden_with_quote(quote: str) -> Explainer:
    document = golden_json(DOCUMENT)
    (prose,) = next(section for section in document["sections"] if section["id"] == "s2")["blocks"]
    for citation in prose["sentences"][0]["citations"]:
        citation["quote"] = quote
    return Explainer.model_validate(document)


def test_the_evaluation_counts_shown_sentences_resting_on_a_passage_about_another_craft() -> None:
    names_of_ajrakh = ajrakh_names()
    assert off_question_sentences(Explainer.model_validate(golden_json(DOCUMENT)), names_of_ajrakh) == 0
    shifted = golden_with_quote("Bagru printers in Rajasthan dye their cloth with indigo")
    assert off_question_sentences(shifted, names_of_ajrakh) == 1


def test_an_off_question_citation_costs_the_rubric_its_every_cited_part() -> None:
    explainer = golden_with_quote("Bagru printers dye with indigo")
    measures = answer_measures(explainer, ["GEOGRAPHY"], off_question=1)
    assert measures.off_question == 1
    clean = measures.model_copy(update={"off_question": 0})
    assert rubric_score(clean) - rubric_score(measures) == pytest.approx(1 / 5)
