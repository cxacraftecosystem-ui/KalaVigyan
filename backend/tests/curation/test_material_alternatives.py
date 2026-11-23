from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.curation.entities import MaterialAlternative
from app.curation.entity_rules import alternative_problems
from app.curation.references import reference_problems
from app.data.district_register import load_district_codes
from app.services.curated_index import IndexAlternative
from app.services.curation_keys import curated_id
from app.services.curation_page_index import curated_page_index
from app.services.curation_rows import concept_plan
from app.services.curation_structure import alternative_rows
from app.services.dossier_export_parts import page_materials

from .builders import changed_dossier, passing_dossier

SLUG = "Kutch-Ajrakh"


def alternatives(*given: tuple[str, str]) -> Callable[[dict[str, Any]], None]:
    def change(plain: dict[str, Any]) -> None:
        plain["materials"][0]["alternatives"] = [
            {"materialId": other, "claimId": claim} for other, claim in given
        ]

    return change


def found(problems: list[Any]) -> list[tuple[str, str]]:
    return [(problem.where, problem.message) for problem in problems]


def test_a_material_names_another_material_of_the_dossier_once_as_its_alternative() -> None:
    assert alternative_problems(changed_dossier(alternatives(("M02", "C004")))) == []
    twice = changed_dossier(alternatives(("M01", "C004"), ("M02", "C004"), ("M02", "C005")))
    assert found(alternative_problems(twice)) == [
        ("M01", "a material is never its own alternative"),
        ("M01", "M02 is listed as its alternative more than once"),
    ]
    unknown = found(reference_problems(changed_dossier(alternatives(("M09", "C004"), ("M02", "C099")))))
    assert ("M01", "M09 names no material in the dossier") in unknown
    assert ("M01", "C099 names no claim in the dossier") in unknown


def test_an_alternative_is_imported_as_a_contrast_edge_resting_on_its_claim() -> None:
    dossier = changed_dossier(alternatives(("M02", "C004")))
    concepts = concept_plan(dossier, craft_id=None, name="Kutch Ajrakh")
    (row,) = alternative_rows(dossier, concepts)
    assert (row["srcId"], row["dstId"], row["relation"], row["claimId"]) == (
        concepts.ids["M01"],
        concepts.ids["M02"],
        "CONTRASTS_WITH",
        curated_id(SLUG, "C004"),
    )
    plain = passing_dossier()
    assert alternative_rows(plain, concept_plan(plain, craft_id=None, name="Kutch Ajrakh")) == []


def test_an_alternative_is_kept_on_the_page_and_comes_back_in_the_exported_dossier() -> None:
    dossier = changed_dossier(alternatives(("M02", "C004")))
    concepts = concept_plan(dossier, craft_id=None, name="Kutch Ajrakh")
    page = curated_page_index(dossier, concepts, load_district_codes(), set())
    assert page.materials[0].alternatives == [IndexAlternative(key="M02", claim_id=curated_id(SLUG, "C004"))]
    assert page.materials[1].alternatives == []
    keys = {curated_id(SLUG, claim.id): claim.id for claim in dossier.claims}
    exported = page_materials(page, keys)
    assert exported[0].alternatives == [MaterialAlternative(material_id="M02", claim_id="C004")]
    assert exported[1].alternatives == []
