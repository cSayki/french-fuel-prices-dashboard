"""Overview tab: KPIs that follow the filters and the long-term trend."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.constants import FUEL_LABELS
from utils.prep import add_measure, compute_kpis, filtered_weekly
from utils.viz import PALETTE, add_events, bar_chart, base_layout, line_chart, show


def scope_label(f) -> str:
    where = ", ".join(f.regions) if f.regions else "metropolitan France"
    road = "" if f.road == "All" else f", {f.road.lower()} stations only"
    return f"{where}{road}, {f.start:%b %Y} to {f.end:%b %Y}"


def render(tables: dict, f) -> None:
    wk = filtered_weekly(tables["dept_road_weekly"], f.fuels, f.regions, f.road, f.start, f.end)
    k = compute_kpis(wk, f.main_fuel)
    if k is None:
        st.warning("No data for this combination of filters.")
        return
    change = k.price_now - k.price_start
    st.subheader(
        f"{FUEL_LABELS[f.main_fuel]} ends the period at {k.price_now:.3f} €/L, "
        f"{'up' if change >= 0 else 'down'} {abs(change) * 100:.0f} cents per litre since "
        f"{f.start:%B %Y}.")
    st.caption(f"Scope: {scope_label(f)}")

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric(f"Latest week ({k.last_week:%d %b %Y})", f"{k.price_now:.3f} €/L",
              f"{change:+.3f} € vs first week", delta_color="inverse",
              help="Average over stations of the last price each station reported that week.")
    c2.metric("Highest in period", f"{k.peak:.3f} €/L", f"week of {k.peak_week:%d %b %Y}",
              delta_color="off")
    c3.metric("Lowest in period", f"{k.low:.3f} €/L", f"week of {k.low_week:%d %b %Y}",
              delta_color="off")
    c4.metric("Cost of a 50 L tank", f"{k.tank_cost:.0f} €",
              f"{(k.price_now - k.low) * 50:+.0f} € vs the lowest week", delta_color="inverse")
    c5.metric("Stations reporting", f"{k.stations:,}".replace(",", " "),
              help="Stations with a price for this fuel this week, or a price carried over from "
                   "the previous three weeks.")

    data = add_measure(wk, f.measure)
    nat = tables["national_weekly"]
    band = None
    if f.measure == "Price (€/L)" and len(f.fuels) == 1 and not f.regions and f.road == "All":
        band = nat[(nat["fuel"] == f.main_fuel) & nat["week"].between(f.start, f.end)]
    fmt = {"Price (€/L)": ".3f", "Index (first week = 100)": ".1f", "Year-on-year change (%)": "+.1f"}
    fig = line_chart(data, "value", f.measure, f"Weekly average pump price, {f.measure}",
                     f.start, f.end, band=band, hover_fmt=fmt[f.measure])
    show(fig,
         alt=(f"Line chart of the weekly {f.measure.lower()} for "
              f"{', '.join(FUEL_LABELS[x] for x in f.fuels)}, {scope_label(f)}. Dotted vertical "
              "lines mark the COVID lockdown, the invasion of Ukraine, the refinery strikes and the "
              "2026 war in Iran, and a shaded area shows the 2022 State rebate. All fuels follow the "
              "same pattern: a drop in spring 2020, a rise during 2021, a peak in 2022, a slow "
              "decline until 2025 and a new jump from March 2026."
              + (" The blue band shows the range where 80 % of stations priced (10th to 90th "
                 "percentile)." if band is not None else "")),
         data=data.pivot_table(index="week", columns="fuel", values="value", observed=True)
                  .reset_index(),
         key="overview_trend")
    nf = nat[nat["fuel"] == f.main_fuel]
    spread = (nf["p90"] - nf["p10"]).median() * 100
    st.info("If you keep a single fuel and no region filter, the chart also shows the range "
            "between cheap and expensive stations, which is usually around "
            f"{spread:.0f} c€/L for {FUEL_LABELS[f.main_fuel].lower()}. The measure selector in "
            "the sidebar can switch to an index, which is easier for comparing fuels, or to the "
            "change over one year, which makes the shocks stand out.")

    st.markdown("#### Year by year")
    y = (wk[wk["fuel"] == f.main_fuel].assign(year=lambda x: x["week"].dt.year)
           .groupby("year")["price"].mean().reset_index())
    y["label"] = y["year"].astype(str)
    y = y.iloc[::-1]
    col1, col2 = st.columns([2, 3])
    with col1:
        fig = bar_chart(y, "price", "label", f"Yearly average, {FUEL_LABELS[f.main_fuel]}",
                        "€ per litre", color=PALETTE[0], height=360)
        fig.update_xaxes(range=[0, y["price"].max() * 1.15])
        fig.update_yaxes(type="category")
        show(fig, alt=f"Horizontal bars with the yearly average price of "
                      f"{FUEL_LABELS[f.main_fuel]}. The highest year is "
                      f"{y.loc[y['price'].idxmax(), 'label']} at {y['price'].max():.3f} €/L and "
                      f"the lowest is {y.loc[y['price'].idxmin(), 'label']} at "
                      f"{y['price'].min():.3f} €/L.",
             key="overview_years")
    with col2:
        stock = tables["stockouts_weekly"]
        s = (stock[stock["week"].between(f.start, f.end) & stock["fuel"].isin(f.fuels)]
             .groupby("week")["stockouts_started"].sum().reset_index())
        if not s.empty:
            fig = go.Figure(go.Bar(x=s["week"], y=s["stockouts_started"],
                                   marker={"color": PALETTE[7]},
                                   hovertemplate="%{x|%d %b %Y}: %{y:,} stock-outs<extra></extra>"))
            base_layout(fig, "Stock-outs declared by stations each week",
                        "stock-out declarations", height=360, legend=False)
            add_events(fig, f.start, f.end)
            top = s.loc[s["stockouts_started"].idxmax()]
            show(fig, alt=f"Weekly bars of the stock-outs declared by stations for the selected "
                          f"fuels. The biggest week is {pd.Timestamp(top['week']):%d %B %Y} with "
                          f"{int(top['stockouts_started']):,} declarations.",
                 key="overview_stockouts")
    st.caption("A shock is not only a price problem. In October 2022 the refinery strikes left "
               "thousands of stations without fuel, at a time when prices were held down by the "
               "State rebate.")
