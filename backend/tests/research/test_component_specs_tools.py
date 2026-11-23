import pytest
from pydantic import ValidationError

from app.research.component_specs_tools import (
    SPEC_MODELS_TOOLS,
    GeneratorSpec,
    LanguageSwitchSpec,
    QuizQuestion,
    QuoteCard,
    spec_component_labels,
    spec_unit_refs,
)
from app.research.monograph_page import render_nodes
from app.scripts.build_monograph import monograph_content
from app.scripts.extract_specs_tools import stale_specs, tool_specs
from app.scripts.extract_specs_tools_markup import inline_nodes, parse_markup

SLUG = "Kutch-Ajrakh"
QUIZ = "kutch-ajrakh/overview/check-yourself-quiz"
ASK = "kutch-ajrakh/overview/ask-next"
LANGUAGES = "kutch-ajrakh/overview/answer-in-hindi-and-urdu"
GENERATOR = "kutch-ajrakh/overview/watch-it-being-made"
EXPLAINER = "kutch-ajrakh/overview/how-to-read-citations"


@pytest.fixture(scope="module")
def specs() -> dict[str, dict]:
    return tool_specs(SLUG)


@pytest.fixture(scope="module")
def content():
    return monograph_content(SLUG)


def test_each_tool_spec_file_is_its_extraction() -> None:
    assert stale_specs(SLUG) == []


def test_ajrakh_has_one_spec_for_each_tool_kind(specs: dict[str, dict], content) -> None:
    kinds = {component.label: component.kind for component in content.components}
    assert sorted(kinds[label] for label in specs) == sorted(SPEC_MODELS_TOOLS)


def test_every_unit_within_a_tool_component_is_drawn_by_its_spec(specs: dict[str, dict], content) -> None:
    kinds = {component.label: component.kind for component in content.components}
    for label, raw in specs.items():
        drawn = spec_unit_refs(SPEC_MODELS_TOOLS[kinds[label]].model_validate(raw))
        within = [entry.ref for entry in content.layout if entry.kind == "unit" and entry.within == label]
        assert sorted(drawn) == sorted(within), label
        assert all(ref in content.units for ref in drawn)


def test_the_quiz_asks_the_three_words_the_page_blanks(specs: dict[str, dict]) -> None:
    questions = specs[QUIZ]["questions"]
    assert [[choice["term"] for choice in q["choices"] if choice["right"]] for q in questions] == [
        ["kut"],
        ["mizan"],
        ["kasanu"],
    ]
    assert questions[0]["before"] == "Printed on harde-treated cloth,"
    assert questions[0]["cite"] == {"key": "rm:p0b399a40611b.2", "sources": ["g1", "g3"]}


def test_each_quiz_sentence_renders_back_to_the_page_markup(specs: dict[str, dict], content) -> None:
    page = content.data["kv-data"]["quiz"]
    for question, original in zip(specs[QUIZ]["questions"], page, strict=True):
        for choice, option in zip(question["choices"], original["opts"], strict=True):
            assert render_nodes(choice["sentence"], content.sources) == option["html"]


def test_ask_next_asks_six_questions_about_the_craft(specs: dict[str, dict]) -> None:
    spec = specs[ASK]
    assert spec["craft"] == "Kutch-Ajrakh"
    assert len(spec["questions"]) == 6
    assert spec["questions"][0] == "How is the indigo vat prepared and kept working for ajrakh?"


def test_the_language_switch_offers_english_hindi_and_urdu(specs: dict[str, dict], content) -> None:
    spec = specs[LANGUAGES]
    assert [(o["lang"], o["direction"]) for o in spec["options"]] == [
        ("en", "ltr"),
        ("hi", "ltr"),
        ("ur", "rtl"),
    ]
    assert spec["english"] == "u0995"
    hindi, urdu = spec["panels"]
    assert hindi["figure"] == "shared/chemistry/alizarin-purpurin-structures-hindi"
    assert "figure" not in urdu
    assert hindi["provenance"]["listen"] == {"label": "सुनें ·", "minutes": 7, "unit": "मिनट"}
    for panel in spec["panels"]:
        render_nodes(panel["lede"], content.sources)
        render_nodes(panel["section"]["body"], content.sources)


def test_the_generator_places_each_sections_pictures_and_the_film(specs: dict[str, dict], content) -> None:
    spec = specs[GENERATOR]
    assert [section["number"] for section in spec["sections"]] == [1, 2, 3, 4, 5, 6, 7]
    assert spec["sections"][0]["media"] == [
        "kutch-ajrakh/chemistry/ai-cloth-lifted-from-vat",
        "kutch-ajrakh/chemistry/ai-video-blue-in-the-air",
    ]
    assert spec["sections"][1]["title"] == "From Sindh to Kutch at a king's invitation"
    assert spec["film"] == "kutch-ajrakh/overview/answer-as-a-film"
    labels = {component.label for component in content.components}
    placed = spec_component_labels(GeneratorSpec.model_validate(spec), labels)
    assert len(placed) == 9


def test_the_explainer_cards_quote_sources_six_and_eleven(specs: dict[str, dict], content) -> None:
    cards = specs[EXPLAINER]["cards"]
    assert [content.sources[card["source"]].number for card in cards] == [6, 11]
    assert [card["keyed"] for card in cards] == [True, False]
    assert cards[1]["quoteUnit"] == "u0980"


def test_inline_markup_becomes_the_pages_marks() -> None:
    markup = (
        '<span class="s" data-src="a1">See <a class="inline" href="#fig1">'
        '<span class="kv-figref" data-figref="chem:1">Fig. 1</span></a>, H<sub>2</sub>O and '
        '<i class="bot">Rubia</i></span>'
    )
    assert inline_nodes(parse_markup(markup).children) == [
        {
            "m": "s",
            "src": "a1",
            "c": [
                "See ",
                {
                    "m": "link",
                    "cls": "inline",
                    "href": "#fig1",
                    "c": [{"m": "figref", "ref": "chem:1", "c": ["Fig. 1"]}],
                },
                ", H",
                {"m": "sub", "c": ["2"]},
                "O and ",
                {"m": "i", "role": "bot", "c": ["Rubia"]},
            ],
        }
    ]
    with pytest.raises(ValueError, match="not an inline mark"):
        inline_nodes(parse_markup("<table></table>").children)


def test_a_spec_refuses_an_ambiguous_or_broken_shape() -> None:
    with pytest.raises(ValidationError, match="exactly one"):
        QuoteCard.model_validate(
            {"source": "g1", "byline": "x", "quote": "q", "quoteUnit": "u0001", "locator": "p. 1"}
        )
    choice = {"term": "kut", "right": True, "sentence": ["kut"]}
    with pytest.raises(ValidationError, match="exactly one right choice"):
        QuizQuestion.model_validate(
            {
                "before": "a",
                "after": "b",
                "cite": {"key": "k", "sources": ["g1"]},
                "choices": [choice, choice],
            }
        )
    option = {"name": "x", "direction": "ltr", "status": "s"}
    with pytest.raises(ValidationError, match="one panel"):
        LanguageSwitchSpec.model_validate(
            {
                "label": "l",
                "options": [{"lang": "en", **option}, {"lang": "hi", **option}],
                "english": "u0001",
                "panels": [],
            }
        )
