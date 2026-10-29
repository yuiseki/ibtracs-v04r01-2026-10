#!/usr/bin/env python3
"""Write data/README.md (the dataset card), data/LICENSE and data/provenance.yaml.

uv run python scripts/04_card.py
"""

import json

import ibt
import pyarrow.compute as pc
import pyarrow.parquet as pq

ROOT = ibt.ROOT
DATA = ROOT / "data"

POLICY = (
    "IBTrACS was developed to support scientific research efforts. The IBTrACS data usage policy follows the "
    "World Data Center for Meteorology (WDC), which provides full and open access to the data. We have "
    "agreements from the Regional Specialized Meteorological Centers that provide track data to make IBTrACS "
    "data open for distribution to contribute to global tropical cyclone research. We also use the World "
    "Meteorological Organization's Resolution 40 policy as the guide for commercial use of IBTrACS data."
)
NC_LICENSE = "These data may be redistributed and used without restriction."
CITE_DATA = (
    "Gahtan, Jennifer; Knapp, Kenneth R.; Schreck, Carl J. III; Diamond, Howard J.; Kossin, James P.; Kruk, "
    "Michael C. (2024). International Best Track Archive for Climate Stewardship (IBTrACS) Project, Version "
    "4.01. [indicate subset used]. NOAA National Centers for Environmental Information. "
    "https://doi.org/10.25921/82ty-9e16 [access date]."
)
CITE_PAPER = (
    "Knapp, K. R., M. C. Kruk, D. H. Levinson, H. J. Diamond, and C. J. Neumann, 2010: The International Best "
    "Track Archive for Climate Stewardship (IBTrACS): Unifying tropical cyclone best track data. Bulletin of "
    "the American Meteorological Society, 91, 363-376. doi:10.1175/2009BAMS2755.1"
)
DISCLAIMER = (
    "Distribution liability: NOAA and NCEI make no warranty, expressed or implied, regarding these data, nor "
    "does the fact of distribution constitute such a warranty. NOAA and NCEI cannot assume liability for any "
    "damages caused by any errors or omissions in these data. Use liability: NOAA and NCEI cannot provide any "
    "warranty as to the accuracy, reliability, or completeness of furnished data. Users assume responsibility "
    "to determine the usability of these data."
)

CARD = """---
license: other
license_name: ibtracs-redistributed-without-restriction-with-citation
license_link: LICENSE
language:
- en
tags:
- tropical-cyclone
- typhoon
- hurricane
- best-track
- climate
- noaa
size_categories:
- 100K<n<1M
configs:
- config_name: observations
  data_files: parquet/ibtracs_all_observations.parquet
---

# IBTrACS v04r01, all basins (NOAA NCEI), files of {modified}

熱帯低気圧(台風・ハリケーン・サイクロン)のベストトラックを世界の機関分まとめた IBTrACS v04r01 の全海域版の凍結コピーです。
配布元の NetCDF と CSV をそのまま置き、CSV の全行を Parquet にしました。

IBTrACS v04r01 (all basins), exactly as published by NOAA NCEI, plus the observation table as Parquet.
{rows:,} observations of {storms:,} systems, {t0} to {t1} (UTC), seasons {s0} to {s1}.

## Source

| file | size (bytes) | Last-Modified | sha256 |
| --- | ---: | --- | --- |
{file_rows}

- Directory: {base}/
- Acquired {acquired}. IBTrACS is overwritten in place by its producer; this repository follows the latest
  files and is not a history. The producer's own change log is `raw/{run}/{log}`.
- The NetCDF attribute `date_created` is {nc_created}, the server's Last-Modified is {modified}; the two files
  agree on the number of storms and of observations (checked in `scripts/03_verify.py`).

## Terms of use and attribution

Three statements of the provider, all saved in this repository:

1. Inside the NetCDF file itself, the global attribute `license` reads (`docs/nc_global_attributes.json`):

> {nc_license}

2. On the NCEI product page (`evidence/ncei_ibtracs_product_page.html`):

> {policy}

3. In the NCEI metadata record of the dataset (`evidence/ncei_C01552_iso19115.xml`): the citation request below
   and this liability text.

> {disclaimer}

Please cite (the provider's request, cite the subset used):

> {cite_data}
>
> {cite_paper}

The maintainer treats the provider's condition (citation of the source) as equivalent to CC BY attribution.
That is the maintainer's reading, not a statement of NOAA or NCEI.

IBTrACS merges tracks from several agencies. The page grounds the redistribution in agreements with the
Regional Specialized Meteorological Centers that provide track data; the NetCDF `contributor_name` also lists
the Joint Typhoon Warning Center, the Shanghai Typhoon Institute (CMA), the Hong Kong Observatory, the Korea
Meteorological Administration, NCAR and two individuals' datasets. The pages do not give the terms of each
contributor separately; the file's own `license` attribute covers the whole file. NOAA, NCEI and the agencies did
not review this copy.

## Files

| file | content |
| --- | --- |
| `raw/{run}/{csv}` | the CSV, byte for byte (header row, then a row of units, then the observations) |
| `raw/{run}/{nc}` | the NetCDF, byte for byte (one row per system, tracks on a fixed grid of 360 steps) |
| `raw/{run}/{map}` | the producer's serial number to name mapping |
| `raw/{run}/{log}` | the producer's change log |
| `raw/{run}/MANIFEST.json` | URLs, sizes, Last-Modified and sha256 of every file and page |
| `parquet/ibtracs_all_observations.parquet` | the CSV as a table, {rows:,} rows, {cols} columns |
| `docs/columns.tsv` | per column: unit, Parquet type, number of non-blank cells |
| `docs/nc_global_attributes.json` | the global attributes of the NetCDF, including `license` |
| `docs/verify_local.json` | the local verification |
| `evidence/` | the NCEI product page and the metadata record with the terms |
| `provenance.yaml`, `LICENSE` | provenance record and the quoted terms |

The provider's column documentation ({coldoc}) and technical details ({techdoc}) are PDFs and are not copied
here; follow the links.

## Columns of `observations`

The {cols} column names are the CSV's own, in the CSV's order (SID, SEASON, NUMBER, BASIN, SUBBASIN, NAME,
ISO_TIME, NATURE, LAT, LON, WMO_*, TRACK_TYPE, DIST2LAND, LANDFALL, IFLAG, then one block of columns per
agency: USA_*, TOKYO_*, CMA_*, HKO_*, KMA_*, NEWDELHI_*, REUNION_*, BOM_*, NADI_*, WELLINGTON_*, DS824_*,
TD9636_*, NEUMANN_*, MLC_*). The unit of each column (the CSV's second line) is the `unit` metadata of the
Parquet field and the `unit` column of `docs/columns.tsv`.

| rule | detail |
| --- | --- |
| missing value | a single blank in the CSV is NULL in the table; no other cell is changed |
| number columns | int32 or float64 only when every non-blank cell is written as a plain number (no leading zeros, no exponent); the type of each column is in `docs/columns.tsv` ({n_int} int32, {n_float} float64) |
| `ISO_TIME` | timestamp (seconds), the text `YYYY-MM-DD HH:MM:SS` of the CSV; the NetCDF time attribute is days since 1858-11-17 |
| strings | {n_str} columns stay strings (identifiers, names, agency codes, flags); {n_empty} of them are blank in every row (REUNION_R64_*, TD9636_PRES) |
| row order | the order of the CSV |

## Transformation

`scripts/01_collect.py` downloads the files and the pages and writes the MANIFEST. `scripts/02_export_parquet.py`
reads the CSV with pyarrow and writes the Parquet. `scripts/03_verify.py` reads the CSV again with DuckDB as
text and compares every cell of the Parquet ({cells:,} cells, 0 differences), compares the units row and the
non-blank counts, and checks the rows per storm and the total against the NetCDF (`numobs`). The checker was
confirmed to fail when one cell of the Parquet was changed. Nothing is scored, smoothed or merged further.

## Limits

- The recent seasons carry provisional tracks (`TRACK_TYPE` `PROVISIONAL`, `US-PROVISIONAL` and
  `US-PROVISIONAL_spur`: {n_prov:,} rows) that the producer replaces when best-track data arrive.
- The NCEI metadata record warns that various agencies have different practices when it comes to reporting
  maximum sustained wind speeds, which makes comparing winds between basins or through time problematic.
- Only known tropical systems are recorded, and far fewer before the satellite era.
- When NCEI publishes a new version or corrects files, this repository follows the latest.
"""


def main() -> int:
    run = sorted((DATA / "raw").glob("*/MANIFEST.json"))[-1].parent
    m = json.loads((run / "MANIFEST.json").read_text())
    ver = json.loads((ROOT / "docs" / "verify_local.json").read_text())
    if not ver["ok"]:
        raise SystemExit("verify_local.json is not ok")
    attrs = json.loads((ROOT / "docs" / "nc_global_attributes.json").read_text())
    pqf = DATA / "parquet" / "ibtracs_all_observations.parquet"
    t = pq.read_table(pqf, columns=["SEASON", "ISO_TIME", "TRACK_TYPE"])
    tmin, tmax = pc.min_max(t["ISO_TIME"]).as_py().values()
    smin, smax = pc.min_max(t["SEASON"]).as_py().values()
    n_prov = int(pc.sum(pc.is_in(t["TRACK_TYPE"], value_set=__import__("pyarrow").array(
        ["PROVISIONAL", "US-PROVISIONAL", "US-PROVISIONAL_spur"]))).as_py())  # fmt: skip
    cols = [ln.split("\t") for ln in (ROOT / "docs" / "columns.tsv").read_text().splitlines()[1:]]
    kinds = [c[2] for c in cols]
    modified = max(f["last_modified"] for f in m["files"].values() if "last_modified" in f)
    file_rows = "\n".join(
        f"| `{n}` | {f['size']:,} | {f['last_modified']} | `{f['sha256']}` |"
        for n, f in m["files"].items() if "last_modified" in f)  # fmt: skip
    card = CARD.format(
        modified=run.name[:4] + "-" + run.name[4:6] + "-" + run.name[6:], rows=ver["parquet_rows"], storms=ver["storms_csv"],
        t0=tmin.strftime("%Y-%m-%d %H:%M"), t1=tmax.strftime("%Y-%m-%d %H:%M"), s0=smin, s1=smax,
        file_rows=file_rows, base=ibt.BASE, acquired=m["acquired_utc"][:10], run=run.name, log=ibt.LOG_NAME,
        nc_created=attrs["date_created"], nc_license=attrs["license"], policy=POLICY, disclaimer=DISCLAIMER,
        cite_data=CITE_DATA, cite_paper=CITE_PAPER, csv=ibt.CSV_NAME, nc=ibt.NC_NAME, map=ibt.MAP_NAME,
        cols=ver["columns"], coldoc=ibt.COLUMN_DOC_URL, techdoc=ibt.TECH_DOC_URL,
        n_int=kinds.count("int32"), n_float=kinds.count("float64"), n_str=kinds.count("string"),
        n_empty=sum(1 for c in cols if int(c[3]) == 0), cells=ver["cells_compared"], n_prov=n_prov,
    )  # fmt: skip
    if attrs["license"] != NC_LICENSE:
        raise SystemExit("the NetCDF licence attribute is not the quoted text")
    (DATA / "README.md").write_text(card, encoding="utf-8")
    (DATA / "LICENSE").write_text(
        "Terms as stated by the provider (NOAA NCEI) for IBTrACS v04r01.\n\n"
        f"NetCDF global attribute `license`:\n\n{NC_LICENSE}\n\n"
        f"NCEI product page ({PAGE_URL}):\n\n{POLICY}\n\n"
        f"NCEI metadata record:\n\n{DISCLAIMER}\n\nRequested citation:\n\n{CITE_DATA}\n\n{CITE_PAPER}\n",
        encoding="utf-8",
    )
    (DATA / "provenance.yaml").write_text(
        "source: IBTrACS v04r01 all basins (NOAA NCEI)\n"
        f"url: {ibt.BASE}/\n"
        "doi: 10.25921/82ty-9e16\n"
        "license: NetCDF license attribute (redistributed and used without restriction) and the NCEI policy; citation requested\n"
        f"retrieved: {m['acquired_utc'][:10]}\nlast_modified: {modified}\n"
        "files:\n"
        + "".join(
            f"  - {n}: {f['sha256']}\n" for n, f in m["files"].items() if "last_modified" in f
        )
        + f"rows: {ver['parquet_rows']}\n",
        encoding="utf-8",
    )
    print(f"card: {len(card):,} chars")
    return 0


PAGE_URL = ibt.PAGES["ncei_ibtracs_product_page.html"]

if __name__ == "__main__":
    raise SystemExit(main())
