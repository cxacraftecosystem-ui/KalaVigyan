import re
from pathlib import Path

from app.api.mcp_tools import TOOLS
from app.api.proposal_limits import LIMIT_NOUNS
from app.core.mcp_scopes import REVIEW_SCOPE
from app.core.rate_limit import FACT_PROPOSALS, LOOKUP_LIMITS, PROPOSAL_LIMITS
from app.data.contributor_kit import (
    CONTRIBUTOR_SKILL_PATH,
    DESIGN_TOKENS_PATH,
    SITE_SKILL_PATH,
    skill_section,
)
from app.data.skill_library import reference_text
from app.models.enums import DISCIPLINES
from app.research.sections import DISCIPLINE_FIELDS, DISCIPLINE_TITLES
from app.research.trust_tiers import TIER_FACTS_PER_HOUR, TIER_TASKS_HELD, TRUST_TIERS

CONTRIBUTOR_TOOLS = (
    "find_crafts",
    "get_page",
    "get_facts",
    "list_components",
    "ask",
    "search_sources",
    "read_source",
    "lookup",
    "supply_source",
    "list_open_work",
    "my_work",
    "reserve_tasks",
    "steward_craft",
    "get_proposal",
    "propose_facts",
    "propose_structure",
    "propose_source",
    "propose_dataset",
    "edit_draft",
    "preview_page",
    "propose_page",
    "give_pictures",
)
ADMIN_TOOLS = ("review_queue", "stage_reviews", "refresh_pages", "admin_reports")
RETIRED_TOOLS = (
    "list_fields",
    "get_section",
    "get_coverage",
    "get_layout",
    "claim_task",
    "claim_tasks",
    "release_task",
    "my_tasks",
    "my_crafts",
    "adopt_craft",
    "drop_craft",
    "propose_fact",
    "propose_component",
    "propose_layout",
    "create_draft",
    "add_to_draft",
    "remove_from_draft",
    "get_draft",
    "preview_draft",
    "submit_draft",
    "start_image_upload",
    "give_image",
    "give_images",
    "check_quote",
    "archive_source",
    "lookup_compound",
    "lookup_entity",
    "find_pictures",
)
LOOKUP_TABLE = {
    "source searches": ("each kind of `search_sources`, its pictures too", (30, 60, 120)),
    "source reads": ("the text and each quote of `read_source`, and `lookup`", (120, 240, 480)),
    "paid searches": ("the Brave and Elsevier routes of `search_sources`", (5, 15, 30)),
    "source archives": ("`read_source` with archive", (5, 10, 20)),
}

REPOSITORY = Path(__file__).resolve().parents[3]
SITE_COPY = REPOSITORY / "frontend" / "public" / SITE_SKILL_PATH.lstrip("/")
SKILL_TOKENS = REPOSITORY / ".claude" / "skills" / "kalavigyan-design" / "references" / "tokens.json"
ROW = re.compile(r"^\| (?P<field>[A-Z]+) \| (?P<title>[^|]+) \| (?P<covers>[^|]+) \|$", re.MULTILINE)


def test_the_site_serves_the_same_contributor_skill_as_the_mcp_resource() -> None:
    assert SITE_COPY.read_bytes() == CONTRIBUTOR_SKILL_PATH.read_bytes()


def test_the_design_tokens_resource_is_the_design_skill_s_tokens() -> None:
    assert DESIGN_TOKENS_PATH.read_bytes() == SKILL_TOKENS.read_bytes()


def test_the_skill_names_itself_for_agents_that_load_skills() -> None:
    head = CONTRIBUTOR_SKILL_PATH.read_bytes().decode("utf-8").split("---")[1]
    assert "name: kalavigyan-contributor" in head
    assert "description:" in head


def test_the_fields_reference_lists_every_field_with_its_title_and_what_it_covers() -> None:
    rows = [match.groupdict() for match in ROW.finditer(reference_text("fields"))]
    assert [row["field"] for row in rows] == list(DISCIPLINES)
    assert {row["field"]: row["title"] for row in rows} == dict(DISCIPLINE_TITLES)
    assert {row["field"]: row["covers"] for row in rows} == dict(DISCIPLINE_FIELDS)


def table_rows(section: str) -> list[list[str]]:
    lines = [line for line in skill_section(section).splitlines() if line.startswith("| ")]
    return [[cell.strip() for cell in line.strip("|").split("|")] for line in lines[1:]]


def test_the_trust_tiers_the_skill_teaches_are_the_tiers_the_server_applies() -> None:
    rows = {row[0]: row for row in table_rows("Trust tiers")}
    assert list(rows) == list(TRUST_TIERS)
    assert {tier: int(row[2]) for tier, row in rows.items()} == dict(TIER_TASKS_HELD)
    assert {tier: int(row[3]) for tier, row in rows.items()} == dict(TIER_FACTS_PER_HOUR)


def test_each_allowance_the_skill_teaches_is_the_server_s_hourly_limit() -> None:
    rows = {row[0]: row[1] for row in table_rows("Allowances")}
    assert set(rows) == set(LIMIT_NOUNS.values())
    for kind, noun in LIMIT_NOUNS.items():
        expected = "by tier" if kind == FACT_PROPOSALS else str(PROPOSAL_LIMITS[kind])
        assert rows[noun] == expected, noun


def test_the_skill_teaches_every_contributor_tool_by_its_name() -> None:
    text = CONTRIBUTOR_SKILL_PATH.read_bytes().decode("utf-8")
    for name in CONTRIBUTOR_TOOLS:
        assert f"`{name}`" in text, name
    for name in RETIRED_TOOLS:
        assert f"`{name}`" not in text and name not in TOOLS, name
    assert set(CONTRIBUTOR_TOOLS) | set(ADMIN_TOOLS) == set(TOOLS)
    assert {name for name, tool in TOOLS.items() if tool.scope == REVIEW_SCOPE} == set(ADMIN_TOOLS)
    assert [name for name in ADMIN_TOOLS if f"`{name}`" in text] == []
    assert "taskKey" not in text and "craftSlug" not in text and "claimId" not in text


def test_the_skill_teaches_every_tool_the_server_offers() -> None:
    text = CONTRIBUTOR_SKILL_PATH.read_bytes().decode("utf-8")
    untaught = sorted(
        name for name, tool in TOOLS.items() if tool.scope != REVIEW_SCOPE and f"`{name}`" not in text
    )
    assert untaught == []


def test_the_source_tool_allowances_the_skill_teaches_are_the_server_s() -> None:
    rows = {
        row[0]: (row[1], tuple(int(cell) for cell in row[2:]))
        for row in table_rows("Finding and reading sources")
    }
    assert rows == LOOKUP_TABLE
    assert {use: tuple(limits.values()) for use, limits in LOOKUP_LIMITS.items()} == {
        use: limits for use, (_tools, limits) in LOOKUP_TABLE.items()
    }
    assert all(tuple(limits) == TRUST_TIERS for limits in LOOKUP_LIMITS.values())
