import ast
import re
from pathlib import Path

from app.research.monograph_page import TEXT_SCRIPTS
from app.research.open_work_translation_keys import TRANSLATION_LANGUAGES
from app.research.vocabulary import ANSWER_LANGUAGE_SPECS, text_direction

REPO = Path(__file__).resolve().parents[3]
SOURCE = (REPO / "frontend" / "lib" / "documentLanguages.ts").read_text(encoding="utf-8")


def _listed(name: str) -> list[str]:
    found = re.search(rf"export const {name}[^=]*= \[(.*?)\]", SOURCE)
    assert found is not None, name
    return list(ast.literal_eval(f"[{found.group(1)}]"))


def test_the_site_routes_and_draws_the_languages_the_server_translates_pages_into() -> None:
    assert tuple(_listed("DOCUMENT_LANGUAGE_CODES")) == TRANSLATION_LANGUAGES


def test_the_site_marks_each_language_with_the_script_and_direction_the_server_writes() -> None:
    block = re.search(r"export const TEXT_SCRIPTS[^=]*= \{(.*?)\};", SOURCE, re.DOTALL)
    assert block is not None
    scripts = dict(re.findall(r"(\w+): \"(\w+)\"", block.group(1)))
    expected = {
        code: TEXT_SCRIPTS.get(code, ANSWER_LANGUAGE_SPECS[code].script) for code in TRANSLATION_LANGUAGES
    }
    assert scripts == expected
    assert scripts["ur"] == "Aran" and scripts["hi"] == "Deva"
    assert _listed("RIGHT_TO_LEFT") == [
        code for code in TRANSLATION_LANGUAGES if text_direction(code) == "rtl"
    ]


def test_the_site_names_each_language_as_the_server_does_in_english_and_its_own_script() -> None:
    pattern = r"(\w+): \{ label: \"([^\"]+)\", autonym: \"([^\"]+)\" \}"
    names = {code: (label, autonym) for code, label, autonym in re.findall(pattern, SOURCE)}
    expected = {
        code: (ANSWER_LANGUAGE_SPECS[code].label, ANSWER_LANGUAGE_SPECS[code].autonym)
        for code in TRANSLATION_LANGUAGES
    }
    assert names == expected
