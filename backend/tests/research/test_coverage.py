import pytest
from pydantic import ValidationError

from app.research.coverage import (
    COVERED,
    MISSING,
    THIN,
    CoverageSubject,
    FieldCount,
    FieldCoverage,
    Holdings,
    field_coverage,
    field_standing,
    held_fields,
)

SUBJECT = CoverageSubject("craft", "Test-Craft", "Test Craft")
HOLDINGS = Holdings(
    filed={
        "c1": frozenset({"CHEMISTRY"}),
        "c2": frozenset({"CHEMISTRY", "HISTORY"}),
        "c3": frozenset({"HISTORY"}),
        "c4": frozenset({"HISTORY"}),
    },
    sources={
        "c1": frozenset({"s1"}),
        "c2": frozenset({"s1", "s2"}),
        "c3": frozenset(),
        "c4": frozenset({"s3"}),
    },
    structure={"SOCIETY": frozenset({"c4", "c9"}), "POLICY": frozenset({"c1"})},
    sections={"CHEMISTRY": 4, "HISTORY": 0},
    figures={"CHEMISTRY": frozenset({"alum-player", "lake-molecule"})},
)


def counted(coverage: FieldCoverage, field: str) -> tuple[int, int, int, int, int, int, str]:
    count = coverage.count(field)
    return (
        count.claims,
        count.structure_claims,
        count.sources,
        count.sections,
        count.sentences,
        count.figures,
        count.standing,
    )


def test_each_field_counts_its_cited_claims_their_sources_its_section_and_figures() -> None:
    coverage = field_coverage(SUBJECT, HOLDINGS, claims_min=3)
    assert counted(coverage, "CHEMISTRY") == (2, 0, 2, 1, 4, 2, THIN)
    assert counted(coverage, "HISTORY") == (2, 0, 3, 1, 0, 0, THIN)
    assert counted(coverage, "PHYSICS") == (0, 0, 0, 0, 0, 0, MISSING)


def test_structure_cited_claims_count_for_society_and_policy_once_and_only_when_cited() -> None:
    coverage = field_coverage(SUBJECT, HOLDINGS, claims_min=3)
    assert counted(coverage, "SOCIETY") == (1, 1, 1, 0, 0, 0, THIN)
    assert counted(coverage, "POLICY") == (1, 1, 1, 0, 0, 0, THIN)
    assert (coverage.claims, coverage.sources) == (3, 3)


def test_the_bar_sets_which_fields_are_covered_thin_or_missing() -> None:
    coverage = field_coverage(SUBJECT, HOLDINGS, claims_min=2)
    assert coverage.covered == ["CHEMISTRY", "HISTORY"]
    assert coverage.thin == ["SOCIETY", "POLICY"]
    assert len(coverage.missing) == 12 and "PHYSICS" in coverage.missing
    assert [count.field for count in coverage.fields][:3] == ["OVERVIEW", "PROCESS", "CHEMISTRY"]
    assert held_fields(coverage) == ("CHEMISTRY", "HISTORY", "SOCIETY", "POLICY")


@pytest.mark.parametrize(
    ("claims", "standing"), [(0, MISSING), (1, THIN), (2, THIN), (3, COVERED), (9, COVERED)]
)
def test_a_field_is_covered_at_three_cited_claims(claims: int, standing: str) -> None:
    assert field_standing(claims, claims_min=3) == standing


def test_a_subject_with_nothing_stored_misses_all_sixteen_fields() -> None:
    coverage = field_coverage(CoverageSubject("category", "Textiles", "Textiles"), Holdings(), claims_min=3)
    assert (coverage.claims, coverage.sources, coverage.covered, coverage.thin) == (0, 0, [], [])
    assert len(coverage.missing) == 16


def test_counts_that_disagree_are_refused() -> None:
    with pytest.raises(ValidationError, match="missing exactly when"):
        FieldCount(
            field="CHEMISTRY",
            claims=2,
            structure_claims=0,
            sources=1,
            sections=0,
            sentences=0,
            figures=0,
            standing=MISSING,
        )
    coverage = field_coverage(SUBJECT, HOLDINGS, claims_min=3).model_dump(mode="json", by_alias=True)
    with pytest.raises(ValidationError, match="vocabulary order"):
        FieldCoverage.model_validate({**coverage, "fields": list(reversed(coverage["fields"]))})
    with pytest.raises(ValidationError, match="disagrees with its claims"):
        FieldCoverage.model_validate({**coverage, "claimsMin": 1})
