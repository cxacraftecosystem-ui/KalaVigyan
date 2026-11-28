import json
import re
from collections.abc import Collection
from functools import cache
from pathlib import Path

from app.curation.files import CURATION_DIR
from app.data.contributor_kit import CONTRIBUTOR_SKILL_PATH
from app.data.monograph_files import MONOGRAPHS_DIR
from app.data.skill_library import REFERENCES_DIR
from app.models.enums import DISCIPLINES
from app.services.document_components_homes import authored_homes
from app.services.monograph_document import has_authored_content, monograph_content
from app.services.monograph_load import CROSS_REFERENCE, cited_refs, component_units

REPOSITORY = Path(__file__).resolve().parents[3]
CRAFT_PAGES_REFERENCES = REPOSITORY / ".claude" / "skills" / "kalavigyan-craft-pages" / "references"
FIELDS = "|".join(field.lower() for field in DISCIPLINES)
NAMED = re.compile(
    rf"`(?P<label>[a-z0-9][a-z0-9-]*/(?:{FIELDS})/[a-z0-9][a-z0-9-]*)`(?P<note>\s*\([^()]*\))?"
)
PAGE_ONLY = "page only"
UNKNOWN = "{label} is neither registered by the library's seed nor drawn by an authored page's component home"
UNMARKED = "{label} is drawn only by an authored page, so it is marked page only where it is named"


def reference_files() -> list[Path]:
    references = sorted(REFERENCES_DIR.glob("*.md")) + sorted(CRAFT_PAGES_REFERENCES.glob("*.md"))
    return [*references, CONTRIBUTOR_SKILL_PATH]


@cache
def dossier_claims(slug: str) -> frozenset[str]:
    path = CURATION_DIR / f"{slug}.json"
    if not path.is_file():
        return frozenset()
    return frozenset(claim["id"] for claim in json.loads(path.read_text(encoding="utf-8"))["claims"])


def held(slug: str, ref: str) -> bool:
    crossed = CROSS_REFERENCE.match(ref)
    if crossed is None:
        return ref in dossier_claims(slug)
    return crossed.group(3) in dossier_claims(crossed.group(2))


@cache
def library_labels() -> frozenset[str]:
    labels: set[str] = set()
    for folder in sorted(MONOGRAPHS_DIR.iterdir()):
        if not folder.is_dir() or not has_authored_content(folder.name):
            continue
        content = monograph_content(folder.name)
        for component in content.components:
            refs = cited_refs(content, component_units(content, component.label))
            if any(held(content.craft_slug, ref) for ref in refs):
                labels.add(component.label)
    return frozenset(labels)


@cache
def drawn_labels() -> frozenset[str]:
    return frozenset(authored_homes()["homes"])


def label_problems(text: str, library: Collection[str], drawn: Collection[str]) -> list[str]:
    problems = []
    for named in NAMED.finditer(text):
        label, note = named.group("label"), named.group("note") or ""
        if label in library:
            continue
        if label not in drawn:
            problems.append(UNKNOWN.format(label=label))
        elif PAGE_ONLY not in note:
            problems.append(UNMARKED.format(label=label))
    return problems


def test_every_label_the_references_name_is_in_the_library_or_marked_as_an_authored_page_s_own() -> None:
    found = {
        str(path.relative_to(REPOSITORY)): label_problems(
            path.read_text(encoding="utf-8"), library_labels(), drawn_labels()
        )
        for path in reference_files()
    }
    assert {path: problems for path, problems in found.items() if problems} == {}


def test_the_library_s_seed_registers_what_cites_a_stored_fact_and_leaves_out_what_cites_none() -> None:
    assert "shared/climate/kachchh-annual-rainfall-chart" in library_labels()
    assert "shared/climate/kachchh-annual-temperature-chart" not in library_labels()
    assert "shared/climate/kachchh-annual-temperature-chart" in drawn_labels()


def test_a_reference_naming_an_unknown_or_an_unmarked_page_s_own_label_fails() -> None:
    library, drawn = (
        {"shared/climate/kachchh-annual-rainfall-chart"},
        {"shared/climate/kachchh-annual-temperature-chart"},
    )
    old_line = "`shared/climate/kachchh-annual-rainfall-chart` and `shared/climate/kachchh-annual-temperature-chart`;"
    assert label_problems(old_line, library, drawn) == [
        UNMARKED.format(label="shared/climate/kachchh-annual-temperature-chart")
    ]
    marked = "`shared/climate/kachchh-annual-temperature-chart` (page only); `shared/climate/kachchh-annual-rainfall-chart`"
    assert label_problems(marked, library, drawn) == []
    unknown = "`shared/climate/jaipur-annual-rainfall-chart` (page only)"
    assert label_problems(unknown, library, drawn) == [
        UNKNOWN.format(label="shared/climate/jaipur-annual-rainfall-chart")
    ]
    assert label_problems("`backend/tests/mcp` and `kit-script/1`", library, drawn) == []
