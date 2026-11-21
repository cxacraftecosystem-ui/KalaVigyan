import pytest
from pydantic import ValidationError

from app.research.monograph_document import (
    MonographDocument,
    fragment_file_name,
    served_language,
    spec_file_name,
)
from app.research.monograph_page import MonographContent

LABEL = "kutch-ajrakh/chemistry/alum-player"


def content() -> MonographContent:
    return MonographContent.model_validate(
        {
            "craftSlug": "Kutch-Ajrakh",
            "sources": {},
            "citations": {},
            "citationClaims": {},
            "data": {},
            "units": {},
            "components": [
                {
                    "label": LABEL,
                    "chapter": "chem",
                    "anchor": "#red",
                    "kind": "reaction_player",
                    "title": "Alum and madder",
                    "description": "The red bath.",
                    "field": "CHEMISTRY",
                    "fields": [],
                    "subjects": [],
                }
            ],
            "layout": [],
        }
    )


def document(**drawn: object) -> MonographDocument:
    return MonographDocument.model_validate(
        {
            "subjectKind": "craft",
            "subjectSlug": "Kutch-Ajrakh",
            "title": "Kutch Ajrakh",
            "version": 1,
            "content": content().model_dump(by_alias=True),
            "pageUrl": "https://kalavigyan.example/crafts/Kutch-Ajrakh",
            **drawn,
        }
    )


def test_a_component_is_drawn_from_its_spec_or_its_fragment() -> None:
    assert document(specs={LABEL: {"steps": []}}).specs == {LABEL: {"steps": []}}
    assert document(fragments={LABEL: "<figure></figure>"}).fragments == {LABEL: "<figure></figure>"}


def test_a_spec_for_an_unknown_component_or_both_ways_at_once_is_refused() -> None:
    with pytest.raises(ValidationError, match="the content lacks"):
        document(specs={"kutch-ajrakh/chemistry/other-player": {}})
    with pytest.raises(ValidationError, match="not both"):
        document(specs={LABEL: {}}, fragments={LABEL: "<figure></figure>"})


def test_a_specs_file_name_replaces_the_labels_slashes() -> None:
    assert spec_file_name(LABEL) == "kutch-ajrakh__chemistry__alum-player.json"


def test_a_fragments_file_name_replaces_the_labels_slashes() -> None:
    assert fragment_file_name(LABEL) == "kutch-ajrakh__chemistry__alum-player.html"


def test_a_document_is_english_unless_it_names_a_language_tag() -> None:
    assert document().language == "en"
    assert document().model_dump(by_alias=True)["language"] == "en"
    assert document(language="kn-Knda").language == "kn-Knda"
    for bad in ("English", "e", "en_IN", "x" * 17):
        with pytest.raises(ValidationError):
            document(language=bad)


@pytest.mark.parametrize(
    ("asked", "served"),
    [(None, "en"), ("en", "en"), (" EN ", "en"), ("hi", "hi"), (" HI ", "hi"), ("ur", "ur"), ("fr", "en")],
)
def test_the_answer_languages_are_served_and_any_other_asks_for_english(
    asked: str | None, served: str
) -> None:
    assert served_language(asked) == served
