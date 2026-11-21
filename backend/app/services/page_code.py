from __future__ import annotations

import ast
import hashlib
from collections.abc import Iterator
from dataclasses import dataclass
from functools import cache
from pathlib import Path

__all__ = [
    "APP_DIR",
    "PAGE_BUILDERS",
    "PAGE_CODE",
    "PAGE_KIT",
    "UNFOLLOWED",
    "CodeSpec",
    "code_files",
    "code_fingerprint",
    "page_code_fingerprint",
]

APP_PACKAGE = "app"
DATA_PACKAGE = "app.data"
APP_DIR = Path(__file__).resolve().parents[1]
PAGE_BUILDERS = ("app.services.craft_page_snapshots", "app.services.monograph_generated")
UNFOLLOWED = ("app.models", "app.core")
PAGE_KIT = ("data/monographs/kit",)


@dataclass(frozen=True)
class CodeSpec:
    app_dir: Path
    roots: tuple[str, ...]
    unfollowed: tuple[str, ...] = UNFOLLOWED
    kit: tuple[str, ...] = PAGE_KIT


PAGE_CODE = CodeSpec(app_dir=APP_DIR, roots=PAGE_BUILDERS)


@cache
def page_code_fingerprint() -> str:
    return code_fingerprint(PAGE_CODE)


def code_fingerprint(spec: CodeSpec) -> str:
    digest = hashlib.sha256()
    for path in code_files(spec):
        named = _named(spec, path)
        digest.update(f"{named}\n{hashlib.sha256(path.read_bytes()).hexdigest()}\n".encode())
    return digest.hexdigest()


def code_files(spec: CodeSpec) -> list[Path]:
    modules = _closure(spec)
    files = {source for module in modules if (source := _source(spec.app_dir, module)) is not None}
    for module in modules:
        if module == DATA_PACKAGE or module.startswith(f"{DATA_PACKAGE}."):
            files |= set(_named_files(spec.app_dir, module))
    for folder in spec.kit:
        files |= {path for path in (spec.app_dir / folder).rglob("*") if path.is_file()}
    return sorted(files, key=lambda path: _named(spec, path))


def _closure(spec: CodeSpec) -> set[str]:
    missing = [root for root in spec.roots if _source(spec.app_dir, root) is None]
    if missing:
        raise ValueError(f"the page code names modules that do not exist: {', '.join(missing)}")
    seen: set[str] = set()
    waiting = list(spec.roots)
    while waiting:
        module = waiting.pop()
        if module in seen or _unfollowed(spec, module):
            continue
        seen.add(module)
        waiting += [found for found in _imports(spec.app_dir, module) if found not in seen]
        waiting += [parent for parent in _parents(module) if _source(spec.app_dir, parent) is not None]
    return seen


def _unfollowed(spec: CodeSpec, module: str) -> bool:
    return any(module == skipped or module.startswith(f"{skipped}.") for skipped in spec.unfollowed)


def _imports(app_dir: Path, module: str) -> list[str]:
    source = _source(app_dir, module)
    if source is None:
        return []
    package = module if source.name == "__init__.py" else module.rpartition(".")[0]
    named = [name for node in ast.walk(ast.parse(source.read_bytes())) for name in _imported(node, package)]
    return [name for name in named if name.startswith(f"{APP_PACKAGE}.") and _source(app_dir, name)]


def _imported(node: ast.AST, package: str) -> Iterator[str]:
    if isinstance(node, ast.Import):
        yield from (alias.name for alias in node.names)
    elif isinstance(node, ast.ImportFrom):
        target = _absolute(node, package)
        yield target
        yield from (f"{target}.{alias.name}" for alias in node.names)


def _absolute(node: ast.ImportFrom, package: str) -> str:
    if not node.level:
        return node.module or ""
    parts = package.split(".")
    base = ".".join(parts[: len(parts) - node.level + 1])
    return f"{base}.{node.module}" if node.module else base


def _parents(module: str) -> list[str]:
    parts = module.split(".")
    return [".".join(parts[:end]) for end in range(2, len(parts))]


def _source(app_dir: Path, module: str) -> Path | None:
    parts = module.split(".")
    if parts[0] != APP_PACKAGE or len(parts) < 2:
        return None
    base = app_dir.joinpath(*parts[1:])
    for candidate in (base / "__init__.py", base.with_suffix(".py")):
        if candidate.is_file():
            return candidate
    return None


def _named_files(app_dir: Path, module: str) -> Iterator[Path]:
    source = _source(app_dir, module)
    if source is None:
        return
    for node in ast.walk(ast.parse(source.read_bytes())):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and _plain_name(node.value):
            beside = source.parent / node.value
            if beside.is_file():
                yield beside


def _plain_name(value: str) -> bool:
    return 0 < len(value) <= 120 and "/" not in value and "\\" not in value and "." in value.strip(".")


def _named(spec: CodeSpec, path: Path) -> str:
    return path.relative_to(spec.app_dir.parent).as_posix()
