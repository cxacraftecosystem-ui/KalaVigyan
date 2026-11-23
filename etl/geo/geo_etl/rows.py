import math
from dataclasses import dataclass, field

import pandas as pd

from geo_etl.catalog import Dataset

STATS = (
    "DISTRICT_MEAN",
    "DISTRICT_P10",
    "DISTRICT_P90",
    "DISTRICT_MIN",
    "DISTRICT_MAX",
    "UNCERTAINTY_Q05_MEAN",
    "UNCERTAINTY_Q95_MEAN",
    "SHARE",
    "CLASS",
    "NORMAL",
    "TOTAL",
    "DENSITY",
    "DISTANCE",
    "COUNT",
    "TREND_PER_DECADE",
    "TREND_P_VALUE",
)

COLUMNS = [
    "districtLgd",
    "stateLgd",
    "districtName",
    "datasetCode",
    "variable",
    "depthOrPeriod",
    "stat",
    "value",
    "valueText",
    "unit",
    "method",
    "pixelCount",
    "source",
    "version",
    "resolution",
    "licence",
]


@dataclass
class Rows:
    dataset: Dataset
    method: str
    items: list[dict] = field(default_factory=list)

    def add(
        self,
        district: pd.Series,
        variable: str,
        depth_or_period: str,
        stat: str,
        value: float | None,
        *,
        unit: str,
        pixels: float | None = None,
        text: str | None = None,
        method: str | None = None,
        resolution: str | None = None,
    ) -> None:
        if stat not in STATS:
            raise ValueError(f"unknown stat {stat}")
        if value is not None and (isinstance(value, float) and not math.isfinite(value)):
            value = None
        if value is None and text is None:
            return
        self.items.append(
            {
                "districtLgd": int(district["districtLgd"]),
                "stateLgd": int(district["stateLgd"]),
                "districtName": str(district["districtName"]),
                "datasetCode": self.dataset.code,
                "variable": variable,
                "depthOrPeriod": depth_or_period,
                "stat": stat,
                "value": None if value is None else float(value),
                "valueText": text,
                "unit": unit,
                "method": method or self.method,
                "pixelCount": None if pixels is None else float(pixels),
                "source": self.dataset.title,
                "version": self.dataset.edition,
                "resolution": resolution or self.dataset.nativeResolution,
                "licence": self.dataset.licence,
            }
        )

    def frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.items, columns=COLUMNS)


def pick(record: pd.Series | dict, prefix: str):
    keys = record.index if isinstance(record, pd.Series) else list(record)
    for key in keys:
        if key == prefix or str(key).startswith(prefix + "_"):
            return record[key]
    raise KeyError(prefix)
