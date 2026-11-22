from __future__ import annotations

import re
from pathlib import Path

import pytest

from brand.wordmark import lockup

REPO_ROOT = Path(__file__).resolve().parents[2]
OUTLINES = REPO_ROOT / "frontend" / "components" / "brandOutlines.ts"
TOKEN = re.compile(r"[A-Za-z]|-?\d+(?:\.\d+)?")
TOLERANCE = 0.05


def committed(name: str) -> str:
    found = re.search(rf'export const {name} =\s*"([^"]+)";', OUTLINES.read_text(encoding="utf-8"))
    assert found is not None, f"{name} is not in {OUTLINES.name}"
    return found.group(1)


def same_outline(written: str, kept: str) -> bool:
    a, b = TOKEN.findall(written), TOKEN.findall(kept)
    if len(a) != len(b):
        return False
    for x, y in zip(a, b, strict=True):
        if x.isalpha() or y.isalpha():
            if x != y:
                return False
        elif abs(float(x) - float(y)) > TOLERANCE:
            return False
    return True


@pytest.fixture(scope="module")
def written() -> dict[str, object]:
    return lockup()


def test_the_generator_reads_the_woff2_fonts_in_the_backend_environment(written: dict[str, object]) -> None:
    assert str(written["latin"]).startswith("M")
    assert str(written["devanagari"]).startswith("M")


def test_the_committed_outlines_are_what_the_generator_writes(written: dict[str, object]) -> None:
    rule = re.search(r"WORDMARK_RULE = \{ x: ([\d.]+),", OUTLINES.read_text(encoding="utf-8"))
    assert rule is not None
    assert written["ruleX"] == pytest.approx(float(rule.group(1)), abs=TOLERANCE)
    assert same_outline(str(written["latin"]), committed("WORDMARK_LATIN_PATH"))
    assert same_outline(str(written["devanagari"]), committed("WORDMARK_DEVANAGARI_PATH"))
