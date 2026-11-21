from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
INDIA = Path("frontend/components/map/indiaGeometry.ts")
DISTRICTS = Path("frontend/public/boundaries/district-shapes.json")
REGISTER = Path("etl/geo/data/lgd_register.json")
OUTPUT = Path("frontend/public/layers")
SHADE_FILE = "relief-shade.webp"


def _write(path: Path, body: dict[str, Any]) -> None:
    text = json.dumps(body, ensure_ascii=False, separators=(",", ":")) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")
    print(f"{path.as_posix()} written, {len(text.encode('utf-8'))} bytes")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build the map's physical layers: rivers and lakes from Natural Earth 1:10m, relief bands and shaded "
            "relief from ETOPO1, and mineral deposits from the USGS Mineral Resources Data System, each fitted to "
            "the Survey of India outline and mirrored into the API, which measures each craft place's ground from "
            "them. Needs numpy, rasterio, shapely and pyogrio (the etl/geo environment)."
        )
    )
    parser.add_argument(
        "downloads",
        type=Path,
        help="folder holding each Natural Earth zip and its unzipped folder, etopo1_india.asc and mrds-csv.zip "
        "(see maplayers/sources.py for each URL)",
    )
    parser.add_argument(
        "--root", type=Path, default=REPO_ROOT, help="repository root to read from and write into"
    )
    options = parser.parse_args(argv)
    from maplayers.geo import india
    from maplayers.minerals import Place, minerals_body, read_sites
    from maplayers.relief import read_grid, relief_body, shade_webp
    from maplayers.rivers import rivers_body
    from maplayers.sources import BOUNDS, MRDS, Downloads
    from maplayers.states import state_locator

    downloads = Downloads(options.downloads)
    outline = india((options.root / INDIA).read_text(encoding="utf-8"))
    folder = options.root / OUTPUT
    folder.mkdir(parents=True, exist_ok=True)
    _write(folder / "rivers.json", rivers_body(downloads, outline))
    grid = read_grid(downloads)
    shade_webp(grid, outline, folder / SHADE_FILE)
    _write(folder / "relief.json", relief_body(downloads, grid, outline, _shade(grid.bounds)))
    locate = state_locator(options.root / DISTRICTS, options.root / REGISTER)
    place = Place(BOUNDS, lambda x, y: outline.contains(_point(x, y)), locate)
    sites = read_sites(downloads.folder / MRDS.file, place)
    _write(folder / "minerals.json", minerals_body(sites, downloads.source(MRDS)))
    return _mirrored(folder, options.root)


def _shade(bounds: tuple[float, float, float, float]) -> dict[str, Any]:
    west, south, east, north = bounds
    return {"href": f"/layers/{SHADE_FILE}", "west": west, "south": south, "east": east, "north": north}


def _mirrored(folder: Path, root: Path) -> int:
    from maplayers.mirror import MEASURED_OUTPUT, mirror_measured

    for path in mirror_measured(folder, root / MEASURED_OUTPUT):
        print(f"{path.as_posix()} mirrored")
    return 0


def _point(longitude: float, latitude: float) -> Any:
    from shapely.geometry import Point

    return Point(longitude, latitude)


if __name__ == "__main__":
    sys.exit(main())
