#!/usr/bin/env python3
"""Read the repository back from the Hub at the recorded revision and compare it with the local copy:
file checksums, row count, schema (names, types, units), value counts, NULL counts and the cells themselves.

    uv run python scripts/05_verify_hub.py   # needs docs/revision.json from src/publish.py --push
"""

import hashlib
import json
import sys
from pathlib import Path

import pyarrow.parquet as pq
from huggingface_hub import hf_hub_download

ROOT = Path(__file__).parents[1]


def main() -> int:
    rev = json.loads((ROOT / "docs" / "revision.json").read_text())
    repo, sha = rev["repo"], rev["revision"]
    out, bad = {"repo": repo, "revision": sha}, []
    cache = ROOT / "data" / "hub_readback"
    for name, want in rev["sha256"].items():
        p = Path(hf_hub_download(repo, name, repo_type="dataset", revision=sha, local_dir=cache))
        h = hashlib.sha256()
        with p.open("rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        if h.hexdigest() != want:
            bad.append(f"checksum {name}")
    out["files_checked"] = len(rev["sha256"])
    hub = pq.read_table(cache / "parquet" / "ibtracs_all_observations.parquet")
    mine = pq.read_table(ROOT / "data" / "parquet" / "ibtracs_all_observations.parquet")
    info = json.loads((ROOT / "data" / "parquet" / "tables.json").read_text())
    out["rows"] = hub.num_rows
    out["columns"] = hub.num_columns
    if hub.schema != mine.schema or not hub.schema.equals(mine.schema, check_metadata=True):
        bad.append("schema or field metadata (units)")
    if hub.num_rows != info["tables"]["ibtracs_all_observations"]["rows"]:
        bad.append("rows vs the local table")
    if not hub.equals(mine):
        bad.append("cells differ from the local copy")
    cols_tsv = [
        ln.split("\t") for ln in (ROOT / "docs" / "columns.tsv").read_text().splitlines()[1:]
    ]
    nonnull = {c[0]: hub.num_rows - hub[c[0]].null_count for c in cols_tsv}
    if any(nonnull[c[0]] != int(c[3]) for c in cols_tsv):
        bad.append("non-null counts differ from docs/columns.tsv")
    out["nonnull_total_cells"] = sum(nonnull.values())
    vc = {}
    for c in ("BASIN", "NATURE", "TRACK_TYPE", "SEASON"):
        vc[c] = {str(d["values"]): d["counts"] for d in hub[c].value_counts().to_pylist()}
        vm = {str(d["values"]): d["counts"] for d in mine[c].value_counts().to_pylist()}
        if vc[c] != vm:
            bad.append(f"value counts {c}")
    out["value_counts"] = {k: dict(sorted(v.items())) for k, v in vc.items() if k != "SEASON"}
    out["distinct_sid"] = len(set(hub["SID"].to_pylist()))
    out["problems"] = bad
    (ROOT / "docs" / "verify_hub.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(out, indent=1))
    print(
        "OK: the repository at", sha, "equals the local copy" if not bad else f"has problems: {bad}"
    )
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
