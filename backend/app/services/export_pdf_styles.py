from __future__ import annotations

from .pdf_writer import ACCENT, LINE_RATIO, MUTED, TextStyle

__all__ = [
    "CELL",
    "CELL_BOLD",
    "FIGURE_GAP_MM",
    "FIGURE_TITLE",
    "KICKER",
    "LABEL_COLUMN_MM",
    "NOTE",
    "cell_height",
]

KICKER = TextStyle(size=8.5, bold=True, colour=ACCENT, gap_after=1)
FIGURE_TITLE = TextStyle(size=11, bold=True, gap_after=2)
NOTE = TextStyle(size=8, colour=MUTED, gap_after=2)
CELL = TextStyle(size=8.5)
CELL_BOLD = TextStyle(size=8.5, bold=True)
LABEL_COLUMN_MM = 42.0
FIGURE_GAP_MM = 3.0


def cell_height(style: TextStyle) -> float:
    return style.size * LINE_RATIO
