import re
from pathlib import Path
from typing import Any

import pytest

from app.api.mcp_prompts import PROMPTS
from app.api.mcp_resources import RESOURCES
from app.api.mcp_tools import TOOLS, ToolContext, answer
from app.data.contributor_kit import CONTRIBUTOR_SKILL_PATH
from app.data.skill_library import (
    CONTRACTS,
    CONTRACTS_DIR,
    INDEX_URI,
    REFERENCES,
    REFERENCES_DIR,
    SKILL_FILES,
    contract_text,
    reference_text,
    server_index,
    skill_file_text,
)
from app.services.craft_resolver import CraftIndexStore

REPOSITORY = Path(__file__).resolve().parents[3]
SITE_PUBLIC = REPOSITORY / "frontend" / "public"
CLAUDE_SKILLS = REPOSITORY / ".claude" / "skills"
CURATION_SKILL = CLAUDE_SKILLS / "kalavigyan-craft-pages" / "SKILL.md"
CURATION_CHECKLIST = CLAUDE_SKILLS / "kalavigyan-craft-pages" / "references" / "page-checklist.md"
DATASETS_SOURCE = CLAUDE_SKILLS / "kalavigyan-datasets" / "SKILL.md"
DATASETS_SITE = SITE_PUBLIC / "skills" / "kalavigyan-datasets" / "SKILL.md"
DATASETS_URI = "kalavigyan://skills/kalavigyan-datasets/SKILL.md"
DATASETS_SKILL_PATH = SKILL_FILES[DATASETS_URI].path
SKILLS = {
    "contributor": CONTRIBUTOR_SKILL_PATH,
    "curation": CURATION_SKILL,
    "datasets": DATASETS_SOURCE,
    **{file.uri: CLAUDE_SKILLS / file.skill / file.name for file in SKILL_FILES.values()},
}
SITE = "https://kalavigyan.example"
CONTEXT = ToolContext(session=None, index=CraftIndexStore(), site=SITE)  # type: ignore[arg-type]
SHINGLE_WORDS = 8
WORD = re.compile(r"[a-z0-9]+")
HEADING = re.compile(r"^#{1,3} (?P<title>.+)$", re.MULTILINE)
RULE = re.compile(r"^(?P<number>\d+)\. \*\*", re.MULTILINE)
CHECKLIST_RULES = 26
DATASET_REFERENCES = ("datasets", "components", "sources", "quotes", "page-checklist")
CURATION_TOOLS = (
    "get_page",
    "get_facts",
    "propose_facts",
    "get_proposal",
    "propose_structure",
    "propose_source",
    "list_components",
    "preview_page",
    "propose_page",
    "give_pictures",
    "search_sources",
    "read_source",
    "lookup",
    "supply_source",
    "edit_draft",
)
INDEX_LINE = re.compile(r"^- `(?P<name>[^`]+)`: \S.*$")
INDEX_SECTIONS = ("Tools", "Prompts", "Resources", "Component schemas")
COMPONENT_SCHEMA = "kalavigyan://components/"


def text_of(path: Path) -> str:
    return path.read_bytes().decode("utf-8")


def site_copy(site_path: str) -> Path:
    return SITE_PUBLIC / site_path.lstrip("/")


def shingles(text: str) -> set[tuple[str, ...]]:
    words = WORD.findall(text.casefold())
    return {tuple(words[at : at + SHINGLE_WORDS]) for at in range(len(words) - SHINGLE_WORDS + 1)}


def headings(text: str) -> set[str]:
    return {match.group("title").strip() for match in HEADING.finditer(text)}


async def result(method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    reply = await answer({"jsonrpc": "2.0", "id": 4, "method": method, "params": params or {}}, CONTEXT)
    assert reply is not None and "result" in reply, reply
    return reply["result"]


@pytest.mark.parametrize("name", sorted(REFERENCES))
def test_the_site_serves_each_reference_exactly_as_its_source(name: str) -> None:
    reference = REFERENCES[name]
    assert site_copy(reference.site_path).read_bytes() == reference.path.read_bytes()


def test_the_references_folders_hold_only_the_references() -> None:
    names = {reference.file_name for reference in REFERENCES.values()}
    assert {path.name for path in REFERENCES_DIR.iterdir()} == names
    assert {path.name for path in (SITE_PUBLIC / "skills" / "references").iterdir()} == names


def test_each_reference_opens_on_its_own_title() -> None:
    for reference in REFERENCES.values():
        assert reference_text(reference.name).startswith(f"# {reference.title}\n\n"), reference.name


def test_the_datasets_skill_is_one_text_in_the_repository_the_server_and_the_site() -> None:
    source = DATASETS_SOURCE.read_bytes()
    assert DATASETS_SKILL_PATH.read_bytes() == source
    assert DATASETS_SITE.read_bytes() == source
    head = source.decode("utf-8").split("---")[1]
    assert "name: kalavigyan-datasets" in head and "description:" in head


def test_every_skill_served_beside_the_contributor_s_is_one_registry_s_file() -> None:
    served = {f"kalavigyan://skills/{file.skill}/{file.name}" for file in SKILL_FILES.values()}
    assert {file.skill for file in SKILL_FILES.values()} == {"kalavigyan-datasets", "kalavigyan-interactives"}
    assert DATASETS_URI in served
    skills = {uri for uri in RESOURCES if uri.startswith("kalavigyan://skills/kalavigyan-")}
    assert skills == {*served, "kalavigyan://skills/kalavigyan-contributor/SKILL.md"}


def test_the_curation_skill_s_checklist_is_the_shared_checklist() -> None:
    assert CURATION_CHECKLIST.read_bytes() == REFERENCES["page-checklist"].path.read_bytes()


@pytest.mark.parametrize("skill", sorted(SKILLS))
def test_no_skill_restates_a_rule_a_reference_owns(skill: str) -> None:
    text = text_of(SKILLS[skill])
    held = shingles(text)
    for reference in REFERENCES.values():
        owned = reference_text(reference.name)
        shared = sorted(" ".join(words) for words in held & shingles(owned))
        assert not shared, f"{skill} restates {reference.file_name}: {shared[:3]}"
        assert not headings(text) & headings(owned), (skill, reference.file_name)


def test_each_skill_names_the_references_it_follows() -> None:
    contributor = text_of(CONTRIBUTOR_SKILL_PATH)
    curation = text_of(CURATION_SKILL)
    for reference in REFERENCES.values():
        assert f"`{reference.uri}`" in contributor and f"`{reference.site_path}`" in contributor
        assert f"`{reference.path.relative_to(REPOSITORY).as_posix()}`" in curation
        assert f"`{reference.uri}`" in curation
    datasets = text_of(DATASETS_SOURCE)
    for name in DATASET_REFERENCES:
        assert f"`{REFERENCES[name].uri}`" in datasets, name
    assert f"`{DATASETS_URI}`" in contributor and f"`{DATASETS_URI}`" in curation


def test_the_page_checklist_numbers_its_26_rules_in_order() -> None:
    checklist = reference_text("page-checklist")
    numbers = [int(match.group("number")) for match in RULE.finditer(checklist)]
    assert numbers == list(range(1, CHECKLIST_RULES + 1))
    assert f"these {CHECKLIST_RULES} rules" in checklist
    assert "rules 23 to 26" in reference_text("fields")


def test_the_curation_skill_sends_every_change_through_the_mcp_tools() -> None:
    curation = text_of(CURATION_SKILL)
    for name in CURATION_TOOLS:
        assert f"`{name}`" in curation and name in TOOLS, name
    head = curation.split("---")[1]
    assert "name: kalavigyan-craft-pages" in head and "propose_structure" in head
    assert "the dossier route" in curation and "Commons" in curation


async def test_every_reference_and_the_datasets_skill_are_resources_read_back_whole() -> None:
    listed = {resource["uri"]: resource for resource in (await result("resources/list"))["resources"]}
    for reference in REFERENCES.values():
        resource = listed[reference.uri]
        assert resource["mimeType"] == "text/markdown"
        assert resource["size"] == reference.path.stat().st_size
        assert f"{SITE}{reference.site_path}" in resource["description"]
        read = await result("resources/read", {"uri": reference.uri})
        assert read["contents"][0]["text"] == reference_text(reference.name)
    skill = listed[DATASETS_URI]
    assert skill["size"] == DATASETS_SKILL_PATH.stat().st_size
    assert f"{SITE}/skills/kalavigyan-datasets/SKILL.md" in skill["description"]
    read = await result("resources/read", {"uri": DATASETS_URI})
    assert read["contents"][0]["text"] == skill_file_text(DATASETS_URI)


@pytest.mark.parametrize("name", sorted(CONTRACTS))
def test_each_contract_resource_is_the_repository_s_contract(name: str) -> None:
    contract = CONTRACTS[name]
    assert contract.path.read_bytes() == (REPOSITORY / contract.repository_path).read_bytes()


def test_the_contracts_folder_holds_only_the_served_contracts() -> None:
    assert {path.name for path in CONTRACTS_DIR.iterdir()} == {c.file_name for c in CONTRACTS.values()}
    assert set(CONTRACTS) == {
        "knowledge-writes",
        "open-work",
        "component-specs-general",
        "image-contributions",
        "mcp-ask-and-upload",
    }


async def test_every_contract_and_the_index_are_resources_read_back_whole() -> None:
    listed = {resource["uri"]: resource for resource in (await result("resources/list"))["resources"]}
    for contract in CONTRACTS.values():
        resource = listed[contract.uri]
        assert resource["mimeType"] == "text/markdown"
        assert resource["size"] == contract.path.stat().st_size
        assert contract.repository_path in resource["description"]
        read = await result("resources/read", {"uri": contract.uri})
        assert read["contents"][0]["text"] == contract_text(contract.name)
    read = await result("resources/read", {"uri": INDEX_URI})
    assert read["contents"][0]["text"] == server_index()


def index_names(section: str) -> list[str]:
    text = server_index().split(f"\n## {section}\n")[1].split("\n## ")[0]
    lines = [line for line in text.splitlines() if line.strip()]
    found = [INDEX_LINE.match(line) for line in lines]
    assert all(found), [line for line, match in zip(lines, found, strict=True) if match is None]
    return [match.group("name") for match in found if match is not None]


def test_the_index_names_every_tool_prompt_and_resource_once_with_one_line_each() -> None:
    offered = {
        "Tools": list(TOOLS),
        "Prompts": list(PROMPTS),
        "Resources": [uri for uri in RESOURCES if not uri.startswith(COMPONENT_SCHEMA)],
        "Component schemas": [uri for uri in RESOURCES if uri.startswith(COMPONENT_SCHEMA)],
    }
    for section in INDEX_SECTIONS:
        named = index_names(section)
        assert len(named) == len(set(named)), section
        assert sorted(named) == sorted(offered[section]), section
    assert server_index().startswith("# The KalaVigyan MCP server\n\n")
