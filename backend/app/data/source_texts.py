from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

__all__ = [
    "SOURCE_FILE",
    "SOURCE_TEXTS_DIR",
    "SOURCE_TEXT_SCHEMA_VERSION",
    "SourcePage",
    "VendoredText",
    "chapter_pages",
    "load_vendored_texts",
    "vendored_texts",
]

SOURCE_TEXTS_DIR = Path(__file__).resolve().parent / "source_texts"
SOURCE_FILE = "source.json"
SOURCE_TEXT_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class SourcePage:
    chapter: int
    chapter_title: str
    page: str
    text: str

    @property
    def locator(self) -> str:
        return f"Chapter {self.chapter}, {self.chapter_title}, p. {self.page}"


@dataclass(frozen=True)
class VendoredText:
    seed_source: str
    title: str
    pages: tuple[SourcePage, ...]


@cache
def vendored_texts() -> tuple[VendoredText, ...]:
    return load_vendored_texts(SOURCE_TEXTS_DIR)


def load_vendored_texts(directory: Path) -> tuple[VendoredText, ...]:
    return tuple(_vendored(record) for record in sorted(directory.glob(f"*/{SOURCE_FILE}")))


def chapter_pages(chapter: int, title: str, text: str) -> list[SourcePage]:
    label = re.compile(rf"{chapter}-(\d+)")
    pages: list[SourcePage] = []
    lines: list[str] = []
    page = 0
    for line in text.split("\n"):
        found = label.fullmatch(line.strip())
        if found is not None and int(found.group(1)) > page:
            if page:
                pages.append(SourcePage(chapter, title, f"{chapter}-{page}", "\n".join(lines)))
                lines = []
            page = int(found.group(1))
            continue
        lines.append(line)
    if not page:
        raise ValueError(f"chapter {chapter} of {title!r} names no page")
    pages.append(SourcePage(chapter, title, f"{chapter}-{page}", "\n".join(lines)))
    return [found for found in pages if found.text.strip()]


def _vendored(record: Path) -> VendoredText:
    body = json.loads(record.read_text(encoding="utf-8"))
    if body.get("schemaVersion") != SOURCE_TEXT_SCHEMA_VERSION:
        raise ValueError(f"{record} is not schema version {SOURCE_TEXT_SCHEMA_VERSION}")
    pages = [page for chapter in body["chapters"] for page in _chapter(record.parent, chapter)]
    return VendoredText(seed_source=body["seedSource"], title=body["title"], pages=tuple(pages))


def _chapter(folder: Path, chapter: dict[str, Any]) -> list[SourcePage]:
    stored = (folder / chapter["file"]).read_text(encoding="utf-8")
    text = stored.removesuffix("\n")
    if hashlib.sha256(text.encode("utf-8")).hexdigest() != chapter["textSha256"]:
        raise ValueError(f"{folder / chapter['file']} is not the text its reader read (textSha256 differs)")
    return chapter_pages(int(chapter["chapter"]), chapter["title"], text)
