import hashlib
import json
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.craft_master_loader import DATA_DIR
from app.data.district_register import REGISTER_FILE, load_district_codes

from .state_values import refresh_state_values

SHAPES_PATH = DATA_DIR / "district-shapes.json"
SHAPES_SHA256 = "5432b41d6d6bc55d8fcae5030178a4ceaefab5d46f5770461552216cb802bc6c"
REGISTER_SHA256 = "2ff0acab5446b7d0710a10b372ab7f71055454a8155c5c82fb08dc997fd1cd21"

ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
LOOKUP = {ch: i for i, ch in enumerate(ALPHABET)}
SCALE = 1000
BATCH = 100

STATE_UPSERT = text(
    'INSERT INTO "AdminState" (lgd, name) VALUES (:lgd, :name) '
    'ON CONFLICT (lgd) DO UPDATE SET name = EXCLUDED.name, "updatedAt" = now() '
    'WHERE "AdminState".name IS DISTINCT FROM EXCLUDED.name'
)

DISTRICT_UPSERT = text(
    'INSERT INTO "AdminDistrict" (lgd, "stateLgd", name, geom, centroid, "boundarySource", indicative) '
    "SELECT CAST(:lgd AS integer), CAST(:state_lgd AS integer), CAST(:name AS varchar), "
    "CASE WHEN built.geom IS NULL OR ST_IsEmpty(built.geom) THEN NULL ELSE built.geom END, "
    "CASE WHEN CAST(:lon AS double precision) IS NULL THEN NULL "
    "ELSE ST_SetSRID(ST_MakePoint(CAST(:lon AS double precision), CAST(:lat AS double precision)), 4326) END, "
    "CAST('KAGGLE_INDICATIVE' AS \"BoundarySource\"), true "
    "FROM (SELECT ST_Multi(ST_CollectionExtract(ST_MakeValid("
    "ST_BuildArea(ST_UnaryUnion(ST_GeomFromText(CAST(:lines AS text), 4326)))), 3)) AS geom) AS built "
    "ON CONFLICT (lgd) DO UPDATE SET "
    '"stateLgd" = EXCLUDED."stateLgd", name = EXCLUDED.name, geom = EXCLUDED.geom, '
    'centroid = EXCLUDED.centroid, "updatedAt" = now() '
    'WHERE "AdminDistrict"."stateLgd" IS DISTINCT FROM EXCLUDED."stateLgd" '
    'OR "AdminDistrict".name IS DISTINCT FROM EXCLUDED.name '
    'OR "AdminDistrict".geom IS DISTINCT FROM EXCLUDED.geom '
    'OR "AdminDistrict".centroid IS DISTINCT FROM EXCLUDED.centroid'
)

STATE_SHAPES = text(
    'UPDATE "AdminState" AS s SET geom = merged.geom, "updatedAt" = now() FROM ('
    'SELECT "stateLgd", ST_Multi(ST_CollectionExtract(ST_MakeValid(ST_Union(geom)), 3)) AS geom '
    'FROM "AdminDistrict" WHERE geom IS NOT NULL GROUP BY "stateLgd") AS merged '
    'WHERE s.lgd = merged."stateLgd" AND s.geom IS DISTINCT FROM merged.geom'
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_inputs() -> None:
    for path, expected in ((SHAPES_PATH, SHAPES_SHA256), (REGISTER_FILE, REGISTER_SHA256)):
        actual = _sha256(path)
        if actual != expected:
            raise RuntimeError(f"{path.name}: sha256 {actual} does not match the vendored {expected}")


def decode_rings(payload: str) -> list[list[tuple[float, float]]]:
    out: list[list[tuple[float, float]]] = []
    index = 0
    x = y = 0

    def read() -> int:
        nonlocal index
        shift = result = 0
        while True:
            value = LOOKUP[payload[index]]
            index += 1
            result |= (value & 0x1F) << shift
            shift += 5
            if value < 0x20:
                break
        return ~(result >> 1) if result & 1 else result >> 1

    while index < len(payload):
        count = read()
        if count <= 0:
            break
        points: list[tuple[float, float]] = []
        for _ in range(count):
            x += read()
            y += read()
            points.append((x / SCALE, y / SCALE))
        out.append(points)
    return out


def rings_wkt(encoded_rings: list[str]) -> str | None:
    lines: list[str] = []
    for encoded in encoded_rings:
        for points in decode_rings(encoded):
            if len(points) < 3:
                continue
            closed = points if points[0] == points[-1] else [*points, points[0]]
            lines.append("(" + ", ".join(f"{lon:.3f} {lat:.3f}" for lon, lat in closed) + ")")
    if not lines:
        return None
    return "MULTILINESTRING(" + ", ".join(lines) + ")"


def district_seed_plan() -> dict[str, list[dict[str, Any]]]:
    verify_inputs()
    codes = load_district_codes()
    shapes = json.loads(SHAPES_PATH.read_text(encoding="utf-8"))
    states = [{"lgd": lgd, "name": name} for name, lgd in codes.states.items()]
    drawn = {int(row["lgd"]): row for row in shapes["districts"]}
    districts = [
        _district_row(lgd, codes.states[state], name, drawn.get(lgd))
        for (state, name), lgd in codes.districts.items()
    ]
    unregistered = sorted(set(drawn) - {row["lgd"] for row in districts})
    if unregistered:
        raise RuntimeError(f"Shapes without a register entry: {unregistered[:10]}")
    districts.sort(key=lambda row: row["lgd"])
    return {"states": sorted(states, key=lambda row: row["lgd"]), "districts": districts}


def _district_row(lgd: int, state_lgd: int, name: str, shape: dict[str, Any] | None) -> dict[str, Any]:
    centroid = shape.get("centroid") if shape else None
    return {
        "lgd": lgd,
        "state_lgd": state_lgd,
        "name": name,
        "lines": rings_wkt(shape["rings"]) if shape else None,
        "lon": float(centroid[0]) if centroid else None,
        "lat": float(centroid[1]) if centroid else None,
    }


async def seed_districts(session: AsyncSession) -> dict[str, int]:
    plan = district_seed_plan()
    await session.execute(STATE_UPSERT, plan["states"])
    rows = plan["districts"]
    for start in range(0, len(rows), BATCH):
        await session.execute(DISTRICT_UPSERT, rows[start : start + BATCH])
    await session.execute(STATE_SHAPES)
    await refresh_state_values(session)
    counts = (
        await session.execute(
            text(
                'SELECT (SELECT count(*) FROM "AdminState"), (SELECT count(*) FROM "AdminDistrict"), '
                '(SELECT count(*) FROM "AdminDistrict" WHERE geom IS NOT NULL)'
            )
        )
    ).one()
    return {
        "states": int(counts[0]),
        "districts": int(counts[1]),
        "districtsWithShape": int(counts[2]),
        "planned": len(rows),
        "plannedWithShape": sum(1 for row in rows if row["lines"]),
    }
