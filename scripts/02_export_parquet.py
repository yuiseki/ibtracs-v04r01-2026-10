#!/usr/bin/env python3
"""Write the per-observation table as Parquet, one row per row of the CSV, in file order.

    systemd-run --user --scope -p MemoryMax=8G -p CPUQuota=200% uv run python -u scripts/02_export_parquet.py

Rules: the column names are the CSV's own; the second CSV line (units) is not a row but is kept as the
`unit` metadata of each column and in docs/columns.tsv; a blank cell (the file's missing marker) becomes NULL;
every other cell is kept as written. A column is int32, float64 or timestamp only when every non-missing cell
has that exact written form (no leading zeros, no exponent); otherwise it stays a string.
"""

import json

import ibt
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.csv as pacsv
import pyarrow.parquet as pq

ROOT = ibt.ROOT


def main() -> int:
    run = sorted((ROOT / "data" / "raw").glob("*/MANIFEST.json"))[-1].parent
    manifest = json.loads((run / "MANIFEST.json").read_text())
    src = run / ibt.CSV_NAME
    with src.open(encoding="utf-8") as f:
        header, units_line = f.readline(), f.readline()
    units = ibt.pair_units(header, units_line)
    names = list(units)
    table = pacsv.read_csv(
        src,
        read_options=pacsv.ReadOptions(skip_rows_after_names=1, block_size=1 << 28),
        convert_options=pacsv.ConvertOptions(
            column_types={n: pa.string() for n in names},
            null_values=[" ", ""],
            strings_can_be_null=True,
            quoted_strings_can_be_null=True,
        ),  # fmt: skip
    )
    if table.column_names != names:
        raise SystemExit("the CSV header changed while reading")
    fields, cols, report = [], [], []
    for n in names:
        col = table[n]
        kind = ibt.infer_type(col)
        if kind == "int32":
            out = pc.cast(col, pa.int32())
        elif kind == "float64":
            out = pc.cast(col, pa.float64())
        elif kind == "timestamp":
            out = pc.strptime(col, format=ibt.TIME_FORMAT, unit="s")
        else:
            out = col
        meta = {"source_text_type": kind}
        if units[n]:
            meta["unit"] = units[n]
        fields.append(pa.field(n, out.type, metadata=meta))
        cols.append(out)
        report.append((n, units[n] or "", kind, len(col) - col.null_count))
    schema = pa.schema(fields, metadata={
        "source_file": ibt.CSV_NAME, "source_sha256": manifest["files"][ibt.CSV_NAME]["sha256"],
        "missing_marker": "a single blank in the CSV, stored as NULL"})  # fmt: skip
    out = pa.Table.from_arrays(cols, schema=schema)
    dest = ROOT / "data" / "parquet"
    dest.mkdir(parents=True, exist_ok=True)
    pq.write_table(
        out, dest / "ibtracs_all_observations.parquet", compression="zstd", row_group_size=100_000
    )
    (ROOT / "docs").mkdir(exist_ok=True)
    with (ROOT / "docs" / "columns.tsv").open("w", encoding="utf-8") as f:
        f.write("column\tunit\tparquet_type\tnon_null\n")
        for n, u, k, c in report:
            f.write(f"{n}\t{u}\t{k}\t{c}\n")
    info = {"tables": {"ibtracs_all_observations": {"rows": out.num_rows, "columns": len(names)}}}
    (dest / "tables.json").write_text(json.dumps(info, indent=1) + "\n")
    print(f"{out.num_rows:,} rows, {len(names)} columns")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
