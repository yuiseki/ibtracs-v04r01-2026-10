#!/usr/bin/env python3
"""Check the Parquet against the CSV with a second reader (DuckDB, all-varchar) and against the NetCDF.

    systemd-run --user --scope -p MemoryMax=8G -p CPUQuota=200% uv run python -u scripts/03_verify.py

Checks (docs/verify_local.json): file checksums against the MANIFEST; every cell of the Parquet against the
CSV text read by DuckDB; the units row against the column metadata; the row count and the rows per storm
against the NetCDF (numobs); the licence attribute of the NetCDF, saved to docs/nc_global_attributes.json.
"""

import hashlib
import json
import sys

import duckdb
import h5py
import ibt
import numpy as np
import pyarrow.parquet as pq

ROOT = ibt.ROOT


def sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    run = sorted((ROOT / "data" / "raw").glob("*/MANIFEST.json"))[-1].parent
    manifest = json.loads((run / "MANIFEST.json").read_text())
    bad = []
    for name, m in manifest["files"].items():
        if not name.startswith("..") and sha256(run / name) != m["sha256"]:
            bad.append(f"checksum {name}")
    csv = run / ibt.CSV_NAME
    pqf = ROOT / "data" / "parquet" / "ibtracs_all_observations.parquet"
    schema = pq.read_schema(pqf)
    names = schema.names
    kinds = {f.name: f.metadata[b"source_text_type"].decode() for f in schema}
    con = duckdb.connect()
    con.execute("set memory_limit='6GB'; set threads=2")
    con.execute(f"create table src as select row_number() over () - 1 as rn, * from read_csv('{csv}', "
                "header=true, all_varchar=true, parallel=false, quote='\"', delim=',', strict_mode=false)")  # fmt: skip
    if con.execute("describe src").fetchall()[1][0] != names[0]:
        bad.append("DuckDB column order")
    # rn 0 is the units row, rn 1.. are the observations
    units_row = con.execute(
        f"select {', '.join(f'"{n}"' for n in names)} from src where rn = 0"
    ).fetchone()
    units_csv = {
        n: (None if (u or "").strip() == "" else u) for n, u in zip(names, units_row, strict=True)
    }
    units_pq = {f.name: (f.metadata.get(b"unit") or b"").decode() or None for f in schema}
    if units_csv != units_pq:
        bad.append("units differ")
    n_src = con.execute("select count(*) from src where rn > 0").fetchone()[0]
    n_pq = pq.read_metadata(pqf).num_rows
    con.execute(f"create table mine as select file_row_number + 1 as rn, * from read_parquet('{pqf}', file_row_number=true)")  # fmt: skip
    exprs = []
    for n in names:
        s, p = f's."{n}"', f'm."{n}"'
        blank = f"nullif(trim({s}), '')"
        if kinds[n] in ("int32", "float64"):
            exprs.append(f"sum(case when try_cast({blank} as double) is distinct from cast({p} as double) "
                         f"or ({blank} is not null and try_cast({blank} as double) is null) then 1 else 0 end)")  # fmt: skip
        elif kinds[n] == "timestamp":
            exprs.append(f"sum(case when strftime({p}, '%Y-%m-%d %H:%M:%S') is distinct from {blank} then 1 else 0 end)")  # fmt: skip
        else:
            exprs.append(f"sum(case when {blank} is distinct from {p} then 1 else 0 end)")
    row = con.execute(f"select count(*), {', '.join(exprs)} from src s full join mine m using (rn) where s.rn > 0 or m.rn > 0").fetchone()  # fmt: skip
    joined, per_col = row[0], dict(zip(names, (int(x or 0) for x in row[1:]), strict=True))
    cell_diff = {n: c for n, c in per_col.items() if c}
    if cell_diff:
        bad.append(f"cell differences in {len(cell_diff)} columns")
    nonnull = dict(zip(names, con.execute("select " + ", ".join(f'count({c})' for c in (f'nullif(trim("{n}"), \'\')' for n in names)) + " from src where rn > 0").fetchone(), strict=True))  # fmt: skip
    cols_tsv = {ln.split("\t")[0]: int(ln.split("\t")[3]) for ln in (ROOT / "docs" / "columns.tsv").read_text().splitlines()[1:]}  # fmt: skip
    if nonnull != cols_tsv:
        bad.append("non-null counts differ from docs/columns.tsv")
    # the NetCDF: rows per storm
    with h5py.File(run / ibt.NC_NAME, "r") as f:
        sid_nc = [b"".join(r).decode().strip("\x00 ") for r in f["sid"][:].astype("S1")]
        numobs = f["numobs"][:].astype(int)
        attrs = {k: (v.decode() if isinstance(v, bytes) else str(v)) for k, v in f.attrs.items()}
    (ROOT / "docs" / "nc_global_attributes.json").write_text(
        json.dumps(attrs, indent=1, ensure_ascii=False) + "\n"
    )
    per_sid = dict(
        con.execute("select SID, count(*) from src where rn > 0 group by SID").fetchall()
    )
    mism = sum(1 for s, k in zip(sid_nc, numobs, strict=True) if per_sid.get(s) != k)
    extra = len(set(per_sid) - set(sid_nc))
    if mism or extra or n_src != int(numobs.sum()) or len(sid_nc) != len(per_sid):
        bad.append("rows per storm differ from the NetCDF")
    lic = attrs.get("license")
    if lic != "These data may be redistributed and used without restriction.":
        bad.append(f"NetCDF licence attribute changed: {lic!r}")
    sids_pq = np.array(pq.read_table(pqf, columns=["SID"])["SID"].to_pylist())
    res = {
        "csv_rows": n_src, "parquet_rows": n_pq, "joined_rows": joined, "columns": len(names),
        "cells_compared": n_src * len(names), "columns_with_differences": len(cell_diff),
        "nonnull_matches_columns_tsv": nonnull == cols_tsv, "units_match": units_csv == units_pq,
        "storms_csv": len(per_sid), "storms_netcdf": len(sid_nc), "netcdf_numobs_sum": int(numobs.sum()),
        "storms_with_different_row_count": mism, "distinct_sid_in_parquet": len(set(sids_pq.tolist())),
        "netcdf_license_attribute": lic, "problems": bad, "ok": not bad and n_src == n_pq == joined,
    }  # fmt: skip
    (ROOT / "docs" / "verify_local.json").write_text(json.dumps(res, indent=1) + "\n")
    print(json.dumps(res, indent=1))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
