from __future__ import annotations

from collections.abc import Sequence

__all__ = ["python_list", "typescript_list"]


def python_list(names: Sequence[str]) -> str:
    items = "".join(f'    "{name}",\n' for name in names)
    return f'__all__ = ["DEPICTED_MATERIALS"]\n\nDEPICTED_MATERIALS = (\n{items})\n'


def typescript_list(names: Sequence[str]) -> str:
    items = ", ".join(f'"{name}"' for name in names)
    return f"export const DEPICTED_MATERIALS = [{items}] as const;\n"
