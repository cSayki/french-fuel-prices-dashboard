"""Introduction tab: why the topic matters, who it is for, the questions and the caveats."""
from __future__ import annotations

import streamlit as st

from utils.io import licence_text


def render(tables: dict, f) -> None:
    nat = tables["national_weekly"]
    d = nat[nat["fuel"] == "Gazole"].set_index("week")["mean"]
    peak_week, peak = d.idxmax(), d.max()
    avg_2019 = d[d.index.year == 2019].mean()
    peak_2022 = d[d.index.year == 2022].max()
    brent = tables["brent_monthly"].set_index("month")["brent_eur_bbl"]
    feb, apr = brent.get("2026-02-01"), brent.get("2026-04-01")

    st.subheader(f"In {peak_week:%B %Y} diesel reached {peak:.2f} € per litre on average in "
                 "France, higher than the 2022 peak.")
    st.markdown(
        "Fuel prices are something almost everyone in France watches. People who live outside big "
        "cities depend on their car to get to work, truck drivers and farmers depend on diesel, and "
        "a rise in fuel taxes was what started the gilets jaunes protests in 2018. In 2026 the war in "
        "Iran and the disruption of traffic in the Strait of Hormuz pushed oil prices up again, and "
        "the usual explanation on TV is simply that oil got more expensive. I wanted to check how "
        "true that is, using the prices that every French station has to declare to the government "
        "since 2019 (around 36 million price updates) and the monthly price of Brent crude.")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Diesel, highest weekly average", f"{peak:.3f} €/L", f"week of {peak_week:%d %b %Y}",
              delta_color="off")
    c2.metric("Diesel, 2019 average", f"{avg_2019:.3f} €/L",
              f"{(peak / avg_2019 - 1) * 100:+.0f} % at the record", delta_color="inverse")
    c3.metric("Diesel, 2022 peak", f"{peak_2022:.3f} €/L")
    if feb and apr:
        c4.metric("Brent crude, April 2026", f"{apr:.0f} €/bbl",
                  f"{(apr / feb - 1) * 100:+.0f} % since February",
                  delta_color="inverse")

    left, right = st.columns([3, 2])
    with left:
        st.markdown("#### Who this is for")
        st.markdown(
            "The dashboard is meant for ordinary drivers, for local journalists and for anyone "
            "following the debate on fuel taxes and rebates. The goal is not to forecast prices but "
            "to give a correct picture of what a litre of fuel is made of.")
        st.markdown("#### Questions")
        st.markdown(
            "The overview tab looks at when prices moved and by how much. The oil tab splits the "
            "pump price into crude oil, taxes and the rest, and checks whether prices go up faster "
            "than they come down. The regions tab compares departments and looks at motorway "
            "stations. Finally the scenarios tab lets you test what a more expensive barrel or a "
            "tax cut would change on a yearly fuel budget.")
        st.markdown("#### How the story goes")
        st.markdown(
            "It starts with the 2026 record, then puts it next to the two previous shocks (the "
            "COVID collapse in 2020 and the war in Ukraine in 2022). The main finding is that crude "
            "oil is only about a quarter of the price, while the part that goes to refining and "
            "distribution has more than doubled for diesel. The last tab discusses what this means "
            "for drivers and for public policy.")
    with right:
        st.markdown("#### Data and caveats")
        st.info(
            "Prices are declared by the stations themselves, which is a legal obligation since "
            "2007, so some come late or contain typos. These are cleaned and the rules are "
            "explained in the data quality tab. I only kept metropolitan France, because overseas "
            "departments have regulated prices. Weekly figures are averages over stations, not "
            "over litres sold, since the volume sold by each station is not published. Brent is a "
            "monthly average, and the tax breakdown relies on the official tax rates and on the "
            "2022 rebate calendar. Events shown on the charts are there for context and are not "
            "presented as proven causes.")
        st.markdown("#### Sources and licences")
        st.markdown(licence_text())
