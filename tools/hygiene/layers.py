from __future__ import annotations

import ast
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import PurePosixPath

__all__ = ["BACKEND_APP", "LAYER_IMPORTS", "ImportViolation", "import_violations", "module_name"]

BACKEND_APP = PurePosixPath("backend/app")
ROOT_PACKAGE = "app"

LAYER_IMPORTS: dict[str, frozenset[str]] = {
    "data": frozenset({"data"}),
    "models": frozenset({"models"}),
    "core": frozenset({"core", "models"}),
    "research": frozenset({"research", "core", "models"}),
    "curation": frozenset({"curation", "research", "models", "data"}),
    "sources": frozenset({"sources", "research", "core", "models"}),
    "fetcher": frozenset({"fetcher", "sources", "research", "core"}),
    "retrieval": frozenset({"retrieval", "research", "core", "models"}),
    "planner": frozenset({"planner", "sources", "research", "core", "models"}),
    "composer": frozenset({"composer", "research", "core", "models"}),
    "schemas": frozenset({"schemas", "research", "core"}),
    "science": frozenset({"science", "schemas", "research", "core"}),
    "geo": frozenset({"geo", "schemas", "research", "core"}),
    "services": frozenset(
        {
            "services",
            "science",
            "geo",
            "planner",
            "composer",
            "retrieval",
            "sources",
            "curation",
            "research",
            "core",
            "models",
            "data",
        }
    ),
    "providers": frozenset({"providers", "services", "research", "core", "models"}),
    "voice": frozenset(
        {"voice", "providers", "services", "composer", "schemas", "research", "core", "models"}
    ),
    "media": frozenset({"media", "providers", "services", "schemas", "research", "core", "models"}),
    "worker": frozenset({"worker", "media", "voice", "core"}),
    "api": frozenset(
        {
            "api",
            "voice",
            "media",
            "providers",
            "services",
            "science",
            "geo",
            "retrieval",
            "research",
            "schemas",
            "core",
            "models",
            "data",
        }
    ),
    "scripts": frozenset(
        {
            "scripts",
            "voice",
            "providers",
            "services",
            "planner",
            "composer",
            "retrieval",
            "research",
            "core",
            "models",
            "data",
        }
    ),
    "main": frozenset({"api", "voice", "providers", "services", "core", "models"}),
}


@dataclass(frozen=True, order=True)
class ImportViolation:
    path: str
    line: int
    layer: str
    target: str
    reason: str

    def describe(self) -> str:
        return f"{self.path}:{self.line}: {self.layer} imports {self.target} ({self.reason})"


def module_name(path: PurePosixPath) -> tuple[str, bool]:
    relative = path.relative_to(BACKEND_APP.parent)
    parts = list(relative.with_suffix("").parts)
    is_package = parts[-1] == "__init__"
    if is_package:
        parts.pop()
    return ".".join(parts), is_package


def import_violations(sources: Iterable[tuple[PurePosixPath, str]]) -> list[ImportViolation]:
    found: list[ImportViolation] = []
    for path, text in sources:
        found.extend(_violations_in(path, text))
    return sorted(found)


def _violations_in(path: PurePosixPath, text: str) -> list[ImportViolation]:
    module, is_package = module_name(path)
    layer = _layer_of(module)
    if layer is None:
        return []
    allowed = LAYER_IMPORTS.get(layer)
    if allowed is None:
        return [ImportViolation(str(path), 1, layer, module, f"app.{layer} is not a layer in LAYER_IMPORTS")]
    found = []
    for line, target in _imported_modules(ast.parse(text, filename=str(path)), module, is_package):
        target_layer = _layer_of(target)
        if target_layer is None and target == ROOT_PACKAGE:
            found.append(ImportViolation(str(path), line, layer, target, "imports the root package"))
        elif target_layer is not None and target_layer not in allowed:
            found.append(
                ImportViolation(str(path), line, layer, target, f"{layer} may not import {target_layer}")
            )
    return found


def _layer_of(module: str) -> str | None:
    parts = module.split(".")
    if parts[0] != ROOT_PACKAGE or len(parts) < 2:
        return None
    return parts[1]


def _imported_modules(tree: ast.Module, module: str, is_package: bool) -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = _absolute_base(node, module, is_package)
            if base == ROOT_PACKAGE:
                found.extend((node.lineno, f"{base}.{alias.name}") for alias in node.names)
            else:
                found.append((node.lineno, base))
    return found


def _absolute_base(node: ast.ImportFrom, module: str, is_package: bool) -> str:
    if node.level == 0:
        return node.module or ""
    package = module.split(".") if is_package else module.split(".")[:-1]
    anchor = package[: len(package) - (node.level - 1)]
    if not anchor:
        raise ValueError(f"relative import climbs above the root package in {module}")
    return ".".join([*anchor, node.module] if node.module else anchor)
