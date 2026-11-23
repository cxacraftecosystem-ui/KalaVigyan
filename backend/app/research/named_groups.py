from __future__ import annotations

import re
from collections.abc import Iterable

from app.models.group_names import GROUP_NAME_KINDS

__all__ = ["NAMED_GROUP_KINDS", "group_name_key", "names_a_listed_group"]

NAMED_GROUP_KINDS = GROUP_NAME_KINDS
PLURAL_ENDING = r"(?:e?s)?"


def group_name_key(name: str) -> str:
    return " ".join(name.casefold().split())


def names_a_listed_group(text: str, names: Iterable[str]) -> bool:
    folded = group_name_key(text)
    return any(_whole_name(key).search(folded) for key in map(group_name_key, names) if key)


def _whole_name(key: str) -> re.Pattern[str]:
    words = r"\s+".join(re.escape(word) for word in key.split(" "))
    return re.compile(rf"(?<!\w){words}{PLURAL_ENDING}(?!\w)")
