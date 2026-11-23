import json
from dataclasses import asdict, dataclass
from pathlib import Path

CLIMATE_FIRST_YEAR = 1981
REGISTRY = Path(__file__).resolve().parents[3] / "backend" / "app" / "data" / "datasets" / "registry.json"
BUILD = "geo-etl"
RECORD_FIELDS = (
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
    "citation",
    "doi",
    "landingUrl",
    "url",
)


@dataclass(frozen=True)
class Dataset:
    code: str
    title: str
    publisher: str
    edition: str
    version: str
    period: str
    nativeResolution: str
    crs: str
    licence: str
    licenceUrl: str | None
    attribution: str | None
    redistributable: bool
    citation: str | None
    doi: str | None
    landingUrl: str
    url: str

    def as_row(self) -> dict:
        return asdict(self)


def read_registry(path: Path = REGISTRY) -> dict[str, Dataset]:
    body = json.loads(path.read_text(encoding="utf-8"))
    built = [entry for entry in body["datasets"] if entry["build"] == BUILD]
    return {entry["code"]: Dataset(**{field: entry[field] for field in RECORD_FIELDS}) for entry in built}


ALL = read_registry()
BOUNDARIES = ALL["DR_DISTRICT_SHAPES"]
SOILGRIDS = ALL["SOILGRIDS_2_0"]
WORLDCOVER = ALL["ESA_WORLDCOVER_2021_V200"]
HANSEN = ALL["HANSEN_GFC_2025_V1_13"]
CHELSA = ALL["CHELSA_2_1_1981_2010"]
CHIRPS = ALL["CHIRPS_3_0"]
GHCN_CAMS = ALL["GHCN_CAMS_T2M"]
GROUNDWATER = ALL["OGD_GW_RESOURCES_RAJASTHAN_2023"]
COPDEM = ALL["COPERNICUS_DEM_GLO90"]
HYDRORIVERS = ALL["HYDRORIVERS_1_0"]
MRDS = ALL["USGS_MRDS"]
GLIM = ALL["GLIM_1_0_05DEG"]
WIKIDATA_RIVER_NAMES = ALL["WIKIDATA_RIVER_NAMES"]
OSM_RIVER_NAMES = ALL["OSM_RIVER_NAMES"]
