"""Download the raw open-data files into data/raw/ (cached: existing files are skipped).

Usage:  python scripts/download_data.py [--force]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from utils.constants import DATA_RAW, SOURCES, YEARS  # noqa: E402


def fetch(url: str, dest: Path, force: bool = False) -> None:
    if dest.exists() and dest.stat().st_size > 0 and not force:
        print(f"[cache] {dest.name}")
        return
    print(f"[get]   {url}")
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        tmp = dest.with_suffix(dest.suffix + ".part")
        with open(tmp, "wb") as fh:
            for chunk in r.iter_content(chunk_size=1 << 20):
                fh.write(chunk)
        tmp.rename(dest)
    print(f"        -> {dest.name} ({dest.stat().st_size / 1e6:.1f} MB)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="re-download even if cached")
    args = ap.parse_args()
    DATA_RAW.mkdir(parents=True, exist_ok=True)

    for year in YEARS:
        fetch(SOURCES["fuel"]["url_template"].format(year=year),
              DATA_RAW / f"PrixCarburants_annuel_{year}.zip", args.force)
    fetch(SOURCES["brent"]["url"], DATA_RAW / "brent_ine_0014443.json", args.force)
    fetch(SOURCES["geo"]["url"], DATA_RAW / "departements.geojson", args.force)


if __name__ == "__main__":
    main()
