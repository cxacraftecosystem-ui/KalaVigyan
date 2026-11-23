import argparse
import dataclasses
import datetime as dt
import json
import re

import pandas as pd
import pytest

from geo_etl import __main__ as cli
from geo_etl.catalog import BOUNDARIES, CHIRPS, GLIM, SOILGRIDS
from geo_etl.layers import Result
from geo_etl.rows import COLUMNS, Rows


def frame(states: dict[int, list[float]]) -> pd.DataFrame:
    rows = []
    lgd = 1
    for state, areas in states.items():
        for area in areas:
            rows.append({"districtLgd": lgd, "stateLgd": state, "districtName": f"d{lgd}", "areaKm2": area})
            lgd += 1
    return pd.DataFrame(rows)


@pytest.mark.parametrize(
    ("text", "expected"),
    [(None, None), ("", None), ("all", None), (" ALL ", None), ("599", {599}), ("599, 600,", {599, 600})],
)
def test_parse_ints(text, expected):
    assert cli.parse_ints(text) == expected


def test_select_shard_none_returns_input():
    districts = frame({1: [10.0]})
    assert cli.select_shard(districts, None) is districts


@pytest.mark.parametrize("shard", ["0/2", "3/2", "1/0"])
def test_select_shard_rejects_out_of_range(shard):
    with pytest.raises(SystemExit):
        cli.select_shard(frame({1: [1.0]}), shard)


def test_select_shard_partitions_by_state_balanced_by_area():
    districts = frame({1: [100.0], 2: [60.0], 3: [50.0], 4: [5.0, 5.0]})
    shards = [cli.select_shard(districts, f"{k}/2") for k in (1, 2)]
    assert sorted(pd.concat(shards)["districtLgd"]) == sorted(districts["districtLgd"])
    assert set(shards[0]["stateLgd"]) == {1, 4}
    assert set(shards[1]["stateLgd"]) == {2, 3}
    for shard in shards:
        assert list(shard.index) == list(range(len(shard)))


def test_select_shard_keeps_states_whole_and_is_deterministic():
    districts = frame({s: [float(s)] * (s % 3 + 1) for s in range(1, 12)})
    owners = {}
    for k in (1, 2, 3):
        shard = cli.select_shard(districts, f"{k}/3")
        assert shard.equals(cli.select_shard(districts, f"{k}/3"))
        for state in set(shard["stateLgd"]):
            assert state not in owners
            owners[state] = k
    assert set(owners) == set(districts["stateLgd"])


def test_select_shard_more_shards_than_states_leaves_some_empty():
    districts = frame({1: [1.0]})
    assert len(cli.select_shard(districts, "1/3")) == 1
    assert cli.select_shard(districts, "2/3").empty


def fake_layer(districts, options):
    rows = Rows(SOILGRIDS, "fake")
    for _, district in districts.iterrows():
        rows.add(district, "clay", "0-5cm", "DISTRICT_MEAN", 250.0, unit="g/kg", pixels=12)
    return Result(SOILGRIDS, rows.frame(), notes={"fake": True})


def test_extract_and_combine_offline(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "LAYERS", {"fake": fake_layer})
    parts = tmp_path / "parts"
    out = tmp_path / "out"
    argv = ["--datasets", "fake", "--districts", "599", "--parts", str(parts), "--cache", str(tmp_path / "cache")]
    assert cli.main(["run", *argv, "--out", str(out)]) == 0
    meta = json.loads((parts / "fake.json").read_text(encoding="utf-8"))
    assert meta["rows"] == 1 and meta["districts"] == 1 and meta["failures"] == []
    values = pd.read_parquet(out / "district_env.parquet")
    assert list(values.columns) == COLUMNS
    assert values.iloc[0]["districtLgd"] == 599
    assert values.iloc[0]["districtName"] == "Mahe"
    summary = json.loads((out / "district_env_summary.json").read_text(encoding="utf-8"))
    assert summary["rows"] == 1
    assert summary["districts"] == 1
    assert summary["boundaries"]["code"] == BOUNDARIES.code
    assert [d["code"] for d in summary["datasets"]] == [SOILGRIDS.code]
    assert summary["layers"][0]["failureCount"] == 0
    assert summary["layers"][0]["districtsWithoutValues"] == []
    assert summary["layers"][0]["silentDistricts"] == []
    assert summary["layers"][0]["unexpectedWithoutCells"] == []
    assert summary["layers"][0]["lostStates"] == []
    assert (out / "district_geology.parquet").exists()
    assert len(summary["csv"]) == 1
    name = summary["csv"][0]
    assert re.fullmatch(r"KalaVigyan_Dataset_\d{4}-\d{2}-\d{2}_SoilGrids-2-0_District-Stats\.csv", name)
    exported = pd.read_csv(out / name)
    assert list(exported.columns) == COLUMNS
    assert exported.iloc[0]["districtLgd"] == 599
    assert "fake: 1 rows" in capsys.readouterr().out


def test_district_stats_filename_uses_ist_date_and_labels():
    late_utc = dt.datetime(2026, 11, 15, 20, 0, tzinfo=dt.UTC)
    assert cli.district_stats_filename("SOILGRIDS_2_0", late_utc) == (
        "KalaVigyan_Dataset_2026-11-16_SoilGrids-2-0_District-Stats.csv"
    )
    assert cli.dataset_label("NEW_SOURCE_V2") == "New-Source-V2"
    for code in cli.DATASET_LABELS:
        assert re.fullmatch(r"[A-Za-z0-9-]+", cli.dataset_label(code))


def test_combine_removes_stale_csvs(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "LAYERS", {"fake": fake_layer})
    out = tmp_path / "out"
    out.mkdir()
    stale = out / "KalaVigyan_Dataset_2020-01-01_Old_District-Stats.csv"
    stale.write_text("x\n", encoding="utf-8")
    argv = ["--datasets", "fake", "--districts", "599", "--parts", str(tmp_path / "parts"), "--cache", str(tmp_path)]
    assert cli.main(["run", *argv, "--out", str(out)]) == 0
    assert not stale.exists()
    assert len(list(out.glob(cli.CSV_GLOB))) == 1


def test_extract_shard_stem_and_failures(tmp_path, monkeypatch):
    def failing(districts, options):
        result = fake_layer(districts, options)
        result.failures.append({"step": "x", "districtLgds": [599], "error": "boom"})
        return result

    monkeypatch.setattr(cli, "LAYERS", {"bad": failing})
    parts = tmp_path / "parts"
    argv = ["extract", "--datasets", "bad", "--states", "34", "--shard", "1/1", "--parts", str(parts)]
    assert cli.main([*argv, "--cache", str(tmp_path)]) == 1
    assert (parts / "bad-shard1of1.parquet").exists()
    assert cli.main([*argv, "--cache", str(tmp_path), "--allow-failures"]) == 0
    meta = json.loads((parts / "bad-shard1of1.json").read_text(encoding="utf-8"))
    assert meta["lostStates"] == []
    assert meta["districtsWithoutValues"] == []


def test_extract_fails_a_state_left_without_values_even_with_allow_failures(tmp_path, monkeypatch, capsys):
    def puducherry_only(districts, options):
        return fake_layer(districts[districts["stateLgd"] == 34], options)

    monkeypatch.setattr(cli, "LAYERS", {"partial": puducherry_only})
    parts = tmp_path / "parts"
    argv = ["extract", "--datasets", "partial", "--states", "31,34", "--parts", str(parts), "--cache", str(tmp_path)]
    assert cli.main([*argv, "--allow-failures"]) == 1
    meta = json.loads((parts / "partial.json").read_text(encoding="utf-8"))
    assert meta["lostStates"] == [31]
    assert meta["districtsWithoutValues"] == [553]
    assert meta["silentDistricts"] == [553]
    assert "states [31]" in capsys.readouterr().err


def ocean_only(dataset):
    def run(districts, options):
        lgds = sorted(int(v) for v in districts["districtLgd"])
        return Result(dataset, Rows(dataset, "fake").frame(), districts_without_cells=lgds)

    return run


def test_extract_keeps_a_state_whose_only_district_is_reviewed_as_without_cells(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "LAYERS", {"ocean": ocean_only(GLIM)})
    parts = tmp_path / "parts"
    out = tmp_path / "out"
    argv = ["--datasets", "ocean", "--states", "31", "--parts", str(parts), "--cache", str(tmp_path)]
    assert cli.main(["run", *argv, "--out", str(out)]) == 0
    meta = json.loads((parts / "ocean.json").read_text(encoding="utf-8"))
    assert meta["rows"] == 0
    assert meta["districtsWithoutValues"] == [553]
    assert meta["districtsWithoutCells"] == [553]
    assert meta["unexpectedWithoutCells"] == []
    assert meta["silentDistricts"] == []
    assert meta["lostStates"] == []
    summary = json.loads((out / "district_env_summary.json").read_text(encoding="utf-8"))
    assert summary["layers"][0]["districtsWithoutValues"] == [553]
    assert summary["layers"][0]["districtsWithoutCells"] == [553]
    assert summary["layers"][0]["unexpectedWithoutCells"] == []
    assert summary["layers"][0]["lostStates"] == []
    assert "ocean: 0 rows, 0 failures, 1 districts without cells" in capsys.readouterr().out


def test_extract_fails_a_district_without_cells_outside_the_reviewed_list_even_with_allow_failures(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setattr(cli, "LAYERS", {"masked": ocean_only(SOILGRIDS)})
    parts = tmp_path / "parts"
    argv = ["extract", "--datasets", "masked", "--states", "31", "--parts", str(parts), "--cache", str(tmp_path)]
    assert cli.main([*argv, "--allow-failures"]) == 1
    meta = json.loads((parts / "masked.json").read_text(encoding="utf-8"))
    assert meta["districtsWithoutCells"] == [553]
    assert meta["unexpectedWithoutCells"] == [553]
    assert meta["lostStates"] == []
    assert "districts [553] were measured without a valid cell" in capsys.readouterr().err


def test_extract_fails_a_silent_district_whose_state_has_values_even_with_allow_failures(tmp_path, monkeypatch, capsys):
    def all_but_mahe(districts, options):
        return fake_layer(districts[districts["districtLgd"] != 599], options)

    monkeypatch.setattr(cli, "LAYERS", {"quiet": all_but_mahe})
    parts = tmp_path / "parts"
    argv = ["extract", "--datasets", "quiet", "--states", "34", "--parts", str(parts), "--cache", str(tmp_path)]
    assert cli.main([*argv, "--allow-failures"]) == 1
    meta = json.loads((parts / "quiet.json").read_text(encoding="utf-8"))
    assert meta["rows"] == 3
    assert meta["silentDistricts"] == [599]
    assert meta["lostStates"] == []
    assert "districts [599] have no values, no failure" in capsys.readouterr().err


def test_extract_fails_a_step_lost_for_a_whole_state_even_with_allow_failures(tmp_path, monkeypatch):
    def whole_state_step(districts, options):
        result = fake_layer(districts, options)
        lgds = [int(v) for v in districts["districtLgd"]]
        result.failures.append({"step": "clay 0-5cm Q0.05", "districtLgds": lgds, "error": "boom"})
        return result

    monkeypatch.setattr(cli, "LAYERS", {"step": whole_state_step})
    parts = tmp_path / "parts"
    argv = ["extract", "--datasets", "step", "--states", "34", "--parts", str(parts), "--cache", str(tmp_path)]
    assert cli.main([*argv, "--allow-failures"]) == 1
    meta = json.loads((parts / "step.json").read_text(encoding="utf-8"))
    assert meta["lostStates"] == [34]
    assert meta["districtsWithoutValues"] == []


def test_extract_with_no_districts_returns_2(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "LAYERS", {"fake": fake_layer})
    argv = ["extract", "--datasets", "fake", "--districts", "-1", "--parts", str(tmp_path), "--cache", str(tmp_path)]
    assert cli.main(argv) == 2


def test_combine_rejects_duplicate_keys(tmp_path):
    parts = tmp_path / "parts"
    parts.mkdir()
    district = pd.Series({"districtLgd": 599, "stateLgd": 34, "districtName": "Mahe"})
    rows = Rows(SOILGRIDS, "fake")
    rows.add(district, "clay", "0-5cm", "DISTRICT_MEAN", 1.0, unit="g/kg")
    for stem in ("a", "b"):
        rows.frame().to_parquet(parts / f"{stem}.parquet", index=False)
        meta = {"stem": stem, "dataset": SOILGRIDS.as_row(), "retrievedAt": "2026-11-16T00:00:00+00:00"}
        (parts / f"{stem}.json").write_text(json.dumps(meta), encoding="utf-8")
    assert cli.main(["combine", "--parts", str(parts), "--out", str(tmp_path / "out")]) == 1


def test_combine_refuses_parts_of_one_dataset_read_over_different_periods(tmp_path, capsys):
    parts = tmp_path / "parts"
    parts.mkdir()
    for stem, lgd, period in (("chirps-shard1of2", 599, "1981-2024"), ("chirps-shard2of2", 553, "1981-2025")):
        dataset = dataclasses.replace(CHIRPS, period=period)
        rows = Rows(dataset, "fake")
        rows.add(
            pd.Series({"districtLgd": lgd, "stateLgd": 34, "districtName": "d"}), "x", period, "NORMAL", 1.0, unit="mm"
        )
        rows.frame().to_parquet(parts / f"{stem}.parquet", index=False)
        meta = {"stem": stem, "dataset": dataset.as_row(), "retrievedAt": "2026-11-16T00:00:00+00:00"}
        (parts / f"{stem}.json").write_text(json.dumps(meta), encoding="utf-8")
    out = tmp_path / "out"
    assert cli.main(["combine", "--parts", str(parts), "--out", str(out)]) == 1
    assert "CHIRPS_3_0: its parts differ in {'period': ['1981-2024', '1981-2025']}" in capsys.readouterr().err
    assert not (out / "district_env.parquet").exists()


def test_the_chirps_last_year_command_prints_the_year_for_every_shard(monkeypatch, capsys):
    monkeypatch.setattr(cli.chirps, "latest_year", lambda: 2025)
    assert cli.main(["chirps-last-year"]) == 0
    assert capsys.readouterr().out == "2025\n"


def test_options_from_flags(tmp_path):
    parser_args = [
        "extract",
        "--cache",
        str(tmp_path),
        "--worldcover-factor",
        "8",
        "--soil-vars",
        "clay,sand",
        "--soil-depths",
        "0-5cm",
        "--chelsa-bio",
        "bio1",
        "--no-soil-uncertainty",
        "--no-chelsa-months",
        "--no-chirps-monthly",
        "--chirps-last-year",
        "2024",
    ]
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    cli.add_extract_args(sub.add_parser("extract"))
    options = cli.options_from(parser.parse_args(parser_args))
    assert options.chirps_last_year == 2024
    assert cli.options_from(parser.parse_args(["extract", "--cache", str(tmp_path)])).chirps_last_year is None
    assert options.worldcover_factor == 8
    assert options.hansen_factor == 1
    assert options.soil_vars == ("clay", "sand")
    assert options.soil_depths == ("0-5cm",)
    assert options.chelsa_bio == ("bio1",)
    assert not options.soil_uncertainty and not options.chelsa_months and not options.chirps_monthly
    assert options.cache == tmp_path
