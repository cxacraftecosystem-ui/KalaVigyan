import json
from collections.abc import Iterable
from typing import Any, get_args

from pydantic import BaseModel, TypeAdapter

from .golden import golden_text

__all__ = ["FieldKey", "field_keys", "reachable_models", "shown_fields", "shown_in", "unshown_fields"]

FieldKey = tuple[str, str]


def field_keys(model: type[BaseModel]) -> set[FieldKey]:
    return {(_named(model), name) for name, info in model.model_fields.items() if info.exclude is not True}


def reachable_models(roots: Iterable[Any]) -> set[type[BaseModel]]:
    found: set[type[BaseModel]] = set()
    waiting = list(roots)
    while waiting:
        current = waiting.pop()
        if isinstance(current, type) and issubclass(current, BaseModel):
            if current not in found:
                found.add(current)
                waiting += [info.annotation for info in current.model_fields.values()]
            continue
        waiting += [arg for arg in get_args(current) if not isinstance(arg, (str, int, float, bool))]
    return found


def shown_fields(root: Any, names: Iterable[str]) -> set[FieldKey]:
    return {key for name in names for key in shown_in(root, golden_text(name))}


def shown_in(root: Any, text: str) -> set[FieldKey]:
    shown: set[FieldKey] = set()
    _walk(TypeAdapter(root).validate_json(text), json.loads(text), shown)
    return shown


def unshown_fields(roots: Iterable[Any], shown: set[FieldKey]) -> list[str]:
    wanted = {key for model in reachable_models(roots) for key in field_keys(model)}
    return sorted(f"{model}.{name}" for model, name in wanted - shown)


def _walk(value: Any, raw: Any, shown: set[FieldKey]) -> None:
    if isinstance(value, BaseModel):
        _walk_model(value, raw, shown)
    elif isinstance(value, (list, tuple)) and isinstance(raw, list):
        for item, raw_item in zip(value, raw, strict=False):
            _walk(item, raw_item, shown)
    elif isinstance(value, dict) and isinstance(raw, dict):
        for key, item in value.items():
            _walk(item, raw.get(str(key)), shown)


def _walk_model(value: BaseModel, raw: Any, shown: set[FieldKey]) -> None:
    if not isinstance(raw, dict):
        return
    model = type(value)
    for name, info in model.model_fields.items():
        key = info.serialization_alias or info.alias or name
        if key in raw:
            shown.add((_named(model), name))
            _walk(getattr(value, name), raw[key], shown)


def _named(model: type[BaseModel]) -> str:
    return f"{model.__module__}.{model.__qualname__}"
