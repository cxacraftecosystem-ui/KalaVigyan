from __future__ import annotations

import re
from collections.abc import Iterator

from .depicted_materials import DEPICTED_MATERIALS

__all__ = [
    "ALLOWED_ROLES",
    "DRAWING_ROLES",
    "INDIGO",
    "MATERIAL_ROLES",
    "MOLECULE_ROLE",
    "PAINT_PROPERTIES",
    "css_declarations",
    "paint_problem",
    "paint_roles",
    "role_problem",
]

SURFACE_ROLES = ("ground", "raised", "sunk", "rule", "rule-strong", "ink-1", "ink-2", "ink-3")
FLAGGED_ROLES = ("madder", "terracotta")
CHART_ROLES = (
    *(
        f"chart-{name}"
        for name in (
            "axis-text",
            "axis-line",
            "grid",
            "series",
            "emph",
            "reference",
            "trend",
            "band",
            "annotation",
            "differ",
        )
    ),
    "series-rain",
    "series-heat",
    "series-count",
)
RAMPS = (
    ("rain", 6),
    ("density", 6),
    ("heat", 6),
    ("ph", 5),
    ("elevation", 7),
    ("earth", 6),
    ("cover", 6),
    ("mineral", 6),
)
RAMP_ROLES = tuple(f"{ramp}-{step}" for ramp, steps in RAMPS for step in range(1, steps + 1))
MAP_ROLES = tuple(
    f"map-{name}"
    for name in (
        "land",
        "land-foreign",
        "water",
        "coast",
        "water-label",
        "river",
        "salt",
        "salt-hatch",
        "border-intl",
        "border-state",
        "border-district",
        "label",
        "label-minor",
        "label-halo",
        "selection",
        "selection-halo",
        "hover",
        "marker",
        "marker-ring",
        "place",
        "nodata",
        "relief-shade",
    )
)
DIPS = 4
MATERIAL_ROLES = frozenset(
    (*(f"dye-{name}" for name in DEPICTED_MATERIALS), *(f"dip-{step}" for step in range(1, DIPS + 1)))
)
DRAWING_ROLES = (
    frozenset((*SURFACE_ROLES, *FLAGGED_ROLES, *CHART_ROLES, *RAMP_ROLES, *MAP_ROLES)) | MATERIAL_ROLES
)
MOLECULE_ROLE = re.compile(r"^(mol|atom)-[a-z]+$")
INDIGO = re.compile(r"^(c-)?(indigo|on-indigo)(-[a-z]+)?$")
ALLOWED_ROLES = (
    "a design role: --ink-1 to --ink-3, --rule, --rule-strong, --ground, --raised or --sunk for lines, "
    "words and grounds; --chart-*, --series-*, a ramp step such as --rain-3 and --map-* for data; a "
    "depicted --dye-* or --dip-* material; --terracotta only for place and --madder only for a hazard"
)
PAINT_PROPERTIES = frozenset({"fill", "stroke", "stop-color", "flood-color", "lighting-color", "color"})
PLAIN_PAINTS = frozenset({"none", "transparent", "currentcolor", "inherit"})
MASK_PAINTS = re.compile(
    r"^(#fff|#ffffff|#000|#000000|white|black|rgba?\((255,255,255|0,0,0)(,(0|1|0?\.\d+))?\))$"
)
LOCAL_REFERENCE = re.compile(r"^url\(#[\w.-]+\)$")
TOKEN = re.compile(r"^var\(--([a-z0-9-]+)\)$")
MIX = re.compile(
    r"^color-mix\(in srgb, ?var\(--([a-z0-9-]+)\) \d{1,3}%, ?var\(--([a-z0-9-]+)\)( \d{1,3}%)?\)$"
)
DECLARATION = re.compile(r"(?P<name>[A-Za-z-]+)\s*:\s*(?P<value>[^;{}]+)")


def role_problem(token: str, *, molecules: bool = False) -> str | None:
    if INDIGO.match(token):
        return f"--{token} is indigo, which means a control a reader can press, never a drawing"
    if token in DRAWING_ROLES or (molecules and MOLECULE_ROLE.match(token)):
        return None
    if token.startswith("dye-"):
        return f"--{token} is not a depicted material the design system records"
    return f"--{token} is not one of the design's roles"


def paint_roles(value: str) -> list[str]:
    compact = " ".join(value.split())
    token = TOKEN.match(compact)
    if token:
        return [token.group(1)]
    mixed = MIX.match(compact)
    return [mixed.group(1), mixed.group(2)] if mixed else []


def paint_problem(value: str, *, in_mask: bool = False, molecules: bool = False) -> str | None:
    compact = " ".join(value.split())
    folded = compact.casefold().replace(" ", "")
    if folded in PLAIN_PAINTS or LOCAL_REFERENCE.match(compact):
        return None
    if in_mask and MASK_PAINTS.match(folded):
        return None
    roles = paint_roles(compact)
    if not roles:
        return f"names the colour {compact!r}; name {ALLOWED_ROLES}"
    problems = [problem for role in roles if (problem := role_problem(role, molecules=molecules))]
    return f"{problems[0]}; name {ALLOWED_ROLES}" if problems else None


def css_declarations(text: str) -> Iterator[tuple[str, str]]:
    for found in DECLARATION.finditer(text):
        yield found.group("name").strip().casefold(), found.group("value").strip()
