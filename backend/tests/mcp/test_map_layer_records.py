import re
from typing import Any

from app.api.mcp_tools import ToolContext, answer
from app.geo.layers import MAP_LAYERS
from app.services.craft_resolver import CraftIndexStore
from app.services.layer_guide import NO_RECORD_HELD, layers_text, map_layers_text
from app.services.layer_records import SiteLayer, layer_row_refs, physical_records, site_layers

CONTEXT = ToolContext(session=None, index=CraftIndexStore(), site="https://kalavigyan.example")  # type: ignore[arg-type]
SHA256 = re.compile(r"^[0-9a-f]{64}$")
ETOPO = "ETOPO1_ICE"
NATURAL_EARTH = "NATURAL_EARTH_10M_PHYSICAL"


def test_each_physical_layer_reads_its_dataset_record_from_the_file_it_is_drawn_from() -> None:
    relief, rivers, minerals = (physical_records(name) for name in ("relief", "rivers", "minerals"))
    assert [record.code for record in relief] == [ETOPO, NATURAL_EARTH]
    assert [record.code for record in rivers] == [NATURAL_EARTH]
    assert [record.code for record in minerals] == ["USGS_MRDS"]
    etopo, earth = relief
    assert (etopo.version, etopo.licence, etopo.doi) == (
        "1",
        "Public domain (U.S. Government work)",
        "10.7289/V5C8276M",
    )
    assert etopo.citation is not None and etopo.citation.startswith("Amante, C. and B.W. Eakins, 2009.")
    assert (earth.version, earth.licence, earth.redistributable) == ("5.0.0", "Public domain", True)
    for record in (etopo, earth, *minerals):
        assert record.read_on is not None and SHA256.match(record.sha256 or ""), record.code


def test_a_layer_file_that_names_no_record_reads_none() -> None:
    assert layer_row_refs({"source": "Elevations in bands", "licence": "Public domain"}) == ()
    assert layer_row_refs({"datasets": [], "source": "Rivers"}) == ()
    assert layer_row_refs({"datasets": [{"title": "A row with no code"}]}) == ()


def test_every_layer_a_map_may_name_is_listed_with_its_record_and_one_without_is_flagged() -> None:
    text = map_layers_text()
    assert text.startswith("# The map layers and their dataset records\n\n")
    for name in ("relief", "rivers", "minerals", *(spec.id for spec in MAP_LAYERS)):
        assert f"| `{name}` |" in text, name
    for code in (ETOPO, NATURAL_EARTH, "USGS_MRDS", "OSM_WATERWAYS", "CHELSA_2_1_1981_2010"):
        assert f"\n### {code}\n" in text, code
    assert NO_RECORD_HELD not in text
    assert all(layer.records for layer in site_layers())
    flagged = layers_text(
        [SiteLayer("bare-soil", "Bare soil", "each district filled by its value's class", ())]
    )
    assert (
        f"| `bare-soil` | Bare soil | each district filled by its value's class | {NO_RECORD_HELD} |"
        in flagged
    )
    assert "\n### " not in flagged


async def test_a_contributor_s_ai_reads_the_layers_and_their_records_over_mcp_with_get_page() -> None:
    found = await answer(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "get_page", "arguments": {"guide": "map-layers/1"}},
        },
        CONTEXT,
    )
    assert found is not None
    shown: dict[str, Any] = found["result"]["structuredContent"]
    (sheet,) = shown["guide"]["pages"]
    assert (sheet["address"], sheet["page"]) == ("map-layers/1", 1)
    assert sheet["text"].startswith("# The map layers and their dataset records")
    assert "| `relief` |" in sheet["text"] and ETOPO in sheet["text"]
