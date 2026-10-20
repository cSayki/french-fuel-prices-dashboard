"""Loading of the tables built by scripts/build_dataset.py."""
from __future__ import annotations

import json
import subprocess
import sys

import pandas as pd
import streamlit as st

from utils.constants import DATA_PROCESSED, ROOT, SOURCES

TABLES = [
    "national_weekly", "dept_road_weekly", "coverage_weekly", "stations_snapshot",
    "monthly_with_brent", "brent_monthly", "stockouts_weekly", "stations",
]


def fetch_and_cache() -> None:
    """Download the raw files and rebuild the processed tables (used when they are missing)."""
    for script in ("download_data.py", "build_dataset.py"):
        subprocess.run([sys.executable, str(ROOT / "scripts" / script)], check=True)


@st.cache_data(show_spinner="Loading data...")
def load_data() -> dict[str, pd.DataFrame]:
    missing = [t for t in TABLES if not (DATA_PROCESSED / f"{t}.parquet").exists()]
    if missing:
        fetch_and_cache()
    return {t: pd.read_parquet(DATA_PROCESSED / f"{t}.parquet") for t in TABLES}


@st.cache_data(show_spinner=False)
def load_quality() -> dict:
    return json.loads((DATA_PROCESSED / "quality.json").read_text())


@st.cache_data(show_spinner=False)
def load_geojson() -> dict:
    return json.loads((DATA_PROCESSED / "departements.geojson").read_text())


def licence_text() -> str:
    lines = []
    for s in SOURCES.values():
        link = s.get("page") or s.get("url")
        lines.append(f"{s['title']}, {s['publisher']}, on [{s['portal']}]({link}). "
                     f"Licence: {s['licence']}.")
    return "\n\n".join(lines)
