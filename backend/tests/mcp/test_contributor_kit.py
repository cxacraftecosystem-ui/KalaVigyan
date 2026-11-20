import re
from pathlib import Path

from app.api.proposal_limits import LIMIT_NOUNS
from app.core.rate_limit import FACT_PROPOSALS, PROPOSAL_LIMITS
from app.data.contributor_kit import (
    CONTRIBUTOR_SKILL_PATH,
    DESIGN_TOKENS_PATH,
    SITE_SKILL_PATH,
    skill_section,
)
from app.models.enums import DISCIPLINES
from app.research.sections import DISCIPLINE_FIELDS, DISCIPLINE_TITLES
from app.research.trust_tiers import TIER_FACTS_PER_HOUR, TIER_TASKS_HELD, TRUST_TIERS

CONTRIBUTOR_TOOLS = (
    "list_open_work",
    "claim_task",
    "claim_tasks",
    "release_task",
    "my_tasks",
    "get_facts",
    "get_section",
    "get_coverage",
    "get_layout",
    "list_components",
    "propose_fact",
    "propose_facts",
    "get_proposal",
    "propose_source",
    "propose_structure",
    "propose_component",
    "preview_page",
    "propose_page",
    "adopt_craft",
    "drop_craft",
    "my_crafts",
    "give_image",
    "give_images",
    "start_image_upload",
)

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


def test_the_skill_lists_every_field_with_its_title_and_what_it_covers() -> None:
    rows = [match.groupdict() for match in ROW.finditer(skill_section("The fields"))]
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
    assert "taskKey" not in text and "craftSlug" not in text and "claimId" not in text
