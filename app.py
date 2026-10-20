"""French fuel prices 2019-2026: oil, taxes and margins.

Run with: streamlit run app.py
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))  # run from any working directory
from sections import conclusions, data_quality, deep_dives, intro, overview  # noqa: E402
from utils.constants import FUEL_LABELS, FUELS, REGIONS  # noqa: E402
from utils.io import load_data  # noqa: E402

st.set_page_config(page_title="French fuel prices 2019-2026",
                   layout="wide", initial_sidebar_state="expanded")


@dataclass(frozen=True)
class Filters:
    fuels: tuple
    main_fuel: str
    start: pd.Timestamp
    end: pd.Timestamp
    regions: tuple
    road: str
    measure: str


def sidebar(tables: dict) -> Filters:
    weeks = tables["national_weekly"]["week"]
    wmin, wmax = weeks.min().date(), weeks.max().date()
    with st.sidebar:
        st.header("Filters")
        fuels = st.multiselect(
            "Fuel(s)", FUELS, default=["Gazole", "E10", "SP98"],
            format_func=lambda f: FUEL_LABELS[f],
            help="Diesel, SP95-E10 and SP98 are the fuels sold by the most stations. Each fuel keeps "
                 "the same colour whatever you select.")
        if not fuels:
            st.warning("No fuel selected, showing diesel.")
            fuels = ["Gazole"]
        main_fuel = st.selectbox(
            "Main fuel (figures, map, price breakdown)", fuels, format_func=lambda f: FUEL_LABELS[f])
        start, end = st.slider("Date range (weeks)", min_value=wmin, max_value=wmax,
                               value=(wmin, wmax), format="MMM YYYY")
        regions = st.multiselect("Region(s)", list(REGIONS), default=[],
                                 placeholder="All metropolitan France",
                                 help="Leave empty for all of metropolitan France.")
        road = st.radio("Station type", ["All", "Road", "Motorway"], horizontal=True,
                        help="Motorway means stations on the toll motorway network (pop = A in the "
                             "source files).")
        measure = st.selectbox("Measure for trend charts",
                               ["Price (€/L)", "Index (first week = 100)", "Year-on-year change (%)"])
        st.divider()
        st.caption("Fuel prices from prix-carburants.gouv.fr on data.gouv.fr (Licence Ouverte "
                   "2.0). Brent from INE Portugal on data.europa.eu (CC BY 4.0).")
    return Filters(tuple(fuels), main_fuel, pd.Timestamp(start), pd.Timestamp(end),
                   tuple(regions), road, measure)


def main() -> None:
    tables = load_data()
    f = sidebar(tables)

    st.title("What really drives fuel prices in France, 2019 to 2026")
    st.caption("Sources: Prix des carburants en France, prix-carburants.gouv.fr on data.gouv.fr, "
               "Licence Ouverte v2.0. Brent oil price in euros per barrel, INE Portugal on "
               "data.europa.eu, CC BY 4.0. About 36 million price updates from 15 400 stations.")

    tabs = st.tabs(["Introduction", "Overview", "Oil and the pump price", "Regions",
                    "Scenarios", "Data quality", "Conclusion"])
    with tabs[0]:
        intro.render(tables, f)
    with tabs[1]:
        overview.render(tables, f)
    with tabs[2]:
        deep_dives.render_drivers(tables, f)
    with tabs[3]:
        deep_dives.render_geography(tables, f)
    with tabs[4]:
        deep_dives.render_what_if(tables, f)
    with tabs[5]:
        data_quality.render(tables, f)
    with tabs[6]:
        conclusions.render(tables, f)


if __name__ == "__main__":
    main()
