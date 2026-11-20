from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, ClassVar, Self

from pydantic import ModelWrapValidatorHandler, PrivateAttr, ValidationError, model_validator

from .mcp_tool_base import Arguments

__all__ = [
    "ARGUMENT_NAMES",
    "OLD_ARGUMENT_NAMES",
    "OLD_NAME_NOTICE",
    "RenamedArguments",
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


def renamed(data: Mapping[str, Any], names: Mapping[str, str]) -> tuple[dict[str, Any], tuple[str, ...]]:
    moved = dict(data)
    used: list[str] = []
    for old, new in names.items():
        if old in moved and new not in moved:
            moved[new] = moved.pop(old)
            used.append(old)
    return moved, tuple(used)


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
            else OLD_NAME_NOTICE.format(old=old, new=self.OLD_NAMES[old])
            for old in self._old_names
        ]
