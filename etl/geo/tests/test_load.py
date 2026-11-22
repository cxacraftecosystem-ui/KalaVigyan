import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import load
from geo_etl.catalog import BOUNDARIES, MRDS, SOILGRIDS
from geo_etl.layers.geology import GEOLOGY_COLUMNS
from geo_etl.rows import COLUMNS

LOAD_PY = Path(load.__file__).resolve()


def value_row(**overrides) -> dict:
    row = dict.fromkeys(COLUMNS)
    row |= {
        "districtLgd": 599,
        "stateLgd": 34,
        "districtName": "Mahe",
        "datasetCode": SOILGRIDS.code,
        "variable": "clay",
        "depthOrPeriod": "0-5cm",
        "stat": "DISTRICT_MEAN",
        "value": 312.0,
        "unit": "g/kg",
        "method": "zonal mean",
        "pixelCount": 96.6,
        "source": SOILGRIDS.title,
        "version": SOILGRIDS.edition,
        "resolution": SOILGRIDS.nativeResolution,
        "licence": SOILGRIDS.licence,
    }
    return row | overrides


def geology_row(**overrides) -> dict:
    row = dict.fromkeys(GEOLOGY_COLUMNS)
    row |= {
        "districtLgd": 599,
        "stateLgd": 34,
        "districtName": "Mahe",
        "datasetCode": MRDS.code,
        "lithology": "mineral_occurrences",
        "lithologyName": "Mineral occurrences",
        "mineralOccurrences": json.dumps([{"depId": "10087"}]),
        "method": "point in polygon",
    }
    return row | overrides


def summary(datasets=(SOILGRIDS, MRDS)) -> dict:
    return {
        "generatedAt": "2026-11-16T00:00:00+00:00",
        "boundaries": BOUNDARIES.as_row() | {"sha256": "abc"},
        "datasets": [d.as_row() | {"retrievedAt": "2026-11-15T00:00:00+00:00"} for d in datasets],
    }


def values_frame(*rows: dict) -> pd.DataFrame:
    return pd.DataFrame(list(rows) or [value_row()], columns=COLUMNS)


def geology_frame(*rows: dict) -> pd.DataFrame:
    return pd.DataFrame(list(rows), columns=GEOLOGY_COLUMNS)


def test_dataset_rows_puts_boundaries_first_and_dedupes():
    raw = summary()
    raw["datasets"].append(SOILGRIDS.as_row() | {"retrievedAt": "later"})
    rows = load.dataset_rows(raw)
    assert [r["code"] for r in rows] == [BOUNDARIES.code, SOILGRIDS.code, MRDS.code]
    assert rows[0]["retrievedAt"] == "2026-11-16T00:00:00+00:00"
    assert rows[0]["sha256"] == "abc"
    assert rows[1]["retrievedAt"] == "later"


def test_dataset_rows_does_not_mutate_summary():
    raw = summary()
    load.dataset_rows(raw)
    assert "retrievedAt" not in raw["boundaries"]


def test_validate_clean_tables():
    datasets = load.dataset_rows(summary())
    assert load.validate(values_frame(), geology_frame(geology_row()), datasets) == []
    assert load.validate(values_frame(), pd.DataFrame(), datasets) == []


def test_validate_unknown_dataset():
    datasets = load.dataset_rows(summary(datasets=(SOILGRIDS,)))
    problems = load.validate(values_frame(value_row(datasetCode="NOPE")), geology_frame(geology_row()), datasets)
    assert any("values cite datasets missing" in p and "NOPE" in p for p in problems)
    assert any("geology cites datasets missing" in p and MRDS.code in p for p in problems)


def test_validate_duplicate_value_keys():
    datasets = load.dataset_rows(summary())
    problems = load.validate(values_frame(value_row(), value_row(value=1.0)), pd.DataFrame(), datasets)
    assert problems == ["1 duplicate value keys"]


def test_validate_value_or_text():
    datasets = load.dataset_rows(summary())
    text_only = value_row(stat="CLASS", value=math.nan, valueText="loam")
    assert load.validate(values_frame(value_row(), text_only), pd.DataFrame(), datasets) == []
    empty = value_row(stat="CLASS", value=None, valueText=None)
    assert load.validate(values_frame(value_row(), empty), pd.DataFrame(), datasets) == [
        "rows with neither value nor valueText"
    ]


def test_validate_geology_problems():
    datasets = load.dataset_rows(summary())
    frame = geology_frame(geology_row(), geology_row(), geology_row(lithology=None))
    problems = load.validate(values_frame(), frame, datasets)
    assert "geology rows without lithology" in problems
    assert "duplicate geology keys" in problems


def test_the_load_writes_the_grid_each_value_was_read_at():
    assert "resolution" in load.VALUE_COLUMNS
    assert set(load.VALUE_COLUMNS) - {"datasetId"} <= set(COLUMNS)
    assert {"lithologyName", "method"} <= set(load.GEOLOGY_COLUMNS)
    assert set(load.GEOLOGY_COLUMNS) - {"datasetId"} <= set(GEOLOGY_COLUMNS)


def test_fit_values_rounds_pixel_count_to_nullable_int():
    fitted = load.fit_values(pd.DataFrame({"pixelCount": [96.6, None, 3.2]}))
    assert str(fitted["pixelCount"].dtype) == "Int64"
    assert fitted["pixelCount"].iloc[0] == 97
    assert fitted["pixelCount"].isna().tolist() == [False, True, False]
    assert load.fit_values(pd.DataFrame({"value": [1.0]})).columns.tolist() == ["value"]


def test_fit_geology_serialises_occurrences():
    frame = pd.DataFrame({"mineralOccurrences": [[{"a": 1}], None, '["x"]', np.array([1, 2])]})
    fitted = load.fit_geology(frame)
    texts = fitted["mineralOccurrences"].tolist()
    assert texts[0] == '[{"a": 1}]'
    assert load.clean(texts[1]) is None
    assert texts[2:] == ['["x"]', "[1, 2]"]
    assert load.fit_geology(pd.DataFrame()).empty


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, None), (math.nan, None), (pd.NA, None), (np.int64(3), 3), (np.float64(1.5), 1.5), ("x", "x")],
)
def test_clean(value, expected):
    result = load.clean(value)
    assert result == expected
    assert type(result) is type(expected)


def test_clean_keeps_containers():
    assert load.clean([1, 2]) == [1, 2]
    assert load.clean({"a": 1}) == {"a": 1}


def test_quote_escapes_identifiers():
    assert load.quote("DistrictEnvValue") == '"DistrictEnvValue"'
    assert load.quote('a"b') == '"a""b"'


@pytest.fixture
def out_dir(tmp_path) -> Path:
    out = tmp_path / "out"
    out.mkdir()
    values = values_frame(value_row(), value_row(stat="DISTRICT_P10", value=280.0, pixelCount=None))
    values.to_parquet(out / "district_env.parquet", index=False)
    geology_frame(geology_row()).to_parquet(out / "district_geology.parquet", index=False)
    (out / "district_env_summary.json").write_text(json.dumps(summary()), encoding="utf-8")
    return out


def test_read_inputs(out_dir):
    values, geology, raw = load.read_inputs(out_dir)
    assert len(values) == 2
    assert str(values["pixelCount"].dtype) == "Int64"
    assert len(geology) == 1
    assert raw["generatedAt"] == "2026-11-16T00:00:00+00:00"


def test_read_inputs_without_geology(out_dir):
    (out_dir / "district_geology.parquet").unlink()
    _, geology, _ = load.read_inputs(out_dir)
    assert geology.empty


def test_main_dry_run(out_dir, capsys, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert load.main(["--out", str(out_dir), "--dry-run"]) == 0
    assert "2 values, 1 geology rows, 3 datasets" in capsys.readouterr().out


def test_main_without_dsn_stops_before_connecting(out_dir, capsys, monkeypatch):
    monkeypatch.delenv("KALAVIGYAN_TEST_DSN_UNSET", raising=False)
    assert load.main(["--out", str(out_dir), "--dsn-env", "KALAVIGYAN_TEST_DSN_UNSET"]) == 2
    assert "KALAVIGYAN_TEST_DSN_UNSET is not set" in capsys.readouterr().err


def test_main_reports_validation_problems(out_dir, capsys):
    values_frame(value_row(), value_row()).to_parquet(out_dir / "district_env.parquet", index=False)
    assert load.main(["--out", str(out_dir), "--dry-run"]) == 1
    assert "duplicate value keys" in capsys.readouterr().err


def test_script_dry_run_subprocess(out_dir):
    completed = subprocess.run(
        [sys.executable, str(LOAD_PY), "--out", str(out_dir), "--dry-run"],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "2 values, 1 geology rows, 3 datasets" in completed.stdout


def test_key_match_uses_equality_for_not_null_columns_so_the_prune_can_hash():
    clause = load.key_match(["districtLgd", "lithology"], {"districtLgd"})
    assert clause == 's."districtLgd" = t."districtLgd" and s."lithology" is not distinct from t."lithology"'


def test_every_value_key_column_matches_by_equality_once_the_table_marks_it_not_null():
    clause = load.key_match(load.VALUE_KEY, set(load.VALUE_KEY))
    assert "distinct" not in clause
    assert clause.count(" = ") == len(load.VALUE_KEY)


class StateCursor:
    def __init__(self, columns: list[str], written: int = 0):
        self.columns = columns
        self.written = written
        self.statements: list[str] = []
        self.found: list[tuple] = []
        self.rowcount = -1

    def execute(self, query: str, params=None):
        self.statements.append(query)
        if params == (load.STATE_TABLE,):
            self.found = [(column, "text") for column in self.columns]
        else:
            self.rowcount = self.written

    def fetchall(self):
        return self.found


def test_refresh_replaces_every_state_series_with_the_shared_refresh(tmp_path):
    refresh = tmp_path / "refresh.sql"
    refresh.write_text('INSERT INTO "StateEnvValue" SELECT 1\n', encoding="utf-8")
    cur = StateCursor(sorted(load.STATE_REQUIRED), written=12)
    assert load.refresh_state_values(cur, refresh) == 12
    assert cur.statements[-2:] == ['delete from "StateEnvValue"', 'INSERT INTO "StateEnvValue" SELECT 1\n']


def test_refresh_stops_before_deleting_when_the_table_is_missing(tmp_path):
    cur = StateCursor([])
    with pytest.raises(SystemExit, match='table "StateEnvValue" does not exist'):
        load.refresh_state_values(cur, tmp_path / "refresh.sql")
    assert not any(statement.startswith("delete") for statement in cur.statements)


def test_the_refresh_the_load_runs_is_the_one_the_backend_writes():
    statement = (load.SHARED / load.STATE_SQL_NAME).read_text(encoding="utf-8")
    assert statement.startswith("WITH district_area AS MATERIALIZED\n")
    assert 'INSERT INTO "StateEnvValue" ("stateLgd", "datasetId",' in statement
