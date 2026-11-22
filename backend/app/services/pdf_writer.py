from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from io import BytesIO
from itertools import pairwise
from typing import Literal

from fpdf import FPDF
from fpdf.enums import Align, MethodReturnValue, XPos, YPos

from app.data.export_assets import font_files
from app.research.vocabulary import ANSWER_LANGUAGE_SPECS, RIGHT_TO_LEFT_SCRIPTS

from .export_pictures import Picture

__all__ = [
    "ACCENT",
    "INK",
    "LINE_RATIO",
    "MUTED",
    "RULE",
    "SUNK",
    "Box",
    "Colour",
    "PdfWriter",
    "Point",
    "TextStyle",
]

LATIN_SCRIPT = "Latn"
LATIN_FAMILY = "kv-latn"
SCRIPT_FAMILY = "kv-text"
MARGIN_MM = 16.0
INK = (17, 24, 39)
MUTED = (75, 85, 99)
ACCENT = (91, 33, 182)
RULE = (209, 213, 219)
SUNK = (243, 244, 246)
CREDIT_SIZE = 8.0
LINE_RATIO = 0.5
PICTURE_GAP_MM = 2.0
CREDIT_LINES = 3
LINE_MM = 0.2
DASH_MM = (0.8, 0.6)
POLYGON_POINTS_MIN = 3

Orientation = Literal["portrait", "landscape"]
Colour = tuple[int, int, int]
Point = tuple[float, float]
TextAlign = Literal["L", "C", "R"]


@dataclass(frozen=True)
class TextStyle:
    size: float
    bold: bool = False
    colour: Colour = INK
    gap_after: float = 2.0


@dataclass(frozen=True)
class Box:
    x: float
    y: float
    width: float
    height: float


class PdfWriter:
    def __init__(self, language: str, *, orientation: Orientation, title: str) -> None:
        self._pdf = FPDF(orientation="L" if orientation == "landscape" else "P", unit="mm", format="A4")
        self._pdf.set_margins(MARGIN_MM, MARGIN_MM, MARGIN_MM)
        self._pdf.set_auto_page_break(auto=True, margin=MARGIN_MM)
        self._pdf.set_title(title)
        self._pdf.set_creator("KalaVigyan")
        script = ANSWER_LANGUAGE_SPECS[language].script
        self._align = Align.R if script in RIGHT_TO_LEFT_SCRIPTS else Align.L
        self._family = self._fonts(script)
        self._pdf.set_text_shaping(use_shaping_engine=True)

    @property
    def left(self) -> float:
        return float(self._pdf.l_margin)

    @property
    def width(self) -> float:
        return float(self._pdf.epw)

    @property
    def bottom(self) -> float:
        return float(self._pdf.h - self._pdf.b_margin)

    @property
    def y(self) -> float:
        return float(self._pdf.get_y())

    def new_page(self) -> None:
        self._pdf.add_page()

    def go_to(self, y: float) -> None:
        self._pdf.set_xy(self._pdf.l_margin, y)

    def text(self, text: str, style: TextStyle, *, link: str | None = None, width: float = 0) -> None:
        self._set(style)
        self._pdf.multi_cell(
            width,
            style.size * LINE_RATIO,
            text,
            align=self._align,
            link=link or "",
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )
        self._pdf.ln(style.gap_after)

    def item(
        self, label: str, text: str, style: TextStyle, *, link: str | None = None, width: float = 0
    ) -> None:
        self._set(style)
        indent = self._pdf.get_string_width(f"{label} ") + 1.0
        top = self._pdf.get_y()
        self._pdf.cell(indent, style.size * LINE_RATIO, label)
        self._pdf.set_xy(self._pdf.l_margin + indent, top)
        self._pdf.multi_cell(
            (width or self.width) - indent,
            style.size * LINE_RATIO,
            text,
            align=self._align,
            link=link or "",
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )
        self._pdf.ln(style.gap_after)

    def picture(self, picture: Picture, credit: str, *, x: float, width: float, max_height: float) -> float:
        credit_room = CREDIT_LINES * CREDIT_SIZE * LINE_RATIO + PICTURE_GAP_MM
        scale = min(width / picture.width, (max_height - credit_room) / picture.height)
        shown_w, shown_h = picture.width * scale, picture.height * scale
        top = self._pdf.get_y()
        if top + shown_h + credit_room > self.bottom:
            self.new_page()
            top = self._pdf.get_y()
        self._pdf.image(BytesIO(picture.data), x=x, y=top, w=shown_w, h=shown_h, alt_text=credit)
        self._set(TextStyle(size=CREDIT_SIZE, colour=MUTED))
        self._pdf.set_xy(x, top + shown_h + PICTURE_GAP_MM)
        self._pdf.multi_cell(width, CREDIT_SIZE * LINE_RATIO, credit, align=self._align, new_y=YPos.NEXT)
        return float(self._pdf.get_y())

    def room(self, height: float) -> float:
        if self._pdf.get_y() + height > self.bottom:
            self.new_page()
        return self.y

    def rect(
        self, box: Box, *, fill: Colour | None = None, line: Colour | None = None, dashed: bool = False
    ) -> None:
        self._paint(fill, line, dashed=dashed)
        self._pdf.rect(box.x, box.y, box.width, box.height, style=_style(fill, line))
        self._pdf.set_dash_pattern()

    def shape(
        self, points: Sequence[Point], *, fill: Colour | None = None, line: Colour | None = None
    ) -> None:
        if len(points) < POLYGON_POINTS_MIN:
            return
        self._paint(fill, line, dashed=False)
        self._pdf.polygon(list(points), style=_style(fill, line))

    def stroke(self, points: Sequence[Point], colour: Colour) -> None:
        self._paint(None, colour, dashed=False)
        for start, end in pairwise(points):
            self._pdf.line(*start, *end)

    def label(self, text: str, style: TextStyle, box: Box, *, align: TextAlign = "L") -> None:
        self._set(style)
        self._pdf.set_xy(box.x, box.y)
        self._pdf.cell(box.width, box.height, text, align=align)

    def line_count(self, text: str, style: TextStyle, width: float) -> int:
        self._set(style)
        lines = self._pdf.multi_cell(
            width, style.size * LINE_RATIO, text, dry_run=True, output=MethodReturnValue.LINES
        )
        return len(lines) if isinstance(lines, list) else 1

    def output(self) -> bytes:
        return bytes(self._pdf.output())

    def _set(self, style: TextStyle) -> None:
        self._pdf.set_font(self._family, "B" if style.bold else "", style.size)
        self._pdf.set_text_color(*style.colour)

    def _paint(self, fill: Colour | None, line: Colour | None, *, dashed: bool) -> None:
        self._pdf.set_line_width(LINE_MM)
        if fill is not None:
            self._pdf.set_fill_color(*fill)
        if line is not None:
            self._pdf.set_draw_color(*line)
        if dashed:
            self._pdf.set_dash_pattern(dash=DASH_MM[0], gap=DASH_MM[1])

    def _fonts(self, script: str) -> str:
        latin = font_files(LATIN_SCRIPT)
        self._pdf.add_font(LATIN_FAMILY, "", latin.regular)
        self._pdf.add_font(LATIN_FAMILY, "B", latin.bold)
        if script == LATIN_SCRIPT:
            return LATIN_FAMILY
        own = font_files(script)
        self._pdf.add_font(SCRIPT_FAMILY, "", own.regular)
        self._pdf.add_font(SCRIPT_FAMILY, "B", own.bold)
        self._pdf.set_fallback_fonts([LATIN_FAMILY], exact_match=False)
        return SCRIPT_FAMILY


def _style(fill: Colour | None, line: Colour | None) -> str:
    if fill is not None and line is not None:
        return "DF"
    return "F" if fill is not None else "D"
