import pytest

from app.retrieval.craft_cases import LEXICAL_KINDS, PASS_FLOOR, case_report, craft_cases_file, outcome_of
from app.services.craft_matching import lexical_match, resolution_from
from app.services.craft_resolver import load_index

from .field_voices_rows import rolled_back

pytestmark = pytest.mark.db

LEXICAL_CASES_MIN = 300


async def test_the_lexical_resolver_finds_each_craft_by_its_names_on_the_seeded_crafts() -> None:
    async with rolled_back() as session:
        index = await load_index(session)
    cases = [case for case in craft_cases_file().cases if case.kind in LEXICAL_KINDS]
    assert len(cases) >= LEXICAL_CASES_MIN
    outcomes = [outcome_of(case, resolution_from(index, lexical_match(index, case.text))) for case in cases]
    report = case_report(outcomes)
    assert set(report) == LEXICAL_KINDS, report
    for kind in sorted(LEXICAL_KINDS):
        assert report[kind]["passed"] >= PASS_FLOOR, (kind, report[kind])
