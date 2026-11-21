from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Sequence

from repo_facts.counts import HTTP_METHODS, Facts

__all__ = ["render"]

BUILD = "tools/repo_facts_build.py"
OPENING = (
    "# Repository facts\n\n"
    f"Every count that changes with the code, generated from the working tree by `{BUILD}`; never edit "
    "this file by hand. Other documents link here instead of restating a number, so a new table, route, "
    "tool or test makes exactly one file stale and one command makes it right. The figures describe the "
    "tree, not production: the deployed API lags the tree by the commits not yet released."
)
KEPT_TRUE = (
    "## How this document is kept true\n\n"
    "| What | How |\n"
    "|---|---|\n"
    f"| Regenerate | `backend/.venv/Scripts/python.exe {BUILD}` from the repository root "
    "(`backend/.venv/bin/python` off Windows) |\n"
    "| Diff against | `--check`, which exits 1 when this file differs from a fresh count and writes nothing |\n"
    "| Counted from | the files `git ls-files` lists and the untracked files that are not ignored, the list the "
    "hygiene check reads, so regenerate on a clean tree after a round's last merge |\n"
    "| Rules | `tools/repo_facts/counts.py`, tested by `tools/tests/test_repo_facts.py` on a small tree whose "
    "counts are worked out by hand |\n\n"
    "Re-read the counting rules when a new kind of table, route, MCP tool or test layout appears: a count "
    "is only as true as the pattern that finds it."
)


def render(facts: Facts) -> str:
    sections = (
        OPENING,
        _data_model(facts),
        _http_api(facts),
        _mcp(facts),
        _tests(facts),
        _records(facts),
        _volume(facts),
        KEPT_TRUE,
    )
    return "\n\n".join(sections) + "\n"


def _table(header: Sequence[str], rows: Iterable[Sequence[object]], numeric_from: int = 1) -> str:
    rule = ["---" if index < numeric_from else "---:" for index in range(len(header))]
    lines = [_row(header), _row(rule)]
    lines.extend(_row([str(cell) for cell in row]) for row in rows)
    return "\n".join(lines)


def _row(cells: Sequence[str]) -> str:
    return "| " + " | ".join(cells) + " |"


def _names(values: Iterable[str]) -> str:
    return ", ".join(f"`{value}`" for value in values) + "."


def _data_model(facts: Facts) -> str:
    counts = _table(
        ["What", "Count"],
        [
            ["Tables (`__tablename__` in `backend/app/models/`)", len(facts.tables)],
            ["Migrations (`backend/migrations/versions/`)", len(facts.migrations)],
        ],
    )
    newest = f"Newest migration: `{facts.migrations[-1]}`." if facts.migrations else "No migrations."
    return f"## Data model\n\n{counts}\n\n{newest}\n\nTables: {_names(facts.tables)}"


def _http_api(facts: Facts) -> str:
    total: Counter[str] = Counter()
    for methods in facts.operations.values():
        total.update(methods)
    spread = ", ".join(f"{total[method.upper()]} {method.upper()}" for method in HTTP_METHODS)
    ranked = sorted(facts.operations.items(), key=lambda item: (-item[1].total(), item[0]))
    rows = [[f"`{name}`", methods.total()] for name, methods in ranked]
    table = _table(["Module", "Operations"], rows)
    summary = (
        f"**{total.total()} operations** in `backend/app/api/routes/` and `backend/app/main.py`: {spread}."
    )
    return f"## HTTP API\n\n{summary}\n\n{table}"


def _mcp(facts: Facts) -> str:
    rows = [[f"`{name}`", count] for name, count in sorted(facts.mcp_tools.items())]
    summary = f"**{facts.mcp_tools.total()} tools**, each a `Tool(...)` declared in `backend/app/api/`."
    return f"## MCP server\n\n{summary}\n\n{_table(['Module', 'Tools'], rows)}"


def _tests(facts: Facts) -> str:
    python = _table(["Python suite", "Files", "Tests"], facts.python_tests)
    frontend = _table(["Frontend (`frontend/e2e/`)", "Files", "Tests"], facts.frontend_tests)
    note = (
        "A Python test is a `test_` function in a `test_` file; a frontend test is a `test(` call at the start "
        "of a line. Every suite runs on GitHub Actions, never on a development machine."
    )
    return f"## Tests\n\n{python}\n\n{frontend}\n\n{note}"


def _records(facts: Facts) -> str:
    return f"## Records\n\n{_table(['What', 'Count'], facts.records)}"


def _volume(facts: Facts) -> str:
    rows = [[f"`{area}`", files, f"{lines:,}"] for area, files, lines in facts.volume]
    note = "Code files are `.py`, `.ts`, `.tsx`, `.mjs`, `.css`, `.sh`, `.tf` and `.sql`; lines are newlines."
    return f"## Code volume\n\n{_table(['Area', 'Files', 'Lines'], rows)}\n\n{note}"
