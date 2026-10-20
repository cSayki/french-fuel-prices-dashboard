"""Build the small parquet tables used by the app from the raw annual XML files.

Each year is handled by its own process. The XML (about 400 MB a year) is read line by
line with regular expressions. Prices published in thousandths of a euro (until 2021) are
converted, then exact duplicates, prices outside the allowed range and obvious typos are
removed. For each station, fuel and week only the last price is kept, and a price is
carried forward for at most ffill_max_weeks weeks when the station sends nothing. The
result is aggregated into national weekly figures, sums and counts per department and
road type, a snapshot of the latest station prices, a monthly series joined with Brent,
the weekly stock-outs and a quality report.

Usage: python scripts/build_dataset.py [--workers 4]
Output: data/processed/*.parquet and data/processed/quality.json
"""
from __future__ import annotations

import argparse
import html
import io
import json
import re
import shutil
import sys
import time
import warnings
import zipfile
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from utils.constants import (  # noqa: E402
    DATA_PROCESSED, DATA_RAW, DEPT_TO_REGION, FUELS, LAT_RANGE, LON_RANGE,
    METRO_DEPTS, SEEDS, YEARS,
)

RE_PDV = re.compile(r'<pdv id="(\d+)" latitude="([^"]*)" longitude="([^"]*)" cp="([^"]*)" pop="([^"]*)"')
RE_PRIX = re.compile(r'<prix nom="([^"]+)" id="\d+" maj="([^"]+)" valeur="([^"]+)"')
RE_RUPT = re.compile(r'<rupture id="\d+" nom="([^"]+)" debut="([^"]*)" fin="([^"]*)"')
RE_VILLE = re.compile(r"<ville>(.*)</ville>")


def cp_to_dept(cp: str) -> str | None:
    cp = (cp or "").strip().zfill(5)
    if not cp.isdigit() or cp == "00000" or cp.startswith("99"):
        return None
    if cp.startswith("97"):
        return cp[:3]
    if cp.startswith("20"):
        return "2A" if int(cp) < 20200 else "2B"
    return cp[:2]


def to_coord(v: str) -> float:
    try:
        x = float(v)
    except ValueError:
        return np.nan
    # PTV_GEODECIMAL format = degrees * 100 000; a few rows are already in degrees
    return x / 100_000 if abs(x) > 180 else x


DATA_INTERIM = DATA_RAW.parent / "interim"


def extract_year(year: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Regex-parse one annual XML into raw tables (cached as parquet in data/interim)."""
    cache = {k: DATA_INTERIM / f"{k}_{year}.parquet" for k in ("prices", "stations", "ruptures")}
    if all(p.exists() for p in cache.values()):
        return tuple(pd.read_parquet(cache[k]) for k in ("prices", "stations", "ruptures"))
    path = DATA_RAW / f"PrixCarburants_annuel_{year}.zip"
    stations, prices, ruptures = [], [], []
    sid = None
    with zipfile.ZipFile(path) as zf:
        name = zf.namelist()[0]
        with zf.open(name) as raw:
            for line in io.TextIOWrapper(raw, encoding="latin-1"):
                if "<prix " in line:
                    m = RE_PRIX.search(line)
                    if m:
                        prices.append((sid, m.group(1), m.group(2), m.group(3)))
                elif "<pdv " in line:
                    m = RE_PDV.search(line)
                    sid = int(m.group(1))
                    stations.append([sid, m.group(2), m.group(3), m.group(4), m.group(5), None])
                elif "<ville>" in line:
                    m = RE_VILLE.search(line)
                    if m and stations:
                        stations[-1][5] = html.unescape(m.group(1)).strip()
                elif "<rupture " in line:
                    m = RE_RUPT.search(line)
                    if m and m.group(2).startswith(str(year)):
                        ruptures.append((sid, m.group(1), m.group(2), m.group(3)))

    st = pd.DataFrame(stations, columns=["station_id", "lat", "lon", "cp", "pop", "city"])
    df = pd.DataFrame(prices, columns=["station_id", "fuel", "ts", "price"])
    df["fuel"] = df["fuel"].astype("category")
    rup = pd.DataFrame(ruptures, columns=["station_id", "fuel", "start", "end"])
    DATA_INTERIM.mkdir(parents=True, exist_ok=True)
    df.to_parquet(cache["prices"], index=False)
    st.to_parquet(cache["stations"], index=False)
    rup.to_parquet(cache["ruptures"], index=False)
    return df, st, rup


def parse_year(year: int) -> dict:
    t0 = time.time()
    df, st, rup = extract_year(year)
    st["lat"] = st["lat"].map(to_coord)
    st["lon"] = st["lon"].map(to_coord)
    st["year"] = year

    stats = {"year": year, "rows_raw": len(df), "stations_in_file": len(st)}
    df["price"] = pd.to_numeric(df["price"], errors="coerce").astype("float64")
    df["ts"] = pd.to_datetime(df["ts"], errors="coerce", format="%Y-%m-%dT%H:%M:%S")
    bad = df["price"].isna() | df["ts"].isna() | ~df["fuel"].astype(str).isin(FUELS)
    stats["rows_unparseable"] = int(bad.sum())
    df = df[~bad]
    milli = df["price"] > 100
    stats["rows_in_thousandths"] = int(milli.sum())
    df.loc[milli, "price"] = df.loc[milli, "price"] / 1000
    off_year = df["ts"].dt.year != year
    stats["rows_outside_year"] = int(off_year.sum())
    df = df[~off_year]

    dup = df.duplicated(["station_id", "fuel", "ts"])
    stats["rows_exact_duplicates"] = int(dup.sum())
    df = df[~dup]
    # same price sent again on the same day, only counted, not removed
    stats["rows_same_day_resubmission"] = int(
        df.assign(d=df["ts"].dt.floor("D")).duplicated(["station_id", "fuel", "d", "price"]).sum())

    oob = ~df["price"].between(SEEDS["price_min_eur_l"], SEEDS["price_max_eur_l"])
    stats["rows_out_of_bounds"] = int(oob.sum())
    df = df[~oob]

    df["week"] = df["ts"].dt.to_period("W-SUN").dt.start_time
    med = df.groupby(["fuel", "week"])["price"].transform("median")
    dev = (df["price"] / med - 1).abs() > SEEDS["max_rel_deviation_from_weekly_median"]
    stats["rows_far_from_weekly_median"] = int(dev.sum())
    df = df[~dev]
    stats["rows_clean"] = len(df)

    df = df.sort_values("ts")
    weekly = (df.groupby(["station_id", "fuel", "week"], sort=False)["price"].last()
                .reset_index())
    weekly["price"] = weekly["price"].astype("float32")
    last_seen = df.groupby(["station_id", "fuel"])["ts"].max().rename("last_update").reset_index()

    rup["start"] = pd.to_datetime(rup["start"], errors="coerce")
    rup["end"] = pd.to_datetime(rup["end"].replace("", None), errors="coerce")
    stats["stockouts_started"] = len(rup)
    stats["seconds"] = round(time.time() - t0, 1)
    print(f"  {year}: {stats['rows_raw']:,} raw -> {stats['rows_clean']:,} clean "
          f"({stats['seconds']}s)", flush=True)
    return {"stations": st, "weekly": weekly, "ruptures": rup, "stats": stats,
            "last_seen": last_seen}


def build_station_table(parts: list[pd.DataFrame]) -> pd.DataFrame:
    st = pd.concat(parts).sort_values("year")
    first = st.groupby("station_id")["year"].min().rename("first_year")
    st = st.groupby("station_id").last()  # most recent metadata wins
    st = st.rename(columns={"year": "last_year"}).join(first)
    st["dept"] = st["cp"].map(cp_to_dept)
    st["region"] = st["dept"].map(DEPT_TO_REGION)
    st["is_metro"] = st["dept"].isin(METRO_DEPTS)
    st["coords_valid"] = st["lat"].between(*LAT_RANGE) & st["lon"].between(*LON_RANGE)
    st["road"] = st["pop"].map({"R": "Road", "A": "Motorway"}).fillna("Unknown")
    return st


def aggregate(weekly: pd.DataFrame, st: pd.DataFrame) -> dict[str, pd.DataFrame]:
    metro_ids = st.index[st["is_metro"]]
    weekly = weekly[weekly["station_id"].isin(metro_ids)]
    all_weeks = pd.date_range(weekly["week"].min(), weekly["week"].max(), freq="W-MON")
    # the first week starts on 31 Dec 2018 and has no carry-forward history: report from week 2
    first_full = all_weeks[1]

    nat_rows, grp_rows, coverage = [], [], []
    for fuel in FUELS:
        sub = weekly[weekly["fuel"] == fuel]
        if sub.empty:
            continue
        mat = (sub.pivot(index="station_id", columns="week", values="price")
                  .reindex(columns=all_weeks))
        observed = mat.notna().sum(axis=0)
        mat = mat.ffill(axis=1, limit=SEEDS["ffill_max_weeks"])
        arr = mat.to_numpy(dtype="float64")
        n = np.sum(~np.isnan(arr), axis=0)
        with warnings.catch_warnings():  # all-NaN weeks are expected for rare fuels
            warnings.simplefilter("ignore", RuntimeWarning)
            q = np.nanquantile(arr, [0.1, 0.5, 0.9], axis=0)
            mean = np.nanmean(arr, axis=0)
        nat_rows.append(pd.DataFrame({
            "fuel": fuel, "week": all_weeks, "mean": mean, "p10": q[0], "median": q[1],
            "p90": q[2], "n_stations": n,
        }))
        coverage.append(pd.DataFrame({"fuel": fuel, "week": all_weeks,
                                      "observed": observed.to_numpy(), "after_ffill": n}))
        keys = st.loc[mat.index, ["dept", "road"]]
        g = mat.groupby([keys["dept"].to_numpy(), keys["road"].to_numpy()])
        s = g.sum(min_count=1).stack().rename("sum_price")
        c = g.count().stack().rename("n")
        gr = pd.concat([s, c], axis=1).reset_index()
        gr.columns = ["dept", "road", "week", "sum_price", "n"]
        gr = gr[gr["n"] > 0]
        gr["fuel"] = fuel
        grp_rows.append(gr)

    nat = pd.concat(nat_rows, ignore_index=True)
    nat = nat[(nat["n_stations"] > 0) & (nat["week"] >= first_full)]
    grp = pd.concat(grp_rows, ignore_index=True)
    grp = grp[grp["week"] >= first_full]
    grp["region"] = grp["dept"].map(DEPT_TO_REGION)
    grp["n"] = grp["n"].astype("int32")
    grp["sum_price"] = grp["sum_price"].astype("float64")
    for col in ["dept", "road", "fuel", "region"]:
        grp[col] = grp[col].astype("category")
    return {"national_weekly": nat, "dept_road_weekly": grp,
            "coverage_weekly": pd.concat(coverage, ignore_index=True).query("week >= @first_full")}


def load_brent() -> pd.DataFrame:
    raw = json.loads((DATA_RAW / "brent_ine_0014443.json").read_text())[0]["Dados"]
    rows = [(pd.to_datetime(k, format="%B %Y"), float(v[0]["valor"]))
            for k, v in raw.items() if v and v[0].get("valor") not in (None, "")]
    return pd.DataFrame(rows, columns=["month", "brent_eur_bbl"]).sort_values("month")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    print("Parsing annual archives...")
    with Pool(min(args.workers, len(YEARS))) as pool:
        res = pool.map(parse_year, YEARS)

    st = build_station_table([r["stations"] for r in res])
    weekly = pd.concat([r["weekly"] for r in res], ignore_index=True)
    # a week straddling New Year appears in two files: keep the later observation
    weekly = weekly.groupby(["station_id", "fuel", "week"], as_index=False)["price"].last()

    print("Aggregating...")
    tables = aggregate(weekly, st)

    # latest snapshot: last weekly price per station x fuel within the last N days
    last_week = weekly["week"].max()
    recent = weekly[weekly["week"] >= last_week - pd.Timedelta(days=SEEDS["snapshot_days"])]
    snap = (recent.sort_values("week").groupby(["station_id", "fuel"]).last().reset_index()
                  .merge(st[["lat", "lon", "cp", "city", "dept", "region", "road",
                             "is_metro", "coords_valid"]], left_on="station_id",
                         right_index=True))
    snap = snap[snap["is_metro"]].drop(columns="is_metro")

    # monthly national mean joined with Brent
    nat = tables["national_weekly"]
    monthly = (nat.assign(month=nat["week"].dt.to_period("M").dt.start_time)
                  .groupby(["fuel", "month"], as_index=False)
                  .agg(price_mean=("mean", "mean"), price_median=("median", "mean"),
                       n_weeks=("week", "count")))
    brent = load_brent()
    brent.to_parquet(DATA_PROCESSED / "brent_monthly.parquet", index=False)
    monthly = monthly.merge(brent, on="month", how="left")
    monthly = monthly[monthly["month"] >= f"{YEARS[0]}-01-01"]

    rup = pd.concat([r["ruptures"] for r in res], ignore_index=True)
    rup = rup.merge(st[["dept", "region", "is_metro"]], left_on="station_id", right_index=True)
    rup = rup[rup["is_metro"] & rup["start"].notna()]
    rup["week"] = rup["start"].dt.to_period("W-SUN").dt.start_time
    rup_weekly = rup.groupby(["week", "fuel"], as_index=False).size().rename(
        columns={"size": "stockouts_started"})

    # quality log
    stats = [r["stats"] for r in res]
    quality = {
        "per_year": stats,
        "stations": {
            "total_unique": int(len(st)),
            "metropolitan": int(st["is_metro"].sum()),
            "overseas_or_unknown_dept": int((~st["is_metro"]).sum()),
            "invalid_postcode": int(st["dept"].isna().sum()),
            "invalid_coordinates_metro": int((st["is_metro"] & ~st["coords_valid"]).sum()),
            "missing_city": int(st["city"].isna().sum()),
            "road_type_counts": st.loc[st["is_metro"], "road"].value_counts().to_dict(),
        },
        "weekly_rows": int(len(weekly)),
        "date_min": str(weekly["week"].min().date()),
        "date_max": str(weekly["week"].max().date()),
        "brent_months": int(len(brent)),
        "brent_last_month": str(brent["month"].max().date()),
        "build_seconds": round(time.time() - t0, 1),
    }

    out = DATA_PROCESSED
    tables["national_weekly"].to_parquet(out / "national_weekly.parquet", index=False)
    tables["dept_road_weekly"].to_parquet(out / "dept_road_weekly.parquet", index=False)
    tables["coverage_weekly"].to_parquet(out / "coverage_weekly.parquet", index=False)
    snap.to_parquet(out / "stations_snapshot.parquet", index=False)
    monthly.to_parquet(out / "monthly_with_brent.parquet", index=False)
    rup_weekly.to_parquet(out / "stockouts_weekly.parquet", index=False)
    st.reset_index().drop(columns=["pop"]).to_parquet(out / "stations.parquet", index=False)
    shutil.copy(DATA_RAW / "departements.geojson", out / "departements.geojson")
    (out / "quality.json").write_text(json.dumps(quality, indent=2, ensure_ascii=False))
    print(f"Done in {time.time() - t0:.0f}s ->", ", ".join(p.name for p in sorted(out.iterdir())))


if __name__ == "__main__":
    main()
