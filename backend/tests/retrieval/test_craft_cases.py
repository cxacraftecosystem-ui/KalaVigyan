import collections

import pytest

from app.core.errors import InvalidInput
from app.data.craft_master_loader import load_master
from app.research.crafts import CraftCandidate, CraftRef, CraftResolution, MatchReason
from app.retrieval.craft_cases import (
    CASE_KINDS,
    CASES_FILE,
    CaseOutcome,
    CraftCase,
    CraftNames,
    RecordedName,
    case_report,
    common_words,
    craft_cases,
    craft_cases_file,
    folded,
    outcome_of,
    parse_cases,
)
from app.scripts.build_craft_cases import cases_text

CASES_MIN = 300

AJRAKH = CraftNames(
    slug="Kutch-Ajrakh",
    name="Kutch Ajrakh",
    sub_category="Hand-Block-Printing",
    aliases=(
        RecordedName("Ajrak", "Latn", "CROSS_PORTAL_CODE", "ACTIVE"),
        RecordedName("Kachchh Ajrakh", "Latn", "TRANSLITERATION", "ACTIVE"),
        RecordedName("अजरख", "Deva", "WIKIDATA", "ACTIVE"),
        RecordedName("अज्रख", "Deva", "TRANSLITERATION", "PROPOSED"),
        RecordedName("Syahi Bégar", "Latn", "CURATED", "ACTIVE"),
    ),
)
BAGRU = CraftNames(
    slug="Bagru-Hand-Block-Print",
    name="Bagru Hand Block Print",
    sub_category="Hand-Block-Printing",
    aliases=(RecordedName("Syahi Begar", "Latn", "CURATED", "ACTIVE"),),
)


def by_key(crafts: list[CraftNames]) -> dict[str, CraftCase]:
    return {case.key: case for case in craft_cases(crafts, seed=3).cases}


def test_a_name_folds_by_case_accents_and_punctuation_but_another_script_keeps_its_marks() -> None:
    assert folded("Banaras Metal Repoussé Craft") == "banaras metal repousse craft"
    assert folded("Filigree & Silverware") == "filigree and silverware"
    assert folded("Applique (Khatwa) Work") == "applique khatwa work"
    assert folded("अजरख ") == "अजरख"


def test_each_craft_is_asked_by_its_name_an_alias_its_own_script_and_a_folded_name() -> None:
    cases = by_key([AJRAKH, BAGRU])
    assert cases["exact-name-Kutch-Ajrakh"].text == "Kutch Ajrakh"
    assert cases["exact-alias-Kutch-Ajrakh"].text in {"Ajrak", "Syahi Bégar"}
    assert cases["exact-native-Kutch-Ajrakh"].text == "अजरख"
    assert cases["folded-name-Kutch-Ajrakh"].text in {"KUTCH AJRAKH", "kutch ajrakh"}
    assert cases["folded-alias-Kutch-Ajrakh"].text == "Syahi Begar"
    assert all(case.status == "RESOLVED" for key, case in cases.items() if key.startswith("exact-name"))


def test_a_name_two_crafts_hold_expects_an_ambiguous_answer_offering_both() -> None:
    folded_alias = by_key([AJRAKH, BAGRU])["folded-alias-Kutch-Ajrakh"]
    assert folded_alias.status == "AMBIGUOUS"
    assert folded_alias.expected == ("Bagru-Hand-Block-Print", "Kutch-Ajrakh")


def test_a_comparison_names_two_crafts_of_one_sub_category_and_expects_both() -> None:
    (comparison,) = [case for case in craft_cases([AJRAKH, BAGRU], seed=3).cases if case.kind == "COMPARISON"]
    assert comparison.text in {
        "Kutch Ajrakh or Bagru Hand Block Print",
        "Bagru Hand Block Print or Kutch Ajrakh",
    }
    assert (comparison.status, set(comparison.expected)) == (
        "AMBIGUOUS",
        {"Kutch-Ajrakh", "Bagru-Hand-Block-Print"},
    )


def test_a_misspelling_edits_the_craft_s_longest_uncommon_word_once() -> None:
    words = {"Craft-L": "Lambani", "Craft-K": "Kasuti", "Craft-S": "Sujini", "Craft-P": "Phulkari"}
    crafts = [
        CraftNames(slug=slug, name=f"{word} Embroidery Work", sub_category=slug)
        for slug, word in words.items()
    ]
    assert common_words([craft.name for craft in crafts]) == {"embroidery", "work"}
    cases = craft_cases(crafts, seed=3).cases
    misspelled = [case for case in cases if case.kind == "MISSPELLED"]
    assert len(misspelled) == 4
    for case in misspelled:
        word, *rest = case.text.split()
        original = words[case.expected[0]]
        assert rest == ["Embroidery", "Work"] and word != original
        assert abs(len(word) - len(original)) <= 1 and word[0] == original[0]
    assert [case for case in cases if case.kind == "PARTIAL"] == []


def resolution(status: str, *slugs: str) -> CraftResolution:
    candidates = [
        CraftCandidate(
            craft=CraftRef(slug=slug, name=slug, path=f"/crafts/{slug}"),
            score=0.9 - 0.1 * rank,
            reasons=[MatchReason(kind="EXACT_NAME", matched=slug, score=1.0)],
        )
        for rank, slug in enumerate(slugs)
    ]
    craft = candidates[0].craft if status == "RESOLVED" else None
    return CraftResolution(status=status, craft=craft, candidates=candidates, normalised="x", script="Latn")


def test_a_case_passes_on_its_first_candidate_or_on_an_ambiguous_answer_offering_every_craft() -> None:
    single = CraftCase(
        key="s", kind="EXACT", text="Kutch Ajrakh", status="RESOLVED", expected=("Kutch-Ajrakh",)
    )
    pair = CraftCase(key="p", kind="COMPARISON", text="a or b", status="AMBIGUOUS", expected=("A", "B"))
    assert outcome_of(single, resolution("RESOLVED", "Kutch-Ajrakh")).resolved
    top = outcome_of(single, resolution("AMBIGUOUS", "Kutch-Ajrakh", "Other"))
    assert top.passed and not top.resolved
    assert not outcome_of(single, resolution("AMBIGUOUS", "Other", "Kutch-Ajrakh")).passed
    assert outcome_of(pair, resolution("AMBIGUOUS", "B", "A", "C")).passed
    assert not outcome_of(pair, resolution("RESOLVED", "A", "B")).passed
    outcomes = [CaseOutcome(single, "RESOLVED", ("Kutch-Ajrakh",)), CaseOutcome(single, "NONE", ())]
    assert case_report(outcomes) == {"EXACT": {"cases": 2, "passed": 0.5, "resolved": 0.5, "failed": ["s"]}}


def test_the_kept_cases_are_built_by_the_script_from_the_craft_lists() -> None:
    assert CASES_FILE.read_text(encoding="utf-8") == cases_text()


def test_the_kept_cases_cover_every_kind_and_name_only_listed_crafts() -> None:
    cases = craft_cases_file().cases
    kinds = collections.Counter(case.kind for case in cases)
    assert len(cases) >= CASES_MIN and set(kinds) == set(CASE_KINDS)
    assert kinds["EXACT"] + kinds["FOLDED"] >= CASES_MIN
    listed = {craft.slug for craft in load_master() if not craft.is_catch_all}
    assert {slug for case in cases for slug in case.expected} <= listed


def test_the_cases_file_is_versioned() -> None:
    with pytest.raises(InvalidInput, match="version 1"):
        parse_cases({"version": 2, "seed": 1, "cases": []})
