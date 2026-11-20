from typing import Any

import pytest
from pydantic import ValidationError

from app.research.component_specs_plates import SPEC_MODELS_PLATES
from app.research.component_specs_plates_parts import DrawingElement

PICTURE = {"src": "/monographs/kutch-ajrakh/img/a-cloth.jpg", "width": 1280, "height": 960, "alt": "A cloth."}
FIGURE = {"classes": ["mk-plate"], "captions": [{"unit": "u0101"}], "credit": "u0102"}
SEAL = {"tag": "svg", "attrs": {"viewBox": "0 0 32 32"}, "children": [{"tag": "circle", "attrs": {"r": "4"}}]}
CITED = [
    {
        "m": "s",
        "c": [
            "Registered ",
            {
                "m": "cite",
                "key": "c1",
                "g": ["g5", "g4"],
                "shown": [{"number": 4, "title": "A"}, {"number": 5, "title": "B"}],
                "c": ["2024"],
            },
        ],
    }
]
MASTHEAD = {
    "kicker": "u0001",
    "title": "u0002",
    "seal": SEAL,
    "registration": CITED,
    "place": "Kachchh, Gujarat",
    "sources": 5,
    "grades": [{"grade": "A", "count": 3}, {"grade": "B", "count": 2}],
    "curated": "2026-11-17",
}
ART = {"symbol": "ai-vat", "viewBox": "0 0 1200 800", "width": 1200, "height": 800}
PLAYBACK = {"durationMs": 8000, "stepMs": 20, "restMs": 8000}
SWATCH = {"dye": "leuco", "caption": "u0081"}
COLOUR = {
    "before": SWATCH,
    "join": "becomes",
    "after": {"dye": "indigo", "caption": "u0082"},
    "name": "u0083",
    "agent": "u0084",
    "text": "u0085",
}
PAIR_SWATCH = {
    "ground": "harda",
    "motif": [{"tag": "circle", "attrs": {"fill": "var(--dye-kut)", "r": "2"}}],
    "label": "On purpose",
}
TESTIMONY = {
    "kicker": "u0911",
    "kickerId": "d7-vk",
    "evidence": "Published testimony",
    "quote": "u0912",
    "credit": "u0913",
    "meta": "u0914",
}
CODA = {
    "label": "Coda",
    "viewBox": "0 0 1200 520",
    "tile": "tile-11",
    "weave": "pt-weave",
    "kicker": "u0966",
    "quote": "u0967",
    "caption": "u0968",
    "note": "u0969",
}

VALID: dict[str, dict[str, Any]] = {
    "picture_plate": {"setting": "masthead", "picture": PICTURE, "figure": FIGURE, "masthead": MASTHEAD},
    "ai_illustration": {
        "section": 1,
        "art": ART,
        "subject": "A vat",
        "sentences": [1, 2],
        "made": "2026-11-18",
        "downloadName": "a-vat",
    },
    "specimen_plate": {
        "picture": PICTURE,
        "phase": "rest",
        "kicker": "u0073",
        "name": "u0074",
        "nameId": "hl-name",
        "sentence": "u0075",
        "replay": {"label": "Dip it again", "statusId": "vat-status", "status": "u0076"},
        "credit": "u0077",
    },
    "label_card": {
        "variant": "gi",
        "kicker": "u0844",
        "seal": SEAL,
        "sentence": "u0846",
        "facts": [{"term": "u0852", "value": "u0853"}],
    },
    "swatch_cards": {
        "chapterNo": "u0078",
        "title": "u0079",
        "titleId": "four-h",
        "intro": "u0080",
        "weave": "mb-weave",
        "colours": [COLOUR],
    },
    "swatch_pair": {
        "id": "b-ws-iron",
        "wide": True,
        "pairClass": "iron-pair",
        "description": "Two swatches",
        "weave": "pt-weave",
        "swatches": [PAIR_SWATCH, {**PAIR_SWATCH, "label": "By accident"}],
        "when": "u0640",
        "title": "u0641",
        "texts": ["u0642"],
        "go": {"stage": 5, "label": [{"m": "span", "c": ["Stage 5"]}]},
    },
    "film": {
        "title": "u1045",
        "meta": "u1046",
        "sceneLabel": "u1047",
        "subtitle": "u1048",
        "scenes": [{"art": ART, "title": "Tannin", "field": "Chemistry"}],
        "playback": {"durationMs": 56000, "stepMs": 100, "restMs": 0},
        "tags": ["AI video"],
        "note": "Subtitles are cited.",
        "downloadName": "a-film",
        "subtitlesName": "a-film-subtitles",
    },
    "ai_video": {
        "section": 1,
        "art": {
            "tag": "svg",
            "attrs": {"id": "vid-svg"},
            "children": [{"tag": "use", "attrs": {"href": "#ai-vat-back"}}],
        },
        "phase": "u1037",
        "playback": PLAYBACK,
        "caption": ["The dip, moving."],
        "made": "2026-11-18",
        "downloadKey": "1",
        "downloadName": "a-video",
    },
    "comic": {
        "label": "Story panels",
        "panels": [{"layout": "p-wide", "caption": CITED, "art": SEAL, "tag": "AI illustration"}],
    },
    "audio_player": {
        "title": "u0981",
        "description": "u0982",
        "action": "Listen",
        "minutes": 7,
        "playerId": "kv-player",
    },
    "voice": {"setting": "testimony", "testimony": TESTIMONY},
    "credits": {
        "groups": [
            {
                "title": "u1068",
                "listClass": "cr-list",
                "lines": [
                    {"unit": "u1069"},
                    {
                        "text": [
                            "Photo: ",
                            {
                                "m": "link",
                                "href": "https://commons.wikimedia.org/wiki/File:A.jpg",
                                "c": ["A"],
                            },
                        ]
                    },
                ],
            }
        ]
    },
}

REFUSED: dict[str, tuple[dict[str, Any], str]] = {
    "picture_plate": ({"setting": "row", "picture": PICTURE, "figure": FIGURE}, "row setting only"),
    "ai_illustration": ({**VALID["ai_illustration"], "sentences": []}, "at least 1"),
    "specimen_plate": ({**VALID["specimen_plate"], "nameId": "hl name"}, "pattern"),
    "label_card": ({**VALID["label_card"], "facts": []}, "at least 1"),
    "swatch_cards": (
        {**VALID["swatch_cards"], "colours": [{**COLOUR, "before": {"dye": "purple", "caption": "u0081"}}]},
        "dye",
    ),
    "swatch_pair": ({**VALID["swatch_pair"], "swatches": [PAIR_SWATCH]}, "at least 2"),
    "film": ({**VALID["film"], "playback": {"durationMs": 100, "stepMs": 10, "restMs": 200}}, "rests within"),
    "ai_video": (
        {**VALID["ai_video"], "art": {"tag": "use", "attrs": {"href": "https://example.org/a.svg#b"}}},
        "refers only to its page",
    ),
    "comic": (
        {**VALID["comic"], "panels": [{**VALID["comic"]["panels"][0], "caption": [{"m": "em", "c": ["x"]}]}]},
        "No inline mark",
    ),
    "audio_player": ({**VALID["audio_player"], "minutes": 0}, "greater than or equal to 1"),
    "voice": ({"setting": "coda", "testimony": TESTIMONY, "coda": CODA}, "testimony part and no other"),
    "credits": (
        {"groups": [{"title": "u1068", "lines": [{"unit": "u1069", "text": ["x"]}]}]},
        "not both or neither",
    ),
}


def test_the_plates_group_names_a_model_for_each_of_its_twelve_kinds() -> None:
    assert sorted(SPEC_MODELS_PLATES) == sorted(
        [
            "picture_plate",
            "ai_illustration",
            "specimen_plate",
            "label_card",
            "swatch_cards",
            "swatch_pair",
            "film",
            "ai_video",
            "comic",
            "audio_player",
            "voice",
            "credits",
        ]
    )


@pytest.mark.parametrize("kind", sorted(VALID))
def test_a_valid_spec_of_each_kind_is_accepted(kind: str) -> None:
    SPEC_MODELS_PLATES[kind].model_validate(VALID[kind])


@pytest.mark.parametrize("kind", sorted(REFUSED))
def test_a_spec_breaking_its_kinds_rule_is_refused(kind: str) -> None:
    spec, reason = REFUSED[kind]
    with pytest.raises(ValidationError, match=reason):
        SPEC_MODELS_PLATES[kind].model_validate(spec)


def test_the_masthead_counts_add_up_to_its_sources() -> None:
    with pytest.raises(ValidationError, match="add up"):
        SPEC_MODELS_PLATES["picture_plate"].model_validate(
            {**VALID["picture_plate"], "masthead": {**MASTHEAD, "sources": 6}}
        )


def test_a_held_citation_shows_each_source_once_in_order() -> None:
    shown = [{"number": 5, "title": "B"}, {"number": 4, "title": "A"}]
    cited = [{"m": "cite", "key": "c1", "g": ["g4", "g5"], "shown": shown, "c": ["2024"]}]
    with pytest.raises(ValidationError, match="once, in order"):
        SPEC_MODELS_PLATES["comic"].model_validate(
            {**VALID["comic"], "panels": [{**VALID["comic"]["panels"][0], "caption": cited}]}
        )


def test_a_drawing_keeps_the_spaces_of_its_text_and_refuses_handlers_and_foreign_elements() -> None:
    label = DrawingElement.model_validate(
        {"tag": "text", "children": ["GI journal ", {"tag": "tspan", "children": ["10"]}]}
    )
    assert label.children[0] == "GI journal "
    with pytest.raises(ValidationError, match="No drawing attribute"):
        DrawingElement.model_validate({"tag": "rect", "attrs": {"onclick": "go()"}})
    with pytest.raises(ValidationError, match="runs no script"):
        DrawingElement.model_validate({"tag": "rect", "attrs": {"fill": "JavaScript: go()"}})
    with pytest.raises(ValidationError):
        DrawingElement.model_validate({"tag": "foreignObject"})


def test_a_cited_passage_may_be_a_text_unit_but_not_any_other_text() -> None:
    comic = SPEC_MODELS_PLATES["comic"].model_validate(
        {**VALID["comic"], "panels": [{**VALID["comic"]["panels"][0], "caption": "u1104"}]}
    )
    assert comic.model_dump(mode="json")["panels"][0]["caption"] == "u1104"
    plate = SPEC_MODELS_PLATES["picture_plate"].model_validate(
        {**VALID["picture_plate"], "masthead": {**MASTHEAD, "registration": "u1110"}}
    )
    assert plate.model_dump(mode="json")["masthead"]["registration"] == "u1110"
    with pytest.raises(ValidationError):
        SPEC_MODELS_PLATES["comic"].model_validate(
            {**VALID["comic"], "panels": [{**VALID["comic"]["panels"][0], "caption": "Panel one"}]}
        )
