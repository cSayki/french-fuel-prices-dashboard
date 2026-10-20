"""Conclusion tab: findings computed from the data, what they mean and what could come next."""
from __future__ import annotations

import streamlit as st

from utils.prep import asymmetry_significant, decompose, pass_through, road_premium


def render(tables: dict, f) -> None:
    dec = decompose(tables["monthly_with_brent"], "Gazole").set_index("month")
    comps = ["Crude oil (Brent)", "Refining, logistics & retail", "TICPE excise", "VAT 20%"]
    share = dec[comps].div(dec[comps].sum(axis=1), axis=0).mean()
    margin = dec["Refining, logistics & retail"]
    pt = pass_through(dec.reset_index())
    rp = road_premium(tables["dept_road_weekly"], "Gazole", (), dec.index.min(),
                      tables["national_weekly"]["week"].max())
    nat = tables["national_weekly"]
    g = nat[nat["fuel"] == "Gazole"].set_index("week")["mean"]
    spread = (nat[nat["fuel"] == "Gazole"]["p90"] - nat[nat["fuel"] == "Gazole"]["p10"]).median()
    motorway = rp["premium"].iloc[-12:].mean()

    if asymmetry_significant(pt):
        asym = ("Diesel prices do seem to go up faster than they come down, and the difference is "
                "significant, but it rests on monthly data only.")
    else:
        asym = ("The idea that prices go up faster than they come down is not clearly supported "
                "with monthly data.")

    st.subheader("Oil explains the swings, taxes explain most of the level, and margins explain "
                 "the trend.")
    st.markdown("#### What the data shows")
    st.markdown(
        f"There were three shocks in seven years. Diesel fell to {g['2020'].min():.2f} €/L during "
        f"the 2020 lockdowns, climbed to {g['2022'].max():.2f} € in 2022 and reached a record of "
        f"{g.max():.2f} €/L in {g.idxmax():%B %Y}, after the war in Iran disrupted the Strait of "
        "Hormuz.")
    st.markdown(
        f"On average crude oil is only about {share['Crude oil (Brent)'] * 100:.0f} % of the "
        f"price of diesel, and taxes are about "
        f"{(share['TICPE excise'] + share['VAT 20%']) * 100:.0f} %. Because the excise is a fixed "
        "amount per litre, it softens the percentage changes: if crude doubles, the pump price is "
        "far from doubling.")
    st.markdown(
        "The least visible change is also the most lasting one. The part between crude and the "
        f"pump went from about {margin['2019':'2021'].mean() * 100:.0f} cents per litre in 2019 to "
        f"2021 to about {margin.iloc[-12:].mean() * 100:.0f} cents over the last twelve months.")
    st.markdown(
        "Changes in crude reach the pump quickly, mostly within the same month (pass-through of "
        f"{pt.up:.2f} for increases and {pt.down:.2f} for decreases). {asym}")
    st.markdown(
        f"Where you fill up matters too. In a normal week there are about {spread * 100:.0f} cents "
        "per litre between the cheapest and the most expensive 10 % of stations, and motorway "
        f"stations charge around {motorway * 100:.0f} cents more than the others, roughly "
        f"{motorway * 50:.0f} € on a full tank.")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### What it means")
        st.markdown(
            "For a driver, the easiest saving is to avoid motorway stations and compare the "
            "stations nearby, instead of waiting for oil to get cheaper. For policy makers, the "
            "2022 flat rebate worked fast and everybody saw it, but it was expensive and helped "
            "everyone the same way. Since crude is a minority of the price, taxes are a strong "
            "lever, and the refining and retail part deserves more attention than it gets, even if "
            "this dataset cannot break it down. For journalists, the price of oil explains why "
            "prices move, not why they are this high.")
    with c2:
        st.markdown("#### What could be done next")
        st.markdown(
            "The obvious next step would be to add the market prices of refined diesel and "
            "gasoline, to separate refinery margins from station margins. Weighting stations by the "
            "volumes they sell would give the real average price paid. Daily prices around each "
            "shock would show how many days it takes for crude to reach the pump. It would also be "
            "interesting to cross the prices with income and car use by department (INSEE data) to "
            "see who is hit hardest.")
    st.markdown("#### Ethics and transparency")
    st.info("The data is about stations, not people. All cleaning rules and assumptions are "
            "described in the data quality tab and in utils/constants.py, and the events on the "
            "charts are context rather than proven causes. The code is under the MIT licence and "
            "the data keeps its original licences (Licence Ouverte 2.0 and CC BY 4.0).")
    st.caption(f"Computed on {len(g):,} weeks and {len(dec)} months of data. The pass-through "
               f"model uses {pt.n} months. The station spread is the median weekly gap between "
               "the 90th and 10th percentiles.")
