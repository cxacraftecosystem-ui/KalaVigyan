import ast
import importlib.util
import re
from pathlib import Path
from types import ModuleType

from app.curation.limits import (
    CLAIM_WORDS_MAX,
    CLAIM_WORDS_MIN,
    CURATED_QUOTE_MIN_CHARS,
    DISCIPLINE_CLAIMS_MIN,
    PICTURES_MAX,
)
from app.data.skill_library import reference_text
from app.models.component_kinds import GENERAL_KINDS
from app.models.enums import DISCIPLINES
from app.models.knowledge import QUOTE_MAX_CHARS
from app.models.knowledge_pieces import DESCRIPTION_MAX_CHARS
from app.research import component_specs_general as general
from app.research.component_proposals import DESCRIPTION_MIN_CHARS, SUBJECTS_MAX
from app.research.component_specs_data import SPEC_MODELS_DATA
from app.research.component_specs_general_delivery import (
    CLAIMS_PER_UNIT_MAX,
    LABEL_MAX_CHARS,
    UNIT_TEXT_MAX,
    UNITS_MAX,
)
from app.research.component_specs_general_svg import DRAWING_MAX_CHARS
from app.research.component_specs_plates import SPEC_MODELS_PLATES
from app.research.component_specs_science import SPEC_MODELS_SCIENCE
from app.research.component_specs_tools import SPEC_MODELS_TOOLS
from app.research.knowledge_writes import PROPOSAL_FIELDS_MAX, PROPOSAL_QUOTES_MAX, PROPOSAL_SOURCES_MAX
from app.research.licences import open_licence
from app.research.page_proposals import FACTS_MAX

REPOSITORY = Path(__file__).resolve().parents[3]
CRAFT_PAGES = REPOSITORY / ".claude" / "skills" / "kalavigyan-craft-pages"
INDIA_BOUNDS = REPOSITORY / "frontend" / "components" / "map" / "indiaBounds.ts"
NUMBER_WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five"}
KIND_GROUPS = {
    "Plates and media": SPEC_MODELS_PLATES,
    "Data and place": SPEC_MODELS_DATA,
    "Science": SPEC_MODELS_SCIENCE,
    "Reading tools": SPEC_MODELS_TOOLS,
}
APPROVED_KINDS = 42
GROUP = re.compile(
    r"^- \*\*(?P<group>[^*]+)\*\* \((?P<count>\d+)\): (?P<kinds>.+?)(?=\n- |\n\n)", re.M | re.S
)
CODE_NAME = re.compile(r"`([a-z0-9_]+)`")
TABLE_ROW = re.compile(r"^\| (?P<layer>[^|]+) \| (?P<tolerance>[^|]+) \|$", re.MULTILINE)
BOUND = re.compile(r"(?P<name>m(?:in|ax)L(?:ong|at)itude): (?P<value>-?[0-9.]+)")
TOLERANCES = {
    "rivers and their centre lines": (("tools/maplayers/rivers.py", "TOLERANCE"),),
    "lakes": (
        ("tools/maplayers/rivers.py", "LAKE_TOLERANCE"),
        ("tools/maplayers/rivers.py", "LAKE_MIN_AREA"),
    ),
    "country outlines, simplified together so neighbours still meet": (
        ("tools/basemap/build.py", "TOLERANCE"),
    ),
    "relief bands": (("tools/maplayers/relief.py", "BAND_TOLERANCE"),),
    "a river basin's reaches, each with its ends kept so junctions stay joined": (
        ("etl/geo/geo_etl/topology.py", "SIMPLIFY_DEGREES"),
    ),
}


def flat(text: str) -> str:
    return " ".join(text.split())


def constant(relative: str, name: str) -> float:
    tree = ast.parse((REPOSITORY / relative).read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == name for t in node.targets
        ):
            return float(ast.literal_eval(node.value))
    raise AssertionError(f"{relative} has no constant {name}")


def gaps_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("craft_pages_gaps", CRAFT_PAGES / "scripts" / "gaps.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_quote_rules_state_the_limits_the_gates_and_the_checker_apply() -> None:
    quotes = flat(reference_text("quotes"))
    assert f"{CURATED_QUOTE_MIN_CHARS} to {QUOTE_MAX_CHARS} characters" in quotes
    assert f"{CLAIM_WORDS_MIN} to {CLAIM_WORDS_MAX} words" in quotes
    assert f"up to {PROPOSAL_SOURCES_MAX} sources, each with up to {PROPOSAL_QUOTES_MAX} quotes" in quotes
    assert f"up to {NUMBER_WORDS[PROPOSAL_FIELDS_MAX]} further fields" in flat(reference_text("fields"))


def test_a_picture_from_elsewhere_needs_a_licence_the_server_reads_as_open() -> None:
    sources = flat(reference_text("sources"))
    bullet = sources.split("**A picture from elsewhere**")[1].split("**A picture a person gives**")[0]
    for licence in ("CC0", "PDDL", "CC BY", "CC BY-SA", "public domain"):
        assert licence in bullet and open_licence(licence), licence
    for licence in ("CC BY-NC 4.0", "CC BY-ND 4.0", "CC BY-NC-SA 4.0", "All rights reserved"):
        assert not open_licence(licence), licence
    assert "non-commercial (NC)" in bullet and "no-derivatives (ND)" in bullet


def test_the_component_guide_lists_the_42_kinds_by_group_and_the_five_general_kinds() -> None:
    components = reference_text("components")
    groups = {match["group"]: match for match in GROUP.finditer(components)}
    assert set(groups) == set(KIND_GROUPS)
    for name, models in KIND_GROUPS.items():
        assert sorted(CODE_NAME.findall(groups[name]["kinds"])) == sorted(models), name
        assert int(groups[name]["count"]) == len(models), name
    assert sum(len(models) for models in KIND_GROUPS.values()) == APPROVED_KINDS
    assert f"The {APPROVED_KINDS} kinds" in components
    named = flat(components).split("use one of the five general kinds: ")[1].split(". ")[0]
    assert tuple(CODE_NAME.findall(named)) == GENERAL_KINDS


def test_the_component_guide_states_the_delivery_limits() -> None:
    components = flat(reference_text("components"))
    bounds = general.BOUNDS
    for stated in (
        f"a text of 1 to {UNIT_TEXT_MAX} characters and up to {CLAIMS_PER_UNIT_MAX} ids",
        f"up to {UNITS_MAX} units",
        f"a label of at most {LABEL_MAX_CHARS} characters",
        f"at most {DRAWING_MAX_CHARS:,} characters of SVG",
        f"`series`, 1 to {general.SERIES_MAX}",
        f"1 to {general.POINTS_MAX} points",
        f"`columns`, 1 to {general.COLUMNS_MAX}",
        f"`rows`, 1 to {general.ROWS_MAX}",
        f"`events`, {general.EVENTS_MIN} to {general.EVENTS_MAX}",
        f"from {general.YEAR_MIN} to {general.YEAR_MAX}",
        f"`places`, 1 to {general.PLACES_MAX}",
        f"longitude {bounds['west']:g} to {bounds['east']:g} and latitude {bounds['south']:g} to "
        f"{bounds['north']:g}",
        f"{DESCRIPTION_MIN_CHARS} to {DESCRIPTION_MAX_CHARS} characters",
        f"**subjects**, 1 to {SUBJECTS_MAX}",
    ):
        assert stated in components, stated


def test_the_dataset_guide_states_the_map_s_frame_and_the_layers_tolerances() -> None:
    datasets = flat(reference_text("datasets"))
    bounds = {
        match["name"]: float(match["value"]) for match in BOUND.finditer(INDIA_BOUNDS.read_text("utf-8"))
    }
    middle = (bounds["minLatitude"] + bounds["maxLatitude"]) / 2
    assert f"the cosine of {middle:.3f} degrees" in datasets
    assert (
        f"({bounds['minLatitude']:g} to {bounds['maxLatitude']:g} degrees north, "
        f"{bounds['minLongitude']:g} to {bounds['maxLongitude']:g} east)"
    ) in datasets
    rows = {row["layer"]: row["tolerance"] for row in TABLE_ROW.finditer(reference_text("datasets"))}
    for layer, constants in TOLERANCES.items():
        for relative, name in constants:
            assert f"{constant(relative, name):g} " in rows[layer], (layer, name)
    assert f"A bundle holds at most {FACTS_MAX} facts" in datasets


def test_the_gaps_script_and_the_curation_bar_count_by_the_server_s_limits() -> None:
    gaps = gaps_script()
    assert gaps.fields() == list(DISCIPLINES)
    assert gaps.FIELD_CLAIMS == DISCIPLINE_CLAIMS_MIN
    assert gaps.BAR["pictures"] <= PICTURES_MAX
    bar = flat((CRAFT_PAGES / "SKILL.md").read_text(encoding="utf-8"))
    assert f"{gaps.BAR['pictures']} or more where open-licence pictures exist, at most {PICTURES_MAX}" in bar
    assert f"{gaps.CURATED_FIELDS} or more for a curated craft" in bar
    assert f"{DISCIPLINE_CLAIMS_MIN} or more cited claims in each covered field" in bar
    checklist = flat(reference_text("page-checklist"))
    assert f"{NUMBER_WORDS[DISCIPLINE_CLAIMS_MIN]} or more cited sentences" in checklist
