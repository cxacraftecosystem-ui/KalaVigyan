import json
from pathlib import Path

import pytest

from app.sources.reference.wikipedia import LANGUAGE_ALIASES, WIKIPEDIA_LANGUAGES
from app.sources.reference.wikipedia_editions import wikipedia_editions

DECISION_0006_LANGUAGES = {
    "en",
    "as",
    "awa",
    "bh",
    "bn",
    "bpy",
    "gom",
    "gu",
    "hi",
    "kn",
    "ks",
    "mai",
    "ml",
    "mni",
    "mr",
    "ne",
    "new",
    "or",
    "pa",
    "sa",
    "sat",
    "sd",
    "ta",
    "tcy",
    "te",
    "ur",
}


def written(path: Path, payload: object) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_the_vendored_editions_keep_every_earlier_language_and_add_the_rest_of_wikipedia() -> None:
    assert DECISION_0006_LANGUAGES <= WIKIPEDIA_LANGUAGES
    assert {"fr", "de", "es", "zh", "zh-yue", "zh-min-nan"} <= WIKIPEDIA_LANGUAGES
    assert not {"xx", "zz", "nb"} & WIKIPEDIA_LANGUAGES


def test_every_alias_leads_to_an_edition_and_never_hides_one() -> None:
    assert set(LANGUAGE_ALIASES.values()) <= WIKIPEDIA_LANGUAGES
    assert not set(LANGUAGE_ALIASES) & WIKIPEDIA_LANGUAGES


def test_a_well_formed_editions_file_loads(tmp_path: Path) -> None:
    path = written(tmp_path / "editions.json", {"schemaVersion": 1, "editions": ["en", "fr", "zh-yue"]})
    assert wikipedia_editions(path) == frozenset({"en", "fr", "zh-yue"})


@pytest.mark.parametrize(
    "payload",
    [
        {"schemaVersion": 2, "editions": ["en"]},
        {"schemaVersion": 1, "editions": []},
        {"schemaVersion": 1, "editions": ["en", "evil.example.com"]},
        {"schemaVersion": 1, "editions": ["EN"]},
        {"schemaVersion": 1, "editions": ["en", "fr\n"]},
        {"schemaVersion": 1, "editions": ["en", 7]},
        {"schemaVersion": 1, "editions": ["fr", "en"]},
        {"schemaVersion": 1, "editions": ["en", "en"]},
        {"schemaVersion": 1, "editions": ["fr"]},
        ["en"],
    ],
)
def test_a_malformed_editions_file_is_refused_on_load(tmp_path: Path, payload: object) -> None:
    with pytest.raises(ValueError):
        wikipedia_editions(written(tmp_path / "editions.json", payload))
