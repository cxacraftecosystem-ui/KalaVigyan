import json

import pytest

from app.research.document_parts import PART_BYTES_MAX, compact_json, document_parts, part_body

SMALL = {"schemaVersion": 1, "version": 7, "shell": None, "specs": {"a": {"x": 1}}, "fragments": {}}


def size(value: object) -> int:
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def test_a_document_under_the_budget_is_one_part_holding_all_of_it() -> None:
    (only,) = document_parts(SMALL)
    assert (only.part, only.parts, only.body) == (0, 1, SMALL)
    assert part_body(only, 7) == {"schemaVersion": 1, "version": 7, "part": 0, "parts": 1, "body": SMALL}


def test_a_large_document_keeps_its_content_first_and_packs_shell_specs_and_fragments_after() -> None:
    body = {
        "title": "Kutch Ajrakh",
        "content": {"units": {"u1": "धोना"}},
        "shell": "<section>" + "s" * 90 + "</section>",
        "specs": {"first": {"t": "a" * 80}, "second": {"t": "b" * 80}, "third": {"t": "c" * 10}},
        "fragments": {"frag": "<p>" + "f" * 40 + "</p>"},
    }
    parts = document_parts(body, most=260)
    assert [part.part for part in parts] == [0, 1, 2, 3]
    assert {part.parts for part in parts} == {4}
    assert parts[0].body == {"title": "Kutch Ajrakh", "content": {"units": {"u1": "धोना"}}}
    assert parts[1].body == {"shell": body["shell"], "specs": {}, "fragments": {}}
    assert parts[2].body == {"specs": {"first": body["specs"]["first"]}, "fragments": {}}
    assert parts[3].body == {
        "specs": {"second": body["specs"]["second"], "third": body["specs"]["third"]},
        "fragments": {"frag": body["fragments"]["frag"]},
    }
    assert all(size(part.body) <= 260 for part in parts)


def test_a_generated_document_without_a_shell_keeps_its_null_shell_in_the_first_part() -> None:
    body = {"shell": None, "content": {}, "specs": {"a": {"t": "a" * 200}}, "fragments": {}}
    first, second = document_parts(body, most=100)
    assert first.body == {"shell": None, "content": {}}
    assert second.body == {"specs": {"a": {"t": "a" * 200}}, "fragments": {}}


def test_the_budget_keeps_every_part_under_the_web_cache_item_once_encoded() -> None:
    assert PART_BYTES_MAX * 4 / 3 < 2 * 1024 * 1024
    assert compact_json({"a": "धोना"}) == '{"a":"धोना"}'
    with pytest.raises(ValueError, match="bytes of wrapping"):
        document_parts(SMALL, most=64)
