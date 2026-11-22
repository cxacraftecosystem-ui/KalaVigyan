import argparse
import datetime as dt
import json
import math
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parent / "out"
SHARED = Path(__file__).resolve().parents[2] / "shared"

DATASET_TABLE = "EnvDataset"
VALUE_TABLE = "DistrictEnvValue"
GEOLOGY_TABLE = "DistrictGeology"
DISTRICT_TABLE = "AdminDistrict"
STATE_TABLE = "StateEnvValue"
STATE_SQL_NAME = "region.state-values.sql"
STATE_REQUIRED = {"stateLgd", "datasetId", "variable", "depthOrPeriod", "stat", "datasetDistricts", "datasetArea"}

DATASET_COLUMNS = [
    "code",
    "title",
    "publisher",
    "edition",
    "version",
    "period",
    "nativeResolution",
    "crs",
    "licence",
    "licenceUrl",
    "attribution",
    "redistributable",
    "retrievedAt",
    "sha256",
    "citation",
    "doi",
    "landingUrl",
    "url",
]
DATASET_REQUIRED = {"code", "title", "licence"}

VALUE_KEY = ["districtLgd", "datasetId", "variable", "depthOrPeriod", "stat"]
VALUE_COLUMNS = [*VALUE_KEY, "value", "valueText", "unit", "method", "resolution", "pixelCount"]
VALUE_REQUIRED = set(VALUE_KEY) | {"value"}

GEOLOGY_KEY = ["districtLgd", "datasetId", "lithology"]
GEOLOGY_COLUMNS = [*GEOLOGY_KEY, "lithologyName", "areaShare", "mineralOccurrences", "method"]
GEOLOGY_REQUIRED = set(GEOLOGY_KEY)

STAMPS = ["createdAt", "updatedAt"]


def quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def clean(value):
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if pd.api.types.is_scalar(value) and pd.isna(value):
        return None
    if isinstance(value, np.generic):
        return value.item()
    return value


def json_text(value):
    value = clean(value)
    if value is None or isinstance(value, str):
        return value
    if hasattr(value, "tolist"):
        value = value.tolist()
    return json.dumps(value)


def fit_values(values: pd.DataFrame) -> pd.DataFrame:
    if "pixelCount" not in values:
        return values
    counts = pd.to_numeric(values["pixelCount"], errors="coerce").round()
    return values.assign(pixelCount=counts.astype("Int64"))


def fit_geology(geology: pd.DataFrame) -> pd.DataFrame:
    if not len(geology):
        return geology
    if "mineralOccurrences" in geology:
        geology = geology.assign(mineralOccurrences=geology["mineralOccurrences"].map(json_text))
    return geology


def read_inputs(out: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    values = fit_values(pd.read_parquet(out / "district_env.parquet"))
    geology_path = out / "district_geology.parquet"
    geology = fit_geology(pd.read_parquet(geology_path)) if geology_path.exists() else pd.DataFrame()
    summary = json.loads((out / "district_env_summary.json").read_text(encoding="utf-8"))
    return values, geology, summary


def dataset_rows(summary: dict) -> list[dict]:
    rows = [dict(summary["boundaries"]) | {"retrievedAt": summary["generatedAt"]}]
    rows.extend(dict(d) for d in summary["datasets"])
    seen: dict[str, dict] = {}
    for row in rows:
        seen[row["code"]] = row
    return list(seen.values())


def validate(values: pd.DataFrame, geology: pd.DataFrame, datasets: list[dict]) -> list[str]:
    problems = []
    codes = {d["code"] for d in datasets}
    unknown = set(values["datasetCode"]) - codes
    if unknown:
        problems.append(f"values cite datasets missing from the summary: {sorted(unknown)}")
    key = ["districtLgd", "datasetCode", "variable", "depthOrPeriod", "stat"]
    duplicates = int(values.duplicated(key).sum())
    if duplicates:
        problems.append(f"{duplicates} duplicate value keys")
    if values["value"].isna().any() and values.loc[values["value"].isna(), "valueText"].isna().any():
        problems.append("rows with neither value nor valueText")
    if len(geology):
        unknown = set(geology["datasetCode"]) - codes
        if unknown:
            problems.append(f"geology cites datasets missing from the summary: {sorted(unknown)}")
        if geology["lithology"].isna().any():
            problems.append("geology rows without lithology")
        if int(geology.duplicated(["districtLgd", "datasetCode", "lithology"], keep=False).sum()):
            problems.append("duplicate geology keys")
    return problems


def table_columns(cur, table: str) -> dict[str, str]:
    cur.execute(
        "select column_name, data_type from information_schema.columns "
        "where table_schema = current_schema() and table_name = %s",
        (table,),
    )
    return {name: kind for name, kind in cur.fetchall()}


def has_unique(cur, table: str, key: list[str]) -> bool:
    cur.execute(
        "select array(select a.attname from unnest(i.indkey) k join pg_attribute a "
        "on a.attrelid = i.indrelid and a.attnum = k) from pg_index i "
        "where i.indrelid = %s::regclass and i.indisunique and i.indpred is null",
        (quote(table),),
    )
    return any(sorted(row[0]) == sorted(key) for row in cur.fetchall())


def require(table: str, present: dict[str, str], required: set[str]) -> None:
    if not present:
        raise SystemExit(f'table "{table}" does not exist; see docs/contracts/geo.md')
    missing = sorted(required - set(present))
    if missing:
        raise SystemExit(f'table "{table}" lacks columns {missing}; see docs/contracts/geo.md')


def upsert_datasets(cur, datasets: list[dict]) -> dict[str, str]:
    present = table_columns(cur, DATASET_TABLE)
    require(DATASET_TABLE, present, DATASET_REQUIRED)
    columns = [c for c in DATASET_COLUMNS if c in present]
    stamps = [c for c in STAMPS if c in present]
    names = ", ".join(quote(c) for c in [*columns, *stamps])
    marks = ", ".join(["%s"] * len(columns) + ["now()"] * len(stamps))
    updates = ", ".join(f"{quote(c)} = excluded.{quote(c)}" for c in columns if c != "code")
    if "updatedAt" in present:
        updates += ', "updatedAt" = now()'
    ids = {}
    for row in datasets:
        cur.execute(
            f"insert into {quote(DATASET_TABLE)} ({names}) values ({marks}) "
            f"on conflict (code) do update set {updates} returning id, code",
            [clean(row.get(c)) for c in columns],
        )
        found_id, code = cur.fetchone()
        ids[code] = str(found_id)
    return ids


def known_districts(cur) -> set[int] | None:
    if not table_columns(cur, DISTRICT_TABLE):
        return None
    cur.execute(f"select lgd from {quote(DISTRICT_TABLE)}")
    return {int(r[0]) for r in cur.fetchall()}


def not_null_columns(cur, table: str) -> set[str]:
    cur.execute(
        "select column_name from information_schema.columns "
        "where table_schema = current_schema() and table_name = %s and is_nullable = 'NO'",
        (table,),
    )
    return {r[0] for r in cur.fetchall()}


def key_match(key: list[str], not_null: set[str]) -> str:
    return " and ".join(
        f"s.{quote(c)} = t.{quote(c)}" if c in not_null else f"s.{quote(c)} is not distinct from t.{quote(c)}"
        for c in key
    )


def upsert(cur, table: str, frame: pd.DataFrame, key: list[str], columns: list[str], required: set[str], prune: bool):
    present = table_columns(cur, table)
    require(table, present, required)
    cols = [c for c in columns if c in present]
    stamps = [c for c in STAMPS if c in present]
    stage = f"stage_{table.lower()}"
    cur.execute(f"create temp table {stage} (like {quote(table)} including defaults) on commit drop")
    copy_cols = ", ".join(quote(c) for c in [*cols, *stamps])
    now = dt.datetime.now(dt.UTC)
    with cur.copy(f"copy {stage} ({copy_cols}) from stdin") as copy:
        for record in frame[cols].itertuples(index=False, name=None):
            copy.write_row([clean(v) for v in record] + [now] * len(stamps))
    cur.execute(f"analyze {stage}")
    match = key_match(key, not_null_columns(cur, table))
    target = quote(table)
    insert_cols = ", ".join(quote(c) for c in [*cols, *stamps])
    conflict = ", ".join(quote(c) for c in key)
    updates = ", ".join(f"{quote(c)} = excluded.{quote(c)}" for c in cols if c not in key)
    if "updatedAt" in present:
        updates = f'{updates}, "updatedAt" = now()' if updates else '"updatedAt" = now()'
    id_cols = "id, " if "id" in present else ""
    id_vals = "gen_random_uuid(), " if "id" in present else ""
    insert = f"insert into {target} ({id_cols}{insert_cols}) select {id_vals}{insert_cols} from {stage}"
    if has_unique(cur, table, key):
        cur.execute(f"{insert} on conflict ({conflict}) do update set {updates}")
    else:
        cur.execute(f"delete from {target} t where exists (select 1 from {stage} s where {match})")
        cur.execute(insert)
    written = cur.rowcount
    pruned = 0
    if prune:
        cur.execute(
            f'delete from {target} t where (t."datasetId", t."districtLgd") in '
            f'(select distinct "datasetId", "districtLgd" from {stage}) '
            f"and not exists (select 1 from {stage} s where {match})"
        )
        pruned = cur.rowcount
    return written, pruned


def refresh_state_values(cur, sql_path: Path = SHARED / STATE_SQL_NAME) -> int:
    require(STATE_TABLE, table_columns(cur, STATE_TABLE), STATE_REQUIRED)
    statement = sql_path.read_text(encoding="utf-8")
    cur.execute(f"delete from {quote(STATE_TABLE)}")
    cur.execute(statement)
    return cur.rowcount


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Upsert etl/geo/out into EnvDataset, DistrictEnvValue, DistrictGeology and refresh StateEnvValue"
    )
    parser.add_argument("--out", default=str(OUT))
    parser.add_argument("--dsn-env", default="DATABASE_URL")
    parser.add_argument("--prune", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    values, geology, summary = read_inputs(Path(args.out))
    datasets = dataset_rows(summary)
    problems = validate(values, geology, datasets)
    if problems:
        for problem in problems:
            print(problem, file=sys.stderr)
        return 1
    print(f"{len(values)} values, {len(geology)} geology rows, {len(datasets)} datasets")
    if args.dry_run:
        return 0

    dsn = os.environ.get(args.dsn_env)
    if not dsn:
        print(f"{args.dsn_env} is not set", file=sys.stderr)
        return 2

    import psycopg

    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        ids = upsert_datasets(cur, datasets)
        allowed = known_districts(cur)
        if allowed is not None and not allowed:
            print(
                f"{DISTRICT_TABLE} is empty: run python -m app.scripts.seed_districts in backend/ first",
                file=sys.stderr,
            )
            conn.rollback()
            return 3
        values = values.assign(datasetId=values["datasetCode"].map(ids))
        if len(geology):
            geology = geology.assign(datasetId=geology["datasetCode"].map(ids))
        if allowed is not None:
            skipped = sorted(set(values["districtLgd"]) - allowed)
            if skipped:
                print(f"skipping {len(skipped)} districts not in {DISTRICT_TABLE}: {skipped[:20]}", file=sys.stderr)
            values = values[values["districtLgd"].isin(allowed)]
            if len(geology):
                geology = geology[geology["districtLgd"].isin(allowed)]
        written, pruned = upsert(cur, VALUE_TABLE, values, VALUE_KEY, VALUE_COLUMNS, VALUE_REQUIRED, args.prune)
        print(f"{VALUE_TABLE}: {written} upserted, {pruned} pruned")
        if len(geology):
            written, pruned = upsert(
                cur, GEOLOGY_TABLE, geology, GEOLOGY_KEY, GEOLOGY_COLUMNS, GEOLOGY_REQUIRED, args.prune
            )
            print(f"{GEOLOGY_TABLE}: {written} upserted, {pruned} pruned")
        print(f"{STATE_TABLE}: {refresh_state_values(cur)} state series")
        conn.commit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
