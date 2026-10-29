#!/usr/bin/env python3
"""Push the card, licence, provenance, the raw files, the Parquet, the evidence and the docs to the Hub.

uv run python src/publish.py             # dry run: list the files and their sizes
uv run python src/publish.py --push      # prints the commit sha and writes docs/revision.json
"""

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
REPO = "yuiseki/ibtracs-v04r01-2026-10"
RAW = ["ibtracs.ALL.list.v04r01.csv", "IBTrACS.ALL.v04r01.nc",
       "IBTrACS_SerialNumber_NameMapping_v04r01_20261027.txt", "IBTrACS_v04r01_change_log.txt", "MANIFEST.json"]  # fmt: skip
DOCS = ["columns.tsv", "nc_global_attributes.json", "verify_local.json"]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def collect() -> dict[str, Path]:
    card = (DATA / "README.md").read_text(encoding="utf-8")
    if (
        "license: other" not in card
        or "These data may be redistributed and used without restriction." not in card
    ):
        raise SystemExit("the card does not carry the licence statement")
    run = sorted((DATA / "raw").glob("*/MANIFEST.json"))[-1].parent
    m = json.loads((run / "MANIFEST.json").read_text())
    ver = json.loads((ROOT / "docs" / "verify_local.json").read_text())
    rows = json.loads((DATA / "parquet" / "tables.json").read_text())["tables"][
        "ibtracs_all_observations"
    ]["rows"]
    if not ver["ok"] or ver["parquet_rows"] != rows or f"{rows:,}" not in card:
        raise SystemExit("the card or the local verification does not match the table")
    for name, f in m["files"].items():
        if not name.startswith("..") and sha256(run / name) != f["sha256"]:
            raise SystemExit(f"{name} is not the file in its manifest")
    files = {"README.md": DATA / "README.md", "LICENSE": DATA / "LICENSE", "provenance.yaml": DATA / "provenance.yaml",
             "parquet/ibtracs_all_observations.parquet": DATA / "parquet" / "ibtracs_all_observations.parquet",
             "parquet/tables.json": DATA / "parquet" / "tables.json"}  # fmt: skip
    files |= {f"raw/{run.name}/{n}": run / n for n in RAW}
    files |= {f"evidence/{p.name}": p for p in sorted((DATA / "evidence").iterdir())}
    files |= {f"docs/{n}": ROOT / "docs" / n for n in DOCS}
    missing = [k for k, v in files.items() if not v.is_file()]
    if missing:
        raise SystemExit(f"missing: {missing}")
    return files


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=REPO)
    ap.add_argument("--push", action="store_true")
    a = ap.parse_args()
    files = collect()
    total = sum(p.stat().st_size for p in files.values())
    print(f"{a.repo}\n  {len(files)} files, {total:,} bytes")
    for k, p in files.items():
        print(f"  {k}  {p.stat().st_size:,}")
    if not a.push:
        print("\ndry run. pass --push to upload")
        return 0
    from huggingface_hub import CommitOperationAdd, HfApi

    api = HfApi()
    api.create_repo(a.repo, repo_type="dataset", exist_ok=True, private=False)
    ops = [CommitOperationAdd(path_in_repo=k, path_or_fileobj=str(p)) for k, p in files.items()]
    info = api.create_commit(a.repo, ops, repo_type="dataset",
                             commit_message="IBTrACS v04r01 all basins as published (files of 2026-10-27)")  # fmt: skip
    sums = {k: sha256(p) for k, p in files.items()}
    (ROOT / "docs" / "revision.json").write_text(
        json.dumps({"repo": a.repo, "revision": info.oid, "sha256": sums}, indent=1) + "\n"
    )
    print("pushed", a.repo, "revision", info.oid)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
