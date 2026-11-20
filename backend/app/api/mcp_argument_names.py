from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, ClassVar, Literal, Self, get_args

from pydantic import BaseModel, ModelWrapValidatorHandler, PrivateAttr, ValidationError, model_validator
from pydantic.alias_generators import to_snake
from pydantic.json_schema import DEFAULT_REF_TEMPLATE, GenerateJsonSchema, JsonSchemaMode

from .mcp_tool_base import Arguments

__all__ = [
    "ARGUMENT_NAMES",
    "OLD_ARGUMENT_NAMES",
    "OLD_NAME_NOTICE",
    "RenamedArguments",
    "SnakeBodyArguments",
    "camel_keys",
    "model_aliases",
    "problems",
    "renamed",
]

ARGUMENT_NAMES = ("craft_slug", "category_slug", "family_slug", "field", "task_key")
OLD_ARGUMENT_NAMES: Mapping[str, str] = MappingProxyType(
    {
        "craftSlug": "craft_slug",
        "categorySlug": "category_slug",
        "familySlug": "family_slug",
        "taskKey": "task_key",
    }
)
OLD_NAME_NOTICE = (
    "{old} is the old name of {new}; it works until the next release, so pass {new} from now on."
)
BODY_ARGUMENT = "proposal"


def renamed(data: Mapping[str, Any], names: Mapping[str, str]) -> tuple[dict[str, Any], tuple[str, ...]]:
    moved = dict(data)
    used: list[str] = []
    for old, new in names.items():
        if old in moved and new not in moved:
            moved[new] = moved.pop(old)
            used.append(old)
    return moved, tuple(used)


def camel_keys(value: Any, aliases: frozenset[str]) -> tuple[str, ...]:
    found: list[str] = []
    pending = [value]
    while pending:
        current = pending.pop(0)
        if isinstance(current, Mapping):
            found += [key for key in current if key in aliases]
            pending += list(current.values())
        elif isinstance(current, list):
            pending += current
    return tuple(dict.fromkeys(found))


def model_aliases(annotation: Any) -> frozenset[str]:
    aliases: set[str] = set()
    seen: set[type[BaseModel]] = set()
    pending = _models_in(annotation)
    while pending:
        model = pending.pop()
        if model in seen:
            continue
        seen.add(model)
        for name, info in model.model_fields.items():
            if info.alias and info.alias != name:
                aliases.add(info.alias)
            pending += _models_in(info.annotation)
    return frozenset(aliases)


def _models_in(annotation: Any) -> list[type[BaseModel]]:
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return [annotation]
    return [model for argument in get_args(annotation) for model in _models_in(argument)]


def problems(refused: ValidationError) -> str:
    return "; ".join(
        f"{'.'.join(str(part) for part in problem['loc']) or 'arguments'}: {problem['msg']}"
        for problem in refused.errors()
    )


class RenamedArguments(Arguments):
    OLD_NAMES: ClassVar[Mapping[str, str]] = OLD_ARGUMENT_NAMES
    OLD_FORMS: ClassVar[Mapping[str, str]] = MappingProxyType({})
    _old_names: tuple[str, ...] = PrivateAttr(default=())

    @classmethod
    def reshaped(cls, data: Mapping[str, Any]) -> tuple[dict[str, Any], tuple[str, ...]]:
        return renamed(data, cls.OLD_NAMES)

    @model_validator(mode="wrap")
    @classmethod
    def _old_names_work(cls, data: Any, handler: ModelWrapValidatorHandler[Self]) -> Self:
        if not isinstance(data, Mapping):
            return handler(data)
        moved, used = cls.reshaped(data)
        model = handler(moved)
        model._old_names = used
        return model

    def notices(self) -> list[str]:
        return [
            self.OLD_FORMS[old]
            if old in self.OLD_FORMS
            else OLD_NAME_NOTICE.format(old=old, new=self.OLD_NAMES.get(old, to_snake(old)))
            for old in self._old_names
        ]


class SnakeBodyArguments(RenamedArguments):
    @classmethod
    def reshaped(cls, data: Mapping[str, Any]) -> tuple[dict[str, Any], tuple[str, ...]]:
        moved, used = super().reshaped(data)
        aliases = model_aliases(cls.model_fields[BODY_ARGUMENT].annotation)
        return moved, (*used, *camel_keys(moved.get(BODY_ARGUMENT), aliases))

    @classmethod
    def model_json_schema(
        cls,
        by_alias: bool | None = None,
        ref_template: str = DEFAULT_REF_TEMPLATE,
        schema_generator: type[GenerateJsonSchema] = GenerateJsonSchema,
        mode: JsonSchemaMode = "validation",
        *,
        union_format: Literal["any_of", "primitive_type_array"] = "any_of",
    ) -> dict[str, Any]:
        return super().model_json_schema(
            False, ref_template, schema_generator, mode, union_format=union_format
        )
