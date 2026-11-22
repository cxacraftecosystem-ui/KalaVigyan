import re
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[3] / ".github" / "workflows" / "open-data.yml"


def _text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def _input(name: str) -> str:
    found = re.search(rf"^      {name}:\n((?:        .*\n)+)", _text(), re.MULTILINE)
    assert found is not None, name
    return found.group(1)


def test_an_empty_craft_releases_the_whole_knowledge_base_and_a_run_publishes_only_when_ticked() -> None:
    assert 'default: ""' in _input("craft")
    assert "empty: the whole knowledge base" in _input("craft")
    assert "default: false" in _input("publish")


def test_the_craft_is_checked_as_a_slug_before_anything_is_sent_and_passed_to_every_step() -> None:
    text = _text()
    assert '[[ "$craft" =~ ^[A-Za-z0-9][A-Za-z0-9-]{0,159}$ ]]' in text
    for step in ("latest", "build", "record"):
        assert re.search(rf'as_app "{step} --target \$TARGET[^"]*\$CRAFT_ARGS"', text), step
    assert 'args+=(--craft "$CRAFT" --craft-name "$CRAFT_NAME")' in text
    assert '[ -z "$CRAFT" ] || args+=(--craft "$CRAFT")' in text


def test_the_summary_names_the_scope_and_both_dois_and_the_record() -> None:
    text = _text()
    for line in (
        'echo "- Scope: ${scope:-the whole knowledge base}"',
        'echo "- Title: $TITLE"',
        'echo "- This version: https://doi.org/$DOI"',
        'echo "- Every version: https://doi.org/$CONCEPT_DOI"',
        'echo "- Record: $RECORD_URL"',
    ):
        assert line in text, line
