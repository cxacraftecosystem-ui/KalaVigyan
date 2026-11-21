from __future__ import annotations

import re
from pathlib import Path

from design.build import build, render
from design.colour import contrast, delta_e, from_oklch
from design.system import load_system
from design_tokens import REPO_ROOT, stale_outputs, write_outputs

SYSTEM = load_system()
OUTPUTS, VIOLATIONS = render(SYSTEM)


def _block(css: str, selector: str) -> str:
    start = css.index(f"{selector} {{")
    return css[start : css.index("}", start)]


def test_the_written_tokens_are_what_the_generator_writes() -> None:
    assert stale_outputs(REPO_ROOT, OUTPUTS) == []


def test_the_approved_token_set_breaks_no_check() -> None:
    assert VIOLATIONS == []


def test_wcag_contrast_and_oklab_distance_match_their_definitions() -> None:
    assert round(contrast("#000000", "#FFFFFF"), 2) == 21.0
    assert round(contrast("#767676", "#FFFFFF"), 2) == 4.54
    assert delta_e("#243B9C", "#243B9C") == 0
    assert from_oklch(1.0, 0.0, 0.0) == "#FFFFFF"


def test_os_contrast_with_the_app_on_dark_gives_high_contrast_dark() -> None:
    css = OUTPUTS["tokens.css"]
    start = css.index(
        '@media (prefers-contrast: more) {\n  :root[data-theme="dark"]:not([data-high-contrast="false"]) {'
    )
    rule = css[start : css.index("}", start)]
    assert "--c-ground: 0 0 0;" in rule
    assert "--c-ink-1: 255 255 255;" in rule
    light = css.index('@media (prefers-contrast: more) {\n  :root:not([data-high-contrast="false"]) {')
    assert light < start


def test_the_font_stacks_name_the_metric_matched_fallbacks_and_every_script_face() -> None:
    root = _block(OUTPUTS["tokens.css"], ":root")
    ui = re.search(r"--font-ui: ([^;]+);", root)
    assert ui is not None
    faces = ui.group(1)
    assert faces.startswith('"IBM Plex Sans", "Noto Sans Devanagari"')
    assert faces.count('"Noto Sans Arabic"') == 1
    assert (
        faces.index('"Noto Sans Ol Chiki"') < faces.index('"plexSans Fallback"') < faces.index('"Noto Sans"')
    )
    assert re.search(r'--font-headline: "Newsreader", "newsreader Fallback",', root)


def test_photo_and_scrim_colours_are_static_tokens() -> None:
    root = _block(OUTPUTS["tokens.css"], ":root")
    assert "--photo-indigo: rgb(36 59 156);" in root
    assert "--scrim-deep: rgb(8 10 16 / 0.92);" in root
    assert "--plate-edge: rgb(0 0 0 / 0.1);" in root
    assert "--photo-indigo" not in _block(OUTPUTS["tokens.css"], ':root[data-theme="dark"]')


def test_the_numeral_size_is_fluid_only_from_the_rail_breakpoint() -> None:
    numeral = build(SYSTEM)["type"]["scale"]["numeral"]
    assert numeral["phone"] is None
    assert numeral["tablet"] is None
    assert numeral["fluidRange"] == [1200, 1920]
    assert numeral["projector"] == 88


OUTPUT_FOLDERS = (
    ".claude/skills/kalavigyan-design/references",
    "frontend/app",
    "frontend/lib",
    "backend/app/data/design",
    "backend/app/research",
)


def test_the_outputs_are_written_where_the_app_and_the_skill_read_them(tmp_path: Path) -> None:
    for folder in OUTPUT_FOLDERS:
        (tmp_path / folder).mkdir(parents=True)
    assert len(stale_outputs(tmp_path, OUTPUTS)) == 7


def test_the_backend_s_tokens_resource_is_written_by_the_generator_as_the_skill_s(tmp_path: Path) -> None:
    for folder in OUTPUT_FOLDERS:
        (tmp_path / folder).mkdir(parents=True)
    write_outputs(tmp_path, OUTPUTS)
    served = tmp_path / "backend/app/data/design/tokens.json"
    skill = tmp_path / ".claude/skills/kalavigyan-design/references/tokens.json"
    assert served.read_bytes() == skill.read_bytes() == OUTPUTS["tokens.json"].encode("utf-8")
    assert stale_outputs(tmp_path, OUTPUTS) == []
