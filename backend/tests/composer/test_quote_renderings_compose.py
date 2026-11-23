import pytest

from app.composer.candidates import research_summary
from app.composer.composer import ModelComposer
from app.composer.drafts import DraftAnswer, DraftSection, DraftSentence
from app.composer.quote_checks import RENDERED_QUOTES_MAX, foreign_quotes, quote_language
from app.research.composition import ComposeCandidate, ComposedSentence, ComposeRequest, QuotedSpan
from app.research.translation import TranslationRequest

from ..planner.fakes import FakeModel
from .fixtures import QUESTION, answer, pack, quote, sentence

HINDI_PAGE = "wikipedia:hi:4242"
HINDI_QUOTE = "फिटकरी लाल रंग को सूती कपड़े पर पक्का करती है"
HINDI_PASSAGE = f"अजरख की छपाई में {HINDI_QUOTE}। रंगाई के बाद कपड़ा धोया जाता है।"
RENDERED = "Alum fixes the red colour on cotton cloth"
STATED = "Alum fixes the red colour on cotton cloth in Ajrakh."


class Translator:
    def __init__(self, rendered: str = RENDERED) -> None:
        self.rendered = rendered
        self.asked: list[list[str]] = []

    async def translate(self, request: TranslationRequest) -> dict[str, str]:
        self.asked.append([item.text for item in request.items])
        return {item.key: self.rendered for item in request.items}


def hindi_request() -> ComposeRequest:
    found = pack()
    page = ComposeCandidate(
        id=HINDI_PAGE,
        kind="EVIDENCE",
        text=HINDI_PASSAGE,
        source_label="Hindi Wikipedia",
        level="PROVISIONAL",
    )
    return ComposeRequest(
        question=QUESTION, craft=found.plan.craft, candidates=[page], searched=research_summary(found)
    )


async def test_a_sentence_resting_only_on_a_hindi_passage_is_kept_by_its_rendering() -> None:
    model = FakeModel([answer(("Alum", [sentence(STATED, quote(HINDI_PAGE, HINDI_QUOTE))]))])
    translator = Translator()
    composed = await ModelComposer(model=model, translator=translator).compose(hindi_request())
    (section,) = composed.sections
    (kept,) = section.sentences
    assert (kept.text, kept.evidence_ids) == (STATED, [HINDI_PAGE])
    assert [span.text for span in kept.spans] == [HINDI_QUOTE]
    assert (len(model.calls), translator.asked) == (1, [[HINDI_QUOTE]])
    assert composed.renderings == {HINDI_QUOTE: RENDERED}
    assert "renderings" not in composed.model_dump(mode="json", by_alias=True)


async def test_a_rendering_that_does_not_carry_the_sentence_keeps_it_failing() -> None:
    model = FakeModel(
        [answer(("Alum", [sentence(STATED, quote(HINDI_PAGE, HINDI_QUOTE))])), '{"sentences": []}']
    )
    translator = Translator("The cloth is washed in the river")
    composed = await ModelComposer(model=model, translator=translator).compose(hindi_request())
    assert composed.sections == [] and composed.not_enough_evidence is not None
    assert (len(model.calls), len(translator.asked)) == (2, 1)


@pytest.mark.parametrize(
    ("ref", "text", "language"),
    [
        (HINDI_PAGE, HINDI_QUOTE, "hi"),
        ("wikipedia:mr:12", "तुरटी लाल रंग पक्का करते", "mr"),
        ("stored_passages:5f0c", HINDI_QUOTE, None),
        ("searxng:https://example.org", "ફટકડી લાલ રંગ પાકો કરે છે", "gu"),
        ("crossref:10.1000/lake", "Alum binds alizarin to cotton", None),
    ],
)
def test_a_quote_s_language_is_its_script_s_or_the_edition_its_source_names(
    ref: str, text: str, language: str | None
) -> None:
    assert quote_language(ref, text) == language


def test_one_draft_renders_at_most_its_bound_of_quotes() -> None:
    quotes = [f"{HINDI_QUOTE} {'अ' * n}" for n in range(1, RENDERED_QUOTES_MAX + 4)]
    failing = [
        DraftSentence(
            "Alum",
            STATED,
            ComposedSentence(
                text=STATED, evidence_ids=[HINDI_PAGE], spans=[QuotedSpan(ref=HINDI_PAGE, text=q)]
            ),
            ("UNRELATED_QUOTE: the quotes do not carry its wording",),
        )
        for q in quotes
    ]
    draft = DraftAnswer(sections=(DraftSection("Alum", tuple(failing)),), follow_ups=())
    assert [quote.text for quote in foreign_quotes(draft.failed)] == quotes[:RENDERED_QUOTES_MAX]
