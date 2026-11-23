import uuid
from dataclasses import dataclass

import pytest

from app.models import Claim, ClaimSource
from app.research.blocks import ExplainerSentence
from app.research.composition import ComposedAnswer, ComposedSection, ComposedSentence, QuotedSpan
from app.services.answer_events import CitedClaims, cited_claims
from app.services.knowledge_view import ClaimView, cited_view
from app.services.section_blocks import (
    BlockRefused,
    KeptSentence,
    explainer_sentence,
    kept_sentences,
    lede_block,
    prose_block,
    section_sentences,
)

from .fakes import ALUM_CLAIM_ID, BOOK_ID, SOURCES, VIEWS, WEB, WRITTEN_LAKE_ID, stored_view

PAGE = "searxng:https://crafts.example.org/ajrakh"
WRITTEN_ID = uuid.UUID("6d000000-0000-4000-8000-000000000001")
CITED = cited_claims(list(VIEWS), SOURCES)
SETTLED = "Ajrakh printers settled in Dhamadka village in Barmer district."
SETTLED_QUOTE = "Ajrakh printers settled in Dhamadka village"


@dataclass
class DifferingView(ClaimView):
    sources_differ: bool = True


@dataclass
class NamedDifferenceView(ClaimView):
    sources_differ: bool = True
    differs_on: str | None = "How long the red dye bath lasts"


def flagged_alum(view_type: type[ClaimView]) -> dict[str, object]:
    alum = VIEWS[0]
    view = view_type(
        alum.id, alum.text, alum.level, alum.concept_type, alum.concept_id, citations=alum.citations
    )
    sentence = KeptSentence(alum.text, (alum.id,), (), False)
    shown = explainer_sentence("s1.b1.1", sentence, cited_claims([view], SOURCES))
    return shown.model_dump(mode="json", by_alias=True)


def live(text: str, quote: str) -> tuple[list[KeptSentence], CitedClaims]:
    view = stored_view(WRITTEN_ID, text, "PROVISIONAL", (40, WEB, quote, None))
    sentence = ComposedSentence(text=text, evidenceIds=[PAGE], spans=[QuotedSpan(ref=PAGE, text=quote)])
    composed = ComposedAnswer(sections=[ComposedSection(heading="Where it is printed", sentences=[sentence])])
    return kept_sentences(composed, [(WRITTEN_ID,)]), cited_claims([view], SOURCES)


@pytest.mark.parametrize(
    ("text", "quote"),
    [
        (SETTLED, SETTLED_QUOTE),
        (
            "The cloth is printed in the dry months of March and April.",
            "the cloth is printed in the dry months",
        ),
    ],
    ids=["a district", "two months"],
)
def test_a_live_sentence_naming_what_its_quotes_do_not_state_is_dropped(text: str, quote: str) -> None:
    kept, cited = live(text, quote)
    assert kept[0].written == (WRITTEN_ID,)
    assert section_sentences(kept, cited).facts == ()


def test_a_stored_claim_a_sentence_cites_still_states_the_names_in_its_own_text() -> None:
    view = stored_view(WRITTEN_ID, SETTLED, "PROVISIONAL", (40, WEB, SETTLED_QUOTE, None))
    sentence = KeptSentence(SETTLED, (WRITTEN_ID,), (), False)
    assert section_sentences([sentence], cited_claims([view], SOURCES)).facts == (sentence,)


def test_a_sentence_with_no_stored_claim_is_dropped_alone_and_its_block_keeps_the_rest() -> None:
    alum = KeptSentence("Alum is the mordant.", (ALUM_CLAIM_ID,), (), False)
    unclaimed = KeptSentence("Alum came to Kutch with the printers.", (), (PAGE,), False)
    split = section_sentences([alum, unclaimed], CITED)
    assert split.facts == (alum,)
    assert [s.text for s in prose_block("s1.b1", split.facts, CITED).sentences] == ["Alum is the mordant."]


def test_a_sentence_citing_a_claim_whose_sources_differ_carries_the_flag() -> None:
    alum = VIEWS[0]
    differing = DifferingView(
        alum.id, alum.text, alum.level, alum.concept_type, alum.concept_id, citations=alum.citations
    )
    sentence = KeptSentence(alum.text, (alum.id,), (), False)
    flagged = explainer_sentence("s1.b1.1", sentence, cited_claims([differing], SOURCES))
    plain = explainer_sentence("s1.b1.1", sentence, CITED)
    assert flagged.model_dump(mode="json", by_alias=True)["sourcesDiffer"] is True
    assert "sourcesDiffer" not in plain.model_dump(mode="json", by_alias=True)
    (shown,) = prose_block("s1.b1", [sentence], cited_claims([differing], SOURCES)).sentences
    assert shown.sources_differ is True


def test_a_flagged_sentence_names_what_its_sources_differ_on_when_the_claim_stores_it() -> None:
    named = flagged_alum(NamedDifferenceView)
    assert (named["sourcesDiffer"], named["differsOn"]) == (True, "How long the red dye bath lasts")
    unnamed = flagged_alum(DifferingView)
    assert unnamed["sourcesDiffer"] is True and "differsOn" not in unnamed


def stored_claim(*, differs: bool, about: str | None) -> Claim:
    alum = VIEWS[0]
    return Claim(id=alum.id, text=alum.text, evidenceLevel=alum.level, sourcesDiffer=differs, differsOn=about)


def test_a_stored_claim_s_subject_of_difference_reaches_the_sentence_that_cites_it() -> None:
    cite = ClaimSource(
        id=uuid.UUID(int=41), claimId=VIEWS[0].id, sourceId=BOOK_ID, quote="Alum is the mordant"
    )
    view = cited_view(
        stored_claim(differs=True, about="How long the red dye bath lasts"), [cite], (None, "MATERIAL")
    )
    assert (view.sources_differ, view.differs_on) == (True, "How long the red dye bath lasts")
    sentence = KeptSentence(view.text, (view.id,), (), False)
    shown = explainer_sentence("s1.b1.1", sentence, cited_claims([view], SOURCES)).model_dump(by_alias=True)
    assert (shown["sourcesDiffer"], shown["differsOn"]) == (True, "How long the red dye bath lasts")
    cleared = cited_view(stored_claim(differs=False, about=None), [cite], (None, "MATERIAL"))
    assert (cleared.sources_differ, cleared.differs_on) == (False, None)


def test_a_sentence_names_a_difference_only_when_its_sources_differ() -> None:
    sentence = flagged_alum(NamedDifferenceView) | {"sourcesDiffer": False}
    with pytest.raises(ValueError, match="differ on only when they differ"):
        ExplainerSentence.model_validate(sentence)


def test_a_lede_whose_answer_sentence_fails_is_refused_even_when_two_others_pass() -> None:
    answer = KeptSentence("Alum came to Kutch with the printers.", (), (), False)
    alum = KeptSentence(VIEWS[0].text, (ALUM_CLAIM_ID,), (), False)
    bath = KeptSentence(VIEWS[1].text, (WRITTEN_LAKE_ID,), (), False)
    with pytest.raises(BlockRefused) as refused:
        lede_block("Which mordant fixes the red?", [answer, alum, bath], CITED)
    assert refused.value.problems == ("the answer, sentence 1 cites no stored claim",)
    shown = lede_block("Which mordant fixes the red?", [alum, bath], CITED)
    assert [s.text for s in shown.sentences] == [VIEWS[0].text, VIEWS[1].text]
