from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from html.parser import HTMLParser
from types import MappingProxyType
from typing import Any

from app.research.monograph_page import COMPONENT_SLOT, SLOT_PATTERN
from app.research.spec_strings import spec_strings

from .monograph_document import (
    MONOGRAPHS_DIR,
    component_specs,
    has_authored_content,
    monograph_content,
    monograph_shell,
    native_views,
    page_parts,
)

__all__ = [
    "BOX_CLASSES",
    "FRAME_ATTRIBUTES",
    "ComponentHome",
    "FrameStep",
    "HomeSource",
    "authored_home_source",
    "authored_homes",
    "component_homes",
    "frame_steps",
    "home_scopes",
    "homes_body",
    "kind_scopes",
    "spec_keys",
]

SCOPE_CLASS = "bx"
SCOPE_PREFIX = "bx-"
CHAPTER_CLASS = "kv-ch"
BOX_CLASSES = frozenset({"screen", "wrap", "kv-wrap"})
COLUMN_HOST = "spread"
COLUMN_CLASS = "main"
FRAGMENT_TAG = "kv-fragment"
FRAME_ATTRIBUTES = ("lang", "dir", "data-ui-lang")
SLOT_TAG = "kv-slot"
VOID_TAGS = frozenset(
    {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }
)
MONOGRAPH_SLUG = re.compile(r"^[A-Za-z0-9-]+$")
SCOPES_CACHED = 32
FIRST_TAG = re.compile(r"<([a-zA-Z][a-zA-Z0-9-]*)([^>]*)>")
ATTRIBUTE = re.compile(r'([a-zA-Z_:][-a-zA-Z0-9_:.]*)="([^"]*)"')

Marks = tuple[tuple[str, str], ...]
Ancestor = tuple[str, tuple[str, ...], Marks]


@dataclass(frozen=True)
class FrameStep:
    classes: tuple[str, ...]
    box: bool
    attrs: Marks = ()


@dataclass(frozen=True)
class ComponentHome:
    kind: str
    scope: str | None
    frame: tuple[FrameStep, ...]
    root: str | None
    within: str | None = None


@dataclass(frozen=True)
class HomeSource:
    shell: str
    fragments: Mapping[str, str]
    specs: Mapping[str, Mapping[str, Any]]
    kinds: Mapping[str, str]
    native: frozenset[str]


class _Ancestry(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[Ancestor] = []
        self.found: dict[str, tuple[Ancestor, ...]] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        named = dict(attrs)
        label = named.get(COMPONENT_SLOT)
        if tag == SLOT_TAG and label:
            self.found.setdefault(label, tuple(a for a in self.stack if a[0] != FRAGMENT_TAG))
        if tag not in VOID_TAGS:
            marks = tuple((name, value) for name in FRAME_ATTRIBUTES if (value := named.get(name)))
            self.stack.append((tag, tuple((named.get("class") or "").split()), marks))

    def handle_endtag(self, tag: str) -> None:
        for at in range(len(self.stack) - 1, -1, -1):
            if self.stack[at][0] == tag:
                del self.stack[at:]
                return


def component_homes(source: HomeSource) -> dict[str, ComponentHome]:
    parser = _Ancestry()
    parser.feed(_expanded(source.shell, source))
    parser.close()
    homes = {
        label: _home(source, label, ancestors)
        for label, ancestors in parser.found.items()
        if label in source.kinds
    }
    for label in source.kinds:
        if label not in homes:
            parent = _parent(source, label, homes)
            if parent is not None:
                homes[label] = _nested(source, label, homes[parent], parent)
    return dict(sorted(homes.items()))


def _expanded(text: str, source: HomeSource, held: tuple[str, ...] = ()) -> str:
    def fill(found: re.Match[str]) -> str:
        label = found.group(2)
        if found.group(1) != COMPONENT_SLOT or label in source.native or label in held:
            return found.group(0)
        fragment = source.fragments.get(label)
        if fragment is None:
            return found.group(0)
        inner = _expanded(fragment, source, (*held, label))
        return f"{found.group(0)}<{FRAGMENT_TAG}>{inner}</{FRAGMENT_TAG}>"

    return SLOT_PATTERN.sub(fill, text)


def _home(source: HomeSource, label: str, ancestors: tuple[Ancestor, ...]) -> ComponentHome:
    classes = [found for _, found, _ in ancestors]
    start = _last(classes, SCOPE_CLASS)
    scope = None
    if start is not None:
        scope = next(
            (name[len(SCOPE_PREFIX) :] for name in classes[start] if name.startswith(SCOPE_PREFIX)), None
        )
    else:
        start = _last(classes, CHAPTER_CLASS)
    first = start + 1 if start is not None else 0
    return ComponentHome(
        kind=source.kinds[label],
        scope=scope,
        frame=frame_steps(classes[first:], [marks for _, _, marks in ancestors[first:]]),
        root=_root(source.fragments.get(label)),
    )


def frame_steps(chain: list[tuple[str, ...]], marks: list[Marks] | None = None) -> tuple[FrameStep, ...]:
    steps: list[FrameStep] = []
    for at, classes in enumerate(chain):
        held = marks[at] if marks else ()
        following = chain[at + 1] if at + 1 < len(chain) else ()
        if COLUMN_CLASS in classes or (COLUMN_HOST in classes and COLUMN_CLASS in following):
            steps.append(FrameStep(classes, box=True, attrs=held))
            continue
        boxed = tuple(name for name in classes if name in BOX_CLASSES)
        rest = tuple(name for name in classes if name not in BOX_CLASSES)
        if rest or not boxed:
            steps.append(FrameStep(rest, box=False, attrs=held))
            held = ()
        if boxed:
            steps.append(FrameStep(boxed, box=True, attrs=held))
    return tuple(steps)


def _last(chain: list[tuple[str, ...]], name: str) -> int | None:
    found = [at for at, classes in enumerate(chain) if name in classes]
    return found[-1] if found else None


def _parent(source: HomeSource, label: str, homes: Mapping[str, ComponentHome]) -> str | None:
    for parent in homes:
        named = spec_strings(source.specs.get(parent))
        slotted = SLOT_PATTERN.findall(source.fragments.get(parent, ""))
        if label in named or (COMPONENT_SLOT, label) in slotted:
            return parent
    return None


def _nested(source: HomeSource, label: str, parent: ComponentHome, within: str) -> ComponentHome:
    root = _root(source.fragments.get(label))
    return ComponentHome(kind=source.kinds[label], scope=parent.scope, frame=(), root=root, within=within)


def _root(fragment: str | None) -> str | None:
    found = FIRST_TAG.search(fragment or "")
    if found is None:
        return None
    attrs = dict(ATTRIBUTE.findall(found.group(2)))
    named = f"#{attrs['id']}" if attrs.get("id") else ""
    return found.group(1).lower() + named + "".join(f".{name}" for name in attrs.get("class", "").split())


def spec_keys(spec: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(sorted(key for key, value in spec.items() if value not in (None, "", [], {})))


def kind_scopes(source: HomeSource, homes: Mapping[str, ComponentHome]) -> dict[str, list[dict[str, Any]]]:
    found: dict[str, list[dict[str, Any]]] = {}
    for label, spec in sorted(source.specs.items()):
        home = homes.get(label)
        if home is None or home.within is not None:
            continue
        entry = {"scope": home.scope, "keys": list(spec_keys(spec))}
        listed = found.setdefault(home.kind, [])
        if entry not in listed:
            listed.append(entry)
    return dict(sorted(found.items()))


def homes_body(source: HomeSource) -> dict[str, Any]:
    homes = component_homes(source)
    return {
        "homes": {label: _home_body(home) for label, home in homes.items()},
        "kinds": kind_scopes(source, homes),
    }


def _home_body(home: ComponentHome) -> dict[str, Any]:
    body: dict[str, Any] = {
        "kind": home.kind,
        "scope": home.scope,
        "frame": [_step_body(step) for step in home.frame],
        "root": home.root,
    }
    if home.within is not None:
        body["within"] = home.within
    return body


def _step_body(step: FrameStep) -> dict[str, Any]:
    body: dict[str, Any] = {"classes": list(step.classes), "box": step.box}
    if step.attrs:
        body["attrs"] = dict(step.attrs)
    return body


def authored_home_source(slug: str) -> HomeSource:
    content = monograph_content(slug)
    return HomeSource(
        shell=monograph_shell(slug),
        fragments=page_parts(content).fragments,
        specs=component_specs(content),
        kinds={component.label: component.kind for component in content.components},
        native=native_views(slug),
    )


@lru_cache(maxsize=SCOPES_CACHED)
def home_scopes(monograph: str) -> Mapping[str, str | None]:
    if not MONOGRAPH_SLUG.fullmatch(monograph) or not has_authored_content(monograph):
        return MappingProxyType({})
    homes = component_homes(authored_home_source(monograph))
    return MappingProxyType({label: home.scope for label, home in homes.items()})


def authored_homes() -> dict[str, Any]:
    slugs = sorted(
        path.name for path in MONOGRAPHS_DIR.iterdir() if path.is_dir() and has_authored_content(path.name)
    )
    homes: dict[str, Any] = {}
    kinds: dict[str, list[dict[str, Any]]] = {}
    for slug in slugs:
        body = homes_body(authored_home_source(slug))
        homes.update(body["homes"])
        for kind, entries in body["kinds"].items():
            listed = kinds.setdefault(kind, [])
            listed.extend(entry for entry in entries if entry not in listed)
    return {"homes": dict(sorted(homes.items())), "kinds": dict(sorted(kinds.items()))}
