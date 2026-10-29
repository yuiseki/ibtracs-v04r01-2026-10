#!/usr/bin/env python3
"""Fetch the IBTrACS v04r01 ALL files and the two terms pages, check them, and write the MANIFEST.

    uv run python scripts/01_collect.py

A file that is already in the run directory with the size the server reports is kept and only checksummed.
The run directory is named after the newest Last-Modified date of the data files.
"""

import email.utils
import hashlib
import json
import shutil
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import ibt

ROOT = ibt.ROOT


def request(url: str, method: str = "GET"):
    return urllib.request.urlopen(
        urllib.request.Request(url, method=method, headers={"User-Agent": ibt.UA}), timeout=300
    )


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    heads = {}
    for name, rel in ibt.FILES.items():
        with request(f"{ibt.BASE}/{rel}", "HEAD") as r:
            heads[name] = {
                "size": int(r.headers["Content-Length"]),
                "last_modified": r.headers["Last-Modified"],
            }
    newest = max(email.utils.parsedate_to_datetime(h["last_modified"]) for h in heads.values())
    run = ROOT / "data" / "raw" / newest.astimezone(UTC).strftime("%Y%m%d")
    run.mkdir(parents=True, exist_ok=True)
    manifest = {"acquired_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"), "files": {}}
    for name, rel in ibt.FILES.items():
        dest = run / name
        if not (dest.is_file() and dest.stat().st_size == heads[name]["size"]):
            with request(f"{ibt.BASE}/{rel}") as r, dest.open("wb") as f:
                shutil.copyfileobj(r, f, 1 << 20)
        if dest.stat().st_size != heads[name]["size"]:
            raise SystemExit(
                f"{name}: {dest.stat().st_size} bytes, the server said {heads[name]['size']}"
            )
        manifest["files"][name] = {
            "url": f"{ibt.BASE}/{rel}",
            **heads[name],
            "sha256": sha256(dest),
        }
        print(name, heads[name]["size"])
    ev = ROOT / "data" / "evidence"
    ev.mkdir(parents=True, exist_ok=True)
    for name, url in ibt.PAGES.items():
        with request(url) as r:
            body = r.read()
        (ev / name).write_bytes(body)
        manifest["files"][f"../../evidence/{name}"] = {
            "url": url, "size": len(body), "sha256": hashlib.sha256(body).hexdigest(), "role": "terms and citation"}  # fmt: skip
    text = (ev / "ncei_ibtracs_product_page.html").read_text(encoding="utf-8", errors="replace")
    for phrase in ("open for distribution", "full and open access", "Resolution 40"):
        if phrase not in text:
            raise SystemExit(f"the NCEI product page no longer says: {phrase}")
    iso = (ev / "ncei_C01552_iso19115.xml").read_text(encoding="utf-8")
    if "Distribution liability" not in iso or "Version 4.01" not in iso:
        raise SystemExit("the NCEI metadata record is not the IBTrACS v04r01 record")
    (run / "MANIFEST.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n")
    print(f"{run}: {len(manifest['files'])} entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
