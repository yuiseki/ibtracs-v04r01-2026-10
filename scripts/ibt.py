"""Constants and helpers shared by the scripts of ibtracs-v04r01-2026-10."""

from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc

ROOT = Path(__file__).parents[1]
BASE = "https://www.ncei.noaa.gov/data/international-best-track-archive-for-climate-stewardship-ibtracs/v04r01"
CSV_NAME = "ibtracs.ALL.list.v04r01.csv"
NC_NAME = "IBTrACS.ALL.v04r01.nc"
MAP_NAME = "IBTrACS_SerialNumber_NameMapping_v04r01_20261027.txt"
LOG_NAME = "IBTrACS_v04r01_change_log.txt"
FILES = {  # name -> path under BASE
    CSV_NAME: f"access/csv/{CSV_NAME}",
    NC_NAME: f"access/netcdf/{NC_NAME}",
    MAP_NAME: f"access/csv/{MAP_NAME}",
    LOG_NAME: f"doc/{LOG_NAME}",
}
PAGES = {  # evidence name -> URL
    "ncei_ibtracs_product_page.html": "https://www.ncei.noaa.gov/products/international-best-track-archive",
    "ncei_C01552_iso19115.xml": "https://www.ncei.noaa.gov/metadata/geoportal/rest/metadata/item/gov.noaa.ncdc:C01552/xml",
}
COLUMN_DOC_URL = f"{BASE}/doc/IBTrACS_v04r01_column_documentation.pdf"
TECH_DOC_URL = f"{BASE}/doc/IBTrACS_version4r01_Technical_Details.pdf"
UA = "Mozilla/5.0 (research; yuiseki)"

_INT = r"^-?(0|[1-9][0-9]*)$"
_FLOAT = r"^-?(0|[1-9][0-9]*)\.[0-9]+$"
_TIME = r"^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}$"
TIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def is_missing(v: str | None) -> bool:
    """The file marks a missing value with a single blank (or nothing)."""
    return v is None or v.strip() == ""


def infer_type(values) -> str:
    """int32, float64, timestamp or string from the non-missing cells; refuse padded cells."""
    arr = (
        values
        if isinstance(values, pa.ChunkedArray | pa.Array)
        else pa.array(list(values), pa.string())
    )
    arr = arr.cast(pa.string())
    arr = pc.if_else(pc.equal(pc.utf8_trim_whitespace(arr), ""), pa.scalar(None, pa.string()), arr)
    cells = arr.drop_null()
    if len(cells) == 0:
        return "string"
    if not pc.all(pc.equal(cells, pc.utf8_trim_whitespace(cells))).as_py():
        raise ValueError("a cell has leading or trailing blanks")

    def every(pattern: str) -> bool:
        return bool(pc.all(pc.match_substring_regex(cells, pattern)).as_py())

    if every(_INT):
        return "int32"
    if every(f"{_INT}|{_FLOAT}"):
        return "float64"
    if every(_TIME):
        return "timestamp"
    return "string"


def pair_units(header: str, units: str) -> dict[str, str | None]:
    names, us = header.rstrip("\n").split(","), units.rstrip("\n").split(",")
    if len(names) != len(us):
        raise ValueError(f"{len(names)} names but {len(us)} unit cells")
    return {n: (None if is_missing(u) else u) for n, u in zip(names, us, strict=True)}
