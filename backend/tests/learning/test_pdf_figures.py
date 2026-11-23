from io import BytesIO

from pypdf import PdfReader

from app.research.blocks_climate import ClimateSeries, GroundwaterValue
from app.research.datasets import BOUNDARY_CAPTION
from app.services.export_pdf_figures import draw_figure
from app.services.export_pdfs import explainer_pdf

from .figure_fixtures import drawn, golden_block, kachchh, kachchh_rain, pdf_text, report_of

PHASE_B = "explainer.phase-b.golden.json"
PHASE_C = "explainer.phase-c.golden.json"
PHASE_D = "explainer.phase-d.golden.json"
FIRST_YEAR = 1981
TREND_YEARS = 45
GAP_AT = 10
MAP_POINTS_MIN = 1000


def figure_of(name: str, block_id: str) -> tuple[str, bytes]:
    block = golden_block(name, block_id)
    return drawn(lambda writer: draw_figure(writer, block))


def line_ops(data: bytes) -> int:
    streams = (page.get_contents() for page in PdfReader(BytesIO(data)).pages)
    return sum(stream.get_data().count(b" l") for stream in streams if stream is not None)


def test_a_climate_block_draws_its_trend_with_slope_significance_and_mean() -> None:
    text, _ = figure_of(PHASE_D, "s6.b1")
    assert "Rainfall trend" in text
    assert "Rainfall in Kachchh has risen by 70.76 mm/year per decade" in text
    assert "+70.76 mm/year per decade" in text and "p = 0.005" in text
    assert "Mean 449.36 mm/year · 1981–2025 · 0.05 degree" in text
    assert "Theil–Sen slope per decade" in text
    assert "Drier" in text and "Wetter" in text


def test_a_climate_block_draws_its_yearly_series_and_groundwater() -> None:
    block = golden_block(PHASE_D, "s6.b1")
    values: list[float | None] = [400.0] * (TREND_YEARS - 1) + [520.5]
    values[GAP_AT] = None
    series = ClimateSeries(
        district=kachchh(),
        variable="annual_precipitation",
        dataset_code="CHIRPS_3_0",
        unit="mm/year",
        first_year=FIRST_YEAR,
        values=values,
    )
    water = GroundwaterValue(
        district=kachchh(),
        dataset_code="CGWB_DYNAMIC_2022",
        variable="stage_of_extraction",
        period="2022",
        value=112.5,
        value_text="Over-exploited",
        unit="%",
        resolution="block",
    )
    shown = block.model_copy(update={"series": [series], "groundwater": [water]})
    text, _ = drawn(lambda writer: draw_figure(writer, shown))
    assert "Rainfall by year · Kachchh" in text
    assert "1981–2025 · lowest 400 mm/year · highest 520.5 mm/year" in text
    assert "Groundwater" in text and "Stage of extraction · Kachchh" in text
    assert "Over-exploited · 112.5%" in text and "2022 · block" in text


def test_a_seasons_block_draws_its_rainfall_bars_and_month_strip() -> None:
    block = golden_block(PHASE_B, "s3.b1")
    row = block.rows[0].model_copy(update={"months": [6, 7, 8, 9]})
    shown = block.model_copy(update={"rows": [row], "rainfall": kachchh_rain()})
    text, _ = drawn(lambda writer: draw_figure(writer, shown))
    assert "July is the wettest month in Kachchh: 150 mm of a 394 mm year" in text
    assert "Rainfall, Kachchh" in text and "1991-2020" in text
    for value in ("150 mm", "120 mm", "60 mm", "0.4 mm", "0.0 mm"):
        assert value in text
    assert "Monsoon humidity" in text and "June–September" in text


def test_a_season_row_without_months_shows_its_season() -> None:
    text, _ = figure_of(PHASE_B, "s3.b1")
    assert text.count("Monsoon") == 2
    assert "June" not in text


def test_a_map_layer_draws_its_district_over_its_state_with_the_boundary_caption() -> None:
    text, data = figure_of(PHASE_B, "s2.b1")
    assert "Soil pH, 0-5 cm" in text and "Kachchh, Gujarat" in text
    assert BOUNDARY_CAPTION in text
    assert line_ops(data) > MAP_POINTS_MIN


def test_a_region_story_draws_its_districts_and_names_its_river() -> None:
    text, data = figure_of(PHASE_B, "s1.b1")
    assert "Kachchh, Gujarat" in text and "River: Khari" in text
    assert BOUNDARY_CAPTION in text
    assert line_ops(data) > MAP_POINTS_MIN


def test_a_zoom_story_draws_its_district_and_its_molecule() -> None:
    text, data = figure_of(PHASE_C, "s3.b1")
    assert "Kachchh, Gujarat" in text and BOUNDARY_CAPTION in text
    assert "Alizarin · C14H8O4 · PubChem CID 6293" in text
    assert line_ops(data) > MAP_POINTS_MIN


def test_players_molecules_materials_and_supply_draw_their_own_values() -> None:
    reaction, _ = figure_of(PHASE_B, "s4.b1")
    assert "Reactions" in reaction and "Scrap iron dissolving into iron acetate" in reaction
    assert "Fe + 2 CH3COOH -> Fe(CH3COO)2 + H2" in reaction
    molecule, _ = figure_of(PHASE_B, "s4.b3")
    assert "Alizarin · C14H8O4 · PubChem CID 6293" in molecule
    material, _ = figure_of(PHASE_B, "s4.b2")
    assert "Alum (fatakdi) · KAl(SO4)2·12H2O" in material and "karam" in material
    supply, _ = figure_of(PHASE_B, "s6.b1")
    assert "Indigo: Shikarpur, Dhamadka" in supply and "Blocks: Pethapur" in supply


def test_a_generated_explainer_draws_its_values_and_a_timeline_its_years() -> None:
    simulation, _ = figure_of(PHASE_C, "s1.b1")
    assert "How fast the water table falls" in simulation and "10-15 feet every year" in simulation
    timeline, _ = figure_of(PHASE_C, "s4.b1")
    assert "Fustat · 1401–1500" in timeline and "Dhamadka · 1586" in timeline
    assert "Ajrakhpur · 2001" in timeline and "Sindh to Kutch · 1586–1631" in timeline


def test_the_report_draws_each_block_before_its_sentences() -> None:
    document, refs = report_of(PHASE_D, ("s4", "s6"))
    text = pdf_text(explainer_pdf(document, refs, {}))
    measure = text.index("10-15 feet is 3.05–4.57 m")
    assert measure < text.index("Water levels have been going down by 10-15 feet every year")
    assert "Rainfall in Kachchh has risen by 70.76 mm/year per decade" in text
    assert "Climate Hazards Center InfraRed Precipitation with Stations v3.0" in text


def test_the_report_draws_the_place_and_matter_blocks_of_an_answer() -> None:
    document, refs = report_of(PHASE_B, ("s1", "s2", "s3", "s4", "s6"))
    data = explainer_pdf(document, refs, {})
    text = pdf_text(data)
    assert text.count(BOUNDARY_CAPTION) == 2
    assert "Soil pH, 0-5 cm" in text and "Fe + 2 CH3COOH -> Fe(CH3COO)2 + H2" in text
    assert line_ops(data) > 2 * MAP_POINTS_MIN
