"""Data quality tab: cleaning steps, missing values, duplicates, checks and limits."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.constants import FUEL_LABELS, METRO_DEPTS, SEEDS
from utils.io import load_quality
from utils.viz import FUEL_COLORS, base_layout, show


def render(tables: dict, f) -> None:
    q = load_quality()
    py = pd.DataFrame(q["per_year"]).set_index("year")
    removed = py["rows_raw"].sum() - py["rows_clean"].sum()
    st.subheader(f"{py['rows_raw'].sum() / 1e6:.1f} million price updates, of which "
                 f"{removed / py['rows_raw'].sum() * 100:.2f} % had to be removed.")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Raw price updates", f"{py['rows_raw'].sum():,}".replace(",", " "))
    c2.metric("Exact duplicates removed", f"{py['rows_exact_duplicates'].sum():,}".replace(",", " "))
    c3.metric("Implausible prices removed",
              f"{(py['rows_out_of_bounds'] + py['rows_far_from_weekly_median']).sum():,}".replace(",", " "))
    c4.metric("Different stations", f"{q['stations']['total_unique']:,}".replace(",", " "))

    st.markdown("#### Cleaning steps per year")
    funnel = py[["rows_raw", "rows_unparseable", "rows_outside_year", "rows_exact_duplicates",
                 "rows_out_of_bounds", "rows_far_from_weekly_median", "rows_clean",
                 "rows_in_thousandths", "rows_same_day_resubmission", "stockouts_started"]]
    st.dataframe(funnel.rename(columns=lambda c: c.replace("rows_", "").replace("_", " ")),
                 width="stretch")
    st.caption(
        f"The thresholds are stored in seeds.json. Prices below {SEEDS['price_min_eur_l']} or above "
        f"{SEEDS['price_max_eur_l']} €/L are dropped, and so are prices more than "
        f"{SEEDS['max_rel_deviation_from_weekly_median'] * 100:.0f} % away from the national median "
        "of the same fuel that week, which catches typos like 0.71 instead of 1.71. Until 2021 "
        "prices were published in thousandths of a euro (1328 meaning 1.328 €), so they are "
        "converted. When a station sends the same price twice on the same day, both rows are kept "
        "because it does not change the weekly value.")

    st.markdown("#### How many stations report each week")
    cov = tables["coverage_weekly"]
    cov = cov[(cov["fuel"] == f.main_fuel) & cov["week"].between(f.start, f.end)]
    fig = go.Figure()
    for fuel, g in cov.groupby("fuel", sort=False):
        fig.add_trace(go.Scatter(x=g["week"], y=g["observed"], mode="lines",
                                 name="Changed their price that week",
                                 line={"color": FUEL_COLORS[fuel], "width": 1.2, "dash": "dot"}))
        fig.add_trace(go.Scatter(x=g["week"], y=g["after_ffill"], mode="lines",
                                 name=f"Including prices carried over up to "
                                      f"{SEEDS['ffill_max_weeks']} weeks (used in the averages)",
                                 line={"color": FUEL_COLORS[fuel], "width": 2}))
    base_layout(fig, f"Stations with a {FUEL_LABELS[f.main_fuel].lower()} price each week",
                "number of stations", height=380)
    show(fig, alt=("Line chart of the number of stations with a price each week. The dotted line "
                   "counts stations that changed their price that week and the solid line also "
                   f"counts stations whose last price is carried over for up to "
                   f"{SEEDS['ffill_max_weeks']} weeks."),
         key="dq_coverage")
    st.caption("Stations only send an update when their price changes, so a station with a "
               "stable price sends nothing. That is why I carry the last known price forward for "
               f"up to {SEEDS['ffill_max_weeks']} weeks. Longer gaps are left empty rather than "
               "filled with a guess.")

    st.markdown("#### Checks on the processed tables")
    nat, grp, snap = tables["national_weekly"], tables["dept_road_weekly"], tables["stations_snapshot"]
    mb = tables["monthly_with_brent"]
    checks = [
        ("No duplicate key in the department table (fuel, department, road type, week)",
         not grp.duplicated(["fuel", "dept", "road", "week"]).any()),
        ("All weekly averages are within the cleaning limits",
         bool(nat["mean"].between(SEEDS["price_min_eur_l"], SEEDS["price_max_eur_l"]).all())),
        ("10th percentile below median below 90th percentile every week",
         bool(((nat["p10"] <= nat["median"]) & (nat["median"] <= nat["p90"])).all())),
        ("All 96 metropolitan departments are present",
         set(grp["dept"].astype(str).unique()) >= METRO_DEPTS),
        ("No missing week in the diesel series",
         bool((nat[nat["fuel"] == "Gazole"]["week"].diff().dropna() == pd.Timedelta(weeks=1)).all())),
        ("Brent available for every month except the current one",
         int(mb[mb["fuel"] == "Gazole"]["brent_eur_bbl"].isna().sum()) <= 1),
        ("Share of stations with valid coordinates", f"{snap['coords_valid'].mean() * 100:.1f} %"),
    ]
    st.dataframe(pd.DataFrame([(c, "pass" if v is True else ("fail" if v is False else v))
                               for c, v in checks], columns=["Check", "Result"]),
                 width="stretch", hide_index=True)

    st.markdown("#### Missing values in the processed tables (%)")
    miss = pd.DataFrame({name: tables[name].isna().mean() * 100 for name in
                         ["national_weekly", "dept_road_weekly", "stations_snapshot",
                          "monthly_with_brent"]}).round(2)  # empty cell = column not in that table
    st.dataframe(miss, width="stretch")
    st.caption("The only real gap is brent_eur_bbl for the current month, because Brent is "
               "published about a month late.")

    s = q["stations"]
    st.markdown("#### Station information")
    st.markdown(
        f"Over 2019 to 2026 the files contain {s['total_unique']:,} different stations, "
        f"{s['metropolitan']:,} of them in metropolitan France. The {s['overseas_or_unknown_dept']} "
        f"others are left out. {s['invalid_coordinates_metro']} metropolitan stations have "
        "coordinates that fall outside France, usually because latitude and longitude are swapped "
        "or empty. They are hidden on the station map but still used in the averages. By type, "
        f"the split is {s['road_type_counts'].get('Road', 0):,} road stations and "
        f"{s['road_type_counts'].get('Motorway', 0):,} motorway stations.")

    st.markdown("#### Limits and possible biases")
    st.warning(
        "The averages give the same weight to every station, so a quiet village station counts as "
        "much as a busy supermarket one, and the real average price paid per litre is probably a "
        "bit lower. Prices are declared by the stations and some declare late, which the carry-over "
        "rule can hide. Brent is a monthly average in euros, so weekly timing and the effect of the "
        "dollar exchange rate are smoothed out. The tax breakdown uses the official rates, frozen "
        "since 2018, and ignores regional variations, biofuel incentives and discounts offered by "
        "companies (one major retailer ran its own rebate in 2022), so all of these end up in the "
        "refining and retail part. The events on the charts are context: the dashboard shows "
        "things moving together, it does not prove what caused them. Finally, the data is about "
        "businesses and contains no personal information.")
