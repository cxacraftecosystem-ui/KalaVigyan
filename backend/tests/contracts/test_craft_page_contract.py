import gzip
import uuid
from pathlib import Path

from app.research.craft_page import CraftPage, craft_page_text
from app.scripts.import_curation import main
from app.services.chapter_preview import chapter_preview
from app.services.craft_page_preview import register_page
from app.services.curation_keys import curated_id

from ..curation.import_support import AJRAKH, AJRAKH_GOLDEN, raw
from ..geo.golden_region import KACHCHH, env_rows
from .golden import SHARED, golden_json, golden_text, reproduces

REGISTER_GOLDEN = "craft.page.register.golden.json"
REGISTER_CRAFT = "Farrukhabad-Prints"
FAMILY = "Textiles-Based-Craft-Category"
INPUTS = "craft.page.inputs.json"
GZIPPED_MAX_BYTES = 250 * 1024
PREVIEW_FLAGS = ["--family", FAMILY, "--inputs", str(SHARED / INPUTS)]


def ajrakh_preview() -> CraftPage:
    return chapter_preview(AJRAKH, family=FAMILY, inputs=SHARED / INPUTS)


def test_the_craft_page_golden_parses_and_matches_the_response_models() -> None:
    assert reproduces(CraftPage, AJRAKH_GOLDEN)


def test_the_craft_page_golden_is_the_kutch_ajrakh_dossier_as_served() -> None:
    assert craft_page_text(ajrakh_preview()) == golden_text(AJRAKH_GOLDEN)


def test_the_climate_series_are_kachchh_s_yearly_district_means_as_the_geo_etl_wrote_them() -> None:
    stored = {
        (row.dataset_code, row.variable, int(row.depth_or_period)): row.value
        for row in env_rows(KACHCHH)
        if row.stat == "DISTRICT_MEAN" and row.depth_or_period.isdigit()
    }
    series = golden_json(INPUTS)["series"]
    assert [
        (item["datasetCode"], item["variable"], item["firstYear"], len(item["values"])) for item in series
    ] == [
        ("CHIRPS_3_0", "annual_precipitation", 1981, 45),
        ("GHCN_CAMS_T2M", "annual_mean_temperature", 1981, 45),
    ]
    for item in series:
        years = range(item["firstYear"], item["firstYear"] + len(item["values"]))
        assert item["values"] == [stored[item["datasetCode"], item["variable"], year] for year in years]
    assert series[0]["values"][:2] == [518.454025, 330.546987]


def test_the_golden_holds_to_its_gzipped_budget() -> None:
    assert len(gzip.compress(golden_text(AJRAKH_GOLDEN).encode("utf-8"))) < GZIPPED_MAX_BYTES


def test_the_golden_claims_are_the_dossier_claims_and_the_family_science_it_cites() -> None:
    page = golden_json(AJRAKH_GOLDEN)
    own = {str(curated_id(AJRAKH, claim["id"])) for claim in raw(AJRAKH)["claims"]}
    family = {str(curated_id(FAMILY, claim["id"])) for claim in raw(f"categories/{FAMILY}")["claims"]}
    listed = {claim["id"] for claim in page["claims"]}
    assert own <= listed
    assert listed - own and listed - own <= family
    assert uuid.UUID(page["craft"]["id"])
    assert page["curated"] is True


def test_the_register_page_golden_parses_and_matches_the_response_models() -> None:
    assert reproduces(CraftPage, REGISTER_GOLDEN)


def test_the_register_page_golden_is_a_craft_without_a_dossier_beside_kutch_ajrakh() -> None:
    page = register_page(REGISTER_CRAFT, dossiers=[AJRAKH], family=FAMILY)
    assert craft_page_text(page) == golden_text(REGISTER_GOLDEN)
    assert (page.curated, page.claims, page.depth.basis) == (False, [], "REGISTER")


def test_the_documented_commands_write_both_goldens(tmp_path: Path) -> None:
    curated, register = tmp_path / AJRAKH_GOLDEN, tmp_path / REGISTER_GOLDEN
    assert main(["--preview", AJRAKH, *PREVIEW_FLAGS, "--out", str(curated)]) == 0
    register_flags = ["--with-dossier", AJRAKH, "--family", FAMILY]
    assert main(["--register-preview", REGISTER_CRAFT, *register_flags, "--out", str(register)]) == 0
    assert curated.read_bytes() == golden_text(AJRAKH_GOLDEN).encode("utf-8")
    assert register.read_bytes() == golden_text(REGISTER_GOLDEN).encode("utf-8")
