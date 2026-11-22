import argparse
import dataclasses
import datetime as dt
import json
import re
import sys
import time
from collections.abc import Callable
from pathlib import Path

import pandas as pd

from geo_etl import catalog, river_names_files, rivers
from geo_etl.coverage import coverage_of
from geo_etl.districts import SHAPES_PATH, districts_without_shapes, load_districts, sha256_of
from geo_etl.layers import (
    Options,
    Result,
    chelsa,
    chirps,
    copdem,
    geology,
    ghcncams,
    groundwater,
    hansen,
    hydrorivers,
    soilgrids,
    worldcover,
)
from geo_etl.layers.geology import GEOLOGY_COLUMNS
from geo_etl.rows import COLUMNS

ROOT = Path(__file__).resolve().parent.parent
LAYERS: dict[str, Callable[..., Result]] = {
    "soilgrids": soilgrids.run,
    "worldcover": worldcover.run,
    "hansen": hansen.run,
    "chelsa": chelsa.run,
    "chirps": chirps.run,
    "ghcncams": ghcncams.run,
    "groundwater": groundwater.run,
    "copdem": copdem.run,
    "hydrorivers": hydrorivers.run,
    "mrds": geology.run_mrds,
    "glim": geology.run_glim,
}
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
DATASET_LABELS = {
    "SOILGRIDS_2_0": "SoilGrids-2-0",
    "ESA_WORLDCOVER_2021_V200": "ESA-WorldCover-2021-v200",
    "HANSEN_GFC_2025_V1_13": "Hansen-GFC-2025-v1-13",
    "CHELSA_2_1_1981_2010": "CHELSA-2-1-1981-2010",
    "CHIRPS_3_0": "CHIRPS-3-0",
    "GHCN_CAMS_T2M": "GHCN-CAMS-T2M",
    "OGD_GW_RESOURCES_RAJASTHAN_2023": "Groundwater-Rajasthan-2023",
    "COPERNICUS_DEM_GLO90": "Copernicus-DEM-GLO-90",
    "HYDRORIVERS_1_0": "HydroRIVERS-1-0",
    "USGS_MRDS": "USGS-MRDS",
    "GLIM_1_0_05DEG": "GLiM-1-0",
}
CSV_GLOB = "KalaVigyan_Dataset_*_District-Stats.csv"
SUMMARY_LAYER_KEYS = (
    "layer",
    "shard",
    "districts",
    "rows",
    "geologyRows",
    "districtsWithoutValues",
    "districtsWithoutCells",
    "unexpectedWithoutCells",
    "silentDistricts",
    "lostStates",
    "seconds",
    "notes",
    "options",
)
PART_FAILING = {
    "lostStates": "states {} have no district with values or without valid cells, or lost a whole step",
    "silentDistricts": "districts {} have no values, no failure and no listing without valid cells",
    "unexpectedWithoutCells": (
        "districts {} were measured without a valid cell but are not in coverage.EXPECTED_WITHOUT_CELLS; "
        "check the grid, then fix the read or add them there with the evidence"
    ),
}


def dataset_label(code: str) -> str:
    if code in DATASET_LABELS:
        return DATASET_LABELS[code]
    words = [w for w in re.split(r"[^A-Za-z0-9]+", code) if w]
    return "-".join(w if any(c.isdigit() for c in w) else w.capitalize() for w in words)


def district_stats_filename(code: str, generated: dt.datetime) -> str:
    label = dataset_label(code)
    date = generated.astimezone(IST).strftime("%Y-%m-%d")
    return "_".join(part for part in ("KalaVigyan", "Dataset", date, label, "District-Stats") if part) + ".csv"


def write_dataset_csvs(values: pd.DataFrame, out: Path, generated: dt.datetime) -> list[str]:
    for stale in out.glob(CSV_GLOB):
        stale.unlink()
    names = []
    for code, frame in values.groupby("datasetCode", sort=True):
        name = district_stats_filename(str(code), generated)
        frame.to_csv(out / name, index=False, encoding="utf-8", lineterminator="\n")
        names.append(name)
    return names


def parse_ints(text: str | None) -> set[int] | None:
    if not text or text.strip().lower() == "all":
        return None
    return {int(v) for v in text.replace(" ", "").split(",") if v}


def select_shard(districts: pd.DataFrame, shard: str | None):
    if not shard:
        return districts
    index, count = (int(v) for v in shard.split("/"))
    if not 1 <= index <= count:
        raise SystemExit(f"--shard {shard}: expected k/n with 1 <= k <= n")
    areas = districts.groupby("stateLgd")["areaKm2"].sum().sort_values(ascending=False, kind="stable")
    loads = [0.0] * count
    owner: dict[int, int] = {}
    for state, area in areas.items():
        target = min(range(count), key=lambda i: (loads[i], i))
        owner[int(state)] = target + 1
        loads[target] += float(area)
    return districts[districts["stateLgd"].map(owner) == index].reset_index(drop=True)


def options_from(args: argparse.Namespace) -> Options:
    options = Options(cache=Path(args.cache))
    for name in ("worldcover_factor", "hansen_factor", "dem_factor", "climate_first_year", "chirps_last_year"):
        if getattr(args, name, None) is not None:
            options = dataclasses.replace(options, **{name: getattr(args, name)})
    if args.soil_vars:
        options = dataclasses.replace(options, soil_vars=tuple(args.soil_vars.split(",")))
    if args.soil_depths:
        options = dataclasses.replace(options, soil_depths=tuple(args.soil_depths.split(",")))
    if args.chelsa_bio:
        options = dataclasses.replace(options, chelsa_bio=tuple(args.chelsa_bio.split(",")))
    return dataclasses.replace(
        options,
        soil_uncertainty=not args.no_soil_uncertainty,
        chelsa_months=not args.no_chelsa_months,
        chirps_monthly=not args.no_chirps_monthly,
        download_striped=args.download_striped,
    )


def extract(args: argparse.Namespace) -> int:
    parts = Path(args.parts)
    parts.mkdir(parents=True, exist_ok=True)
    districts = select_shard(load_districts(parse_ints(args.districts), parse_ints(args.states)), args.shard)
    if districts.empty:
        print("no districts selected", file=sys.stderr)
        return 2
    options = options_from(args)
    keys = [k.strip() for k in args.datasets.split(",")] if args.datasets != "all" else list(LAYERS)
    metas = [extract_layer(key, districts, options, parts=parts, shard=args.shard) for key in keys]
    return part_status(metas, allow_failures=args.allow_failures)


def extract_layer(key: str, districts: pd.DataFrame, options: Options, *, parts: Path, shard: str | None) -> dict:
    started = time.monotonic()
    result = LAYERS[key](districts, options)
    stem = key if shard is None else f"{key}-shard{shard.replace('/', 'of')}"
    result.values.to_parquet(parts / f"{stem}.parquet", index=False)
    if result.geology is not None:
        result.geology.to_parquet(parts / f"{stem}.geology.parquet", index=False)
    reach = coverage_of(districts, result)
    meta = {
        "layer": key,
        "stem": stem,
        "shard": shard,
        "dataset": result.dataset.as_row(),
        "retrievedAt": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "districts": int(len(districts)),
        "rows": int(len(result.values)),
        "geologyRows": 0 if result.geology is None else int(len(result.geology)),
        "failures": result.failures,
        "districtsWithoutValues": reach.districts_without_values,
        "districtsWithoutCells": reach.districts_without_cells,
        "unexpectedWithoutCells": reach.unexpected_without_cells,
        "silentDistricts": reach.silent_districts,
        "lostStates": reach.lost_states,
        "notes": result.notes,
        "options": {k: (str(v) if isinstance(v, Path) else v) for k, v in dataclasses.asdict(options).items()},
        "seconds": round(time.monotonic() - started, 1),
    }
    (parts / f"{stem}.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print(
        f"{key}: {meta['rows']} rows, {len(result.failures)} failures, "
        f"{len(reach.districts_without_cells)} districts without cells, {meta['seconds']} s"
    )
    for item in result.failures:
        print(f"  failure {item['step']} {item['districtLgds'][:5]}: {item['error']}", file=sys.stderr)
    return meta


def part_status(metas: list[dict], *, allow_failures: bool) -> int:
    failing = False
    for meta in metas:
        for key, problem in PART_FAILING.items():
            if meta[key]:
                failing = True
                print(
                    f"{meta['layer']}: {problem.format(meta[key])}; this fails the part even with --allow-failures",
                    file=sys.stderr,
                )
    failed = any(m["failures"] for m in metas)
    return 1 if failing or (failed and not allow_failures) else 0


def combine(args: argparse.Namespace) -> int:
    parts = Path(args.parts)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    metas = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(parts.glob("*.json"))]
    disagreeing = disagreeing_datasets(metas)
    for code, fields in disagreeing.items():
        print(f"{code}: its parts differ in {fields}; the parts of one dataset share one dataset row", file=sys.stderr)
    if disagreeing:
        return 1
    frames = [pd.read_parquet(parts / f"{m['stem']}.parquet") for m in metas]
    values = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=COLUMNS)
    key = ["districtLgd", "datasetCode", "variable", "depthOrPeriod", "stat"]
    values = values.sort_values(key, kind="stable")
    duplicates = int(values.duplicated(key).sum())
    if duplicates:
        print(f"{duplicates} duplicate keys in the combined table", file=sys.stderr)
        return 1
    values.to_parquet(out / "district_env.parquet", index=False)
    generated = dt.datetime.now(dt.UTC)
    csv_names = write_dataset_csvs(values, out, generated)
    geo_frames = [pd.read_parquet(p) for p in sorted(parts.glob("*.geology.parquet"))]
    geology_table = pd.concat(geo_frames, ignore_index=True) if geo_frames else pd.DataFrame(columns=GEOLOGY_COLUMNS)
    geology_table.to_parquet(out / "district_geology.parquet", index=False)
    summary = summary_of(metas, values, geology_table, generated=generated, csv_names=csv_names)
    (out / "district_env_summary.json").write_text(json.dumps(summary, indent=1, default=str), encoding="utf-8")
    print(f"combined {len(values)} rows over {summary['districts']} districts into {out}")
    return 0


def disagreeing_datasets(metas: list[dict]) -> dict[str, dict[str, list]]:
    rows: dict[str, list[dict]] = {}
    for meta in metas:
        rows.setdefault(meta["dataset"]["code"], []).append(meta["dataset"])
    disagreeing = {}
    for code, held in rows.items():
        fields = sorted({name for row in held for name in row if row.get(name) != held[0].get(name)})
        if fields:
            disagreeing[code] = {name: sorted({str(row.get(name)) for row in held}) for name in fields}
    return disagreeing


def summary_of(
    metas: list[dict],
    values: pd.DataFrame,
    geology_table: pd.DataFrame,
    *,
    generated: dt.datetime,
    csv_names: list[str],
) -> dict:
    datasets = {m["dataset"]["code"]: {**m["dataset"], "retrievedAt": m["retrievedAt"]} for m in metas}
    return {
        "generatedAt": generated.isoformat(timespec="seconds"),
        "boundaries": catalog.BOUNDARIES.as_row() | {"sha256": sha256_of(SHAPES_PATH)},
        "datasets": list(datasets.values()),
        "layers": [
            {k: m[k] for k in SUMMARY_LAYER_KEYS}
            | {"datasetCode": m["dataset"]["code"], "failureCount": len(m["failures"]), "failures": m["failures"]}
            for m in metas
        ],
        "rows": int(len(values)),
        "geologyRows": int(len(geology_table)),
        "districts": int(values["districtLgd"].nunique()) if len(values) else 0,
        "variables": (values.groupby("datasetCode")["variable"].nunique().astype(int).to_dict() if len(values) else {}),
        "districtsWithoutShapes": districts_without_shapes(),
        "csv": csv_names,
    }


def add_extract_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--datasets", default="all", help=",".join(LAYERS))
    parser.add_argument("--districts", default="all")
    parser.add_argument("--states", default="all")
    parser.add_argument("--parts", default=str(ROOT / "out" / "parts"))
    parser.add_argument("--cache", default=str(Path.home() / ".cache" / "kalavigyan-geo"))
    parser.add_argument("--worldcover-factor", type=int)
    parser.add_argument("--hansen-factor", type=int)
    parser.add_argument("--dem-factor", type=int)
    parser.add_argument("--climate-first-year", type=int)
    parser.add_argument(
        "--chirps-last-year",
        type=int,
        help="the last CHIRPS year, resolved once for every shard (chirps-last-year); without it the layer finds it",
    )
    parser.add_argument("--soil-vars")
    parser.add_argument("--soil-depths")
    parser.add_argument("--chelsa-bio")
    parser.add_argument("--no-soil-uncertainty", action="store_true")
    parser.add_argument("--no-chelsa-months", action="store_true")
    parser.add_argument("--no-chirps-monthly", action="store_true")
    parser.add_argument("--download-striped", action="store_true")
    parser.add_argument(
        "--allow-failures",
        action="store_true",
        help="keep a part whose failures are scattered districts; a lost state, a silent district or a district "
        "unexpectedly without valid cells still fails the part",
    )
    parser.add_argument("--shard", help="k/n: process the k-th of n state groups, balanced by area")


def river_lines(args: argparse.Namespace) -> int:
    try:
        manifest = rivers.build(Path(args.out), cache=Path(args.cache))
    except rivers.RiverNetworkError as error:
        for problem in error.problems[: rivers.PROBLEMS_SHOWN]:
            print(problem, file=sys.stderr)
        print(f"{len(error.problems)} river network problems; nothing written", file=sys.stderr)
        return 1
    largest = max((basin["bytes"] for basin in manifest["basins"]), default=0)
    print(
        f"{manifest['reaches']} reaches in {len(manifest['basins'])} basins into {args.out}, "
        f"largest topology {largest} bytes"
    )
    return 0


def river_names(args: argparse.Namespace) -> int:
    summary = river_names_files.build_names(Path(args.rivers), scratch=Path(args.scratch))
    print(
        f"{summary['wikidataRivers']} rivers named from Wikidata over {summary['wikidataReaches']} reaches, "
        f"{summary['osmRivers']} from OpenStreetMap over {summary['osmReaches']} reaches"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="geo_etl")
    sub = parser.add_subparsers(dest="command", required=True)
    add_extract_args(sub.add_parser("extract"))
    combine_parser = sub.add_parser("combine")
    combine_parser.add_argument("--parts", default=str(ROOT / "out" / "parts"))
    combine_parser.add_argument("--out", default=str(ROOT / "out"))
    run_parser = sub.add_parser("run")
    add_extract_args(run_parser)
    run_parser.add_argument("--out", default=str(ROOT / "out"))
    rivers_parser = sub.add_parser("rivers")
    rivers_parser.add_argument("--out", default=str(ROOT / "out" / "rivers"))
    rivers_parser.add_argument("--cache", default=str(Path.home() / ".cache" / "kalavigyan-geo"))
    names_parser = sub.add_parser("river-names")
    names_parser.add_argument("--rivers", default=str(ROOT / "out" / "rivers"))
    names_parser.add_argument("--scratch", default=str(ROOT / "out" / "osm"))
    sub.add_parser("chirps-last-year")
    args = parser.parse_args(argv)
    if args.command == "chirps-last-year":
        print(chirps.latest_year())
        return 0
    if args.command == "rivers":
        return river_lines(args)
    if args.command == "river-names":
        return river_names(args)
    if args.command == "extract":
        return extract(args)
    if args.command == "combine":
        return combine(args)
    status = extract(args)
    return combine(args) or status


if __name__ == "__main__":
    raise SystemExit(main())
