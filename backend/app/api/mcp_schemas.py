from __future__ import annotations

import copy
from collections.abc import Mapping
from functools import cache
from typing import Any

from pydantic import BaseModel

from app.models.component_kinds import PIECE_KINDS

__all__ = ["KINDS_LISTED_ONCE", "compact", "input_schema", "output_schema", "schema_types"]

DATA_KEYS = frozenset({"default", "const", "enum", "examples"})
MAP_KEYS = frozenset({"properties", "$defs", "patternProperties"})
NULL: Mapping[str, str] = {"type": "null"}
JSON_TYPES = ((bool, "boolean"), (int, "integer"), (float, "number"), (str, "string"))
KINDS_LISTED_ONCE = frozenset(PIECE_KINDS)


def input_schema(model: type[BaseModel]) -> dict[str, Any]:
    return copy.deepcopy(_input(model))


def output_schema(model: type[BaseModel]) -> dict[str, Any]:
    return copy.deepcopy(_output(model))


@cache
def _input(model: type[BaseModel]) -> dict[str, Any]:
    return compact(model.model_json_schema())


@cache
def _output(model: type[BaseModel]) -> dict[str, Any]:
    full = model.model_json_schema(by_alias=True, mode="serialization")
    defs = full.get("$defs", {})
    properties = {name: _shallow(value, defs) for name, value in full.get("properties", {}).items()}
    shallow: dict[str, Any] = {"type": "object", "properties": properties}
    if full.get("required"):
        shallow["required"] = list(full["required"])
    return shallow


def compact(node: Any) -> Any:
    if isinstance(node, list):
        return [compact(item) for item in node]
    if not isinstance(node, dict):
        return node
    kept: dict[str, Any] = {}
    for key, value in node.items():
        if key == "title" or (key == "default" and value is None):
            continue
        if key in MAP_KEYS and isinstance(value, dict):
            kept[key] = {name: compact(child) for name, child in value.items()}
        elif key in DATA_KEYS:
            kept[key] = value
        else:
            kept[key] = compact(value)
    return _kinds_unlisted(_nullable(kept))


def schema_types(node: Mapping[str, Any], defs: Mapping[str, Any]) -> list[str]:
    reference = node.get("$ref")
    if isinstance(reference, str):
        return schema_types(defs.get(reference.rsplit("/", 1)[-1], {}), defs)
    options = node.get("anyOf") or node.get("oneOf") or node.get("allOf")
    if isinstance(options, list):
        return sorted({kind for option in options for kind in schema_types(option, defs)})
    stated = node.get("type")
    if isinstance(stated, str):
        return [stated]
    if isinstance(stated, list):
        return sorted(str(kind) for kind in stated)
    values = node.get("enum", [node["const"]] if "const" in node else [])
    return sorted({_value_type(value) for value in values})


def _shallow(node: Mapping[str, Any], defs: Mapping[str, Any]) -> dict[str, Any]:
    types = schema_types(node, defs)
    if not types:
        return {}
    return {"type": types[0] if len(types) == 1 else types}


def _value_type(value: Any) -> str:
    if value is None:
        return "null"
    return next((name for kind, name in JSON_TYPES if isinstance(value, kind)), "object")


def _kinds_unlisted(node: dict[str, Any]) -> dict[str, Any]:
    values = node.get("enum")
    if not isinstance(values, list) or {value for value in values if value is not None} != KINDS_LISTED_ONCE:
        return node
    return {key: value for key, value in node.items() if key != "enum"}


def _nullable(node: dict[str, Any]) -> dict[str, Any]:
    options = node.get("anyOf")
    if not isinstance(options, list) or len(options) != 2 or NULL not in options:
        return node
    other = next(option for option in options if option != NULL)
    if not isinstance(other, dict) or not isinstance(other.get("type"), str) or "$ref" in other:
        return node
    merged = {key: value for key, value in node.items() if key != "anyOf"} | other
    merged["type"] = [other["type"], "null"]
    if isinstance(other.get("enum"), list):
        merged["enum"] = [*other["enum"], None]
    return merged
