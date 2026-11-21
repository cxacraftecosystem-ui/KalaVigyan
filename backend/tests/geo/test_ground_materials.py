import pytest

from app.geo.ground_layers import Deposit
from app.geo.ground_materials import CraftMaterial, material_commodities, material_deposits, soil_materials


def site(dep_id: int, *commodities: str) -> Deposit:
    return Deposit(dep_id, f"site {dep_id}", 77.0, 20.0, 0, "Occurrence", commodities)


@pytest.mark.parametrize(
    ("name", "kind", "commodities"),
    [
        ("Alum", "MORDANT", ("Aluminum",)),
        ("Iron filings", "METAL", ("Iron",)),
        ("Red ochre (geru)", "MINERAL", ("Iron",)),
        ("Brass sheet", "METAL", ("Copper", "Zinc")),
        ("Bell metal", "METAL", ("Copper",)),
        ("Slaked lime", "MINERAL", ("Calcium",)),
        ("Lime juice", "OTHER", ()),
        ("Makrana marble", "MINERAL", ("Stone, Dimension", "Marble")),
        ("Natural indigo", "DYE", ()),
        ("Iron mordant bath", "DYE", ()),
    ],
)
def test_a_material_names_the_commodities_of_the_minerals_it_is_made_of(
    name: str, kind: str, commodities: tuple[str, ...]
) -> None:
    assert material_commodities(CraftMaterial(name, kind)) == commodities


def test_clays_and_earths_are_read_against_the_soil_not_the_deposit_records() -> None:
    materials = [
        CraftMaterial("River silt", "OTHER"),
        CraftMaterial("Kaolin", "CLAY"),
        CraftMaterial("Alum", "MORDANT"),
    ]
    assert soil_materials(materials) == ["Kaolin", "River silt"]


def test_each_material_counts_its_deposits_within_the_radius_and_the_nearest() -> None:
    found = [
        (site(1, "Iron"), 11.12),
        (site(2, "Copper", "Gold"), 20.0),
        (site(3, "Iron", "Manganese"), 33.36),
    ]
    materials = [
        CraftMaterial("Iron filings", "METAL"),
        CraftMaterial("Alum", "MORDANT"),
        CraftMaterial("Brass", "METAL"),
    ]
    matched = material_deposits(materials, found)
    assert [(m.material, m.commodities, m.count, m.nearest_km) for m in matched] == [
        ("Brass", ["Copper", "Zinc"], 1, 20.0),
        ("Iron filings", ["Iron"], 2, 11.1),
    ]
