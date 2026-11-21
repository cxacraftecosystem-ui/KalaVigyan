import json
import uuid
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.core.errors import InvalidInput
from app.retrieval.golden import (
    GENERATED_FILE,
    GENERATED_SCHEMA_FILE,
    GeneratedQuestion,
    generated_schema_text,
    generated_set,
    parse_generated,
)

FACT = uuid.uuid5(uuid.NAMESPACE_URL, "test-generated/fact")
TWIN = uuid.uuid5(uuid.NAMESPACE_URL, "test-generated/twin")
OTHER = uuid.uuid5(uuid.NAMESPACE_URL, "test-generated/other")


def question(**changes: Any) -> dict[str, Any]:
    return {
        "key": f"{FACT}-en",
        "craftSlug": "Kutch-Ajrakh",
        "field": "CHEMISTRY",
        "question": "What turns the cloth black where iron meets it?",
        "expected": [[str(FACT), str(TWIN)]],
        "fact": str(FACT),
        "language": "en",
        **changes,
    }


def generated(*questions: dict[str, Any]) -> dict[str, Any]:
    return {
        "version": 1,
        "revision": 1,
        "generatedAt": "2026-11-22T00:00:00Z",
        "model": "a-model",
        "seed": 7,
        "factsPerCraft": 20,
        "questions": list(questions),
    }


def test_a_generated_question_expects_its_own_fact_and_its_restatements() -> None:
    parsed = GeneratedQuestion.model_validate(question())
    assert parsed.facts == ((str(FACT), str(TWIN)),)
    assert (parsed.fact, parsed.language, parsed.rejected) == (FACT, "en", ())


@pytest.mark.parametrize(
    "changes",
    [
        {"expected": [[str(TWIN)]]},
        {"expected": [[str(FACT)], [str(TWIN)]]},
        {"expected": [["seed-0123456789abcdef0123"]]},
        {"rejected": [str(TWIN)]},
        {"language": "English"},
        {"craftSlug": None},
    ],
)
def test_a_generated_question_that_breaks_a_rule_is_refused(changes: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        GeneratedQuestion.model_validate(question(**changes))


def test_the_generated_file_is_versioned_and_each_key_is_its_own() -> None:
    parsed = parse_generated(generated(question(), question(key=f"{FACT}-hi", language="hi")))
    assert [one.language for one in parsed.questions] == ["en", "hi"]
    with pytest.raises(InvalidInput, match="version 1"):
        parse_generated({**generated(question()), "version": 2})
    with pytest.raises(InvalidInput, match="malformed"):
        parse_generated(generated(question(), question()))


def test_no_generated_file_means_no_generated_set(tmp_path: Path) -> None:
    assert generated_set(tmp_path / "absent.json") is None
    kept = tmp_path / "kept.json"
    kept.write_text(json.dumps(generated(question())), encoding="utf-8")
    found = generated_set(kept)
    assert found is not None and found.revision == 1


def test_the_kept_schema_is_generated_from_the_model() -> None:
    assert GENERATED_SCHEMA_FILE.read_text(encoding="utf-8") == generated_schema_text()


def test_a_kept_generated_set_is_valid_when_there_is_one() -> None:
    found = generated_set()
    assert found is None or found.questions
    assert found is not None or not GENERATED_FILE.exists()
