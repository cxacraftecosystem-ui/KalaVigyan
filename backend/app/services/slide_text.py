from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .pdf_writer import PdfWriter, TextStyle

__all__ = [
    "LINE_HEIGHT_RATIO",
    "SPACE_AFTER_RATIO",
    "Ladder",
    "SizedText",
    "SlideText",
    "TextFrameSize",
]

EMU_PER_POINT = 12700
MM_PER_POINT = 25.4 / 72
LINE_HEIGHT_RATIO = 1.5
SPACE_AFTER_RATIO = 0.4
SIDE_INSET_POINTS = 7.2
END_INSET_POINTS = 3.6


@dataclass(frozen=True)
class TextFrameSize:
    width: int
    height: int

    @property
    def text_width_points(self) -> float:
        return self.width / EMU_PER_POINT - 2 * SIDE_INSET_POINTS

    @property
    def text_height_points(self) -> float:
        return self.height / EMU_PER_POINT - 2 * END_INSET_POINTS


@dataclass(frozen=True)
class Ladder:
    sizes: tuple[int, ...]
    bold: bool = False

    @property
    def smallest(self) -> int:
        return self.sizes[-1]


@dataclass(frozen=True)
class SizedText:
    lines: tuple[str, ...]
    size: int
    start: int = 0


class SlideText:
    def __init__(self, language: str) -> None:
        self._writer = PdfWriter(language, orientation="landscape", title=language)
        self._writer.new_page()

    def line_height(self, line: str, size: int, frame: TextFrameSize, *, bold: bool = False) -> float:
        style = TextStyle(size=size, bold=bold)
        rows = self._writer.line_count(line, style, frame.text_width_points * MM_PER_POINT)
        return size * (rows * LINE_HEIGHT_RATIO + SPACE_AFTER_RATIO)

    def fitted(self, lines: Sequence[str], frame: TextFrameSize, ladder: Ladder) -> int | None:
        room = frame.text_height_points
        for size in ladder.sizes:
            if sum(self.line_height(line, size, frame, bold=ladder.bold) for line in lines) <= room:
                return size
        return None

    def sized(self, lines: Sequence[str], frame: TextFrameSize, ladder: Ladder) -> int:
        return self.fitted(lines, frame, ladder) or ladder.smallest

    def pages(self, lines: Sequence[str], frame: TextFrameSize, ladder: Ladder) -> list[SizedText]:
        whole = self.fitted(lines, frame, ladder)
        if whole is not None or len(lines) <= 1:
            return [SizedText(tuple(lines), whole or ladder.smallest)]
        return [
            SizedText(tuple(lines[start:end]), self.sized(lines[start:end], frame, ladder), start)
            for start, end in self._spans(lines, frame, ladder)
        ]

    def _spans(self, lines: Sequence[str], frame: TextFrameSize, ladder: Ladder) -> list[tuple[int, int]]:
        room = frame.text_height_points
        spans: list[tuple[int, int]] = []
        start, used = 0, 0.0
        for index, line in enumerate(lines):
            needed = self.line_height(line, ladder.smallest, frame, bold=ladder.bold)
            if index > start and used + needed > room:
                spans.append((start, index))
                start, used = index, 0.0
            used += needed
        spans.append((start, len(lines)))
        return spans
