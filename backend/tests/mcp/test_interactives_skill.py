import json
import re
import uuid
from pathlib import Path
from typing import Any

import pytest

from app.api.mcp_component_schemas import component_schema_text
from app.api.mcp_tools import ToolContext, answer
from app.data.contributor_kit import CONTRIBUTOR_SKILL_PATH
from app.data.skill_library import REFERENCES, SKILL_FILES, skill_file_text
from app.research.component_specs_science_parts import COLOUR_TOKEN_PATTERN
from app.research.open_work import COMPONENT_NEEDS, TASK_KINDS, parse_task_key
from app.research.open_work_flagship_backlog import FLAGSHIPS
from app.services.category_register import register_categories
from app.services.craft_resolver import CraftIndexStore

REPOSITORY = Path(__file__).resolve().parents[3]
SKILL = "kalavigyan-interactives"
FOLDERS = (
    REPOSITORY / ".claude" / "skills" / SKILL,
    REPOSITORY / "backend" / "app" / "data" / "contributor" / SKILL,
    REPOSITORY / "frontend" / "public" / "skills" / SKILL,
)
SERVED = ("SKILL.md", "references/flagships.md", "references/storyboard.md")
ENTRY_URI = f"kalavigyan://skills/{SKILL}/SKILL.md"
FLAGSHIPS_URI = f"kalavigyan://skills/{SKILL}/references/flagships.md"
STORYBOARD_URI = f"kalavigyan://skills/{SKILL}/references/storyboard.md"
SITE = "https://kalavigyan.example"
CONTEXT = ToolContext(session=None, index=CraftIndexStore(), site=SITE)  # type: ignore[arg-type]
FOLLOWED_REFERENCES = ("components", "page-checklist", "quotes", "sources")
FAMILIES = 9
STEPS_MIN = 2
DIP_PHASES_MIN = 2
DRAWING_COLOURS = {
    "--ground": "--ground",
    "--raised": "--raised",
    "--sunk": "--sunk",
    "--rule": "--rule",
    "--rule-strong": "--rule-strong",
    "--ink-1": "--ink-1",
    "--ink-3": "--ink-3",
    "--madder": "--madder",
    "--indigo": "--indigo",
    "--dye-*": "--dye-madder-bright",
    "--dip-*": "--dip-4",
    "--mol-*": "--mol-bond",
    "--atom-*": "--atom-c",
    "--map-*": "--map-border-state",
    "--chart-*": "--chart-series",
}
REFUSED_COLOURS = ("--plate-metal", "--plate-clay", "--turmeric", "--terracotta", "--ink-4")
COLOURS_SENTENCE = re.compile(r"accept these colours in a drawing: (?P<list>.+?)\.", re.DOTALL)
CODE = re.compile(r"`([^`]+)`")
SECTION = re.compile(r"^## (?P<title>[^\n]+)\n(?P<body>.*?)(?=^## |\Z)", re.MULTILINE | re.DOTALL)
PAGES = re.compile(r"\*\*Pages\*\*: `(?P<family>[A-Za-z-]+)`; anchor `(?P<anchor>[A-Za-z-]+)`")
TASK = re.compile(r"`(MISSING_COMPONENT:[^`]+)`")
FACT_ID = re.compile(r"`([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})`")
ROW = re.compile(r"^\| (?P<state>[^|]+) \| `(?P<fact>[0-9a-f-]{36})` \|", re.MULTILINE)
MISSING = re.compile(r"\*\*Missing\*\*: (?P<lacks>.*?)(?=\n- \*\*|\n\n)", re.DOTALL)
FLAGSHIP_KEY = re.compile(r"`(FLAGSHIP:category:[A-Za-z-]+)`")


def family_sections() -> dict[str, tuple[str, str]]:
    found: dict[str, tuple[str, str]] = {}
    for section in SECTION.finditer(skill_file_text(FLAGSHIPS_URI)):
        pages = PAGES.search(section["body"])
        if pages is not None:
            found[pages["family"]] = (pages["anchor"], section["body"])
    return found


async def result(method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    reply = await answer({"jsonrpc": "2.0", "id": 7, "method": method, "params": params or {}}, CONTEXT)
    assert reply is not None and "result" in reply, reply
    return reply["result"]


def test_the_skill_serves_its_three_files_from_one_registry() -> None:
    assert sorted(skill.name for skill in SKILL_FILES.values() if skill.skill == SKILL) == sorted(SERVED)
    assert {ENTRY_URI, FLAGSHIPS_URI, STORYBOARD_URI} <= set(SKILL_FILES)


@pytest.mark.parametrize("name", SERVED)
def test_each_file_is_one_text_in_the_repository_the_server_and_the_site(name: str) -> None:
    source, server, site = (folder / name for folder in FOLDERS)
    assert server.read_bytes() == source.read_bytes()
    assert site.read_bytes() == source.read_bytes()


@pytest.mark.parametrize("folder", FOLDERS, ids=("repository", "server", "site"))
def test_each_copy_of_the_skill_holds_only_the_served_files(folder: Path) -> None:
    held = {path.relative_to(folder).as_posix() for path in folder.rglob("*") if path.is_file()}
    assert held == set(SERVED)


def test_the_skill_names_itself_for_agents_that_load_skills() -> None:
    head = skill_file_text(ENTRY_URI).split("---")[1]
    assert f"name: {SKILL}" in head and "description:" in head
    assert skill_file_text(FLAGSHIPS_URI).startswith("# The family flagships\n\n")
    assert skill_file_text(STORYBOARD_URI).startswith("# The storyboard of a flagship\n\n")


async def test_each_file_is_a_resource_read_back_whole_with_its_place_on_the_site() -> None:
    listed = {resource["uri"]: resource for resource in (await result("resources/list"))["resources"]}
    for name in SERVED:
        uri = f"kalavigyan://skills/{SKILL}/{name}"
        source = FOLDERS[0] / name
        assert listed[uri]["mimeType"] == "text/markdown"
        assert listed[uri]["size"] == source.stat().st_size
        assert f"{SITE}/skills/{SKILL}/{name}" in listed[uri]["description"]
        read = await result("resources/read", {"uri": uri})
        assert read["contents"][0]["text"] == source.read_bytes().decode("utf-8")


def test_the_skill_names_its_own_references_and_the_shared_ones_it_follows() -> None:
    entry = skill_file_text(ENTRY_URI)
    for uri in (FLAGSHIPS_URI, STORYBOARD_URI, *(REFERENCES[name].uri for name in FOLLOWED_REFERENCES)):
        assert f"`{uri}`" in entry, uri
    assert f"`{ENTRY_URI}`" in CONTRIBUTOR_SKILL_PATH.read_bytes().decode("utf-8")


def test_a_reaction_player_holds_two_steps_or_more_and_a_dip_player_two_phases_or_more() -> None:
    schema = json.loads(component_schema_text("reaction_player"))
    assert schema["properties"]["steps"]["minItems"] == STEPS_MIN
    assert "two steps or more" in skill_file_text(ENTRY_URI)
    dip = json.loads(component_schema_text("dip_player"))
    assert dip["properties"]["phases"]["minItems"] == DIP_PHASES_MIN
    assert "two phases or more, each named once" in skill_file_text(ENTRY_URI)


def test_the_colours_the_skill_lists_are_the_ones_a_drawing_may_use() -> None:
    sentence = COLOURS_SENTENCE.search(" ".join(skill_file_text(ENTRY_URI).split()))
    assert sentence is not None
    assert CODE.findall(sentence["list"]) == list(DRAWING_COLOURS)
    for listed, sample in DRAWING_COLOURS.items():
        assert re.fullmatch(COLOUR_TOKEN_PATTERN, sample), listed
    for refused in REFUSED_COLOURS:
        assert re.fullmatch(COLOUR_TOKEN_PATTERN, refused) is None, refused
    assert "the plate grounds (`--plate-*`)" in " ".join(skill_file_text(ENTRY_URI).split())


def test_the_backlog_gives_each_of_the_nine_families_an_anchor_of_its_own() -> None:
    families = {category.slug: category for category in register_categories()}
    sections = family_sections()
    assert len(families) == FAMILIES
    assert set(sections) == set(families)
    for family, (anchor, _) in sections.items():
        assert anchor in families[family].member_slugs(), (family, anchor)


def test_every_task_the_backlog_names_is_a_craft_s_reaction_player_task() -> None:
    crafts = {slug for category in register_categories() for slug in category.member_slugs()}
    named = TASK.findall(skill_file_text(FLAGSHIPS_URI))
    assert named
    for key in named:
        task = parse_task_key(key)
        assert (task.kind, task.subject_kind, task.detail) == (
            "MISSING_COMPONENT",
            "craft",
            "reaction-player",
        ), key
        assert task.slug in crafts, key
    assert "reaction_player" in COMPONENT_NEEDS["reaction-player"]


def test_open_work_holds_a_flagship_task_for_each_family_as_the_backlog_says() -> None:
    backlog = skill_file_text(FLAGSHIPS_URI)
    open_work = backlog.split("## Open work and the flagships\n")[1]
    assert "FLAGSHIP" in TASK_KINDS and "Open work cannot hold" not in backlog
    assert "`FLAGSHIP:category:<slug>`" in open_work
    assert FLAGSHIP_KEY.findall(open_work) == ["FLAGSHIP:category:Metal-Craft-Category"]
    assert parse_task_key("FLAGSHIP:category:Metal-Craft-Category").slug in FLAGSHIPS


def test_the_server_s_flagships_are_the_backlog_s_mechanism_anchor_facts_and_lacks() -> None:
    sections = [
        section
        for section in SECTION.finditer(skill_file_text(FLAGSHIPS_URI))
        if PAGES.search(section["body"])
    ]
    assert len(sections) == len(FLAGSHIPS) == FAMILIES
    for section in sections:
        pages, missing = PAGES.search(section["body"]), MISSING.search(section["body"])
        assert pages is not None and missing is not None
        flagship = FLAGSHIPS[pages["family"]]
        facts = [row["fact"] for row in ROW.finditer(section["body"]) if "candidate" not in row["state"]]
        assert f"{flagship.family}: {flagship.mechanism}" == section["title"]
        assert (flagship.anchor, list(flagship.facts)) == (pages["anchor"], facts)
        assert flagship.lacks == " ".join(missing["lacks"].split()).removesuffix(".")


def test_each_backlog_fact_is_named_once_and_the_storyboard_draws_only_backlog_facts() -> None:
    backlog = FACT_ID.findall(skill_file_text(FLAGSHIPS_URI))
    assert backlog and len(backlog) == len(set(backlog))
    assert all(str(uuid.UUID(fact)) == fact for fact in backlog)
    storyboard = set(FACT_ID.findall(skill_file_text(STORYBOARD_URI)))
    assert storyboard and storyboard <= set(backlog)
