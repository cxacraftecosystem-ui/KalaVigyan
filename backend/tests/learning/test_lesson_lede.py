import uuid
from io import BytesIO

from pptx import Presentation
from pypdf import PdfReader

from app.research.lesson_builder import lesson_pack
from app.research.lessons import LessonPack, LessonRequest
from app.services.export_pdfs import lesson_pdf
from app.services.lesson_deck import lesson_deck
from app.services.lesson_pptx import lesson_pptx

from .lesson_fixtures import BUILT_AT, golden_pack, lede_version, pack_references, visible_claims

LEDE_TEXTS = [
    "Alum is the mordant that fixes the red, together with dhaori (tamarisk galls).",
    "First the cloth is soaked in harde, and the tannin in the myrobalan is an essential pre-mordant aiding "
    "adhesion of printed mordants.",
    "The red dye then links to the alum mordant on the cotton fibres.",
]
GI_JOURNAL = "d0f53ee9-4b97-5df7-a367-686957bdb7c8"
WATER_WOES = "907e2c52-14e7-5e41-9b27-9c10f70906a9"
FIRST_LEDE_CLAIM = "f0b75ff9-d401-543e-b58e-4b73484ecafe"


def lede_pack(visible: frozenset[str] | None = None) -> LessonPack:
    document = lede_version()
    request = LessonRequest(
        explainer_id=document.mark.explainer_id,
        version=document.mark.version,
        title=None,
        section_ids=["s1"],
        quiz=False,
    )
    return lesson_pack(
        document,
        request,
        visible_claim_ids=visible if visible is not None else visible_claims(document),
        pack_id=uuid.UUID(int=11),
        created_at=BUILT_AT,
    )


def shape_texts(slide) -> list[str]:
    return [shape.text_frame.text for shape in slide.shapes if shape.has_text_frame]


def test_the_title_slide_opens_with_the_lede() -> None:
    opening = lede_pack().slides[0]
    assert opening.kind == "TITLE" and opening.block_ids == ["lede"] and opening.section_id is None
    assert [sentence.text for sentence in opening.bullets] == LEDE_TEXTS
    assert all(sentence.citations for sentence in opening.bullets)


def test_the_lede_s_sources_are_the_lesson_s_sources() -> None:
    pack = lede_pack()
    assert [source.id for source in pack.sources] == [GI_JOURNAL, WATER_WOES]
    assert {item.source.id for item in pack.reading_list} == {GI_JOURNAL, WATER_WOES}


def test_a_lede_sentence_whose_claim_is_withdrawn_is_left_off() -> None:
    visible = visible_claims(lede_version()) - {FIRST_LEDE_CLAIM}
    assert [sentence.text for sentence in lede_pack(visible).slides[0].bullets] == LEDE_TEXTS[1:]


def test_an_explainer_without_a_lede_keeps_a_bare_title_slide() -> None:
    opening = golden_pack().slides[0]
    assert opening.bullets == [] and opening.block_ids == []


def test_the_slides_open_with_the_lede_and_its_source_numbers() -> None:
    pack = lede_pack()
    refs = pack_references(pack)
    expected = [f"• {sentence.text} {refs.sentence_marker(sentence)}" for sentence in pack.slides[0].bullets]
    assert [refs.sentence_marker(sentence) for sentence in pack.slides[0].bullets] == ["[1]", "[1, 2]", "[1]"]
    deck = Presentation(BytesIO(lesson_pptx(pack, refs, {})))
    texts = shape_texts(next(iter(deck.slides)))
    assert texts[0] == pack.title and texts[-1].split("\n") == expected


def test_the_html_deck_opens_with_the_lede() -> None:
    pack = lede_pack()
    refs = pack_references(pack)
    html = lesson_deck(pack, refs, {}).decode("utf-8")
    opening = html.split('<section data-kind="TITLE" data-number="1">', 1)[1].split("</section>", 1)[0]
    for sentence in pack.slides[0].bullets:
        assert (
            f'<li>{sentence.text} <span class="kv-cite">{refs.sentence_marker(sentence)}</span></li>'
            in opening
        )


def test_the_handout_opens_with_the_lede() -> None:
    pack = lede_pack()
    refs = pack_references(pack)
    reader = PdfReader(BytesIO(lesson_pdf(pack, refs, {})))
    first = " ".join(reader.pages[0].extract_text().split())
    for sentence in pack.slides[0].bullets:
        assert f"{sentence.text} {refs.sentence_marker(sentence)}" in first
