from __future__ import annotations

import re
from pathlib import Path

from webfonts.build import git_blob
from webfonts.ranges import ARROWS, KEPT_FEATURES, LATIN, LATIN_EXT, NEWSREADER_FACES, codepoints, css_range

REPO_ROOT = Path(__file__).resolve().parents[2]
LATIN_FONTS = REPO_ROOT / "frontend" / "app" / "latinFonts.ts"
FACE_BLOCK = re.compile(r"const (\w+) = localFont\(\{(.*?)\n\}\);", re.DOTALL)
RANGE_VALUE = re.compile(r'"unicode-range", value: "([^"]+)"')
SOURCE_FILE = re.compile(r'"\.\./fonts/([^"]+\.woff2)"')

GOOGLE_LATIN_WITH_ARROWS = (
    "U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+0304, U+0308, U+0329, "
    "U+2000-206F, U+20AC, U+2122, U+2190-2199, U+2212, U+2215, U+FEFF, U+FFFD"
)
GOOGLE_LATIN_EXT_WITHOUT_ARROWS = (
    "U+0100-02BA, U+02BD-02C5, U+02C7-02CC, U+02CE-02D7, U+02DD-02FF, U+0300-036F, U+1D00-1DBF, U+1E00-1EFF, "
    "U+2070-209F, U+20A0-20AB, U+20AD-20C0, U+2100-214F, U+2150-218F, U+219A-21FF, U+2200-2211, U+2213-2214, "
    "U+2216-22FF, U+2C60-2C7F, U+A720-A7FF, U+FB00-FB06"
)


def declared_faces() -> dict[str, tuple[list[str], list[str]]]:
    text = LATIN_FONTS.read_text(encoding="utf-8")
    return {
        name: (RANGE_VALUE.findall(body), SOURCE_FILE.findall(body))
        for name, body in FACE_BLOCK.findall(text)
    }


def test_the_latin_subset_is_google_latin_with_every_arrow_and_latin_ext_gives_them_up() -> None:
    assert css_range(LATIN) == GOOGLE_LATIN_WITH_ARROWS
    assert css_range(LATIN_EXT) == GOOGLE_LATIN_EXT_WITHOUT_ARROWS


def test_the_vat_equation_arrow_is_drawn_from_the_latin_subset_alone() -> None:
    arrows = set(range(ARROWS[0], ARROWS[1] + 1))
    assert 0x2192 in arrows
    assert arrows <= codepoints(LATIN)
    assert not arrows & codepoints(LATIN_EXT)


def test_the_page_declares_the_ranges_the_generator_subsets_to() -> None:
    faces = declared_faces()
    assert faces["newsreader"] == ([GOOGLE_LATIN_WITH_ARROWS], ["newsreader-latin-var.woff2"])
    assert faces["newsreaderItalic"] == ([GOOGLE_LATIN_WITH_ARROWS], ["newsreader-italic-latin-var.woff2"])
    assert faces["newsreaderExtended"] == (
        [GOOGLE_LATIN_EXT_WITHOUT_ARROWS],
        ["newsreader-latin-ext-var.woff2", "newsreader-italic-latin-ext-var.woff2"],
    )
    written = {output.name for output in NEWSREADER_FACES}
    declared = {name for ranges, files in faces.values() for name in files if name.startswith("newsreader")}
    assert written == declared


def test_the_subset_keeps_the_figures_and_shaping_the_site_uses_and_drops_the_rest() -> None:
    assert {"kern", "liga", "rvrn", "lnum", "onum", "pnum", "tnum", "case", "mark", "mkmk"} <= set(
        KEPT_FEATURES
    )
    assert not {"smcp", "c2sc", "sups", "subs", "sinf", "frac", "ordn", "dlig", "salt", "ss01"} & set(
        KEPT_FEATURES
    )


def test_a_source_is_checked_against_its_git_blob() -> None:
    assert git_blob(b"") == "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391"
    assert git_blob(b"hello\n") == "ce013625030ba8dba906f756967f9e9ca394464a"
