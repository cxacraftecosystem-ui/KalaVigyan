import datetime as dt
import hashlib
import json

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import LineString

import load_rivers
from geo_etl.river_districts import HIT_COLUMNS
from geo_etl.rivers import topology_key, write_rivers
from load_rivers import (
    BASIN_COLUMNS,
    REACH_COLUMNS,
    delete_superseded,
    output_problems,
    reach_rows,
    read_outputs,
    replace_rivers,
    stored_sha256,
    superseded_keys,
    upload_topologies,
)

SOURCE, MOUTH, COAST = 41000010, 41000040, 41000090
KACHCHH, BANASKANTHA, UNSEEDED = 449, 450, 999
SEEDED = [(KACHCHH,), (BANASKANTHA,)]
DATASET_ID = "8c5f1d2e-0000-4000-8000-000000000043"


def reaches() -> gpd.GeoDataFrame:
    rows = [
        (SOURCE, MOUTH, MOUTH, [(69.0, 23.6), (69.1, 23.4)]),
        (MOUTH, 0, MOUTH, [(69.1, 23.4), (69.2, 23.1)]),
        (COAST, 0, COAST, [(70.0, 22.0), (70.1, 21.9)]),
    ]
    return gpd.GeoDataFrame(
        [
            {
                "hyrivId": rid,
                "nextDown": down,
                "mainRiv": main,
                "ordStra": 2,
                "uplandSkm": 150.0,
                "disAvCms": 0.5,
                "lengthKm": 4.2,
                "geometry": LineString(coords),
            }
            for rid, down, main, coords in rows
        ],
        geometry="geometry",
        crs="EPSG:4326",
    )


def hits() -> pd.DataFrame:
    rows = [[SOURCE, KACHCHH, 0.0], [MOUTH, KACHCHH, 0.0], [MOUTH, BANASKANTHA, 0.75], [COAST, UNSEEDED, 0.2]]
    return pd.DataFrame(rows, columns=HIT_COLUMNS)


@pytest.fixture
def outputs(tmp_path):
    write_rivers(reaches(), hits(), tmp_path, retrieved_at=dt.datetime(2026, 11, 17, tzinfo=dt.UTC))
    return read_outputs(tmp_path)


class MissingKey(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.response = {"Error": {"Code": code}}


class FakeBucket:
    def __init__(self, stored: dict[str, str]):
        self.stored = stored
        self.puts: list[dict] = []

    def head_object(self, Bucket, Key):
        if Key not in self.stored:
            raise MissingKey("404")
        return {"Metadata": {"sha256": self.stored[Key]}}

    def put_object(self, **kwargs):
        self.puts.append(kwargs)


def test_written_outputs_pass_the_load_checks(outputs):
    assert output_problems(outputs) == []


def test_a_changed_topology_or_count_is_refused(outputs):
    basin = outputs.manifest["basins"][0]
    (outputs.folder / basin["file"]).write_bytes(b"{}")
    outputs.manifest["reaches"] = 4
    outputs.manifest["basins"][1]["reaches"] = 5
    assert output_problems(outputs) == [
        f"basin {MOUTH}'s topology does not match its sha256",
        f"basin {COAST} lists 5 reaches, the file holds 1",
        "the manifest counts 4 reaches, the file holds 3",
    ]


def test_reach_districts_that_disagree_with_the_reaches_are_refused(outputs):
    outputs.manifest["reachDistricts"] = 5
    extra = pd.DataFrame([[41999999, KACHCHH, 0.1], [MOUTH, KACHCHH, 1.5]], columns=HIT_COLUMNS)
    broken = outputs.__class__(
        folder=outputs.folder,
        reaches=outputs.reaches,
        hits=pd.concat([outputs.hits, extra], ignore_index=True),
        manifest=outputs.manifest,
    )
    assert output_problems(broken) == [
        "the manifest counts 5 reach districts, the file holds 6",
        "reach districts name reaches that are not kept: [41999999]",
        "a reach lists a district twice",
        "a reach enters a district outside its own length",
    ]


def test_only_topologies_not_stored_under_their_digest_are_uploaded(outputs):
    first, second = outputs.manifest["basins"]
    key_first, key_second = (topology_key("v10", b["mainRiv"], b["sha256"]) for b in (first, second))
    assert key_second.split("/")[3:5] == [str(COAST), second["sha256"]]
    stale = topology_key("v10", second["mainRiv"], hashlib.sha256(b"older").hexdigest())
    bucket = FakeBucket({key_first: first["sha256"], stale: "older"})
    assert upload_topologies(bucket, "kalavigyan-media", outputs) == (1, 1)
    [put] = bucket.puts
    body = (outputs.folder / second["file"]).read_bytes()
    assert put == {
        "Bucket": "kalavigyan-media",
        "Key": key_second,
        "Body": body,
        "ContentType": "application/json",
        "ServerSideEncryption": "AES256",
        "Metadata": {"sha256": hashlib.sha256(body).hexdigest()},
    }
    assert json.loads(body)["objects"]["reaches"]["geometries"][0]["id"] == COAST


class ListedBucket:
    def __init__(self, pages: list[list[str]], refused: tuple[str, ...] = ()):
        self.pages = pages
        self.refused = refused
        self.listed: list[dict] = []
        self.deletes: list[list[str]] = []

    def get_paginator(self, name):
        assert name == "list_objects_v2"
        return self

    def paginate(self, **kwargs):
        self.listed.append(kwargs)
        return [{"Contents": [{"Key": key} for key in page]} if page else {} for page in self.pages]

    def delete_objects(self, Bucket, Delete):
        keys = [item["Key"] for item in Delete["Objects"]]
        assert Delete["Quiet"] is True
        self.deletes.append(keys)
        return {"Errors": [{"Key": key, "Code": "AccessDenied"} for key in keys if key in self.refused]}


def test_every_river_file_no_basin_of_the_load_names_leaves_the_bucket(outputs):
    first, second = outputs.manifest["basins"]
    kept = [topology_key("v10", basin["mainRiv"], basin["sha256"]) for basin in (first, second)]
    older = topology_key("v10", first["mainRiv"], hashlib.sha256(b"older").hexdigest())
    dropped = topology_key("v10", 41999999, hashlib.sha256(b"gone").hexdigest())
    earlier = topology_key("v9", second["mainRiv"], second["sha256"])
    bucket = ListedBucket([[kept[0], older], [], [dropped, kept[1], earlier]])
    found = superseded_keys(bucket, "kalavigyan-media", outputs)
    assert bucket.listed == [{"Bucket": "kalavigyan-media", "Prefix": "media/rivers/"}]
    assert found == sorted([older, dropped, earlier])
    assert delete_superseded(bucket, "kalavigyan-media", found) == 3
    assert bucket.deletes == [sorted([older, dropped, earlier])]


def test_deletes_go_in_batches_of_a_thousand_and_a_refused_delete_fails_the_load():
    keys = [f"media/rivers/v10/{n}/x/f.json" for n in range(2001)]
    bucket = ListedBucket([])
    assert delete_superseded(bucket, "b", keys) == 2001
    assert [len(batch) for batch in bucket.deletes] == [1000, 1000, 1]
    assert delete_superseded(bucket, "b", []) == 0
    refusing = ListedBucket([], refused=(keys[3],))
    with pytest.raises(
        RuntimeError, match=r"1 superseded river topologies could not be deleted: .*/3/x/f.json \(AccessDenied\)"
    ):
        delete_superseded(refusing, "b", keys[:5])


def test_a_head_error_other_than_missing_stops_the_upload():
    class Refusing:
        def head_object(self, Bucket, Key):
            raise MissingKey("403")

    assert stored_sha256(FakeBucket({}), "b", "k") is None
    with pytest.raises(MissingKey):
        stored_sha256(Refusing(), "b", "k")


def test_reach_rows_carry_the_line_as_ewkb_in_wgs84(outputs):
    rows = reach_rows(outputs.reaches)
    assert [row[:7] for row in rows] == [
        [SOURCE, MOUTH, MOUTH, 2, 150.0, 0.5, 4.2],
        [MOUTH, 0, MOUTH, 2, 150.0, 0.5, 4.2],
        [COAST, 0, COAST, 2, 150.0, 0.5, 4.2],
    ]
    assert rows[0][7].upper().startswith("0102000020E6100000")


class FakeCursor:
    def __init__(self):
        self.executed: list[str] = []
        self.copied: dict[str, list[list]] = {}
        self._answer: list = []

    def execute(self, sql, params=None):
        self.executed.append(sql)
        if "information_schema.columns" in sql:
            table = params[0]
            names = {
                "RiverBasin": BASIN_COLUMNS,
                "RiverReach": REACH_COLUMNS,
                "RiverReachDistrict": HIT_COLUMNS,
                "AdminDistrict": ["lgd", "name"],
            }.get(table)
            if names is None:
                names = ["code", "title", "licence", "edition", "licenceUrl", "attribution"]
            self._answer = [(name, "text") for name in names]
        elif sql.startswith('insert into "EnvDataset"'):
            self._answer = [(DATASET_ID, "HYDRORIVERS_1_0")]
        elif sql == 'select lgd from "AdminDistrict"':
            self._answer = SEEDED

    def fetchall(self):
        return self._answer

    def fetchone(self):
        return self._answer[0]

    def copy(self, sql):
        rows = self.copied.setdefault(sql, [])

        class Copy:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def write_row(self, row):
                rows.append(row)

        return Copy()


def test_replace_rivers_writes_the_dataset_row_then_basins_then_reaches(outputs):
    cursor = FakeCursor()
    assert replace_rivers(cursor, outputs) == (2, 3, 3)
    deletes = [sql for sql in cursor.executed if sql.startswith("delete")]
    assert deletes == ['delete from "RiverReachDistrict"', 'delete from "RiverReach"', 'delete from "RiverBasin"']
    basin_copy, reach_copy, hit_copy = cursor.copied
    assert basin_copy.startswith('copy "RiverBasin" ("mainRiv", "datasetId", "reachCount", "topologySha256")')
    assert [row[:3] for row in cursor.copied[basin_copy]] == [[MOUTH, DATASET_ID, 2], [COAST, DATASET_ID, 1]]
    assert [row[0] for row in cursor.copied[reach_copy]] == [SOURCE, MOUTH, COAST]
    assert hit_copy.startswith('copy "RiverReachDistrict" ("hyrivId", "districtLgd", "entry")')
    assert cursor.copied[hit_copy] == [[SOURCE, KACHCHH, 0.0], [MOUTH, KACHCHH, 0.0], [MOUTH, BANASKANTHA, 0.75]]


def test_reach_districts_wait_for_the_seeded_districts():
    with pytest.raises(SystemExit, match="seed_districts"):
        load_rivers.hit_rows(hits(), set())
    with pytest.raises(SystemExit, match="seed_districts"):
        load_rivers.hit_rows(hits(), None)


def test_a_missing_river_table_stops_the_load(outputs):
    cursor = FakeCursor()
    cursor.execute = lambda sql, params=None: setattr(cursor, "_answer", [])
    with pytest.raises(SystemExit, match='table "RiverBasin" does not exist'):
        replace_rivers(cursor, outputs)


def test_main_validates_without_connecting(outputs, capsys, monkeypatch):
    assert load_rivers.main(["--out", str(outputs.folder), "--dry-run"]) == 0
    assert "3 reaches in 2 basins" in capsys.readouterr().out
    monkeypatch.delenv("KALAVIGYAN_TEST_DSN_UNSET", raising=False)
    assert load_rivers.main(["--out", str(outputs.folder), "--dsn-env", "KALAVIGYAN_TEST_DSN_UNSET"]) == 2
