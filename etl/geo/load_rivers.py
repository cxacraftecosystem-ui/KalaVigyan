import argparse
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import pandas as pd
import shapely

from geo_etl.river_districts import HIT_COLUMNS, REACH_DISTRICTS_FILE
from geo_etl.rivers import BASINS_FILE, PROBLEMS_SHOWN, REACHES_FILE, network_problems, topology_key
from load import clean, known_districts, quote, require, table_columns, upsert_datasets

OUT = Path(__file__).resolve().parent / "out" / "rivers"
BASIN_TABLE = "RiverBasin"
REACH_TABLE = "RiverReach"
REACH_DISTRICT_TABLE = "RiverReachDistrict"
BASIN_COLUMNS = ["mainRiv", "datasetId", "reachCount", "topologySha256"]
REACH_COLUMNS = ["hyrivId", "nextDown", "mainRiv", "ordStra", "uplandSkm", "disAvCms", "lengthKm", "geom"]
TOPOLOGY_TYPE = "application/json"
SERVER_SIDE_ENCRYPTION = "AES256"
SHA_METADATA = "sha256"
SRID = 4326
MISSING_CODES = frozenset({"404", "NoSuchKey", "NotFound"})


@dataclass(frozen=True)
class RiverOutputs:
    folder: Path
    reaches: gpd.GeoDataFrame
    hits: pd.DataFrame
    manifest: dict

    def body(self, basin: dict) -> bytes:
        return (self.folder / basin["file"]).read_bytes()


def read_outputs(folder: Path) -> RiverOutputs:
    manifest = json.loads((folder / BASINS_FILE).read_text(encoding="utf-8"))
    return RiverOutputs(
        folder=folder,
        reaches=gpd.read_parquet(folder / REACHES_FILE),
        hits=pd.read_parquet(folder / REACH_DISTRICTS_FILE),
        manifest=manifest,
    )


def output_problems(outputs: RiverOutputs) -> list[str]:
    problems = network_problems(outputs.reaches)
    counts = outputs.reaches.groupby("mainRiv").size().to_dict()
    listed = {basin["mainRiv"]: basin for basin in outputs.manifest["basins"]}
    if set(counts) != set(listed):
        problems.append(f"the manifest lists {len(listed)} basins, the reaches hold {len(counts)}")
    for main_riv, basin in listed.items():
        problems.extend(_basin_problems(outputs, basin, counts.get(main_riv, 0)))
    counted, held = outputs.manifest["reaches"], len(outputs.reaches)
    if counted != held:
        problems.append(f"the manifest counts {counted} reaches, the file holds {held}")
    return problems + hit_problems(outputs)


def hit_problems(outputs: RiverOutputs) -> list[str]:
    hits, counted = outputs.hits, outputs.manifest["reachDistricts"]
    problems = []
    if counted != len(hits):
        problems.append(f"the manifest counts {counted} reach districts, the file holds {len(hits)}")
    unknown = sorted(set(hits["hyrivId"].astype("int64")) - set(outputs.reaches["hyrivId"].astype("int64")))
    if unknown:
        problems.append(f"reach districts name reaches that are not kept: {unknown[:PROBLEMS_SHOWN]}")
    if int(hits.duplicated(["hyrivId", "districtLgd"]).sum()):
        problems.append("a reach lists a district twice")
    if not hits["entry"].between(0.0, 1.0).all():
        problems.append("a reach enters a district outside its own length")
    return problems


def _basin_problems(outputs: RiverOutputs, basin: dict, reaches: int) -> list[str]:
    path = outputs.folder / basin["file"]
    if basin["reaches"] != reaches:
        return [f"basin {basin['mainRiv']} lists {basin['reaches']} reaches, the file holds {reaches}"]
    if not path.is_file():
        return [f"basin {basin['mainRiv']} has no topology file {basin['file']}"]
    if hashlib.sha256(path.read_bytes()).hexdigest() != basin["sha256"]:
        return [f"basin {basin['mainRiv']}'s topology does not match its sha256"]
    return []


def stored_sha256(client, bucket: str, key: str) -> str | None:
    try:
        head = client.head_object(Bucket=bucket, Key=key)
    except Exception as error:
        code = str(((getattr(error, "response", None) or {}).get("Error") or {}).get("Code") or "")
        if code in MISSING_CODES:
            return None
        raise
    return (head.get("Metadata") or {}).get(SHA_METADATA)


def upload_topologies(client, bucket: str, outputs: RiverOutputs) -> tuple[int, int]:
    edition = outputs.manifest["dataset"]["edition"]
    uploaded = unchanged = 0
    for basin in outputs.manifest["basins"]:
        key = topology_key(edition, basin["mainRiv"], basin["sha256"])
        if stored_sha256(client, bucket, key) == basin["sha256"]:
            unchanged += 1
            continue
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=outputs.body(basin),
            ContentType=TOPOLOGY_TYPE,
            ServerSideEncryption=SERVER_SIDE_ENCRYPTION,
            Metadata={SHA_METADATA: basin["sha256"]},
        )
        uploaded += 1
    return uploaded, unchanged


def reach_rows(reaches: gpd.GeoDataFrame) -> list[list]:
    lines = shapely.to_wkb(shapely.set_srid(reaches.geometry.to_numpy(), SRID), hex=True, include_srid=True)
    values = reaches[REACH_COLUMNS[:-1]].itertuples(index=False, name=None)
    return [[clean(value) for value in row] + [line] for row, line in zip(values, lines, strict=True)]


def replace_rivers(cur, outputs: RiverOutputs) -> tuple[int, int, int]:
    require(BASIN_TABLE, table_columns(cur, BASIN_TABLE), set(BASIN_COLUMNS))
    require(REACH_TABLE, table_columns(cur, REACH_TABLE), set(REACH_COLUMNS))
    require(REACH_DISTRICT_TABLE, table_columns(cur, REACH_DISTRICT_TABLE), set(HIT_COLUMNS))
    dataset_id = upsert_datasets(cur, [outputs.manifest["dataset"]])[outputs.manifest["dataset"]["code"]]
    cur.execute(f"delete from {quote(REACH_DISTRICT_TABLE)}")
    cur.execute(f"delete from {quote(REACH_TABLE)}")
    cur.execute(f"delete from {quote(BASIN_TABLE)}")
    basins = [[b["mainRiv"], dataset_id, b["reaches"], b["sha256"]] for b in outputs.manifest["basins"]]
    _copy(cur, BASIN_TABLE, BASIN_COLUMNS, basins)
    _copy(cur, REACH_TABLE, REACH_COLUMNS, reach_rows(outputs.reaches))
    hits = hit_rows(outputs.hits, known_districts(cur))
    _copy(cur, REACH_DISTRICT_TABLE, HIT_COLUMNS, hits)
    return len(basins), len(outputs.reaches), len(hits)


def hit_rows(hits: pd.DataFrame, districts: set[int] | None) -> list[list]:
    if not districts:
        raise SystemExit(
            "AdminDistrict is empty or missing: run python -m app.scripts.seed_districts in backend/ first"
        )
    rows = hits[HIT_COLUMNS].itertuples(index=False, name=None)
    return [[int(rid), int(lgd), float(entry)] for rid, lgd, entry in rows if int(lgd) in districts]


def _copy(cur, table: str, columns: list[str], rows: list[list]) -> None:
    names = ", ".join(quote(c) for c in columns)
    with cur.copy(f"copy {quote(table)} ({names}) from stdin") as copy:
        for row in rows:
            copy.write_row(row)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Upload river topologies and replace RiverBasin and RiverReach")
    parser.add_argument("--out", default=str(OUT))
    parser.add_argument("--dsn-env", default="DATABASE_URL")
    parser.add_argument("--bucket-env", default="S3_BUCKET")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    outputs = read_outputs(Path(args.out))
    problems = output_problems(outputs)
    if problems:
        for problem in problems:
            print(problem, file=sys.stderr)
        return 1
    print(f"{len(outputs.reaches)} reaches in {len(outputs.manifest['basins'])} basins")
    if args.dry_run:
        return 0
    dsn, bucket = os.environ.get(args.dsn_env), os.environ.get(args.bucket_env)
    if not dsn or not bucket:
        print(f"{args.dsn_env} and {args.bucket_env} must both be set", file=sys.stderr)
        return 2
    return load(outputs, dsn=dsn, bucket=bucket)


def load(outputs: RiverOutputs, *, dsn: str, bucket: str) -> int:
    import boto3
    import psycopg

    client = boto3.client("s3", region_name=os.environ.get("AWS_REGION"))
    uploaded, unchanged = upload_topologies(client, bucket, outputs)
    print(f"topologies: {uploaded} uploaded, {unchanged} unchanged")
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        basins, reaches, hits = replace_rivers(cur, outputs)
        conn.commit()
    print(f"{BASIN_TABLE}: {basins} rows, {REACH_TABLE}: {reaches} rows, {REACH_DISTRICT_TABLE}: {hits} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
