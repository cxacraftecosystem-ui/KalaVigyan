from app.research.composition import ComposeCandidate, ComposedSentence, QuotedSpan, sentence_violations
from app.research.quote_renderings import QuotedIn, english_renderings, read_as, rendering_problems
from app.research.translation import TranslationRequest

HINDI = "फिटकरी लाल रंग को सूती कपड़े पर 60 °C पर बाँधती है"
RENDERED = "Alum binds the red colour to cotton cloth at 60 °C."
REF = "wikipedia:hi:Ajrakh"
HINDI_PASSAGE = ComposeCandidate(
    id=REF, kind="EVIDENCE", text=f"अजरख में {HINDI}।", sourceLabel="हिन्दी विकिपीडिया", level="HYPOTHESIS"
)
SENTENCE = ComposedSentence(
    text="Alum binds the red colour to cotton cloth at 60 °C.",
    evidenceIds=[REF],
    spans=[QuotedSpan(ref=REF, text=HINDI)],
)
NEGATION_MISSING = "the original's negation (not, no, never, without) is missing"


class FakeTranslator:
    def __init__(self, replies: dict[str, str]) -> None:
        self.replies = replies
        self.requests: list[TranslationRequest] = []

    async def translate(self, request: TranslationRequest) -> dict[str, str]:
        self.requests.append(request)
        return {item.key: self.replies[item.text] for item in request.items if item.text in self.replies}


def kinds(renderings: dict[str, str]) -> list[str]:
    return [
        violation.kind
        for violation in sentence_violations(SENTENCE, {REF: HINDI_PASSAGE}, renderings=renderings)
    ]


def test_a_sentence_resting_on_a_hindi_quote_alone_is_unrelated_without_its_rendering() -> None:
    assert kinds({}) == ["UNRELATED_QUOTE"]


def test_the_overlap_reads_the_checked_rendering_while_the_citation_keeps_the_verbatim_quote() -> None:
    assert kinds({HINDI: RENDERED}) == []
    assert [span.text for span in SENTENCE.spans] == [HINDI]


def test_a_rendering_that_moves_a_figure_or_drops_a_negation_is_refused() -> None:
    assert rendering_problems(QuotedIn(HINDI, "hi"), RENDERED) == []
    assert rendering_problems(
        QuotedIn(HINDI, "hi"), "Alum binds the red colour to cotton cloth at 70 °C."
    ) == [
        "number 60 is missing",
        "number 70 is not in the original",
    ]
    refused = QuotedIn("फिटकरी के बिना रंग नहीं टिकता", "hi")
    assert rendering_problems(refused, "Without alum the colour does not hold.") == []
    assert rendering_problems(refused, "Alum makes the colour hold.") == [NEGATION_MISSING]


def test_a_hindi_hedge_must_survive_in_the_english_rendering() -> None:
    doubtful = QuotedIn("फिटकरी शायद रंग बाँधती है", "hi")
    assert rendering_problems(doubtful, "Alum perhaps binds the colour.") == []
    assert rendering_problems(doubtful, "Alum binds the colour.") == ["the original's hedge is missing"]


async def test_only_foreign_quotes_are_sent_into_english_and_only_checked_renderings_come_back() -> None:
    wrong = QuotedIn("रंग 3 बार धोया जाता है", "hi")
    translator = FakeTranslator({HINDI: RENDERED, wrong.text: "The colour is washed 4 times."})
    quotes = [QuotedIn(HINDI, "hi"), QuotedIn("alum forms a red lake", "en"), wrong, QuotedIn(HINDI, "hi")]
    renderings = await english_renderings(quotes, translator)
    assert renderings == {HINDI: RENDERED}
    (request,) = translator.requests
    assert request.language == "en"
    assert [item.text for item in request.items] == [HINDI, wrong.text]


async def test_nothing_is_asked_when_every_quote_is_english() -> None:
    translator = FakeTranslator({})
    assert await english_renderings([QuotedIn("alum forms a red lake", "en")], translator) == {}
    assert translator.requests == []


def test_a_quote_without_a_rendering_is_read_as_written() -> None:
    assert read_as([HINDI, "alum forms a red lake"], {HINDI: RENDERED}) == [RENDERED, "alum forms a red lake"]
