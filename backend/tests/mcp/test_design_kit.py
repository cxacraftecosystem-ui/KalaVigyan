import json
import re
from pathlib import Path
from typing import Any

from app.api.mcp_resources import resource_list, resource_read
from app.data.answer_kit import answer_view
from app.data.design_palette import THEMES, design_palettes
from app.data.drawing_kit import DRAWING_GUIDE_URI, TOKENS_CSS_URI
from app.data.page_preview_view import page_preview_view
from app.research.drawing_roles import DRAWING_ROLES
from app.research.drawing_themes import mixed_hex
from app.services.drawing_themes import themed_picture, themed_spec

REPOSITORY = Path(__file__).resolve().parents[3]
TOKENS: dict[str, Any] = json.loads(
    (REPOSITORY / ".claude" / "skills" / "kalavigyan-design" / "references" / "tokens.json").read_text(
        "utf-8"
    )
)
SITE = "https://kalavigyan.example"
ROLE_DRAWING = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 200">'
    '<rect width="9" height="9" fill="var(--ink-1)" stroke="var(--rain-2)"/>'
    '<circle r="4" fill="color-mix(in srgb, var(--ink-1) 50%, var(--ground))"/></svg>'
)


def colour(name: str, theme: str) -> str:
    return str(TOKENS["color"][name][theme]["hex"])


def test_every_drawing_role_has_a_value_in_each_of_the_four_themes() -> None:
    palettes = design_palettes()
    for theme in THEMES:
        assert set(palettes[theme]) >= DRAWING_ROLES, theme
    assert palettes["dark"]["ink-1"] == colour("ink-1", "dark")
    assert palettes["hcLight"]["rain-6"] == TOKENS["dataviz"]["ramps"]["rain"]["hcLight"]["steps"][5]
    assert palettes["hcDark"]["dye-madder"] == TOKENS["specimen"]["dye-madder"]["hex"]


def test_a_mix_is_the_share_of_the_first_colour_in_srgb() -> None:
    assert mixed_hex("#000000", 50, "#FFFFFF") == "#808080"
    assert mixed_hex("#FF0000", 25, "#0000FF") == "#4000BF"


def test_a_drawing_is_served_in_four_themes_each_painted_from_its_tokens() -> None:
    spec = themed_spec("drawing", {"head": {"title": "u5001"}, "svg": ROLE_DRAWING, "alt": "u5002"})
    assert set(spec["themes"]) == {"light", "dark", "hcLight", "hcDark"}
    for theme in THEMES:
        variant = spec["themes"][theme]
        assert f'fill="{colour("ink-1", theme)}"' in variant and "var(--" not in variant
        steps = TOKENS["dataviz"]["ramps"]["rain"][theme]["steps"]
        assert f'stroke="{steps[1]}"' in variant
        assert mixed_hex(colour("ink-1", theme), 50, colour("ground", theme)) in variant
        assert "IBM Plex Sans" in variant
    assert spec["svg"] == ROLE_DRAWING
    assert themed_spec("chart", {"svg": ROLE_DRAWING}) == {"svg": ROLE_DRAWING}


def test_a_picture_is_themed_only_when_it_is_a_drawing() -> None:
    dark = themed_picture(ROLE_DRAWING.encode("utf-8"), "image/svg+xml", "dark").decode("utf-8")
    assert colour("ink-1", "dark") in dark
    light = themed_picture(ROLE_DRAWING.encode("utf-8"), "image/svg+xml", None).decode("utf-8")
    assert colour("ink-1", "light") in light
    assert themed_picture(b"\x89PNG", "image/png", "dark") == b"\x89PNG"


def test_the_design_css_and_the_drawing_guide_are_served_to_ai_clients() -> None:
    listed = {entry["uri"]: entry for entry in resource_list(SITE)["resources"]}
    assert listed[TOKENS_CSS_URI]["mimeType"] == "text/css"
    assert listed[DRAWING_GUIDE_URI]["mimeType"] == "text/markdown"
    css = resource_read({"uri": TOKENS_CSS_URI})["contents"][0]["text"]
    hc_dark = ':root[data-theme="dark"][data-high-contrast="true"]{color-scheme:dark;'
    assert hc_dark in css and f"--ink-1:{colour('ink-1', 'hcDark')};" in css.split(hc_dark, 1)[1]
    assert "@media (prefers-contrast: more) and (prefers-color-scheme: dark)" in css
    assert f"--text-caption:{TOKENS['type']['scale']['caption']['value']};" in css
    guide = resource_read({"uri": DRAWING_GUIDE_URI})["contents"][0]["text"]
    assert "{{" not in guide and guide.startswith("# Drawing for KalaVigyan\n")
    row = f"| `--ink-1` | {colour('ink-1', 'light')} | {colour('ink-1', 'dark')} |"
    assert row in guide
    assert re.search(r"\| `--text-caption` \| IBM Plex Sans \| 12 \| 12 \|", guide)
    for rule in ("indigo", "madder", "12 px", "Caption first", "Motion only to explain"):
        assert rule in guide, rule


def test_the_mcp_app_views_take_each_of_the_four_themes_and_the_type_scale() -> None:
    for page in (answer_view(), page_preview_view()):
        for selector, theme in (
            (':root[data-theme="dark"][data-high-contrast="true"]{color-scheme:dark;', "hcDark"),
            (':root[data-high-contrast="true"]{color-scheme:light;', "hcLight"),
        ):
            assert f"{selector}--ground:{colour('ground', theme)};" in page, (selector, theme)
        assert "(prefers-contrast: more) and (prefers-color-scheme: dark)" in page
        assert f"--text-h1:{TOKENS['type']['scale']['h1']['value']};" in page
        assert "font-size:var(--text-h1)" in page
