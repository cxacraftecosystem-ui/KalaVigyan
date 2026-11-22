from app.composer.expert_takes import SEAT_SYSTEM_PROMPT, SeatAsk, parsed_take
from app.research.composition import ComposeCandidate, ComposeFocus
from app.research.crafts import CraftRef
from app.research.expert_panel import EXPERT_PANEL
from app.research.gap_admissions import admits_gap
from app.services.expert_views import ExpertPanelBuilder
from app.services.gap_routing import routed_gaps

from .fixtures import FOUR_HUNDRED, build_ask, panel_model, said, take, tools

KHURJA = CraftRef(slug="Khurja-Pottery", name="Khurja Pottery", path="/crafts/Khurja-Pottery")
GLAZES = ComposeCandidate(
    id="d1000000-0000-4000-8000-000000000001",
    kind="CLAIM",
    text="Khurja pottery is known for its blue and turquoise glazes.",
    source_label="stored claim, provisional",
    level="PROVISIONAL",
)
GLAZES_QUOTE = "Khurja pottery is known for its blue and turquoise glazes"
KHURJA_GAP = (
    "Khurja potters glaze in blue and turquoise, but the stored statements do not name the oxides behind "
    "Khurja's blue and turquoise."
)
FOUR_HUNDRED_GAP = (
    "The technique came to Kutch from Sindh some 400 years ago, but the stored statements do not name the "
    "king who invited the printers."
)


def chemist_take(text: str) -> list[tuple[str, ...]]:
    ask = SeatAsk(
        question="What gives Khurja's glazes their blue and turquoise colours?",
        craft=KHURJA,
        focus=ComposeFocus(discipline="CHEMISTRY", title="The chemistry"),
        seat=EXPERT_PANEL["CHEMIST"],
        candidates=(GLAZES,),
    )
    reply = {"take": [{"text": text, "quotes": [{"source": GLAZES.id, "quote": GLAZES_QUOTE}]}]}
    return [sentence.problem_kinds for sentence in parsed_take(reply, ask).sentences]


def test_a_seat_s_gap_admission_from_the_khurja_answer_passes_its_grounding() -> None:
    assert admits_gap(KHURJA_GAP)
    assert chemist_take(KHURJA_GAP) == [()]


def test_a_seat_sentence_that_turns_its_statement_negative_still_fails() -> None:
    assert chemist_take("Khurja pottery is not known for its blue and turquoise glazes.") == [
        ("NEGATION_CHANGED",)
    ]


def test_a_negation_beside_the_admission_still_fails() -> None:
    flipped = (
        "Khurja pottery is never glazed in blue and turquoise, and the stored statements do not name it."
    )
    assert chemist_take(flipped) == [("NEGATION_CHANGED",)]


def test_the_seats_are_told_a_gap_is_an_open_question_and_never_their_view() -> None:
    assert "A gap is an open question, never part of the view" in SEAT_SYSTEM_PROMPT


async def test_a_seat_s_gap_goes_to_the_open_questions_and_its_view_keeps_what_it_states() -> None:
    gap = said(FOUR_HUNDRED, FOUR_HUNDRED_GAP, FOUR_HUNDRED.text.rstrip("."))
    model = panel_model([take("HISTORIAN", said(FOUR_HUNDRED), gap)])
    found = await ExpertPanelBuilder(tools(model)).build(build_ask(("HISTORIAN",)))
    (view,) = found.blocks
    assert [sentence.text for sentence in view.cited_sentences()] == [FOUR_HUNDRED.text, FOUR_HUNDRED_GAP]
    routed = routed_gaps([view])
    (kept,) = routed.blocks
    assert [sentence.text for sentence in kept.cited_sentences()] == [FOUR_HUNDRED.text]
    assert [question["text"] for question in routed.gaps] == [FOUR_HUNDRED_GAP]
    assert [citation["claimId"] for citation in routed.gaps[0]["citations"]] == [str(FOUR_HUNDRED.id)]
