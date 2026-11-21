from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from app.research.monograph_page import ComponentEntry
from app.research.why_here import WHY_HERE_KIND, CraftGround, GroundNote, WhyHereSpec

from .monograph_generated_units import DraftUnit

__all__ = [
    "NOTES_MAX",
    "NOTE_TERMS",
    "WHY_CHAPTER",
    "PlacingPage",
    "WhyHerePlaced",
    "ground_hash",
    "kept_refs",
    "note_readings",
    "place_why_here",
    "why_here_entry",
    "why_here_label",
    "why_here_placed",
    "with_why_here",
]

WHY_CHAPTER = "why"
WHY_FIELD = "GEOGRAPHY"
WHY_FIELDS = ("GEOGRAPHY", "GEOLOGY", "CLIMATE", "ECOLOGY")
LABEL_TAIL = "geography/why-here"
HEADING_PREFIX = "h-"
SENTENCE_TAG = "p"
NOTES_MAX = 8
NOTES_PER_READING = 2
CHAPTER_OPEN = '<section class="kv-ch"'
WHY_SECTION = re.compile(r'<section class="kv-ch" id="why[a-z0-9-]*"[^>]*>')
SECTION_CLOSE = "</section>"
SHELL_SLOT = '<div class="kv-page kv-why-here" data-app=""><kv-slot component="{label}"></kv-slot></div>'
NOTE_TERMS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "deposits",
        ("mine", "mines", "mined", "mineral", "minerals", "ore", "ores", "deposit", "deposits", "quarry"),
    ),
    ("river", ("river", "rivers", "stream", "streams", "riverbed", "running water")),
    ("lake", ("lake", "lakes", "tank", "tanks", "pond", "ponds", "reservoir", "reservoirs")),
    ("soil", ("soil", "soils", "clay", "silt", "alluvial", "alluvium", "earth", "mud")),
    ("rainfall", ("rain", "rains", "rainfall", "monsoon", "arid", "humid", "humidity", "drought")),
    (
        "elevation",
        ("hill", "hills", "plateau", "plain", "plains", "mountain", "mountains", "altitude", "valley"),
    ),
    ("cover", ("forest", "forests", "tree", "trees", "grassland", "grasslands")),
)
PATTERNS = tuple(
    (reading, re.compile(r"\b(" + "|".join(re.escape(term) for term in terms) + r")\b"))
    for reading, terms in NOTE_TERMS
)


@dataclass(frozen=True)
class WhyHerePlaced:
    label: str
    entry: ComponentEntry
    spec: dict[str, Any]
    held: tuple[str, ...]
    kept: tuple[str, ...]


def why_here_label(slug: str) -> str:
    stem = re.sub(r"-+", "-", re.sub(r"[^a-z0-9-]", "", slug.lower())).strip("-")
    return f"{stem}/{LABEL_TAIL}"


def why_here_entry(ground: CraftGround, label: str) -> ComponentEntry:
    name = ground.craft.name
    return ComponentEntry(
        label=label,
        chapter=WHY_CHAPTER,
        anchor="#" + label.replace("/", "--"),
        kind=WHY_HERE_KIND,
        title=f"The ground under {name}",
        description=(
            f"A map of where {name} is practised over relief, rivers and recorded mineral deposits, "
            f"with each place's measured ground beside it."
        ),
        field=WHY_FIELD,
        fields=list(WHY_FIELDS),
        subjects=[f"craft:{ground.craft.slug}"],
    )


def _shown(ground: CraftGround) -> set[str]:
    grounds = [place.ground for place in ground.places]
    shown = {"elevation"}
    shown |= {"river"} if any(g.river for g in grounds) else set()
    shown |= {"lake"} if any(g.lake for g in grounds) else set()
    shown |= {"deposits"} if any(g.deposit_total for g in grounds) else set()
    return shown | {reading.reading for g in grounds for reading in g.readings}


def note_readings(drafts: Sequence[DraftUnit], ground: CraftGround) -> list[GroundNote]:
    shown = _shown(ground)
    notes: list[GroundNote] = []
    for draft in drafts:
        if draft.tag != SENTENCE_TAG or draft.field not in WHY_FIELDS or len(notes) >= NOTES_MAX:
            continue
        text = draft.text.casefold()
        for reading, pattern in PATTERNS:
            taken = sum(1 for note in notes if note.reading == reading)
            if reading in shown and taken < NOTES_PER_READING and pattern.search(text):
                notes.append(GroundNote(reading=reading, unit=draft.unit_id))
                break
    return notes


def kept_refs(refs: Sequence[str], held: set[str]) -> tuple[str, ...]:
    kept: list[str] = []
    for ref in refs:
        if ref in held:
            continue
        if kept and kept[-1].startswith(HEADING_PREFIX) and ref.startswith(HEADING_PREFIX):
            kept.pop()
        kept.append(ref)
    if kept and kept[-1].startswith(HEADING_PREFIX):
        kept.pop()
    return tuple(kept)


def _slotted(shell: str, label: str) -> str | None:
    opened = WHY_SECTION.search(shell)
    if opened is None:
        return None
    following = shell.find(CHAPTER_OPEN, opened.end())
    end = shell.rfind(SECTION_CLOSE, opened.end(), following if following >= 0 else len(shell))
    if end < 0:
        return None
    return shell[:end] + SHELL_SLOT.format(label=label) + shell[end:]


def _laid(layout: Sequence[Mapping[str, Any]], label: str) -> list[Mapping[str, Any]] | None:
    placed = [at for at, entry in enumerate(layout) if entry.get("chapter") == WHY_CHAPTER]
    if not placed:
        return None
    at = placed[-1] + 1
    entry = {"chapter": WHY_CHAPTER, "kind": "component", "ref": label, "within": None}
    return [*layout[:at], entry, *layout[at:]]


def with_why_here(body: Mapping[str, Any], ground: CraftGround | None) -> Mapping[str, Any]:
    content: Mapping[str, Any] = body.get("content") or {}
    components = list(content.get("components") or [])
    if ground is None or any(component.get("kind") == WHY_HERE_KIND for component in components):
        return body
    label = why_here_label(str(body.get("subjectSlug") or ground.craft.slug))
    shell = body.get("shell")
    layout: list[Mapping[str, Any]] | None = list(content.get("layout") or [])
    slotted = _slotted(shell, label) if isinstance(shell, str) else None
    if not isinstance(shell, str):
        layout = _laid(layout or [], label)
    if (isinstance(shell, str) and slotted is None) or layout is None:
        return body
    entry = why_here_entry(ground, label).model_dump(mode="json", by_alias=True)
    spec = WhyHereSpec(ground=ground, notes=[]).model_dump(mode="json", by_alias=True)
    placed = {**content, "components": [*components, entry], "layout": layout}
    shelled = {"shell": slotted} if slotted is not None else {}
    return {**body, **shelled, "content": placed, "specs": {**(body.get("specs") or {}), label: spec}}


def why_here_placed(
    ground: CraftGround | None, slug: str, refs: Sequence[str], drafts: Mapping[str, DraftUnit]
) -> WhyHerePlaced | None:
    if ground is None:
        return None
    label = why_here_label(slug)
    notes = note_readings([drafts[ref] for ref in refs if ref in drafts], ground)
    held = tuple(note.unit for note in notes)
    spec = WhyHereSpec(ground=ground, notes=notes).model_dump(mode="json", by_alias=True)
    return WhyHerePlaced(
        label=label,
        entry=why_here_entry(ground, label),
        spec=spec,
        held=held,
        kept=kept_refs(refs, set(held)),
    )


def ground_hash(content_hash: str, ground: CraftGround | None) -> str:
    if ground is None:
        return content_hash
    folded = f"{content_hash}:{ground.model_dump_json(by_alias=True)}"
    return hashlib.sha256(folded.encode("utf-8")).hexdigest()


class PlacingPage(Protocol):
    drafts: dict[str, DraftUnit]
    components: dict[str, ComponentEntry]
    specs: dict[str, dict[str, Any]]
    held: dict[str, list[str]]


def place_why_here(
    ground: CraftGround | None,
    slug: str,
    page: PlacingPage,
    found: tuple[dict[str, list[str]], dict[str, list[str]]],
) -> None:
    texts, components = found
    placed = why_here_placed(ground, slug, texts.get(WHY_CHAPTER, []), page.drafts)
    if placed is None:
        return
    page.components[placed.label] = placed.entry
    page.specs[placed.label] = placed.spec
    page.held[placed.label] = list(placed.held)
    texts[WHY_CHAPTER] = list(placed.kept)
    components.setdefault(WHY_CHAPTER, []).append(placed.label)
