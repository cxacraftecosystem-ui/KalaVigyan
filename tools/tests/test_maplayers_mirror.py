from __future__ import annotations

from pathlib import Path

from maplayers.mirror import MEASURED_FILES, MEASURED_OUTPUT, mirror_measured, unmirrored

REPO_ROOT = Path(__file__).resolve().parents[2]
DRAWN = REPO_ROOT / "frontend" / "public" / "layers"


def test_the_api_measures_from_the_same_layer_files_the_map_draws() -> None:
    assert MEASURED_FILES == ("relief.json", "rivers.json", "minerals.json")
    assert unmirrored(DRAWN, REPO_ROOT / MEASURED_OUTPUT) == []


def test_a_build_mirrors_each_measured_layer_byte_for_byte(tmp_path: Path) -> None:
    drawn, measured = tmp_path / "drawn", tmp_path / "measured"
    drawn.mkdir()
    for at, name in enumerate(MEASURED_FILES):
        (drawn / name).write_bytes(f'{{"layer":{at}}}\n'.encode())
    assert unmirrored(drawn, measured) == list(MEASURED_FILES)
    written = mirror_measured(drawn, measured)
    assert [path.name for path in written] == list(MEASURED_FILES)
    assert (measured / "rivers.json").read_text(encoding="utf-8") == '{"layer":1}\n'
    assert unmirrored(drawn, measured) == []
    (measured / "minerals.json").write_text("{}\n", encoding="utf-8")
    assert unmirrored(drawn, measured) == ["minerals.json"]
